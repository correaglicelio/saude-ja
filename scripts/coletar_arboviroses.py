"""
Saúde Já - Dengue, chikungunya e zika por município (InfoDengue, Fiocruz/FGV).

API: https://info.dengue.mat.br/api/alertcity?geocode=<IBGE 7 dígitos>&disease=<doença>&format=json
     &ew_start=1&ew_end=53&ey_start=<ano>&ey_end=<ano>
Atualização semanal (semana epidemiológica). Guardamos as semanas do ano anterior e do atual:
  c = casos notificados por semana, n = nível de alerta por semana (1 verde, 2 amarelo, 3 laranja, 4 vermelho),
  e = casos estimados das últimas 8 semanas (corrige o atraso de notificação), rt e inc da última semana.

Gera public/data/arboviroses/<uf>.json e meta.json.
Uso: python scripts/coletar_arboviroses.py [--uf MT | --uf MT,GO | --uf todas]
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coletar_cnes as cc  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "public" / "data" / "arboviroses"
API = "https://info.dengue.mat.br/api/alertcity"
DOENCAS = {"dengue": "d", "chikungunya": "c", "zika": "z"}
IBGE = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado"


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


def get_json(url: str, tentativas: int = 5):
    for t in range(tentativas):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SaudeJa/1.0", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60, context=cc._CTX) as r:
                dados = r.read()
            if dados[:2] == b"\x1f\x8b":
                import gzip
                dados = gzip.decompress(dados)
            return json.loads(dados.decode("utf-8") or "[]")
        except urllib.error.HTTPError as ex:
            if ex.code in (400, 404):
                return []
            time.sleep(3 * (t + 1))
        except urllib.error.URLError as ex:
            if isinstance(getattr(ex, "reason", None), __import__("ssl").SSLCertVerificationError):
                cc._sem_verificacao()
                continue
            time.sleep(3 * (t + 1))
        except (TimeoutError, ConnectionError, json.JSONDecodeError):
            time.sleep(3 * (t + 1))
    raise RuntimeError(f"Falhou {url}")


def serie(geo7: int, doenca: str, ano_ini: int, ano_fim: int) -> dict[int, dict]:
    url = f"{API}?geocode={geo7}&disease={doenca}&format=json&ew_start=1&ew_end=53&ey_start={ano_ini}&ey_end={ano_fim}"
    return {int(x["SE"]): x for x in (get_json(url) or []) if x.get("SE")}


def main() -> int:
    print("Dengue, chikungunya e zika (InfoDengue)")
    hoje = date.today()
    ano_fim, ano_ini = hoje.year, hoje.year - 1
    ibge = get_json(IBGE)
    geo7 = {int(x["municipio-id"]) // 10: int(x["municipio-id"]) for x in ibge}
    mun = json.loads((RAIZ / "public" / "data" / "municipios.json").read_text("utf-8"))
    por_uf: dict[int, list[int]] = defaultdict(list)
    escolha = ufs_escolhidas()
    print(f"   Estados: {'todos' if escolha is None else ', '.join(k for k, v in SIGLAS.items() if v in escolha)}")
    for m in mun:
        if m[0] in geo7 and (escolha is None or m[2] in escolha):
            por_uf[m[2]].append(m[0])

    SAIDA.mkdir(parents=True, exist_ok=True)
    semanas_vistas: set[int] = set()
    total_uf = len(por_uf)
    for k, (uf, muns) in enumerate(sorted(por_uf.items()), 1):
        tarefas = [(m, d) for m in muns for d in DOENCAS]

        def um(t):
            m, d = t
            return m, d, serie(geo7[m], d, ano_ini, ano_fim)

        brutos: dict[int, dict[str, dict]] = defaultdict(dict)
        with ThreadPoolExecutor(8) as ex:
            for i, (m, d, s) in enumerate(ex.map(um, tarefas), 1):
                if s:
                    brutos[m][d] = s
                    semanas_vistas.update(s)
                if i % 50 == 0:
                    print(f"\r   UF {k}/{total_uf}: {i}/{len(tarefas)} consultas   ", end="", flush=True)
        ses = sorted(se for se in semanas_vistas if ano_ini * 100 < se < (ano_fim + 1) * 100)
        out = {"se": ses, "m": {}}
        for m, ds in brutos.items():
            r = {}
            for d, s in ds.items():
                if not any((s.get(se) or {}).get("casos") for se in ses):
                    continue    # doença sem nenhum caso nos dois anos: não guarda
                c = [None if se not in s else int(s[se].get("casos") or 0) for se in ses]
                n = "".join("0" if se not in s else str(int(s[se].get("nivel") or 0)) for se in ses)
                e = [None if se not in s else round(s[se].get("casos_est") or 0) for se in ses[-8:]]
                ult = s[max(s)]
                r[DOENCAS[d]] = {"c": c, "n": n, "e": e, "rt": round(ult.get("Rt") or 0, 2),
                                 "inc": round(ult.get("p_inc100k") or 0, 1), "pop": int(float(ult.get("pop") or 0))}
            if r:
                out["m"][str(m)] = r
        (SAIDA / f"{uf}.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), "utf-8")
        print(f"\r   UF {k}/{total_uf}: {len(out['m'])} municípios com dados          ", flush=True)

    ses = sorted(semanas_vistas)
    meta = {"gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ultima_semana": ses[-1] if ses else None, "anos": [ano_ini, ano_fim],
            "ufs": sorted(int(f.stem) for f in SAIDA.glob("[0-9]*.json")),
            "fonte": "InfoDengue (Fiocruz e FGV), info.dengue.mat.br, a partir das notificações do Sinan"}
    (SAIDA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), "utf-8")
    tam = sum(f.stat().st_size for f in SAIDA.glob("*.json")) / 1e6
    print(f"Pronto: public/data/arboviroses ({tam:.1f} MB), até a semana {meta['ultima_semana']}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
