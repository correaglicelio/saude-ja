"""
Saúde Já - coleta de doses aplicadas (Programa Nacional de Imunizações, SI-PNI).

Fonte: dadosabertos.saude.gov.br/dataset/doses-aplicadas-pelo-programa-de-nacional-de-imunizacoes-pni-<ano>
O Ministério publica um ZIP por mês com cada dose aplicada no Brasil (cerca de 20 milhões de
linhas e 1,5 a 4 GB compactado por mês). O arquivo NÃO é salvo no computador: este script lê
enquanto baixa, soma as doses e guarda só os totais por município (poucos MB).

Gera em public/data/vacinacao/:
  <uf>.json   por município:
              "a": doses aplicadas nas unidades do município, por mês e vacina
              "r": doses em moradores de 0 e 1 ano (e 9 a 14 anos para HPV, meningo ACWY e dengue),
                   por mês, vacina, dose e idade -> base da cobertura estimada
              "p": população de 0 ano, 1 ano e 9 a 14 anos (estimativa do Ministério, svsa)
  meta.json   meses coletados, nomes das vacinas, data da coleta

Uso:
  python scripts/coletar_vacinacao.py                 # mês mais recente publicado
  python scripts/coletar_vacinacao.py --meses 7 8 9   # julho a setembro (do ano atual)
  python scripts/coletar_vacinacao.py --ano 2025 --meses 12
Meses já coletados são mantidos; coletar de novo um mês substitui só aquele mês.
"""
from __future__ import annotations

import argparse
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
import zlib
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coletar_cnes as cc  # noqa: E402  (usa cc._CTX, que pode mudar se o certificado falhar)
from coletar_cnes import UFS  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "public" / "data" / "vacinacao"          # versão somada, leve, usada pelo app
MENSAL = RAIZ / "dados" / "vacinacao-mensal"              # mês a mês (base para as próximas coletas)
# Siglas usadas nos indicadores de cobertura (o resto fica só no total de doses aplicadas).
SIGLAS_IND = {"BCG", "ROTA", "Penta", "Hexa acelular", "VIP", "VPC10", "VPC20", "MenC", "MenACWY", "VFA",
              "SCR", "SCRV", "DTP", "HAinf", "VZ", "HPV4", "HPV9", "DNG"}
URL = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/PNI/csv/vacinacao_{mes}_{ano}_csv.zip"
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
POP_API = "https://apidadosabertos.saude.gov.br/vigilancia-e-meio-ambiente/svsa-populacao-residente"
UF_DE = {str(u): u for u in UFS}

# Vacinas acompanhadas também na faixa de 9 a 14 anos (guardadas com idade 9 = "9 a 14").
ADOLESC = {b"HPV4", b"HPV9", b"MenACWY", b"DNG"}


def abrir(url: str, inicio: int = 0):
    for tentativa in range(5):
        try:
            h = {"User-Agent": "SaudeJa/1.0"}
            if inicio:
                h["Range"] = f"bytes={inicio}-"
            return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=120, context=cc._CTX)
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as ex:
            if isinstance(getattr(ex, "reason", None), ssl.SSLCertVerificationError):
                cc._sem_verificacao()
                continue
            print(f"   conexão falhou ({ex}); tentando de novo...")
            time.sleep(5 * (tentativa + 1))
    raise RuntimeError(f"Não consegui abrir {url}")


def tamanho(url: str) -> int | None:
    """Tamanho do arquivo sem baixá-lo (pede só o primeiro byte)."""
    for tentativa in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SaudeJa/1.0", "Range": "bytes=0-0"})
            with urllib.request.urlopen(req, timeout=60, context=cc._CTX) as r:
                cr = r.headers.get("Content-Range") or ""
                return int(cr.split("/")[-1]) if "/" in cr else int(r.headers.get("Content-Length") or 0) or None
        except urllib.error.HTTPError as ex:
            if ex.code in (403, 404):
                return None
            raise
        except urllib.error.URLError as ex:
            if isinstance(getattr(ex, "reason", None), ssl.SSLCertVerificationError):
                cc._sem_verificacao()
                continue
            time.sleep(3)
    return None


