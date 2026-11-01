# Saúde Já: cronograma

Prioridade atual: **versão web** (PC/notebook e navegador do celular).

| # | Módulo | Situação |
|---|--------|----------|
| 1 | Unidades de saúde (busca, mapa, GPS, painel, CSV/PDF, WhatsApp) | ✅ pronto |
| 1.1 | Leitos hospitalares e UTI + população IBGE | ✅ pronto (31/10/2026) |
| 2 | Qualidade da água (SISAGUA) | ✅ pronto (31/10/2026) |
| 3 | Remédios (Farmácia Popular, estoque, preços BPS, PCDT, modo cidadão/gestor) | ✅ pronto (31/10/2026) |
| 4 | Doenças: dengue, chikungunya e zika (InfoDengue) | ✅ pronto (01/11/2026) |
| 4.1b | Doenças: gripe, covid e VSR (SRAG, SIVEP-Gripe) | ✅ pronto (01/11/2026) |
| 4.2 | Doenças: febre amarela | planejado |
| 4.1 | Academia da Saúde no mapa (ajuste rápido no módulo 1) | planejado |
| 5 | Vacinação: calendário de vacinação + doses aplicadas e cobertura estimada (PNI) | ✅ pronto (31/10/2026) |
| 5.1 | Doar sangue: locais de doação (CNES), requisitos, próxima doação | ✅ pronto (31/10/2026) |
| 6 | Transparência: gastos em saúde (SIOPS) + desempenho da atenção básica (Previne Brasil) | ✅ pronto (01/11/2026) |
| 7 | Prevenção: câncer de colo do útero e de mama | planejado |

Ordem pensada para entregar algo visível a cada etapa. Ideias anotadas em 31/10/2026
depois de revisar os 140 conjuntos do Portal de Dados Abertos do SUS.

---

## Próximos módulos (anotados em 31/10/2026, ainda não verificados a fundo)

Antes de implementar cada um: abrir os arquivos, conferir campos, tamanho e data de
atualização, como foi feito com estoque e preços.

### 4. Doenças (dengue, chikungunya, zika, SRAG, febre amarela)
- Fontes: Sinan/Dengue, Sinan/Febre de Chikungunya, Sinan/Vírus Zika, SRAG 2019 a 2026,
  **Febre Amarela em humanos e primatas não-humanos (1994 a 2026)**.
- Cidadão: "casos subindo na sua região nas últimas 4 semanas", em linguagem simples.
- Febre amarela: alerta quando houver casos ou morte de macacos na região ("confira sua vacina"),
  ligando ao calendário de vacinação (módulo 5).
- Gestor: curva semanal, comparação com anos anteriores, faixas etárias.
- Atenção: microdados grandes; agregar por município e semana no script.

### 4.1 Academia da Saúde no mapa
- Os polos já estão no CNES (tipo 74, "Polo Academia da Saúde"): incluir no filtro de tipos
  como "Atividade física gratuita". Conjunto [MGDI] Programa Academia da Saúde para indicadores.

### 5. Vacinação

**Calendário pronto em 31/10/2026** (aba Vacinas):
- Fonte: Instrução Normativa do Calendário Nacional de Vacinação 2026, **4ª edição, 08/10/2026**
  (gov.br/saude/pt-br/vacinacao/publicacoes). Dados em `public/data/vacinas/calendario.json`,
  escritos à mão e conferidos item por item com a IN. **Quando sair nova edição, revisar o arquivo.**
- Pontos da IN que diferem de quadros antigos: pneumocócica em transição (VPC20 aos 2 meses e reforço
  aos 12; 2ª dose aos 4 meses pode ser VPC10); Men ACWY no reforço dos 12 meses; aos 15 meses SCR 2ª
  dose + varicela 1ª dose (não tetraviral); VIP com reforços aos 15 meses e 4 anos; VSR na gestante
  a partir da 28ª semana; VPC20 para idosos acamados/institucionalizados (60–84) e todos com 85+.
- "Onde vacinar" mostra só unidades que atendem pelo SUS (clínicas privadas de vacina ficam de fora).

