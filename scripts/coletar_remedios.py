"""
Saúde Já — módulo Remédios.

1) Programa Farmácia Popular do Brasil (PFPB): pessoas atendidas por município.
   https://dadosabertos.saude.gov.br/dataset/mgdi-programa-farmacia-popular-do-brasil
   Os arquivos trazem um retrato de dezembro de cada ano e o mês mais recente.

2) BNAFAR – Posição de Estoque: o que cada farmácia/unidade do SUS registrava em estoque.
   https://dadosabertos.saude.gov.br/dataset/bnafar-posicao-de-estoque
   Mantém só medicamentos (tipos B = básico, S = estratégico, E = especializado),
   só lotes com saldo e dentro da validade na data da posição.

3) Banco de Preços em Saúde (BPS): compras públicas de medicamentos dos últimos 12 meses.
   https://dadosabertos.saude.gov.br/dataset/bps
4) PCDT: protocolos clínicos acompanhados pela Conitec.

Grava em public/data/remedios/:
   meta.json, fp_<uf>.json (Farmácia Popular), est_<uf>.json (estoque),
   precos.json (preço de referência), compras_<uf>.json (compras por estado), pcdt.json
Uso:  python scripts/coletar_remedios.py
Baixa cerca de 130 MB. Leva de 3 a 8 minutos.
"""
from __future__ import annotations

import csv
import io
import json
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from coletar_cnes import UFS, baixar  # noqa: E402
from coletar_agua import baixar_para_arquivo  # noqa: E402

SAIDA = Path(__file__).resolve().parents[1] / "public" / "data" / "remedios"
csv.field_size_limit(10_000_000)

# ------------------------------------------------------------------ Farmácia Popular
FP_URL = "https://demas-dados-abertos.s3.amazonaws.com/csv/{codigo}.csv.zip"
FP_INDICADORES = {
    "pfpbben": "Total de pessoas atendidas",
    "sntpbh": "Hipertensão",
    "sntpbd": "Diabetes",
    "sntpdhc": "Hipertensão e diabetes juntas",
    "sntpba": "Asma",
    "sntpbos": "Osteoporose",
    "sntpbcon": "Contracepção",
    "pfpbdm": "Absorventes (Dignidade Menstrual)",
    "pfpbbfam": "Beneficiários do Bolsa Família",
}


def ler_zip_csv(dados: bytes, encoding: str, delim: str):
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        texto = z.read(nome).decode(encoding, errors="replace")
    return csv.reader(io.StringIO(texto), delimiter=delim)


def coletar_farmacia_popular():
    valores: dict[str, dict[int, dict[str, float]]] = {}   # codigo -> mun -> {aaaamm: valor}
    brasil: dict[str, dict[str, float]] = {}
    meses_todos: set[str] = set()
    for cod in FP_INDICADORES:
        print(f"  Farmácia Popular: {FP_INDICADORES[cod]}...", flush=True)
        linhas = ler_zip_csv(baixar(FP_URL.format(codigo=cod)), "utf-8-sig", ",")
        cab = next(linhas)
        i_mes, i_mun = cab.index("co_anomes"), cab.index("co_ibge")
        i_val, i_br = cab.index("vl_indicador_calculado_mun"), cab.index("vl_indicador_calculado_br")
        por_mun: dict[int, dict[str, float]] = defaultdict(dict)
        for c in linhas:
            try:
                mes, mun = c[i_mes], int(c[i_mun])
                por_mun[mun][mes] = float(c[i_val] or 0)
                brasil.setdefault(cod, {})[mes] = float(c[i_br] or 0)
                meses_todos.add(mes)
            except (ValueError, IndexError):
                continue
        valores[cod] = por_mun
    meses = sorted(meses_todos)
    por_uf: dict[int, dict] = {uf: {} for uf in UFS}
    muns = set().union(*[set(v) for v in valores.values()])
    for mun in muns:
        uf = mun // 10000
        if uf not in por_uf:
            continue
        reg = {}
        for cod, pm in valores.items():
            serie = [pm.get(mun, {}).get(m) for m in meses]
            if any(v is not None for v in serie):
                reg[cod] = [None if v is None else int(v) for v in serie]
        por_uf[uf][mun] = reg
    return meses, por_uf, {c: [brasil.get(c, {}).get(m) for m in meses] for c in FP_INDICADORES}