def linhas_do_zip(url: str, total: int):
    """Baixa o ZIP em pedaços e devolve as linhas do CSV (bytes), sem gravar nada em disco.
    Se a conexão cair, continua do ponto em que parou (Range)."""
    pos = 0
    dec = zlib.decompressobj(-15)
    cab = b""
    dados_inicio = None
    resto = b""
    t0 = time.time()
    ultimo = 0.0
    while True:
        try:
            resp = abrir(url, pos)
            while True:
                bloco = resp.read(1 << 20)
                if not bloco:
                    break
                pos += len(bloco)
                if dados_inicio is None:
                    cab += bloco
                    if len(cab) < 30:
                        continue
                    if cab[:4] != b"PK\x03\x04":
                        raise RuntimeError("O arquivo baixado não é um ZIP")
                    nl = int.from_bytes(cab[26:28], "little")
                    xl = int.from_bytes(cab[28:30], "little")
                    if int.from_bytes(cab[8:10], "little") != 8:
                        raise RuntimeError("Compactação do ZIP não suportada")
                    dados_inicio = 30 + nl + xl
                    if len(cab) < dados_inicio:
                        dados_inicio = None
                        continue
                    bloco = cab[dados_inicio:]
                    cab = b""
                txt = resto + dec.decompress(bloco)
                partes = txt.split(b"\n")
                resto = partes.pop()
                yield from partes
                agora = time.time()
                if agora - ultimo > 5:
                    ultimo = agora
                    pct = pos / total * 100 if total else 0
                    vel = pos / max(agora - t0, 1) / 1e6
                    falta = (total - pos) / (vel * 1e6) / 60 if total and vel else 0
                    print(f"\r   {pct:5.1f}%  {pos / 1e9:.2f} de {total / 1e9:.2f} GB  "
                          f"{vel:.1f} MB/s  faltam ~{falta:.0f} min   ", end="", flush=True)
                if dec.eof:
                    break
            resp.close()
            if dec.eof or (total and pos >= total):
                break
            raise ConnectionError("download interrompido")
        except (ConnectionError, TimeoutError, urllib.error.URLError, OSError) as ex:
            if dec.eof:
                break
            print(f"\n   conexão caiu em {pos / 1e9:.2f} GB ({ex}); continuando de onde parou...")
            time.sleep(5)
    resto += dec.flush()
    if resto:
        yield from resto.split(b"\n")
    print()


def processar_mes(ano: int, mes: int, total: int):
    url = URL.format(mes=MESES[mes - 1], ano=ano)
    aplic = defaultdict(int)   # (mun_estab, sigla) -> n
    res = defaultdict(int)     # (mun_pac, sigla, dose, idade) -> n
    nomes: dict[bytes, bytes] = {}
    idx = None
    n = ruins = apagadas = 0
    for linha in linhas_do_zip(url, total):
        if linha.endswith(b"\r"):
            linha = linha[:-1]
        if not linha:
            continue
        f = linha.split(b";")
        if idx is None:
            h = [x.strip().decode("latin-1") for x in f]
            try:
                idx = {k: h.index(k) for k in ("co_municipio_estabelecimento", "co_municipio_paciente", "sg_imunobiologico",
                                              "ds_tipo_dose", "nu_idade_paciente", "ds_nome", "dt_deletado_rnds")}
            except ValueError as ex:
                raise RuntimeError(f"Colunas do arquivo mudaram: {ex}")
            ncol = len(h)
            continue
        if len(f) != ncol:
            ruins += 1
            continue
        if f[idx["dt_deletado_rnds"]].strip():
            apagadas += 1
            continue
        n += 1
        sg = f[idx["sg_imunobiologico"]]
        if sg not in nomes:
            nomes[sg] = f[idx["ds_nome"]]
        aplic[(f[idx["co_municipio_estabelecimento"]], sg)] += 1
        ida = f[idx["nu_idade_paciente"]]
        if ida in (b"0", b"1"):
            res[(f[idx["co_municipio_paciente"]], sg, f[idx["ds_tipo_dose"]], ida)] += 1
        elif sg in ADOLESC and ida in (b"9", b"10", b"11", b"12", b"13", b"14"):
            res[(f[idx["co_municipio_paciente"]], sg, f[idx["ds_tipo_dose"]], b"9")] += 1
    mil = lambda x: f"{x:,}".replace(",", ".")
    print(f"   {mil(n)} doses lidas" + (f"; {mil(apagadas)} registros apagados ignorados" if apagadas else "")
          + (f"; {mil(ruins)} linhas com defeito ignoradas" if ruins else ""))
    return aplic, res, nomes, n


