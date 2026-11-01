"""
Saúde Já — qualidade da água para consumo humano (SISAGUA / Ministério da Saúde).

Fontes (dadosabertos.saude.gov.br, conjuntos "SISAGUA"):
  * Controle mensal - Parâmetros básicos: análises feitas pelos responsáveis pelo
    abastecimento (empresa/serviço de água), já resumidas por mês e ponto de coleta.
  * Vigilância - Parâmetros básicos: amostras coletadas pelo setor saúde
    (vigilância municipal/estadual), uma linha por análise.

O que calcula, por município e por mês (só amostras do sistema de distribuição e
pontos de consumo, onde a água chega às pessoas):
  ec = Escherichia coli         [amostras, com presença]
  ct = Coliformes totais        [amostras, com presença]
  cl = Cloro residual livre     [amostras, abaixo de 0,2 mg/L, acima de 5,0 mg/L]
  tu = Turbidez                 [amostras, acima de 5,0 uT]
Limites conforme o padrão de potabilidade (Portaria GM/MS nº 888/2021).

Grava public/data/agua/<codigo_uf>.json e public/data/agua/meta.json.
Uso:  python scripts/coletar_agua.py           (ano atual; inclui o anterior se houver poucos meses)
      python scripts/coletar_agua.py --ano 2025
Só usa a biblioteca padrão do Python 3.10+. Baixa cerca de 250 MB e leva alguns minutos.
"""
from __future__ import annotations

import csv
import io
import json
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from coletar_cnes import UFS, _sem_verificacao  # noqa: E402  (reaproveita o ajuste de certificado)
import coletar_cnes  # noqa: E402

BASE = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SISAGUA/"
URL_CONTROLE = BASE + "controle_mensal_parametros_basicos_{ano}_csv.zip"
URL_VIGILANCIA = BASE + "vigilancia_parametros_basicos_{ano}_csv.zip"
SAIDA = Path(__file__).resolve().parents[1] / "public" / "data" / "agua"

csv.field_size_limit(10_000_000)


# ------------------------------------------------------------------ download
def baixar_para_arquivo(url: str, destino: Path) -> bool:
    """Baixa um arquivo grande em partes, mostrando o progresso. False se não existir."""
    for tentativa in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SaudeJa/1.0"})
            with urllib.request.urlopen(req, timeout=120, context=coletar_cnes._CTX) as resp, open(destino, "wb") as f:
                total = int(resp.headers.get("Content-Length") or 0)
                lido, marca = 0, 0
                while True:
                    bloco = resp.read(1 << 20)
                    if not bloco:
                        break
                    f.write(bloco)
                    lido += len(bloco)
                    if total and lido * 10 // total > marca:
                        marca = lido * 10 // total
                        print(f"    {marca * 10}% de {total / 1e6:.0f} MB", flush=True)
            return True
        except urllib.error.HTTPError as ex:
            if ex.code in (403, 404):
                return False
            erro = ex
        except (urllib.error.URLError, TimeoutError, ConnectionError) as ex:
            erro = ex
            if "CERTIFICATE_VERIFY_FAILED" in str(ex):
                _sem_verificacao()
                continue
        time.sleep(2 ** tentativa)
    raise RuntimeError(f"Falhou {url}: {erro}")


def linhas_csv(caminho_zip: Path):
    """Lê o CSV de dentro do ZIP sem descompactar no disco (texto em latin-1, separador ';')."""
    with zipfile.ZipFile(caminho_zip) as z:
        nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(nome) as bruto:
            texto = io.TextIOWrapper(bruto, encoding="latin-1", newline="")
            yield from csv.reader(texto, delimiter=";", quotechar='"')


# ------------------------------------------------------------------ helpers
PONTOS_REDE = {"SISTEMA DE DISTRIBUIÇÃO", "PONTO DE CONSUMO"}
PROCEDENCIA_EXCLUIDA = {"ESTAÇÃO DE TRATAMENTO DE ÁGUA"}


def _num(txt: str):
    t = (txt or "").strip().replace(" ", "")
    if not t:
        return None
    t = t.lstrip("<>=").replace(".", "").replace(",", ".") if "," in t else t.lstrip("<>=")
    try:
        return float(t)
    except ValueError:
        return None


def _int(txt: str) -> int:
    v = _num(txt)
    return int(v) if v is not None else 0


def _mun(txt: str) -> int:
    """Código IBGE de 6 dígitos. O SISAGUA registra o Distrito Federal por região
    administrativa (530001, 530002...); tudo vira Brasília (530010), como no IBGE."""
    m = int(txt)
    return 530010 if m // 10000 == 53 else m


