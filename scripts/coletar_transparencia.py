"""
Saúde Já - Transparência: gastos com saúde (SIOPS) e desempenho da atenção básica (Previne Brasil).

1) SIOPS - Sistema de Informações sobre Orçamentos Públicos em Saúde
   API: https://siops-consulta-publica-api.saude.gov.br/v1/indicador/municipal/{municipio}/{ano}/{periodo}
   Atualização diária. Período "2" = ano fechado (6º bimestre); 12/14/1/18/20 = 1º a 5º bimestre.
   Guardamos por município e ano:
     [% da receita própria aplicada em saúde (mínimo legal 15%, LC 141/2012),
      despesa total com saúde por habitante (R$), valor aplicado (R$), receita própria (R$),
      % pessoal, % medicamentos, % investimentos, despesa total com saúde (R$)]
   Anos fechados já coletados não são baixados de novo (o ano anterior e o ano atual sempre são).

2) Previne Brasil - indicadores de desempenho da APS (Sisab), encerrado em 2024 (Portaria GM/MS 3.493/2024).
   Arquivos: s3 .../sisab/indicador_desempenho/csv/sisab_indicador_desempenho_<AAAAQn>.csv.zip
   Guardamos a visão "geral" de cada indicador por quadrimestre.

Gera public/data/transparencia/<uf>.json e meta.json. Cache em dados/siops/<uf>.json.
Uso: python scripts/coletar_transparencia.py [--uf MT | --uf MT,GO | --uf todas]
"""
from __future__ import annotations

import csv
import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coletar_cnes as cc  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "public" / "data" / "transparencia"
CACHE = RAIZ / "dados" / "siops"
SIOPS = "https://siops-consulta-publica-api.saude.gov.br/v1"
PREVINE = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/sisab/indicador_desempenho/csv/sisab_indicador_desempenho_{q}.csv.zip"
QUADRIMESTRES = ["2024Q1", "2024Q2", "2024Q3"]   # únicos publicados em CSV aberto
ANO_INICIAL = 2020
PERIODOS = {"12": "1º bimestre", "14": "2º bimestre", "1": "3º bimestre (1º semestre)", "18": "4º bimestre",
            "20": "5º bimestre", "2": "ano fechado"}
ORDEM_PER = ["12", "14", "1", "18", "20", "2"]


SIGLAS = {"RO": 11, "AC": 12, "AM": 13, "RR": 14, "PA": 15, "AP": 16, "TO": 17, "MA": 21, "PI": 22, "CE": 23, "RN": 24,
          "PB": 25, "PE": 26, "AL": 27, "SE": 28, "BA": 29, "MG": 31, "ES": 32, "RJ": 33, "SP": 35, "PR": 41, "SC": 42,
          "RS": 43, "MS": 50, "MT": 51, "GO": 52, "DF": 53}


def ufs_escolhidas() -> set[int] | None:
    """--uf MT  |  --uf MT,GO  |  --uf todas (padrão: todas)."""
    if "--uf" not in sys.argv:
        return None
    i = sys.argv.index("--uf")
    val = sys.argv[i + 1] if i + 1 < len(sys.argv) else "todas"
    if val.lower() in ("todas", "todos", "br", "brasil"):
        return None
    ufs = {SIGLAS[s.strip().upper()] for s in val.split(",") if s.strip().upper() in SIGLAS}
    if not ufs:
        raise SystemExit(f"UF desconhecida: {val}. Use a sigla, por exemplo --uf MT ou --uf MT,GO, ou --uf todas.")
    return ufs


def get_json(url: str, tentativas: int = 4):
    """GET com novas tentativas. Devolve None quando o dado não existe (404 = não homologado)."""
    for t in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SaudeJa/1.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60, context=cc._CTX) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as ex:
            if ex.code in (400, 404):
                return None
            time.sleep(2 * (t + 1))
        except urllib.error.URLError as ex:
            if isinstance(getattr(ex, "reason", None), __import__("ssl").SSLCertVerificationError):
                cc._sem_verificacao()
                continue
            time.sleep(2 * (t + 1))
        except (TimeoutError, ConnectionError, json.JSONDecodeError):
            time.sleep(2 * (t + 1))
    raise RuntimeError(f"Falhou {url}")


def indicadores(lista) -> list | None:
    """[%ASPS, R$/hab, aplicado, receita própria, %pessoal, %medicamentos, %investimentos, despesa total saúde]"""
    if not lista:
        return None
    by = {x.get("numero_indicador", "").strip(): x for x in lista}

    def razao(cod, f=1.0):
        x = by.get(cod)
        if not x or not x.get("denominador"):
            return None
        return round(x["numerador"] / x["denominador"] * f, 2)

    asps, desp = by.get("3.2"), by.get("2.1")
    pct = None
    if asps and asps.get("denominador"):
        # truncado em 2 casas, como o SIOPS publica (14,999% não vira 15%)
        pct = int(asps["numerador"] / asps["denominador"] * 10000) / 100
    return [pct, razao("2.1"),
            round(asps["numerador"], 2) if asps else None, round(asps["denominador"], 2) if asps and asps.get("denominador") else None,
            razao("2.2", 100), razao("2.3", 100), razao("2.5", 100), round(desp["numerador"], 2) if desp else None]


