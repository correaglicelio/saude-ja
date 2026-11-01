"""
Saúde Já — coleta das unidades de saúde do CNES para o app.

Fonte: API de Dados Abertos do Ministério da Saúde
       https://apidadosabertos.saude.gov.br/cnes/estabelecimentos

O que faz
  1. Percorre os 27 estados x tipos de unidade que atendem o público.
     A API devolve no máximo 20 registros por página, então pagina por offset.
  2. Mantém só os campos que o app usa, em formato compacto (lista de listas).
  3. Junta os leitos hospitalares de cada hospital (arquivo mensal do Ministério)
     e baixa a população estimada de cada município (IBGE).
  4. Grava um arquivo por estado em  public/data/uf/<codigo_uf>.json,
     public/data/populacao.json e um resumo em public/data/meta.json.

Opção:  --sem-cnes  reaproveita as unidades já baixadas e só atualiza leitos e população.

Roda sozinho toda semana pelo GitHub Actions (.github/workflows/atualizar-dados.yml).
Para rodar na sua máquina:  python scripts/coletar_cnes.py
Só usa a biblioteca padrão do Python 3.10+.
"""
from __future__ import annotations

import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

API = "https://apidadosabertos.saude.gov.br/cnes/estabelecimentos"
LIMITE = 20                  # teto da API
PARALELO = 6                 # requisições simultâneas; não exagere, é serviço público
TENTATIVAS = 4

UFS = [11, 12, 13, 14, 15, 16, 17, 21, 22, 23, 24, 25, 26, 27, 28, 29,
       31, 32, 33, 35, 41, 42, 43, 50, 51, 52, 53]

# Tipos de unidade (tabela /cnes/tipounidades) que atendem o cidadão diretamente.
TIPOS = {
    1: "Posto de saúde",
    2: "Unidade básica (UBS)",
    4: "Policlínica",
    5: "Hospital geral",
    7: "Hospital especializado",
    15: "Unidade mista",
    20: "Pronto-socorro geral",
    21: "Pronto-socorro especializado",
    61: "Centro de parto normal",
    62: "Hospital-dia",
    70: "CAPS",
    73: "Pronto atendimento (UPA)",
    85: "Centro de imunização",
}

# Ordem dos campos em cada linha gravada (o app lê nesta mesma ordem).
CAMPOS = ["cnes", "nome", "tipo", "municipio", "lat", "lng", "endereco",
          "numero", "bairro", "cep", "telefone", "sus", "turno",
          "hospitalar", "esfera", "atualizado"]

SAIDA = Path(__file__).resolve().parents[1] / "public" / "data"


def _txt(valor) -> str:
    return "" if valor is None else str(valor).strip()


def _coord(valor):
    try:
        return round(float(valor), 5) if valor is not None else None
    except (TypeError, ValueError):
        return None


def compactar(e: dict) -> list:
    return [
        e.get("codigo_cnes"),
        _txt(e.get("nome_fantasia") or e.get("nome_razao_social")),
        e.get("codigo_tipo_unidade"),
        e.get("codigo_municipio"),
        _coord(e.get("latitude_estabelecimento_decimo_grau")),
        _coord(e.get("longitude_estabelecimento_decimo_grau")),
        _txt(e.get("endereco_estabelecimento")),
        _txt(e.get("numero_estabelecimento")),
        _txt(e.get("bairro_estabelecimento")),
        _txt(e.get("codigo_cep_estabelecimento")),
        _txt(e.get("numero_telefone_estabelecimento")),
        1 if e.get("estabelecimento_faz_atendimento_ambulatorial_sus") == "SIM" else 0,
        _txt(e.get("codigo_identificador_turno_atendimento")),
        1 if e.get("estabelecimento_possui_atendimento_hospitalar") else 0,
        _txt(e.get("descricao_esfera_administrativa")),
        _txt(e.get("data_atualizacao")),
    ]


# Alguns computadores não reconhecem a cadeia de certificados dos sites .gov.br.
# Se a verificação falhar, a coleta continua sem ela (os dados são públicos e só
# são lidos, nada é enviado) e um aviso é mostrado.
_CTX = ssl.create_default_context()
_SSL_AVISADO = False