**Doses aplicadas (gestores) prontas em 31/10/2026** (aba Vacinas → Para gestores):
- Fonte: SI-PNI, um ZIP por mês em `s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/PNI/csv/vacinacao_<mes>_<ano>_csv.zip`
  (1,4 a 4,3 GB por mês em 2026; ~20 milhões de linhas, 56 colunas, `;`, latin-1). O script lê enquanto baixa
  (sem gravar), continua de onde parou se a conexão cair e guarda só totais por município (~9 MB no Brasil).
- Primeira coleta: setembro/2026, 11,8 milhões de doses.
- Cobertura **estimada** = doses em moradores de 0 ano (ou 1 ano) ÷ população da idade (API svsa-populacao-residente,
  2025) × meses/12. Não é a oficial (que usa nascidos vivos e acumula o ano). Aviso fixo na tela.
  Brasil set/2026: BCG 79%, Rota 90%, Penta 85%, Pneumo 93%, FA 71%, SCR D1 86%.
- **Cuidado:** a API svsa repete e pula linhas quando lida por páginas: consultar município por município.
- Nomes reais no SI-PNI: SCR 2ª dose aos 15 meses aparece como `SCRV Única`; reforço pneumo em transição como
  `VPC20 Única`; alguns estados usam Men ACWY aos 3 e 5 meses.
- Próximos passos possíveis: coletar mais meses (`--meses 1 2 3 ...`) para cobertura acumulada no ano; HPV 9–14 anos.

- **Calendário de vacinação** (ideia de 31/10/2026):
  - Por fase da vida: criança, adolescente, adulto, gestante, idoso; vacina, doses e idade.
  - "Quais vacinas tomar agora?": data de nascimento ou gestação → vacinas da idade e próximas.
    A data fica só no aparelho, nada é enviado.
  - Ligar à **sala de vacina mais perto** (CNES tipo 85, já no mapa).
  - **Cuidado:** o calendário não está no portal de dados abertos como base de dados; é publicado
    pelo Ministério em página/documento e muda de tempos em tempos. Montar a partir da versão
    oficial mais recente, conferindo item por item, mostrar "calendário vigente em [data]" e o
    aviso "confirme na sala de vacina".
- Doses aplicadas pelo PNI (2020 a 2026): cobertura por vacina e município vs. meta (gestor).
  Microdados muito grandes (milhões de linhas): agregar no script.
- ESAVI (eventos adversos): avaliar com cuidado antes de usar, para não gerar medo sem contexto.

### 4.1b Gripe, covid e VSR: SRAG (pronto em 01/11/2026)
- Fonte: banco oficial de SRAG (SIVEP-Gripe) no OpenDataSUS, um CSV por ano de início dos sintomas, publicado às
  segundas: `s3.../ckan.saude.gov.br/SRAG/<ano>/INFLUD<aa>-<dd>-<mm>-<aaaa>.csv` (2026: ~260 MB; 2025: ~380 MB).
  É a mesma base do InfoGripe (Fiocruz); o repositório de dados do InfoGripe (gitlab.fiocruz.br) não respondeu.
  A API (`/vigilancia-e-meio-ambiente/srag-2019-2026`) não tem os dados de 2026.
- Por município de residência e semana de início dos sintomas: casos, óbitos, influenza, covid, VSR, outros,
  sem vírus identificado, crianças < 5 e idosos 60+. Tendência: 4 semanas completas vs. 4 anteriores (as 3 mais
  recentes ainda estão em digitação). Fica na aba "Doenças" (botão "Gripe e covid") e tem card no Painel.
- Coleta: `8-coletar-gripe.bat` (`scripts/coletar_srag.py`), toda semana; o ano anterior fica em `dados/srag/`.

### 4. Dengue, chikungunya e zika (pronto em 01/11/2026)
- Fonte: API do InfoDengue (Fiocruz e FGV), `info.dengue.mat.br/api/alertcity`, semanal, por município (IBGE 7 dígitos)
  e doença. Guardamos o ano anterior e o atual: casos notificados por semana, nível de alerta (1 verde a 4 vermelho),
  casos estimados das últimas 8 semanas (corrigem o atraso de notificação), Rt e incidência da última semana.