# ------------------------------------------------------------------ Estoque (BNAFAR)
BNAFAR_PAGINA = "https://dadosabertos.saude.gov.br/dataset/bnafar-posicao-de-estoque"
BNAFAR_URL = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/bnafar/csv/Posicao_Estoque_csv_{data}.zip"
BNAFAR_PADRAO = "06-06-2026"
TIPOS_MEDICAMENTO = {"B", "S", "E"}
# Nomes que indicam depósito/central, que normalmente não atende o público direto.
CENTRAL = re.compile(r"\b(CENTRAL|ALMOXARIFADO|DEPOSITO|DEPÓSITO|CAF|ABASTECIMENTO|ESTOQUE|LOGISTICA|LOGÍSTICA|DISTRIBUI)", re.I)


def descobrir_posicao_mais_recente() -> str:
    """Procura na página do conjunto a data do arquivo de posição de estoque mais recente."""
    try:
        html = baixar(BNAFAR_PAGINA).decode("utf-8", errors="replace")
        datas = set(re.findall(r"Posicao_Estoque_csv_(\d{2}-\d{2}-\d{4})\.zip", html))
        if datas:
            return max(datas, key=lambda d: datetime.strptime(d, "%d-%m-%Y"))
    except Exception as ex:  # página fora do ar: usa a data conhecida
        print(f"  Aviso: não consegui ler a página do BNAFAR ({ex}); usando {BNAFAR_PADRAO}.")
    return BNAFAR_PADRAO


def _qtd(txt: str) -> float:
    try:
        return float((txt or "0").replace(",", "."))
    except ValueError:
        return 0.0


def _coord(txt: str):
    try:
        v = round(float((txt or "").replace(",", ".")), 5)
        return v if -75 < v < 10 and v != 0 else None
    except ValueError:
        return None