def novo():
    return {"ec": [0, 0], "ct": [0, 0], "cl": [0, 0, 0], "tu": [0, 0]}


# dados[fonte][mun][ano*100+mes] = indicadores
def processar_controle(caminho: Path, dados):
    linhas = linhas_csv(caminho)
    cab = [c.strip() for c in next(linhas)]
    i = {n: cab.index(n) for n in ("Código IBGE", "Ano de referência", "Mês de referência",
                                   "Ponto de Monitoramento", "Parâmetro", "Campo", "Valor")}
    n = 0
    for c in linhas:
        n += 1
        if n % 1_000_000 == 0:
            print(f"    controle: {n / 1e6:.0f} milhões de linhas lidas", flush=True)
        try:
            if c[i["Ponto de Monitoramento"]].strip().upper() not in PONTOS_REDE:
                continue
            par, campo = c[i["Parâmetro"]], c[i["Campo"]]
            mun = _mun(c[i["Código IBGE"]])
            am = int(c[i["Ano de referência"]]) * 100 + int(c[i["Mês de referência"]])
        except (ValueError, IndexError):
            continue
        val = _int(c[i["Valor"]])
        d = dados["ctl"][mun].setdefault(am, novo())
        if par.startswith("Escherichia"):
            if campo.startswith("Número de amostras analisadas"): d["ec"][0] += val
            elif "presença" in campo: d["ec"][1] += val
        elif par.startswith("Coliformes totais"):
            if campo.startswith("Número de amostras analisadas"): d["ct"][0] += val
            elif "presença" in campo: d["ct"][1] += val
        elif par.startswith("Cloro Residual Livre"):
            if campo.startswith("Número de amostras analisadas"): d["cl"][0] += val
            elif campo.startswith("Número de dados < 0,2"): d["cl"][1] += val
            elif campo.startswith("Número de dados > 5,0"): d["cl"][2] += val
        elif par.startswith("Turbidez"):
            if campo.startswith("Número de amostras analisadas"): d["tu"][0] += val
            elif campo.startswith("Número de dados > 5,0"): d["tu"][1] += val
    print(f"    controle: {n} linhas", flush=True)


def processar_vigilancia(caminho: Path, dados):
    linhas = linhas_csv(caminho)
    cab = [c.strip() for c in next(linhas)]
    i = {n: cab.index(n) for n in ("CO_MUNICIPIO_IBGE", "TP_ABASTECIMENTO", "NU_ANO", "NU_MES",
                                   "TP_PROCEDENCIA_COLETA", "PARAMETRO", "RESULTADO")}
    n = 0
    for c in linhas:
        n += 1
        if n % 1_000_000 == 0:
            print(f"    vigilância: {n / 1e6:.0f} milhões de linhas lidas", flush=True)
        try:
            proc = c[i["TP_PROCEDENCIA_COLETA"]].strip().upper()
            if proc in PROCEDENCIA_EXCLUIDA or proc.startswith("PONTO DE CAPTA"):
                continue
            mun = _mun(c[i["CO_MUNICIPIO_IBGE"]])
            am = int(c[i["NU_ANO"]]) * 100 + int(c[i["NU_MES"]])
            par, res = c[i["PARAMETRO"]].strip(), c[i["RESULTADO"]].strip().upper()
            tipo = c[i["TP_ABASTECIMENTO"]].strip().upper()
        except (ValueError, IndexError):
            continue
        fonte = "vig" if tipo == "SAA" else "alt"     # SAA = rede pública; SAC/SAI = poço, carro-pipa, etc.
        d = dados[fonte][mun].setdefault(am, novo())
        if par.startswith("Escherichia"):
            if res in ("PRESENTE", "AUSENTE"):
                d["ec"][0] += 1; d["ec"][1] += res == "PRESENTE"
        elif par.startswith("Coliformes totais"):
            if res in ("PRESENTE", "AUSENTE"):
                d["ct"][0] += 1; d["ct"][1] += res == "PRESENTE"
        elif par.lower().startswith("cloro residual livre"):
            v = _num(res)
            if v is not None:
                d["cl"][0] += 1; d["cl"][1] += v < 0.2; d["cl"][2] += v > 5.0
        elif par.startswith("Turbidez"):
            v = _num(res)
            if v is not None:
                d["tu"][0] += 1; d["tu"][1] += v > 5.0
    print(f"    vigilância: {n} linhas", flush=True)


def somar(meses: dict, chaves) -> dict:
    t = novo()
    for k in chaves:
        m = meses.get(k)
        if not m:
            continue
        for p in t:
            t[p] = [a + b for a, b in zip(t[p], m[p])]
    return t