- O campo `notif_accum_year` da API muda conforme o período consultado: o total do ano é somado semana a semana.
- Zika não tem série para os municípios de MT (a API devolve vazio); a aba mostra zika só onde houver dados.
- Aba com alerta da cidade, tendência, casos no ano vs. ano anterior, gráfico semanal colorido pelo nível,
  mapa do estado, municípios em alerta, mais casos por habitante, prevenção e sinais de alarme, CSV.
- Coleta: `7-coletar-dengue.bat` (`scripts/coletar_arboviroses.py`), rodar toda semana.

### 6. Transparência (pronto em 01/11/2026)
- SIOPS (API pública `siops-consulta-publica-api.saude.gov.br/v1`, atualização diária): por município e ano,
  % da receita própria aplicada em saúde (indicador 3.2, mínimo de 15% da LC 141/2012), gasto total com saúde por
  habitante (2.1), pessoal (2.2), medicamentos (2.3) e investimentos (2.5). Anos fechados 2020 a 2025 + ano em curso
  até o último bimestre homologado (em 01/11/2026: 4º bimestre de 2026, 107 de 142 municípios de MT já enviaram).
- Selo "Cumpriu os 15%" no ano fechado (vermelho se abaixo); ano em curso só como atenção (âmbar), porque o mínimo
  é conferido no fechamento. Ranking do estado, gráficos de 2020 a 2026 e CSV.
- Previne Brasil: só 2024 (1º a 3º quadrimestre) está em CSV aberto; o programa foi substituído pela Portaria
  GM/MS 3.493/2024 e os novos indicadores ainda não são publicados. Mostrado como dado histórico.
- Coleta: `6-coletar-transparencia.bat` (`scripts/coletar_transparencia.py`), cache dos anos fechados em `dados/siops/`.

### 5.1 Doar sangue (pronto em 31/10/2026)
- Não há conjunto de dados próprio. Fonte: CNES tipo 69 (hemoterapia) + tipo 39 com nome de hemocentro/banco de
  sangue + Hemope e Hemorio (cadastrados como hospital) + Hemonúcleo de Piancó (policlínica), por código CNES.
- O tipo 69 mistura locais de doação com **agências transfusionais** (dentro de hospitais, não recebem doador) e
  laboratórios: separados pelo nome (`scripts/coletar_sangue.py`). Resultado: 290 locais, coordenador nos 27 estados.
- **Lacunas conhecidas:** Santa Catarina aparece só com o Hemosc de Florianópolis (os regionais não estão no CNES
  com nome identificável); estoque de sangue por tipo não existe em dados abertos.
- Requisitos conferidos com Fundação Hemoba (BA) e SES-SP; a página do Ministério não estava acessível.
- Próximos passos possíveis: link de agendamento de cada hemocentro coordenador; painel do gestor (locais por 100 mil).

### 6. Transparência (para gestores e conselheiros)
- **SIOPS**: gasto em saúde por habitante e % da receita aplicada em saúde
  (mínimo constitucional de 15% para municípios).
- **Previne Brasil** (Sisab): indicadores de desempenho da atenção básica (pré-natal,
  preventivo, hipertensos e diabéticos acompanhados): o "boletim da UBS".
- Opcional: indicadores RIPSA já calculados (mortalidade infantil, cobertura de planos, saneamento)
  e OuvidorSUS (reclamações por tema).

### 7. Prevenção
- [MGDI] Prevenção do Câncer de Colo e Mama: cobertura de preventivo e mamografia por município,
  com "quem deve fazer e a cada quanto tempo".
- Pode ser juntado ao módulo de Vacinação como uma aba "Prevenção".

---

## Módulo 3: Remédios (anotado e implementado em 31/10/2026)

Resultado da primeira coleta: estoque informado por 9.245 unidades em 2.489 municípios
(posição de 05/06/2026; Minas Gerais quase não aparece porque usa sistema próprio).
Farmácia Popular: 12,9 milhões de pessoas atendidas em ago/2026.

**Ecossistema Remédios completado em 31/10/2026:**
- **Banco de Preços em Saúde (BPS)**: preço de referência (mediana e faixa típica) dos últimos 12 meses
  para 2.144 itens, compras por estado com comparação à mediana (gestor), e preço ao lado de cada
  remédio do estoque (ligação pelo código CATMAT; em MT, 954 de 1.342 itens do estoque têm preço).
