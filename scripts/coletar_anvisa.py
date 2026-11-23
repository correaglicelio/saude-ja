"""Avisos da Anvisa: pega as notícias mais recentes (só título, data e link) e grava public/data/anvisa/avisos.json.
Só biblioteca padrão. Fonte: portal gov.br/anvisa (busca pública em JSON)."""
from __future__ import annotations
import json, re, sys, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://www.gov.br/anvisa/++api++/pt-br/@search"
QS = "?portal_type=News%20Item&sort_on=effective&sort_order=reverse&b_size={n}&metadata_fields=effective"
UA = "Mozilla/5.0 (compatible; SaudeJa/1.0)"
DESTAQUE = re.compile(r"recolh|apreen|proíbe|proibe|suspende|suspens|interdi|falsific|alerta", re.I)
SAIDA = Path(__file__).resolve().parent.parent / "public" / "data" / "anvisa" / "avisos.json"

def buscar(n: int):
    ult = None
    for t in range(6):
        try:
            req = urllib.request.Request(BASE + QS.format(n=n), headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except Exception as e:  # noqa: BLE001
            ult = e; time.sleep(10 * (t + 1))
    raise SystemExit(f"Anvisa fora do ar: {ult}")

def main():
    j = buscar(25)
    itens = []
    for it in j.get("items", []):
        titulo = (it.get("title") or "").strip(); url = it.get("@id") or ""; data = (it.get("effective") or "")[:10]
        if not (titulo and url.startswith("https://www.gov.br/anvisa/") and data): continue
        itens.append({"t": titulo, "d": data, "u": url, "r": 1 if DESTAQUE.search(titulo) else 0})
    if not itens: raise SystemExit("Nenhum aviso retornado; mantendo o arquivo anterior.")
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps({"coletado_em": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "fonte": "Anvisa (gov.br/anvisa), notícias", "itens": itens[:20]}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(itens)} avisos gravados")

if __name__ == "__main__":
    main()