def coletar_estoque(caminho_zip: Path):
    produtos: dict[str, str] = {}                    # catmat -> descrição
    estab: dict[int, dict] = {}                      # cnes -> dados
    saldo: dict[int, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    data_posicao = ""
    with zipfile.ZipFile(caminho_zip) as z:
        nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        with z.open(nome) as bruto:
            linhas = csv.reader(io.TextIOWrapper(bruto, encoding="latin-1", newline=""), delimiter=";", quotechar='"')
            cab = [c.strip() for c in next(linhas)]
            i = {k: cab.index(k) for k in cab}
            n = 0
            for c in linhas:
                n += 1
                if n % 1_000_000 == 0:
                    print(f"    estoque: {n / 1e6:.0f} milhões de linhas lidas", flush=True)
                if len(c) != len(cab):
                    continue
                if c[i["tp_produto"]].strip() not in TIPOS_MEDICAMENTO:
                    continue
                q = _qtd(c[i["qt_estoque"]])
                if q <= 0:
                    continue
                pos = c[i["dt_posicao_estoque"]].strip()
                val = c[i["dt_validade"]].strip()[:10]
                if val and pos and val.replace("-", "/") < pos[:10]:
                    continue                                       # lote vencido na data da posição
                try:
                    cnes = int(c[i["co_cnes"]])
                    mun = int(c[i["co_municipio_ibge"]])
                except ValueError:
                    continue
                data_posicao = max(data_posicao, pos[:10])
                cat = c[i["co_catmat"]].strip()
                if cat not in produtos:
                    produtos[cat] = " ".join(c[i["ds_produto"]].split())
                if cnes not in estab:
                    nome_f = (c[i["no_fantasia"]] or c[i["no_razao_social"]]).strip()
                    estab[cnes] = {
                        "mun": 530010 if mun // 10000 == 53 else mun,
                        "dados": [nome_f, " ".join(f"{c[i['no_logradouro']].strip()}, {c[i['nu_endereco']].strip()}".split()),
                                  c[i["no_bairro"]].strip(), c[i["nu_telefone"]].strip(),
                                  _coord(c[i["nu_latitude"]]), _coord(c[i["nu_longitude"]]),
                                  1 if CENTRAL.search(nome_f) else 0],
                    }
                saldo[cnes][cat] += q
    print(f"    estoque: {n} linhas, {len(estab)} estabelecimentos com medicamentos, {len(produtos)} medicamentos", flush=True)
    return data_posicao, produtos, estab, saldo


# ------------------------------------------------------------------ Banco de Preços em Saúde
BPS_URL = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/BPS/csv/{ano}_csv.zip"
SIGLA_UF = {"RO": 11, "AC": 12, "AM": 13, "RR": 14, "PA": 15, "AP": 16, "TO": 17, "MA": 21, "PI": 22, "CE": 23,
            "RN": 24, "PB": 25, "PE": 26, "AL": 27, "SE": 28, "BA": 29, "MG": 31, "ES": 32, "RJ": 33, "SP": 35,
            "PR": 41, "SC": 42, "RS": 43, "MS": 50, "MT": 51, "GO": 52, "DF": 53}


def catmat_num(cod: str):
    """'BR0268856' ou 'BR0233632U0062' -> 268856 (o mesmo código do Banco de Preços)."""
    m = re.match(r"\s*(?:BR)?0*(\d+)", cod or "")
    return int(m.group(1)) if m else None


def _quartis(v: list[float]):
    v = sorted(v)
    q = lambda p: v[min(len(v) - 1, max(0, round(p * (len(v) - 1))))]
    return q(.25), q(.5), q(.75)


def coletar_precos():
    """Compras públicas dos últimos 12 meses: preço de referência por item e compras por estado."""
    ano = datetime.now().year
    linhas = []
    for a in (ano - 1, ano):
        try:
            dados = baixar(BPS_URL.format(ano=a))
        except Exception as ex:
            print(f"  Banco de Preços {a}: não encontrado ({ex}), pulando.")
            continue
        r = ler_zip_csv(dados, "utf-8-sig", ";")
        cab = [c.strip() for c in next(r)]
        i = {k: cab.index(k) for k in cab}
        n = 0
        for c in r:
            if len(c) != len(cab):
                continue
            try:
                d = datetime.strptime(c[i["dt_compra"]].strip(), "%d/%m/%Y")
                preco = float(c[i["vl_preco_unitario"]] or 0)
                cat = int(c[i["co_catmat"]])
            except ValueError:
                continue
            if preco <= 0:
                continue
            linhas.append((d, cat, c, i))
            n += 1
        print(f"  Banco de Preços {a}: {n} compras", flush=True)
    if not linhas:
        return None, {}, ""
    fim = max(d for d, *_ in linhas)
    inicio = fim.replace(year=fim.year - 1)
    linhas = [x for x in linhas if x[0] > inicio]
    grupos: dict[tuple, dict] = {}
    compras_uf: dict[int, list] = defaultdict(list)
    for d, cat, c, i in linhas:
        un = (c[i["un_fornecimento"]] or c[i["sg_unidade_medida"]] or "").strip().upper()
        g = grupos.setdefault((cat, un), {"nome": " ".join(c[i["ds_item"]].split()), "pdm": c[i["no_pdm"]].strip(),
                                          "precos": [], "uf": defaultdict(list), "ult": d})
        preco = float(c[i["vl_preco_unitario"]])
        g["precos"].append(preco)
        g["ult"] = max(g["ult"], d)
        uf = SIGLA_UF.get(c[i["sg_uf"]].strip())
        if uf:
            g["uf"][uf].append(preco)
            qt = _qtd(c[i["qt_medicamento"]])
            compras_uf[uf].append([cat, un, d.strftime("%Y-%m-%d"), " ".join(c[i["no_instituicao"]].split()),
                                   c[i["no_municipio"]].strip(), c[i["ds_esfera"]].strip(), round(qt),
                                   round(preco, 4), c[i["modalidade"]].strip(), " ".join(c[i["no_fornecedor"]].split())])
    itens = []
    for (cat, un), g in grupos.items():
        p25, med, p75 = _quartis(g["precos"])
        itens.append([cat, g["nome"], g["pdm"], un, len(g["precos"]), round(p25, 4), round(med, 4), round(p75, 4),
                      {uf: [len(v), round(_quartis(v)[1], 4)] for uf, v in g["uf"].items()}])
    itens.sort(key=lambda x: x[1])
    periodo = f"{inicio:%d/%m/%Y} a {fim:%d/%m/%Y}"
    return itens, compras_uf, periodo


# ------------------------------------------------------------------ PCDT (Conitec)
PCDT_URL = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/CONITEC/csv/pcdt.csv.zip"


def coletar_pcdt():
    r = ler_zip_csv(baixar(PCDT_URL), "utf-8-sig", ";")
    next(r)
    return [[c[0].strip(), c[1].strip(), c[2].strip()] for c in r if len(c) >= 3 and c[0].strip()]


def main() -> int:
    SAIDA.mkdir(parents=True, exist_ok=True)

    print("Baixando Banco de Preços em Saúde (compras públicas)...", flush=True)
    itens, compras_uf, periodo = coletar_precos()
    if itens:
        (SAIDA / "precos.json").write_text(json.dumps({"periodo": periodo, "itens": itens}, ensure_ascii=False, separators=(",", ":")), "utf-8")
        for uf in UFS:
            (SAIDA / f"compras_{uf}.json").write_text(json.dumps(sorted(compras_uf.get(uf, []), key=lambda x: x[2], reverse=True), ensure_ascii=False, separators=(",", ":")), "utf-8")
        print(f"  {len(itens)} itens com preço de referência ({periodo})")
    print("Baixando protocolos clínicos (PCDT/Conitec)...", flush=True)
    try:
        pcdt = coletar_pcdt()
        (SAIDA / "pcdt.json").write_text(json.dumps(pcdt, ensure_ascii=False, separators=(",", ":")), "utf-8")
        print(f"  {len(pcdt)} protocolos")
    except Exception as ex:
        print(f"  PCDT indisponível ({ex}), seguindo sem.")

    print("Baixando Farmácia Popular (Ministério da Saúde)...", flush=True)
    meses, fp_uf, fp_br = coletar_farmacia_popular()
    for uf, d in fp_uf.items():
        (SAIDA / f"fp_{uf}.json").write_text(json.dumps(d, separators=(",", ":")), "utf-8")
    print(f"  {sum(len(d) for d in fp_uf.values())} municípios; meses: {', '.join(meses)}")

    data = descobrir_posicao_mais_recente()
    print(f"Baixando estoque do SUS (BNAFAR, posição de {data})...", flush=True)
    tmp = Path(tempfile.mkdtemp(prefix="saudeja_rem_"))
    try:
        arq = tmp / "bnafar.zip"
        if not baixar_para_arquivo(BNAFAR_URL.format(data=data), arq):
            raise RuntimeError("Arquivo de estoque do BNAFAR não encontrado.")
        print("  processando (pode levar alguns minutos)...", flush=True)
        data_pos, produtos, estab, saldo = coletar_estoque(arq)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    for uf in UFS:
        cnes_uf = [c for c, e in estab.items() if e["mun"] // 10000 == uf]
        cats = sorted({cat for c in cnes_uf for cat in saldo[c]}, key=lambda k: produtos[k])
        idx = {cat: n for n, cat in enumerate(cats)}
        saida = {
            "p": [produtos[c] for c in cats],
            "c": [catmat_num(c) for c in cats],          # código CATMAT numérico (liga com o Banco de Preços)
            "e": {c: [estab[c]["mun"], *estab[c]["dados"],
                      sorted([[idx[cat], round(q)] for cat, q in saldo[c].items()], key=lambda x: x[0])]
                  for c in cnes_uf},
        }
        (SAIDA / f"est_{uf}.json").write_text(json.dumps(saida, ensure_ascii=False, separators=(",", ":")), "utf-8")
        print(f"UF {uf}: {len(cnes_uf)} estabelecimentos, {len(cats)} medicamentos em estoque")

    meta = {
        "atualizado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fp": {"meses": meses, "indicadores": FP_INDICADORES, "brasil": fp_br,
               "fonte": "https://dadosabertos.saude.gov.br/dataset/mgdi-programa-farmacia-popular-do-brasil"},
        "precos": {"periodo": periodo, "fonte": "https://dadosabertos.saude.gov.br/dataset/bps",
                   "campos_item": ["catmat", "nome", "pdm", "unidade", "compras", "p25", "mediana", "p75", "por_uf {uf: [compras, mediana]}"],
                   "campos_compra": ["catmat", "unidade", "data", "instituicao", "municipio", "esfera", "quantidade", "preco_unitario", "modalidade", "fornecedor"]},
        "pcdt": {"fonte": "https://dadosabertos.saude.gov.br/dataset/pcdt-protocolos-clinicos-e-diretrizes-terapeuticas"},
        "estoque": {"data_posicao": data_pos, "arquivo": BNAFAR_URL.format(data=data), "fonte": BNAFAR_PAGINA,
                    "campos_estabelecimento": ["mun", "nome", "endereco", "bairro", "telefone", "lat", "lng", "central", "itens [indice_produto, quantidade]"]},
    }
    (SAIDA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), "utf-8")
    print("Pronto: dados de remédios gravados em public/data/remedios/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