- **PCDT/Conitec**: busca dos 83 protocolos acompanhados pela Conitec, com situação e link para o
  site do Ministério (gov.br/saude/pt-br/assuntos/pcdt/<letra>). O conjunto não traz a lista de
  remédios de cada protocolo.
- Busca de remédio no **estado inteiro** (municípios que tinham em estoque) ou só na cidade.

Pergunta do cidadão: **"onde consigo meu remédio de graça?"**

### Fontes

1. **BNAFAR – Posição de Estoque**
   https://dadosabertos.saude.gov.br/dataset/bnafar-posicao-de-estoque
   - Arquivo: `https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/bnafar/csv/Posicao_Estoque_csv_<DD-MM-AAAA>.zip`
     (cerca de 120 MB compactado; CSV separado por `;`, texto em latin-1).
   - Campos: `sg_uf; co_municipio_ibge; no_municipio; co_cnes; no_razao_social; no_fantasia;
     co_cep; no_logradouro; nu_endereco; no_bairro; nu_telefone; nu_latitude; nu_longitude; no_email;
     dt_posicao_estoque; co_catmat; ds_produto; qt_estoque; nu_lote; dt_validade; tp_produto;
     sg_programa_saude; ds_programa_saude; sg_origem`.
   - **Atenção:** última posição disponível é de **05/06/2026** e a página diz "Em manutenção".
     Cobre só os estabelecimentos que enviam dados (ex.: municípios que usam o Hórus).

2. **Programa Farmácia Popular do Brasil (PFPB)**
   https://dadosabertos.saude.gov.br/dataset/mgdi-programa-farmacia-popular-do-brasil
   - Pessoas atendidas **por município e por mês** (último: 08/2026), também com totais
     de região de saúde, estado e Brasil.
   - Arquivos em `https://demas-dados-abertos.s3.amazonaws.com/csv/<código>.csv.zip`:
     `pfpbben` (total), `sntpbih` (gratuidade), `atfpbcop` (copagamento),
     `sntpbh` (hipertensão), `sntpbd` (diabetes), `sntpdhc` (hipertensão e diabetes),
     `sntpba` (asma), `sntpbos` (osteoporose), `sntpbcon` (contracepção),
     `pfpbdm` / `pfpbdma` (absorventes, Dignidade Menstrual),
     `pfpbbfam`, `pfpbbfgrat`, `pfpbbfcop` (beneficiários do Bolsa Família).
   - **Não há** lista de farmácias credenciadas com endereço nos dados abertos.

### Como implementar (decidido)

- **Cruzamento pelo código CNES**: o estoque do BNAFAR se liga às unidades que já estão no app.
- **No card da unidade**: "Medicamentos registrados no estoque em 05/06/2026", com a data
  sempre visível e o aviso **"ligue antes de ir"**.
- **Busca por remédio**: digitar o nome (ex.: losartana) e ver no mapa as unidades do
  município que o tinham em estoque.
- **Filtrar**: só medicamentos (sem insumos como sacos de lixo ou fórmulas) e só quantidade > 0.
  Corrigir a acentuação (latin-1) no script.
- **Farmácia Popular para o cidadão**: lista fixa dos remédios gratuitos do programa e
  "no seu município, X pessoas pegaram remédio grátis para hipertensão no último mês".
- **Painel do gestor**: pessoas atendidas pelo PFPB por condição, evolução mensal,
  comparação com estado e Brasil; quantas unidades do município informam estoque e
  quais medicamentos da atenção básica aparecem zerados.
- **Atualização**: o script semanal procura a posição de estoque mais recente; quando o
  Ministério voltar a publicar, o app atualiza sozinho.
- **Arquivos de saída**: estoque resumido por UF (`data/estoque/<uf>.json`, só itens com saldo)
  e `data/farmacia_popular.json` por município, para o app continuar leve.

### Riscos

- Dado de estoque antigo pode levar alguém a ir à unidade à toa: sempre mostrar a data e o aviso.
- Cobertura parcial: deixar claro quando o município não envia dados de estoque
  ("este município não informa estoque ao Ministério"), em vez de mostrar "nenhum remédio".
