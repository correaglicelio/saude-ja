"""
Saúde Já - SRAG: síndrome respiratória aguda grave (gripe, covid, VSR) por município.

Fonte: banco oficial de SRAG do Ministério da Saúde (SIVEP-Gripe), publicado toda segunda-feira no OpenDataSUS:
  https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/<ano>/INFLUD<aa>-<dd>-<mm>-<aaaa>.csv
É a mesma base usada pelo InfoGripe (Fiocruz). Um arquivo por ano de início dos sintomas (2026: ~260 MB).
O arquivo é lido direto da internet, sem gravar no disco; ficam só os totais.

Por município de residência e semana epidemiológica de início dos sintomas:
  [casos, óbitos, influenza, covid, VSR, outros vírus/agentes, não especificado ou em investigação,
   crianças < 5 anos, idosos 60+]

Gera public/data/srag/<uf>.json e meta.json. O ano anterior fica em cache (dados/srag/) e só é relido com --refazer.
Uso: python scripts/coletar_srag.py [--uf MT | --uf MT,GO | --uf todas] [--refazer]
"""
from __future__ import annotations

import csv
import io
import json
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coletar_cnes as cc  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "public" / "data" / "srag"
CACHE = RAIZ / "dados" / "srag"
BASE = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SRAG/{ano}/INFLUD{aa}-{d}.csv"

SIGLAS = {"RO": 11, "AC": 12, "AM": 13, "RR": 14, "PA": 15, "AP": 16, "TO": 17, "MA": 21, "PI": 22, "CE": 23, "RN": 24,
          "PB": 25, "PE": 26, "AL": 27, "SE": 28, "BA": 29, "MG": 31, "ES": 32, "RJ": 33, "SP": 35, "PR": 41, "SC": 42,
          "RS": 43, "MS": 50, "MT": 51, "GO": 52, "DF": 53}


def ufs_escolhidas() -> set[str] | None:
    if "--uf" not in sys.argv:
        return None
    i = sys.argv.index("--uf")
    val = sys.argv[i + 1] if i + 1 < len(sys.argv) else "todas"
    if val.lower() in ("todas", "todos", "br", "brasil"):
        return None
    ufs = {s.strip().upper() for s in val.split(",") if s.strip().upper() in SIGLAS}
    if not ufs:
        raise SystemExit(f"UF desconhecida: {val}. Use a sigla, por exemplo --uf MT, ou --uf todas.")
    return ufs


def abrir(url: str, inicio: int = 0, metodo: str = "GET"):
    h = {"User-Agent": "SaudeJa/1.0"}
    if inicio:
        h["Range"] = f"bytes={inicio}-"
    req = urllib.request.Request(url, headers=h, method=metodo)
    try:
        return urllib.request.urlopen(req, timeout=120, context=cc._CTX)
    except urllib.error.URLError as ex:
        if isinstance(getattr(ex, "reason", None), __import__("ssl").SSLCertVerificationError):
            cc._sem_verificacao()
            return urllib.request.urlopen(req, timeout=120, context=cc._CTX)
        raise


def arquivo_mais_recente(ano: int) -> tuple[str, date] | None:
    """O arquivo novo sai às segundas; procura do dia de hoje para trás (até 120 dias)."""
    hoje = date.today()
    for i in range(0, 120):
        d = hoje - timedelta(days=i)
        url = BASE.format(ano=ano, aa=str(ano)[2:], d=d.strftime("%d-%m-%Y"))
        try:
            with abrir(url, metodo="HEAD") as r:
                if r.status == 200:
                    return url, d
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ConnectionError):
            continue
    return None


def linhas(url: str):
    """Lê o CSV em fluxo; se a conexão cair, continua do byte em que parou (HTTP Range)."""
    pos, resto, tent = 0, b"", 0
    while True:
        try:
            with abrir(url, pos) as r:
                tent = 0
                while True:
                    bloco = r.read(1 << 20)
                    if not bloco:
                        if resto:
                            yield resto.decode("latin-1")
                        return
                    pos += len(bloco)
                    dados = resto + bloco
                    corte = dados.rfind(b"\n")
                    if corte < 0:
                        resto = dados
                        continue
                    resto = dados[corte + 1:]
                    for ln in dados[:corte].split(b"\n"):
                        yield ln.decode("latin-1").rstrip("\r")
                    print(f"\r      {pos / 1e6:,.0f} MB lidos   ", end="", flush=True)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            tent += 1
            if tent > 8:
                raise
            pos -= len(resto)       # volta para o início da linha incompleta
            resto = b""
            time.sleep(5 * tent)


