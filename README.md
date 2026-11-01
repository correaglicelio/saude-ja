# Saúde Já

**Acesse:** https://correaglicelio.github.io/saude-ja/ (dados atualizados automaticamente toda segunda-feira)

App (site instalável no Android e no PC) para encontrar unidades de saúde do SUS:
UBS, postos, UPAs, prontos-socorros, hospitais, policlínicas, CAPS e salas de vacina,
com dados oficiais do **CNES** (Cadastro Nacional de Estabelecimentos de Saúde).

## O que tem nesta versão (módulo 1: Unidades de saúde)

- **Encontrar**: lista e mapa, com busca por estado/município ou **Perto de mim** (GPS).
- Filtros por tipo de unidade, **atende pelo SUS** e **aberto 24 horas**, e busca por nome ou bairro.
- Em cada unidade: **Como chegar** (Google Maps), **Compartilhar no WhatsApp**, copiar telefone.
- **Leitos hospitalares** em cada hospital (total, SUS e UTI) e filtro **Com UTI**.
- **Painel** para gestores: indicadores, unidades por tipo, esfera administrativa, horários,
  leitos por mil habitantes comparados com o estado e o Brasil, UTI por tipo e ranking de municípios.
- **Água** (módulo 2): situação da água de cada município (E. coli, coliformes, cloro e turbidez),
  análises da empresa de água e da vigilância lado a lado, gráfico mensal e ranking do estado.
- **Remédios** (módulo 3): Farmácia Popular por município (pessoas atendidas por condição, evolução, como pegar
  e os 41 itens gratuitos), busca de remédios no estoque do SUS (BNAFAR) na cidade ou no estado, preço pago
  pelo SUS em compras públicas (Banco de Preços) e protocolos clínicos (PCDT).
- **Vacinas** (módulo 5): Calendário Nacional de Vacinação 2026 por fase da vida, "Quais vacinas tomar agora?"
  pela data de nascimento ou semana de gestação (fica só no aparelho) e salas de vacina/UBS do SUS mais perto.
  Para gestores: doses aplicadas (SI-PNI) por vacina, cobertura estimada de 14 vacinas infantis vs. meta,
  ranking dos municípios do estado e CSV.
- **Doar sangue**: hemocentros, hemonúcleos e unidades de coleta (CNES) na cidade escolhida ou os mais próximos,
  "Posso doar?" com requisitos e prazos, e "Quando posso doar de novo?" (data só no aparelho).
- **Dengue, chikungunya e zika**: nível de alerta da cidade (verde a vermelho), casos por semana, tendência,
  mapa do estado com os municípios em alerta, prevenção e sinais de alarme (InfoDengue, semanal).
- **Gripe, covid e VSR**: casos e óbitos de SRAG por semana e por vírus, tendência e municípios com casos subindo
  (SIVEP-Gripe, atualizado toda segunda-feira). Fica na aba Doenças, junto com a dengue.
- **Transparência**: quanto o município aplica em saúde (SIOPS), com selo do mínimo de 15% da receita própria,
  gasto por habitante, evolução 2020 a 2026, ranking do estado, e o último resultado do Previne Brasil (2024).
- Exportar **CSV** (abre no Excel) e **relatório PDF**.
- Funciona **offline** com os últimos dados abertos (service worker) e pode ser **instalado** na tela inicial do Android.

## Pastas

```
1-coletar-dados.bat        clique duplo: baixa os dados do CNES no seu PC (3 a 5 min)
2-abrir-no-computador.bat  clique duplo: abre o app em http://localhost:8000
public/                    o site pronto (é isso que vai para a internet)
  data/uf/<código>.json    unidades por estado (gerado pela coleta)
  data/municipios.json     municípios com coordenadas (IBGE)
  data/estados.geojson     contorno dos estados
src/index.src.html         código-fonte do app (edite aqui)
dados/vacinacao-mensal/     doses aplicadas mês a mês (base das próximas coletas; o app usa a versão somada em public/data/vacinacao)
scripts/coletar_cnes.py    coleta da API do Ministério da Saúde
8-coletar-gripe.bat         gripe, covid e VSR (SRAG; rodar toda semana)
7-coletar-dengue.bat        dengue, chikungunya e zika (InfoDengue; rodar toda semana)
6-coletar-transparencia.bat gastos com saúde (SIOPS) e Previne Brasil
                            Os três coletam só MT (linha "set UFS=MT"); troque por MT,GO ou por todas.
scripts/coletar_sangue.py  locais de doação de sangue (python scripts/coletar_sangue.py, 3 a 6 min)
scripts/montar_site.py     monta public/index.html a partir de src/
config-github/             atualização automática semanal (vai em .github/workflows no GitHub)
```

## Rodar no seu computador

Precisa do Python 3.10 ou mais novo (python.org, marque "Add Python to PATH").