def _sem_verificacao() -> None:
    global _CTX, _SSL_AVISADO
    if not _SSL_AVISADO:
        print("Aviso: certificado do site do Ministério não reconhecido neste computador; "
              "seguindo sem verificar (dados públicos, somente leitura).")
        _SSL_AVISADO = True
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    _CTX = ctx


def pagina(uf: int, tipo: int, offset: int) -> list[dict]:
    url = (f"{API}?limit={LIMITE}&offset={offset}&status=1"
           f"&codigo_uf={uf}&codigo_tipo_unidade={tipo}")
    erro = None
    for tentativa in range(TENTATIVAS):
        try:
            req = urllib.request.Request(url, headers={
                "Accept": "application/json",
                "User-Agent": "SaudeJa/1.0"})
            with urllib.request.urlopen(req, timeout=60, context=_CTX) as resp:
                corpo = json.loads(resp.read().decode("utf-8"))
            return corpo.get("estabelecimentos", []) if isinstance(corpo, dict) else corpo
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as ex:
            erro = ex
            if isinstance(getattr(ex, "reason", None), ssl.SSLCertVerificationError):
                _sem_verificacao()
                continue
            time.sleep(2 ** tentativa)
    raise RuntimeError(f"Falhou UF {uf} tipo {tipo} offset {offset}: {erro}")


def coletar(uf: int, tipo: int) -> list[list]:
    linhas, offset = [], 0
    while True:
        lote = pagina(uf, tipo, offset)
        linhas.extend(compactar(e) for e in lote)
        if len(lote) < LIMITE:
            return linhas
        offset += LIMITE


def baixar(url: str, timeout: int = 180) -> bytes:
    """GET simples com novas tentativas (para arquivos grandes do S3 e do IBGE)."""
    erro = None
    for tentativa in range(TENTATIVAS):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SaudeJa/1.0"})
            with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as resp:
                dados = resp.read()
            # O IBGE responde compactado (gzip) mesmo sem pedirmos.
            if dados[:2] == b"\x1f\x8b":
                import gzip
                dados = gzip.decompress(dados)
            return dados
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, TimeoutError) as ex:
            erro = ex
            if isinstance(getattr(ex, "reason", None), ssl.SSLCertVerificationError):
                _sem_verificacao()
                continue
            time.sleep(2 ** tentativa)
    raise RuntimeError(f"Falhou {url}: {erro}")


# ---------------------------------------------------------------- leitos
# Arquivo mensal "Hospitais e Leitos" (dadosabertos.saude.gov.br/dataset/hospitais-e-leitos).
# Um ZIP por ano, com uma linha por hospital e por competência (mês). Usamos o mês mais recente.
LEITOS_URL = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/Leitos_SUS/Leitos_csv_{ano}.zip"
# Ordem gravada em cada unidade (coluna "leitos"):
LEITOS_CAMPOS = ["LEITOS_EXISTENTES", "LEITOS_SUS", "UTI_TOTAL_EXIST", "UTI_TOTAL_SUS",
                 "UTI_ADULTO_EXIST", "UTI_PEDIATRICO_EXIST", "UTI_NEONATAL_EXIST"]


def coletar_leitos() -> tuple[str, dict[int, list[int]]]:
    import csv, io, zipfile
    ano = datetime.now().year
    for a in (ano, ano - 1):
        try:
            dados = baixar(LEITOS_URL.format(ano=a))
            break
        except urllib.error.HTTPError as ex:
            if ex.code not in (403, 404):
                raise
    else:
        raise RuntimeError("Arquivo de leitos não encontrado para este ano nem o anterior.")
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        bruto = z.read(nome)
    try:
        texto = bruto.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = bruto.decode("latin-1")
    linhas = list(csv.DictReader(io.StringIO(texto), delimiter=";"))
    comp = max(l["COMP"] for l in linhas)
    por_cnes: dict[int, list[int]] = {}
    for l in linhas:
        if l["COMP"] != comp or l.get("MOTIVO_DESABILITACAO"):
            continue
        valores = [int(l.get(c) or 0) for c in LEITOS_CAMPOS]
        if valores[0] > 0:
            por_cnes[int(l["CNES"])] = valores
    return comp, por_cnes


# ---------------------------------------------------------------- população
# Estimativa de população do IBGE (tabela 6579), ano mais recente disponível.
IBGE = "https://servicodados.ibge.gov.br/api/v3/agregados/6579"


