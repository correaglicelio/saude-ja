"""
Saúde Já - locais de doação de sangue (CNES).

Não existe conjunto de dados próprio de doação de sangue. Os locais saem do CNES:
  1. tipo 69 "Centro de Atenção Hemoterapia e/ou Hematológica" (todos os estados);
  2. tipo 39 "Unidade de apoio diagnose e terapia", só os com nome de hemocentro/banco de sangue
     (ex.: Hemocentro de São Paulo / Fundação Pró-Sangue está cadastrado assim);
  3. hemocentros coordenadores cadastrados como hospital (Hemope, Hemorio) buscados pelo código CNES.

O tipo 69 mistura locais onde se DOA com agências transfusionais (dentro de hospitais, só
transfundem) e laboratórios. A separação é feita pelo nome; agências e laboratórios ficam de fora.

Gera public/data/sangue.json:
  {"gerado_em", "fonte", "u": [[cnes, nome, tipo, uf, municipio, lat, lng, endereco, telefone, sus,
                                turno, esfera, coordenador]]}
  tipo: "h" hemocentro, "n" hemonúcleo, "c" unidade/posto de coleta ou banco de sangue,
        "s" serviço de hemoterapia (confirmar se recebe doadores)

Uso: python scripts/coletar_sangue.py
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coletar_cnes as cc  # noqa: E402
from coletar_cnes import UFS  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
SAIDA = RAIZ / "public" / "data" / "sangue.json"
API = "https://apidadosabertos.saude.gov.br/cnes/estabelecimentos"

# Hemocentro coordenador de cada estado (código CNES) e nome de exibição.
COORD = {
    4001338: "Fundação Hemeron (Hemocentro de Rondônia)",
    2306387: "Hemoacre (Centro de Hematologia e Hemoterapia do Acre)",
    2013274: "Fundação Hemoam",
    2566214: "Hemoraima (Centro de Hemoterapia e Hematologia de Roraima)",
    2752697: "Fundação Hemopa",
    2020904: "Hemoap",
    2370298: "Hemocentro Coordenador de Palmas",
    2697653: "Hemomar (Centro de Hematologia e Hemoterapia Dr. Dário Itapary Nicolau)",
    2406071: "Hemopi (Centro de Hematologia e Hemoterapia do Piauí)",
    2479958: "Hemoce (Centro de Hematologia e Hemoterapia do Ceará)",
    2381451: "Hemonorte (Hemocentro Dalton Barbosa Cunha)",
    2399598: "Hemocentro da Paraíba",
    809: "Fundação Hemope",
    2003899: "Hemoal (Hemocentro de Alagoas)",
    3532240: "Hemose (Centro de Hemoterapia de Sergipe)",
    6149: "Fundação Hemoba",
    4034325: "Hemominas, Hemocentro de Belo Horizonte",
    12378: "Hemoes (Hemocentro do Espírito Santo)",
    2295067: "Hemorio (Instituto Estadual de Hematologia Arthur de Siqueira Cavalcanti)",
    2088789: "Hemocentro de São Paulo (Fundação Pró-Sangue)",
    2795957: "Hemepar (Centro de Hematologia e Hemoterapia do Paraná)",
    4059956: "Hemosc (Hemocentro de Santa Catarina)",
    2237768: "Hemocentro do Rio Grande do Sul (Hemorgs)",
    2612089: "Hemosul Coordenador",
    2534258: "MT Hemocentro",
    2339072: "Hemogo (Hemocentro Prof. Nion Albernaz)",
    11339: "Fundação Hemocentro de Brasília",
}
# Cadastrados como hospital ou policlínica (não aparecem nos tipos 69/39).
EXTRAS = {809: "h", 2295067: "h", 2604671: "n"}

# Locais de doação que funcionam dentro de hospitais e não têm cadastro próprio no CNES.
# Entram com os dados do hospital (código CNES) e as informações conferidas na fonte indicada.
MANUAIS = [
    {"cnes_hospital": 2534460, "id": 9000001, "uf": 51, "mun": 510250,
     "nome": "UCT Dr. Márcio Curvo de Lima (banco de sangue do Hospital Regional de Cáceres)", "tipo": "c",
     "obs": "Segunda a sexta, 7h às 11h e 13h às 18h. Funciona no Hospital Regional de Cáceres: confirme a unidade pelo telefone.",
     "fonte": "https://www.caceresnoticias.com.br/cidade/banco-de-sangue-do-hospital-regional-de-caceres-fortalece-atendimento-e-incentiva-doacoes-com-gestao-da-agir/666097",
     "conferido": "2026-10-31"},
    {"id": 9000002, "uf": 51, "mun": 510760, "lat": -16.45374, "lng": -54.64242,
     "nome": "MT Hemocentro, Unidade de Coleta e Transfusão de Rondonópolis", "tipo": "c",
     "end": "RUA RIO BRANCO 2802, JARDIM SANTA MARTA (ao lado da UPA 24 horas)", "tel": "(66) 3426-9848",
     "obs": "Segunda a sexta (horário informado em 2022: 7h às 10h30 e 13h às 16h30). Também (66) 3426-9505. Ligue antes.",
     "fonte": "https://www.salvovidas.com/doacao-de-sangue-no-mt-hemocentro-rondonopolis-mt/", "conferido": "2026-10-31"},
    {"cnes_hospital": 2795655, "id": 9000003, "uf": 51, "mun": 510792, "lat": -12.5406, "lng": -55.7238,
     "nome": "Unidade de coleta do Hospital Regional de Sorriso", "tipo": "c",
     "end": "AV PORTO ALEGRE 3125, CENTRO", "tel": "(66) 3907-7107",
     "obs": "Segunda a sexta, 7h às 11h e 13h às 17h (informado em 2022). Atende com agendamento: ligue antes. Local no mapa aproximado.",
     "fonte": "https://www.salvovidas.com/doacao-de-sangue-no-hospital-regional-de-sorriso-mt/", "conferido": "2026-10-31"},
    {"cnes_hospital": 3269728, "id": 9000004, "uf": 51, "mun": 510480,
     "nome": "MT Hemocentro, UCT de Jaciara (Hospital Municipal de Jaciara)", "tipo": "c",
     "end": "RUA GUAICURUS 1165, CENTRO", "tel": "(66) 3461-3454",
     "obs": "Segunda a sexta, 7h às 12h (informado em 2022). Ligue antes.",
     "fonte": "https://www.salvovidas.com/doacao-de-sangue-na-unidade-de-coleta-e-transfusao-de-jaciara-mt/", "conferido": "2026-10-31"},
]

NAO = re.compile(r"AGENCIA|AGENCI|^AT |\bAT\b|^AG |\bAGT\b|AG\.? TRANSF|UNIDADE TRANSFUSIONAL|TERAPIA CELULAR|LABORAT|"
                 r"TOXICOLOG|CELLPRESERVE|DIAGNOST|ONCO|FALCIFORME|CRIOBANCO|HEMOCENTRO TRANSFUSAO")
SIM = re.compile(r"HEMOCENTRO|HEMONUCLEO|NUCLEO DE HEMOTERAPIA|COLETA|BANCO DE SANGUE|FUNDACAO HEMO|PRO.?SANGUE|"
                 r"\bHEMO(ACRE|AL|AP|AM|BA|CE|ES|GO|SUL|MINAS|PA|PI|NORTE|RAIMA|SE|TO|PE|RIO|SC|MAR|PADUA)\b|"
                 r"HEMERON|HEMEPAR|\bUCT\b|CENTRO DE HEMATOLOGIA E HEMOTERAPIA|CENTRO DE HEMOTERAPIA E HEMATOLOGIA|HEMAT DR DARIO")
BUSCA39 = re.compile(r"SANGUE|HEMOCENTRO|HEMONUCLEO|HEMOTERAP|PRO.?SANGUE|HEMEPAR|HEMERON|"
                     r"\bHEMO(ACRE|AL|AP|AM|BA|CE|ES|GO|SUL|MINAS|PA|PI|NORTE|RAIMA|SE|TO|PE|RIO|SC|MAR)\b")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    return re.sub(r"\b([A-Z]) (?=[A-Z]\b)", r"\1", s).strip()   # "H E M O P A" -> "HEMOPA"


def classificar(nome: str, sus: bool) -> str | None:
    n = norm(nome)
    if NAO.search(n) and "COLETA" not in n:
        return None
    if SIM.search(n):
        if re.search(r"HEMONUCLEO|NUCLEO DE HEMOTERAPIA", n):
            return "n"
        if re.search(r"COLETA|\bUCT\b|BANCO DE SANGUE", n):
            return "c"
        return "h"
    if sus and re.search(r"HEMOTERAPIA|TRANSFUS|HEMOTERAPICO", n):
        return "s"
    return None


def pagina(params: str, offset: int) -> list[dict]:
    url = f"{API}?{params}&status=1&limit=20&offset={offset}"
    dados = cc.baixar(url, timeout=60)
    corpo = json.loads(dados.decode("utf-8"))
    return corpo.get("estabelecimentos", []) if isinstance(corpo, dict) else corpo


def todas(params: str) -> list[dict]:
    linhas, off = [], 0
    while True:
        lote = pagina(params, off)
        linhas.extend(lote)
        if len(lote) < 20:
            return linhas
        off += 20


def linha(e: dict, tipo: str) -> list:
    cnes = int(e["codigo_cnes"])
    end = " ".join(x for x in [(e.get("endereco_estabelecimento") or "").strip(), (e.get("numero_estabelecimento") or "").strip()] if x)
    bairro = (e.get("bairro_estabelecimento") or "").strip()
    return [cnes, COORD.get(cnes) or norm(e.get("nome_fantasia") or e.get("nome_razao_social")), tipo, e["codigo_uf"], e["codigo_municipio"],
            e.get("latitude_estabelecimento_decimo_grau"), e.get("longitude_estabelecimento_decimo_grau"),
            end + (", " + bairro if bairro else ""), (e.get("numero_telefone_estabelecimento") or "").strip(),
            1 if e.get("estabelecimento_faz_atendimento_ambulatorial_sus") == "SIM" else 0,
            e.get("codigo_identificador_turno_atendimento") or "", (e.get("descricao_esfera_administrativa") or "").strip(),
            1 if cnes in COORD else 0]


def main() -> int:
    print("Locais de doação de sangue (CNES)...")
    achados: dict[int, list] = {}

    def add(e, origem):
        sus = e.get("estabelecimento_faz_atendimento_ambulatorial_sus") == "SIM"
        t = classificar(e.get("nome_fantasia") or "", sus)
        if not t or (origem == 39 and t == "s" and not sus):
            return
        if e.get("latitude_estabelecimento_decimo_grau") is None:
            return
        achados.setdefault(int(e["codigo_cnes"]), linha(e, t))

    with ThreadPoolExecutor(6) as ex:
        for lote in ex.map(lambda uf: todas(f"codigo_tipo_unidade=69&codigo_uf={uf}"), UFS):
            for e in lote:
                add(e, 69)
        print(f"   tipo 69: {len(achados)} locais")
        for lote in ex.map(lambda uf: todas(f"codigo_tipo_unidade=39&codigo_uf={uf}"), UFS):
            for e in lote:
                if BUSCA39.search(norm((e.get("nome_fantasia") or "") + " " + (e.get("nome_razao_social") or ""))):
                    add(e, 39)
        print(f"   + tipo 39: {len(achados)} locais")
    for cnes, tipo in EXTRAS.items():
        try:
            e = json.loads(cc.baixar(f"{API}/{cnes}", timeout=60).decode("utf-8"))
            achados[cnes] = linha(e, tipo)
        except Exception as ex:  # noqa: BLE001
            print(f"   aviso: não consegui buscar o CNES {cnes}: {ex}")

    for m in MANUAIS:
        e = {}
        if m.get("cnes_hospital"):
            try:
                e = json.loads(cc.baixar(f"{API}/{m['cnes_hospital']}", timeout=60).decode("utf-8"))
            except Exception as ex:  # noqa: BLE001
                print(f"   aviso: não consegui buscar o hospital {m['cnes_hospital']}: {ex}")
        lat = m.get("lat", e.get("latitude_estabelecimento_decimo_grau"))
        lng = m.get("lng", e.get("longitude_estabelecimento_decimo_grau"))
        if lat is None:
            continue
        end = m.get("end") or " ".join(x for x in [(e.get("endereco_estabelecimento") or "").strip(), (e.get("numero_estabelecimento") or "").strip()] if x) \
            + (", " + e["bairro_estabelecimento"].strip() if e.get("bairro_estabelecimento") else "")
        tel = m.get("tel") or (e.get("numero_telefone_estabelecimento") or "").strip()
        achados[m["id"]] = [m["id"], m["nome"], m["tipo"], m["uf"], m["mun"], lat, lng, end, tel, 1, "", "ESTADUAL", 0, m["obs"], m["fonte"]]
    u = sorted(achados.values(), key=lambda r: (r[3], -r[12], r[1]))
    SAIDA.write_text(json.dumps({"gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                 "fonte": "CNES, Ministério da Saúde (tipos 69 e 39, classificados pelo nome)",
                                 "u": u}, ensure_ascii=False, separators=(",", ":")), "utf-8")
    print(f"Pronto: {len(u)} locais de doação em public/data/sangue.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