1. Clique duas vezes em `1-coletar-dados.bat` (unidades, leitos e população).
2. Clique duas vezes em `3-coletar-agua.bat` (qualidade da água, 5 a 10 min).
3. Clique duas vezes em `4-coletar-remedios.bat` (Farmácia Popular e estoque, 3 a 8 min).
4. Clique duas vezes em `5-coletar-vacinacao.bat` (doses aplicadas do mês mais recente, 15 a 30 min;
   lê cerca de 2 GB da internet sem gravar no disco). Para outros meses: `5-coletar-vacinacao.bat --meses 7 8`.
5. Clique duas vezes em `2-abrir-no-computador.bat`.

Só leitos e população: `1b-atualizar-so-leitos-e-populacao.bat` (menos de 1 min).

## Publicar na internet de graça (GitHub Pages)

1. Crie uma conta em github.com e um repositório **público** chamado `saude-ja`.
2. Envie esta pasta inteira para ele (pelo GitHub Desktop é o jeito mais fácil).
3. Mova `config-github/atualizar-dados.yml` para `.github/workflows/atualizar-dados.yml`
   (crie as pastas `.github` e `workflows`; o ponto no início do nome é obrigatório).
   No site do GitHub dá para fazer isso em **Add file → Create new file**, digitando o caminho
   `.github/workflows/atualizar-dados.yml` e colando o conteúdo.
4. No repositório: **Settings → Pages → Source: GitHub Actions**.
5. Em **Actions → Atualizar dados e publicar → Run workflow**, rode a primeira vez.
6. O endereço fica `https://SEU-USUARIO.github.io/saude-ja/`.

Depois disso, toda segunda-feira os dados são atualizados e o site republicado sozinho.
Custo: R$ 0. Domínio próprio (.com.br) é opcional, cerca de R$ 40 por ano.

> Se a coleta falhar no GitHub (a API do governo às vezes bloqueia servidores fora do Brasil),
> rode `1-coletar-dados.bat` no seu PC e envie a pasta `public/data` atualizada.

## Instalar no Android

Abra o endereço no Chrome do celular → menu ⋮ → **Adicionar à tela inicial** / **Instalar app**.
Para a Play Store no futuro: empacote o mesmo site com o Bubblewrap (TWA), sem reescrever nada.

## Próximos módulos

4. Doenças: dengue e SRAG  4.1 Academia da Saúde  6. Transparência  7. Prevenção

Detalhes, fontes e decisões de cada módulo em `ROADMAP.md`.

## Fontes e licenças

- Unidades: CNES / Ministério da Saúde, [Portal de Dados Abertos do SUS](https://dadosabertos.saude.gov.br/).
- Leitos: [Hospitais e Leitos](https://dadosabertos.saude.gov.br/dataset/hospitais-e-leitos), competência mais recente do ano.
- Água: [SISAGUA](https://dadosabertos.saude.gov.br/dataset?q=sisagua), Controle mensal e Vigilância, parâmetros básicos.
- Preços: [Banco de Preços em Saúde](https://dadosabertos.saude.gov.br/dataset/bps); protocolos: [PCDT/Conitec](https://dadosabertos.saude.gov.br/dataset/pcdt-protocolos-clinicos-e-diretrizes-terapeuticas).
- Remédios: [Farmácia Popular](https://dadosabertos.saude.gov.br/dataset/mgdi-programa-farmacia-popular-do-brasil) e [BNAFAR – Posição de Estoque](https://dadosabertos.saude.gov.br/dataset/bnafar-posicao-de-estoque).
- Vacinas: [Instrução Normativa do Calendário Nacional de Vacinação 2026](https://www.gov.br/saude/pt-br/vacinacao/publicacoes/instrucao-normativa-que-instrui-o-calendario-nacional-de-vacinacao-2026.pdf), 4ª edição (08/10/2026).
- Dengue, chikungunya e zika: InfoDengue (Fiocruz e FGV), a partir das notificações do Sinan.
- Gripe, covid e VSR: SIVEP-Gripe, banco de SRAG do Ministério da Saúde (OpenDataSUS).
- Transparência: SIOPS (API pública de consulta, Ministério da Saúde) e Sisab/Previne Brasil (indicadores de desempenho 2024).
- Doação de sangue: CNES (tipos 69 e 39, classificados pelo nome); requisitos conferidos com a Fundação Hemoba e a Secretaria da Saúde de SP.
- Doses aplicadas: [SI-PNI, Doses aplicadas pelo PNI](https://dadosabertos.saude.gov.br/dataset?q=doses+aplicadas); população por idade: API de dados abertos do Ministério da Saúde (svsa-populacao-residente, 2025).
- População: estimativas do IBGE (tabela 6579, [API de agregados](https://servicodados.ibge.gov.br/api/docs/agregados?versao=3)).
- Municípios: [kelvins/municipios-brasileiros](https://github.com/kelvins/municipios-brasileiros) (MIT), base IBGE.
- Contorno dos estados: [giuliano-oliveira/geodata-br-states](https://github.com/giuliano-oliveira/geodata-br-states) (MIT).
- Mapa: [Leaflet](https://leafletjs.com/) e © colaboradores do [OpenStreetMap](https://www.openstreetmap.org/copyright).

Horários e telefones são os informados por cada estabelecimento ao CNES e podem estar desatualizados.
