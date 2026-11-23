"""Notícias da saúde: junta Agência Brasil (seção Saúde), Fiocruz e Anvisa (quando o gov.br responde).
Grava public/data/anvisa/avisos.json {coletado_em, fonte, itens:[{t,d,u,r,f}]} (só título, data, link e fonte).
Só biblioteca padrão. O gov.br recusa conexões de fora do Brasil (inclusive do GitHub), então a Anvisa é 'se der':
as notícias da Anvisa já guardadas são mantidas por até 45 dias."""
from __future__ import annotations
import html, json, re, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
DESTAQUE = re.compile(r"recolh|apreen|proíbe|proibe|suspende|suspens|interdi|falsific|alerta|surto", re.I)
SAIDA = Path(__file__).resolve().parent.parent / "public" / "data" / "anvisa" / "avisos.json"
ANVISA = "https://www.gov.br/anvisa/++api++/pt-br/@search?portal_type=News%20Item&sort_on=effective&sort_order=reverse&b_size=25&metadata_fields=effective"
RSS = [("Agência Brasil", "https://agenciabrasil.ebc.com.br/rss/saude/feed.xml"),
       ("Fiocruz", "https://agencia.fiocruz.br/rss.xml")]
FUSO = timezone(timedelta(hours=-4))  # Mato Grosso

def baixar(url: str, tent: int, espera: int, json_=False):
    ult = None
    for t in range(tent):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json" if json_ else "application/rss+xml, application/xml, */*"})
            with urllib.request.urlopen(req, timeout=45) as r:
                b = r.read()
            return json.loads(b) if json_ else b.decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            ult = e; time.sleep(espera * (t + 1))
    raise RuntimeError(str(ult))

def limpa(s: str) -> str:
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s, flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()

def ler_rss(nome: str, url: str):
    x = baixar(url, 4, 5)
    out = []
    for it in re.findall(r"<item>(.*?)</item>", x, re.S):
        t = re.search(r"<title>(.*?)</title>", it, re.S); l = re.search(r"<link>(.*?)</link>", it, re.S); d = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
        if not (t and l and d): continue
        try: dt = parsedate_to_datetime(d.group(1).strip()).astimezone(FUSO)
        except Exception: continue  # noqa: BLE001
        titulo, link = limpa(t.group(1)), limpa(l.group(1))
        if titulo and link.startswith("http"): out.append({"t": titulo, "d": dt.date().isoformat(), "u": link, "f": nome})
    return out

def ler_anvisa():
    j = baixar(ANVISA, 2, 5, json_=True)
    out = []
    for it in j.get("items", []):
        t = (it.get("title") or "").strip(); u = it.get("@id") or ""; d = (it.get("effective") or "")[:10]
        if t and u.startswith("https://www.gov.br/anvisa/") and d: out.append({"t": t, "d": d, "u": u, "f": "Anvisa"})
    return out

def main():
    antigo = []
    try: antigo = json.loads(SAIDA.read_text(encoding="utf-8")).get("itens", [])
    except Exception: pass  # noqa: BLE001
    novos, resumo = [], []
    for nome, url in RSS:
        try:
            r = ler_rss(nome, url); novos += r; resumo.append(f"{nome}: {len(r)}")
        except Exception as e:  # noqa: BLE001
            resumo.append(f"{nome}: FALHOU ({e})")
    try:
        r = ler_anvisa(); novos += r; resumo.append(f"Anvisa: {len(r)}")
    except Exception as e:  # noqa: BLE001
        resumo.append(f"Anvisa: indisponível ({e}); mantendo as já guardadas")
        corte = (datetime.now(FUSO) - timedelta(days=45)).date().isoformat()
        novos += [dict(i, f="Anvisa") for i in antigo if (i.get("f") or "Anvisa") == "Anvisa" and i["d"] >= corte]
    print("; ".join(resumo))
    vistos, itens = set(), []
    for i in sorted(novos, key=lambda i: i["d"], reverse=True):
        if i["u"] in vistos: continue
        vistos.add(i["u"]); i["r"] = 1 if DESTAQUE.search(i["t"]) else 0; itens.append(i)
    if not any(i["f"] != "Anvisa" for i in novos):
        raise SystemExit("Nenhuma fonte de notícias respondeu; mantendo o arquivo anterior.")
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps({"coletado_em": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "fonte": "Agência Brasil, Fiocruz e Anvisa (notícias)", "itens": itens[:24]}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(itens[:24])} notícias gravadas")

if __name__ == "__main__":
    main()