def agregar(url: str, ano: int, escolha: set[str] | None) -> dict[str, dict[int, list[int]]]:
    out: dict[str, dict[int, list[int]]] = defaultdict(dict)
    it = linhas(url)
    cab = next(csv.reader([next(it)], delimiter=";"))
    I = {k.strip().strip('"'): i for i, k in enumerate(cab)}
    n = 0
    for ln in it:
        if not ln:
            continue
        f = next(csv.reader([ln], delimiter=";"))
        g = lambda k: (f[I[k]] if I.get(k) is not None and I[k] < len(f) else "").strip()  # noqa: E731
        uf = g("SG_UF")
        if escolha is not None and uf not in escolha:
            continue
        mun = g("CO_MUN_RES")
        if not mun.isdigit():
            continue
        try:
            sem = int(float(g("SEM_PRI")))
        except ValueError:
            continue
        dt = g("DT_SIN_PRI")
        a = int(dt[:4]) if dt[:4].isdigit() else ano
        mes = int(dt[5:7]) if dt[5:7].isdigit() else 6
        if mes == 1 and sem >= 52:
            a -= 1
        elif mes == 12 and sem == 1:
            a += 1
        se = a * 100 + sem
        v = out[mun].setdefault(se, [0] * 9)
        cf, ev = g("CLASSI_FIN"), g("EVOLUCAO")
        vsr = g("PCR_VSR") == "1" or g("AN_VSR") == "1"
        tp, idade = g("TP_IDADE"), g("NU_IDADE_N")
        idade = int(idade) if idade.isdigit() else -1
        v[0] += 1
        if ev == "2":
            v[1] += 1
        if cf == "1":
            v[2] += 1
        elif cf == "5":
            v[3] += 1
        elif vsr:
            v[4] += 1
        elif cf in ("2", "3"):
            v[5] += 1
        else:
            v[6] += 1
        if tp in ("1", "2") or (tp == "3" and 0 <= idade < 5):
            v[7] += 1
        if tp == "3" and idade >= 60:
            v[8] += 1
        n += 1
    print(f"\r      {n:,} casos agregados".replace(",", ".") + " " * 20)
    return out


def main() -> int:
    print("SRAG: gripe, covid e VSR (SIVEP-Gripe, OpenDataSUS)")
    escolha = ufs_escolhidas()
    print(f"   Estados: {'todos' if escolha is None else ', '.join(sorted(escolha))}")
    ano = date.today().year
    CACHE.mkdir(parents=True, exist_ok=True)
    dados: dict[str, dict[int, list[int]]] = defaultdict(dict)
    arquivos = {}
    for a in (ano - 1, ano):
        cache = CACHE / f"{a}.json"
        if a < ano and cache.exists() and "--refazer" not in sys.argv:
            c = json.loads(cache.read_text("utf-8"))
            if c.get("ufs") is None or escolha is None or escolha <= set(c["ufs"]):
                print(f"   {a}: usando o que já foi lido ({c['arquivo']})")
                for m, s in c["m"].items():
                    if escolha is None or m[:2] in {str(SIGLAS[u]) for u in escolha}:
                        dados[m].update({int(k): v for k, v in s.items()})
                arquivos[a] = c["arquivo"]
                continue
        achado = arquivo_mais_recente(a)
        if not achado:
            print(f"   {a}: arquivo não encontrado")
            continue
        url, d = achado
        print(f"   {a}: lendo {url.rsplit('/', 1)[-1]} (publicado em {d:%d/%m/%Y})")
        ag = agregar(url, a, escolha)
        for m, s in ag.items():
            dados[m].update(s)
        arquivos[a] = d.strftime("%d/%m/%Y")
        cache.write_text(json.dumps({"arquivo": arquivos[a], "ufs": None if escolha is None else sorted(escolha),
                                     "m": {m: {str(k): v for k, v in s.items()} for m, s in ag.items()}},
                                    separators=(",", ":")), "utf-8")

    SAIDA.mkdir(parents=True, exist_ok=True)
    por_uf: dict[str, dict] = defaultdict(dict)
    for m, s in dados.items():
        por_uf[m[:2]][m] = {str(k): v for k, v in sorted(s.items()) if (ano - 1) * 100 < k < (ano + 1) * 100}
    for uf, muns in por_uf.items():
        if escolha is not None and int(uf) not in {SIGLAS[u] for u in escolha}:
            continue
        (SAIDA / f"{uf}.json").write_text(json.dumps({"m": muns}, separators=(",", ":")), "utf-8")
    ult = max((k for s in dados.values() for k in s if k // 100 == ano), default=None)
    meta = {"gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"), "arquivos": arquivos,
            "ultima_semana": ult, "anos": [ano - 1, ano],
            "ufs": sorted(int(f.stem) for f in SAIDA.glob("[0-9]*.json")),
            "campos": ["casos", "obitos", "influenza", "covid", "vsr", "outros", "nao_especificado", "criancas_0_4", "idosos_60"],
            "fonte": "SIVEP-Gripe, banco de SRAG do Ministério da Saúde (OpenDataSUS)"}
    (SAIDA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), "utf-8")
    tam = sum(f.stat().st_size for f in SAIDA.glob("*.json")) / 1e6
    print(f"Pronto: public/data/srag ({tam:.1f} MB), até a semana {ult}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