def main() -> int:
    SAIDA.mkdir(parents=True, exist_ok=True)
    ano = datetime.now().year
    if "--ano" in sys.argv:
        ano = int(sys.argv[sys.argv.index("--ano") + 1])

    dados = {f: defaultdict(dict) for f in ("ctl", "vig", "alt")}
    anos = [ano]
    tmp = Path(tempfile.mkdtemp(prefix="saudeja_agua_"))
    try:
        for a in list(anos):
            for nome, url, func in (("controle (empresa de água)", URL_CONTROLE, processar_controle),
                                    ("vigilância (setor saúde)", URL_VIGILANCIA, processar_vigilancia)):
                print(f"Baixando SISAGUA {nome} {a}...", flush=True)
                arq = tmp / f"{func.__name__}_{a}.zip"
                if not baixar_para_arquivo(url.format(ano=a), arq):
                    print(f"  arquivo de {a} não encontrado, pulando.")
                    continue
                print("  processando...", flush=True)
                func(arq, dados)
                arq.unlink(missing_ok=True)
            # No começo do ano há poucos meses publicados: completa com o ano anterior.
            meses = {am for m in dados["ctl"].values() for am in m}
            if len(meses) < 4 and a == ano and ano - 1 not in anos:
                anos.append(ano - 1)
                print(f"Poucos meses em {ano}; incluindo também {ano - 1}.")
                for nome, url, func in (("controle", URL_CONTROLE, processar_controle),
                                        ("vigilância", URL_VIGILANCIA, processar_vigilancia)):
                    print(f"Baixando SISAGUA {nome} {ano - 1}...", flush=True)
                    arq = tmp / f"{func.__name__}_{ano - 1}.zip"
                    if baixar_para_arquivo(url.format(ano=ano - 1), arq):
                        print("  processando...", flush=True)
                        func(arq, dados)
                        arq.unlink(missing_ok=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # Meses considerados "recentes": os 3 últimos com volume razoável de dados
    # (o mês corrente costuma estar incompleto porque os envios atrasam).
    volume = defaultdict(int)
    for m in dados["ctl"].values():
        for am, d in m.items():
            volume[am] += d["ec"][0]
    meses_ord = sorted(volume)
    if not meses_ord:
        print("Nenhum dado de água encontrado.")
        return 1
    media = sum(volume.values()) / len(volume)
    validos = [am for am in meses_ord if volume[am] >= 0.4 * media]
    recentes = validos[-3:]
    serie = [am for am in meses_ord if am <= recentes[-1]][-12:]
    print(f"Período recente: {recentes[0] % 100:02d}/{recentes[0] // 100} a {recentes[-1] % 100:02d}/{recentes[-1] // 100}")

    por_uf: dict[int, dict] = {uf: {} for uf in UFS}
    todos = set(dados["ctl"]) | set(dados["vig"]) | set(dados["alt"])
    br = {f: novo() for f in dados}
    for mun in todos:
        uf = mun // 10000
        if uf not in por_uf:
            continue
        reg = {}
        for f in dados:
            meses = dados[f].get(mun, {})
            tot = somar(meses, recentes)
            if any(v[0] for v in tot.values()):
                reg[f] = tot
                br[f] = {p: [a + b for a, b in zip(br[f][p], tot[p])] for p in br[f]}
        # série mensal de E. coli e cloro (empresa e vigilância) para os gráficos
        reg["s"] = [[am,
                     *dados["ctl"].get(mun, {}).get(am, novo())["ec"],
                     *dados["vig"].get(mun, {}).get(am, novo())["ec"],
                     *dados["ctl"].get(mun, {}).get(am, novo())["cl"][:2]] for am in serie]
        por_uf[uf][mun] = reg

    for uf, muns in por_uf.items():
        (SAIDA / f"{uf}.json").write_text(json.dumps(muns, separators=(",", ":")), "utf-8")
        print(f"UF {uf}: {len(muns)} municípios com dados de água")

    meta = {
        "atualizado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fontes": [URL_CONTROLE.format(ano=a) for a in anos] + [URL_VIGILANCIA.format(ano=a) for a in anos],
        "recentes": recentes,
        "serie": serie,
        "brasil": br,
        "campos": {"ec": "E. coli [amostras, presença]", "ct": "Coliformes totais [amostras, presença]",
                   "cl": "Cloro residual livre [amostras, < 0,2 mg/L, > 5,0 mg/L]", "tu": "Turbidez [amostras, > 5,0 uT]",
                   "s": "série mensal [aaaamm, ctl E.coli amostras, ctl presença, vig amostras, vig presença, ctl cloro amostras, ctl cloro < 0,2]"},
    }
    (SAIDA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), "utf-8")
    print("Pronto: dados de água gravados em public/data/agua/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