def coletar_siops(muns_por_uf: dict[int, list[int]]) -> tuple[dict, dict]:
    anos = get_json(f"{SIOPS}/ente/anos") or []
    disp = {(int(a["ano"]), str(a["periodo"])) for a in anos}
    ano_max = max(a for a, _ in disp)
    per_atual = max((p for a, p in disp if a == ano_max), key=ORDEM_PER.index)
    fechados = sorted(a for a, p in disp if p == "2" and a >= ANO_INICIAL)
    alvo = [(a, "2") for a in fechados]
    if per_atual != "2":
        alvo.append((ano_max, per_atual))
    chave = lambda a, p: str(a) if p == "2" else f"{a}-{p}"  # noqa: E731
    sempre = {chave(a, p) for a, p in alvo if a >= ano_max - 1}   # ano atual e anterior: sempre atualiza
    print(f"   SIOPS: anos fechados {fechados[0]}-{fechados[-1]}, ano atual {ano_max} até {PERIODOS[per_atual]}")

    CACHE.mkdir(parents=True, exist_ok=True)
    resultado = {}
    for uf, muns in muns_por_uf.items():
        arq = CACHE / f"{uf}.json"
        cache = json.loads(arq.read_text("utf-8")) if arq.exists() else {}
        tarefas = [(m, a, p) for m in muns for a, p in alvo
                   if chave(a, p) in sempre or chave(a, p) not in cache.get(str(m), {})]

        def um(t):
            m, a, p = t
            return m, chave(a, p), indicadores(get_json(f"{SIOPS}/indicador/municipal/{m}/{a}/{p}"))

        with ThreadPoolExecutor(16) as ex:
            for m, k, v in ex.map(um, tarefas):
                d = cache.setdefault(str(m), {})
                if v:
                    d[k] = v
                else:
                    d.pop(k, None)
        # descarta períodos parciais antigos (ficam só os anos fechados e o período atual)
        validas = {chave(a, p) for a, p in alvo}
        for m in cache:
            cache[m] = {k: v for k, v in cache[m].items() if k in validas}
        arq.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")), "utf-8")
        resultado[uf] = cache
        print(f"\r   SIOPS: UF {uf} ok ({len(tarefas)} consultas)        ", end="", flush=True)
    print()
    meta = {"anos": fechados, "atual": {"ano": ano_max, "periodo": per_atual, "descricao": PERIODOS[per_atual],
                                         "chave": chave(ano_max, per_atual)}}
    return resultado, meta


def coletar_previne() -> dict:
    por_mun: dict[str, dict] = defaultdict(dict)
    achados = []
    for q in QUADRIMESTRES:
        try:
            dados = cc.baixar(PREVINE.format(q=q), timeout=180)
        except Exception:  # noqa: BLE001
            continue
        with zipfile.ZipFile(io.BytesIO(dados)) as z:
            nome = z.namelist()[0]
            with z.open(nome) as f:
                for lin in csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"), delimiter=";"):
                    if lin.get("visao_equipe") != "geral":
                        continue
                    try:
                        v = float(lin["vl_perc_quad"])
                        num, den = int(float(lin["numerador"])), int(float(lin["denominador_utilizador"]))
                    except (ValueError, KeyError):
                        continue
                    por_mun[lin["ibge"].strip()].setdefault(q, {})[lin["co_tipo_indicador"].strip()] = [v, num, den]
        achados.append(q)
        print(f"\r   Previne Brasil: {q} ok   ", end="", flush=True)
    print()
    return dict(por_mun), achados


def main() -> int:
    print("Transparência: gastos com saúde (SIOPS) e atenção básica (Previne Brasil)")
    mun = json.loads((RAIZ / "public" / "data" / "municipios.json").read_text("utf-8"))
    muns_por_uf: dict[int, list[int]] = defaultdict(list)
    escolha = ufs_escolhidas()
    for m in mun:
        if escolha is None or m[2] in escolha:
            muns_por_uf[m[2]].append(m[0])
    print(f"   Estados: {'todos' if escolha is None else ', '.join(k for k, v in SIGLAS.items() if v in escolha)}")
    siops, meta_siops = coletar_siops(dict(muns_por_uf))
    previne, quads = coletar_previne()

    SAIDA.mkdir(parents=True, exist_ok=True)
    for uf, muns in muns_por_uf.items():
        out = {"s": {str(m): siops.get(uf, {}).get(str(m), {}) for m in muns},
               "p": {str(m): previne.get(str(m), {}) for m in muns if str(m) in previne}}
        (SAIDA / f"{uf}.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), "utf-8")
    meta = {"gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "siops": meta_siops, "previne": {"quadrimestres": quads},
            "ufs": sorted(int(f.stem) for f in SAIDA.glob("[0-9]*.json")),
            "fonte": "SIOPS (siops-consulta-publica-api.saude.gov.br) e Sisab/Previne Brasil (dadosabertos.saude.gov.br)"}
    (SAIDA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), "utf-8")
    tam = sum(f.stat().st_size for f in SAIDA.glob("*.json")) / 1e6
    print(f"Pronto: public/data/transparencia ({tam:.1f} MB).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
