"""
Monta public/index.html a partir de src/index.src.html.

- Embute o CSS do Leaflet (src/leaflet.css) no lugar do marcador /*LEAFLET_CSS*/.
- Gera a página completa (com <!doctype>, <head> e <body>) para hospedar
  no GitHub Pages / Cloudflare Pages.
- Com --artefato, gera também build/artefato.html (sem o esqueleto), usado
  para publicar a prévia dentro do Claude.

Uso:  python scripts/montar_site.py [--artefato]
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
fonte = (RAIZ / "src" / "index.src.html").read_text("utf-8")
css = (RAIZ / "src" / "leaflet.css").read_text("utf-8")
corpo = fonte.replace("/*LEAFLET_CSS*/", css)

pagina = ("<!doctype html>\n<html lang=\"pt-BR\">\n<head>\n<meta charset=\"utf-8\">\n"
          "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">\n"
          "<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}"
          "body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n"
          "</head>\n<body>\n" + corpo + "\n</body>\n</html>\n")
(RAIZ / "public" / "index.html").write_text(pagina, "utf-8")
print("public/index.html gerado")

if "--artefato" in sys.argv:
    (RAIZ / "build").mkdir(exist_ok=True)
    (RAIZ / "build" / "artefato.html").write_text(corpo, "utf-8")
    print("build/artefato.html gerado")