def coletar_populacao() -> tuple[str, dict[int, int]]:
    periodos = json.loads(baixar(f"{IBGE}/periodos"))
    ano = max(p["id"] for p in periodos)
    res = json.loads(baixar(f"{IBGE}/periodos/{ano}/variaveis/9324?localidades=N6[all]"))
    pop = {}
    for s in res[0]["resultados"][0]["series"]:
        valor = s["serie"].get(ano)
        if valor and valor.isdigit():
            pop[int(s["localidade"]["id"]) // 10] = int(valor)   # código de 6 dígitos, igual ao CNES
    return ano, pop


def main() -> int:
    (SAIDA / "uf").mkdir(parents=True, exist_ok=True)
    so_complementos = "--sem-cnes" in sys.argv   # reaproveita as unidades já baixadas
    por_uf: dict[int, list] = {uf: [] for uf in UFS}

    if so_complementos:
        for uf in UFS:
            arq = SAIDA / "uf" / f"{uf}.json"
            por_uf[uf] = [l[:len(CAMPOS)] for l in json.loads(arq.read_text("utf-8"))]
        print("Usando as unidades já baixadas (--sem-cnes).")
    else:
        tarefas = [(uf, t) for uf in UFS for t in TIPOS]
        print(f"Coletando {len(tarefas)} combinações de estado x tipo de unidade...")
        feitas = 0
        with ThreadPoolExecutor(PARALELO) as pool:
            for (uf, _), linhas in zip(tarefas, pool.map(lambda a: coletar(*a), tarefas)):
                por_uf[uf].extend(linhas)
                feitas += 1
                if feitas % 27 == 0 or feitas == len(tarefas):
                    print(f"  {feitas}/{len(tarefas)} ({sum(map(len, por_uf.values()))} unidades até agora)", flush=True)

    print("Baixando leitos hospitalares (Ministério da Saúde)...")
    comp, leitos = coletar_leitos()
    print(f"  competência {comp[4:]}/{comp[:4]}: {len(leitos)} hospitais com leitos")
    print("Baixando população dos municípios (IBGE)...")
    try:
        ano_pop, pop = coletar_populacao()
        print(f"  estimativa {ano_pop}: {len(pop)} municípios")
    except Exception as ex:                      # sem população o app funciona, só sem as taxas
        anterior = SAIDA / "populacao.json"
        if anterior.exists():
            p = json.loads(anterior.read_text("utf-8"))
            ano_pop, pop = p["ano"], {int(k): v for k, v in p["por_municipio"].items()}
            print(f"  IBGE indisponível ({ex}); mantendo a população de {ano_pop} já salva.")
        else:
            ano_pop, pop = None, {}
            print(f"  IBGE indisponível ({ex}); seguindo sem população (as taxas por habitante ficam vazias).")

    total = 0
    tot_leitos = [0] * len(LEITOS_CAMPOS)
    for uf, linhas in por_uf.items():
        vistos, unicos = set(), []
        for l in linhas:                       # um CNES pode aparecer duas vezes
            if l[0] not in vistos:
                vistos.add(l[0])
                l = l[:len(CAMPOS)] + [leitos.get(l[0], 0)]
                unicos.append(l)
                if l[-1]:
                    tot_leitos = [a + b for a, b in zip(tot_leitos, l[-1])]
        unicos.sort(key=lambda l: (l[3] or 0, l[1]))
        (SAIDA / "uf" / f"{uf}.json").write_text(
            json.dumps(unicos, ensure_ascii=False, separators=(",", ":")), "utf-8")
        total += len(unicos)
        print(f"UF {uf}: {len(unicos)} unidades")

    (SAIDA / "populacao.json").write_text(
        json.dumps({"ano": ano_pop, "por_municipio": pop}, separators=(",", ":")), "utf-8")

    meta = {
        "atualizado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fonte": API,
        "campos": CAMPOS + ["leitos"],
        "leitos_campos": LEITOS_CAMPOS,
        "leitos_competencia": comp,
        "populacao_ano": ano_pop,
        "brasil": {"unidades": total, "populacao": sum(pop.values()),
                   **{c.lower(): v for c, v in zip(LEITOS_CAMPOS, tot_leitos)}},
        "tipos": TIPOS,
        "total": total,
    }
    (SAIDA / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), "utf-8")
    print(f"Total: {total} unidades, {tot_leitos[0]} leitos ({tot_leitos[2]} de UTI)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