def coletar_populacao(ano: int = 2025) -> dict[int, list[int]]:
    """População por idade simples de cada município (svsa). Guarda 0 ano, 1 ano e 9-14 anos.
    A API repete e pula linhas quando lida em páginas, por isso a consulta é feita município
    por município (lista de municípios do IBGE)."""
    with abrir("https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado") as r:
        dados = r.read()
    if dados[:2] == b"\x1f\x8b":
        import gzip
        dados = gzip.decompress(dados)
    cods = [int(x["municipio-id"]) for x in json.loads(dados.decode("utf-8"))]

    def um(cod):
        url = f"{POP_API}?cod_mun={cod}&ano={ano}&limit=200&offset=0"
        for tentativa in range(5):
            try:
                with abrir(url) as r:
                    linhas = json.loads(r.read().decode("utf-8")).get("svsa_populacao_residente", [])
                v = [0, 0, 0]
                for x in linhas:
                    i = x.get("idade")
                    k = 0 if i == 0 else 1 if i == 1 else 2 if isinstance(i, int) and 9 <= i <= 14 else None
                    if k is not None:
                        v[k] += int(x.get("pop") or 0)
                return cod // 10, v
            except Exception:  # noqa: BLE001
                time.sleep(2 * (tentativa + 1))
        return cod // 10, None

    pop: dict[int, list[int]] = {}
    with ThreadPoolExecutor(16) as ex:
        for n, (m, v) in enumerate(ex.map(um, cods), 1):
            if v:
                pop[m] = v
            if n % 250 == 0:
                print(f"\r   população: {n} de {len(cods)} municípios", end="", flush=True)
    print(f"\r   população {ano}: {len(pop)} de {len(cods)} municípios          ")
    return pop


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ano", type=int, default=datetime.now().year)
    ap.add_argument("--meses", type=int, nargs="*")
    ap.add_argument("--sem-populacao", action="store_true", help="não atualiza a população (usa a já salva)")
    ap.add_argument("--ano-todo", action="store_true", help="todos os meses publicados do ano que ainda não foram coletados")
    ap.add_argument("--refazer", action="store_true", help="coleta de novo meses que já estão salvos")
    a = ap.parse_args()
    SAIDA.mkdir(parents=True, exist_ok=True)

    meses = a.meses
    if a.ano_todo:
        meses = list(range(1, 13))
    if not meses:
        print("Procurando o mês mais recente publicado...")
        for m in range(12, 0, -1):
            if tamanho(URL.format(mes=MESES[m - 1], ano=a.ano)):
                meses = [m]
                break
        if not meses:
            print("Nenhum mês encontrado para", a.ano)
            return 1

    meta_arq = SAIDA / "meta.json"
    meta = json.loads(meta_arq.read_text("utf-8")) if meta_arq.exists() else {"meses": [], "nomes": {}, "doses": {}}
    por_uf: dict[int, dict] = {}
    MENSAL.mkdir(parents=True, exist_ok=True)
    for uf in UFS:
        arq_m, arq_p = MENSAL / f"{uf}.json", SAIDA / f"{uf}.json"
        if arq_m.exists():
            por_uf[uf] = json.loads(arq_m.read_text("utf-8"))
        elif arq_p.exists() and "periodo" not in (d := json.loads(arq_p.read_text("utf-8"))):
            por_uf[uf] = d            # formato antigo (mês a mês em public): migra para dados/
        else:
            por_uf[uf] = {"a": {}, "r": {}, "p": {}}

    def somado(d):
        a = {}
        for mun, v in d["a"].items():
            t = defaultdict(int)
            for x in v.values():
                for s, q in x.items():
                    t[s] += q
            a[mun] = dict(t)
        r = {}
        for mun, v in d["r"].items():
            t = defaultdict(int)
            for linhas in v.values():
                for s, dose, ida, q in linhas:
                    if s in SIGLAS_IND:
                        t[(s, dose, ida)] += q
            r[mun] = [[s, dose, ida, q] for (s, dose, ida), q in t.items()]
        return {"periodo": meta["meses"], "a": a, "r": r, "p": d["p"]}

    def gravar():
        for uf, d in por_uf.items():
            for pasta, conteudo in ((MENSAL, d), (SAIDA, somado(d))):
                tmp = pasta / f"{uf}.json.tmp"
                tmp.write_text(json.dumps(conteudo, ensure_ascii=False, separators=(",", ":")), "utf-8")
                tmp.replace(pasta / f"{uf}.json")
        meta["gerado_em"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        meta["fonte"] = "SI-PNI, Doses aplicadas pelo Programa Nacional de Imunizações (dadosabertos.saude.gov.br)"
        meta_arq.write_text(json.dumps(meta, ensure_ascii=False, indent=1), "utf-8")

    for m in meses:
        chave = f"{a.ano}-{m:02d}"
        if chave in meta.get("meses", []) and not a.refazer and (a.ano_todo or not a.meses):
            print(f"{MESES[m - 1]}/{a.ano}: já coletado, pulando (use --refazer para coletar de novo)")
            continue
        url = URL.format(mes=MESES[m - 1], ano=a.ano)
        total = tamanho(url)
        if not total:
            print(f"{chave}: arquivo não encontrado, pulando")
            continue
        print(f"\nDoses aplicadas {MESES[m - 1]}/{a.ano} ({total / 1e9:.1f} GB, lido sem salvar no disco)")
        aplic, res, nomes, n = processar_mes(a.ano, m, total)
        for d in por_uf.values():
            for parte in ("a", "r"):
                for mun in d[parte].values():
                    mun.pop(chave, None)
        for (mun, sg), q in aplic.items():
            mun = mun.decode().strip()
            uf = UF_DE.get(mun[:2])
            if uf and len(mun) == 6:
                por_uf[uf]["a"].setdefault(mun, {}).setdefault(chave, {})[sg.decode("latin-1")] = q
        for (mun, sg, dose, ida), q in res.items():
            mun = mun.decode().strip()
            uf = UF_DE.get(mun[:2])
            if uf and len(mun) == 6:
                por_uf[uf]["r"].setdefault(mun, {}).setdefault(chave, []).append([sg.decode("latin-1"), dose.decode("latin-1"), int(ida), q])
        for sg, nome in nomes.items():
            meta["nomes"][sg.decode("latin-1")] = nome.decode("latin-1")
        meta["doses"][chave] = n
        if chave not in meta["meses"]:
            meta["meses"].append(chave)
        meta["meses"].sort()
        gravar()   # salva a cada mês: se parar no meio, os meses prontos ficam guardados
        print(f"   {MESES[m - 1]}/{a.ano} salvo.")

    if not a.sem_populacao or not meta.get("pop_ano"):
        print("\nPopulação por idade (estimativa do Ministério da Saúde)...")
        pop = coletar_populacao(2025)
        for uf, d in por_uf.items():
            d["p"] = {str(mun): v for mun, v in pop.items() if str(mun)[:2] == str(uf)}
        meta["pop_ano"] = 2025

    gravar()
    tam = sum(f.stat().st_size for f in SAIDA.glob("*.json")) / 1e6
    print(f"\nPronto: {len(meta['meses'])} mês(es) em public/data/vacinacao ({tam:.1f} MB).")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrompido. Os meses que terminaram ficaram salvos; rode de novo para continuar.")
        sys.exit(1)
