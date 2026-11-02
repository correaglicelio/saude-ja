# Manual do Saúde Já (referência para o Educa Já)

Este manual descreve como o **Saúde Já** foi construído entre 31/10 e 02/11/2026, para que o próximo app (Educa Já) reaproveite a arquitetura, o visual e as soluções, e não repita os mesmos tropeços.

- Site: https://correaglicelio.github.io/saude-ja/
- Repositório: https://github.com/correaglicelio/saude-ja (público)
- Cópia local: `D:\saudeja` (cópia de segurança; a principal é o GitHub)

---

## 1. O que o Saúde Já faz

| Módulo (menu) | Conteúdo | Fonte |
|---|---|---|
| **Unidades** | UBS, UPAs, hospitais, CAPS, salas de vacina; lista + mapa, filtros (SUS, 24 h, UTI), leitos, CSV/PDF | CNES (API dados abertos do MS), IBGE |
| **Água** | qualidade da água por município (E. coli, coliformes, cloro, turbidez), empresa × vigilância | SISAGUA |
| **Remédios** | Farmácia Popular, estoque do SUS (BNAFAR), preços pagos (Banco de Preços), PCDT; modo cidadão/gestor | MS dados abertos |
| **Vacinas** | calendário nacional por idade, "quais vacinas tomar agora", salas de vacina; para gestores: doses aplicadas e cobertura estimada | IN do calendário + SI-PNI |
| **Doenças** | dengue/chikungunya/zika (alerta verde→vermelho, casos/semana, mapa) e gripe/covid/VSR (SRAG) | InfoDengue (Fiocruz) e SIVEP-Gripe (OpenDataSUS) |
| **Doar sangue** | hemocentros e locais de coleta perto, requisitos, próxima doação | CNES + cadastro manual |
| **Gastos (Transparência)** | % da receita própria aplicada em saúde (mínimo 15%, LC 141), R$/habitante, ranking, atrasados no SIOPS; Previne Brasil (histórico 2024) | SIOPS, Sisab |
| **Painel** | resumo da cidade em cards (um por módulo, borda vermelha = alerta, laranja = atenção) + indicadores e tabela de unidades | todas |

Cidade padrão: Pontes e Lacerda (MT). Escolha da cidade fica salva no aparelho e vale para todos os módulos.

---

## 2. Estrutura do repositório

```
.github/workflows/atualizar-dados.yml   rotina semanal: coleta tudo e publica no GitHub Pages
.github/workflows/android.yml           compila o projeto Android para conferir (gera APK de teste)
config-github/                          cópia da rotina (o Claude não grava direto em .github pelo PC)
src/index.src.html                      O APP INTEIRO (HTML + CSS + JS), ~300 KB
src/leaflet.css                         CSS do mapa, embutido na montagem
scripts/montar_site.py                  monta public/index.html (e build/artefato.html para prévia)
scripts/coletar_<tema>.py               uma coleta por fonte (só biblioteca padrão do Python)
public/                                 o site publicado (index.html, sw.js, manifest, ícones, data/)
public/data/<tema>/<UF>.json            dados compactos por estado (código IBGE da UF: 51 = MT)
public/data/<tema>/meta.json            data da coleta, períodos, UFs disponíveis
dados/                                  caches das coletas (ex.: meses de vacinação, anos fechados do SIOPS)
android/                                projeto do APK (WebView)
N-coletar-<tema>.bat                    atalhos para rodar cada coleta no Windows
README.md, ROADMAP.md                   documentação e cronograma
```

Ciclo de uma mudança: editar `src/index.src.html` → `python scripts/montar_site.py --artefato` → testar (Playwright) → commit e push → GitHub Pages publica em ~1 min → site e APK atualizados.

---

## 3. Front-end (padrões a repetir)

**Base**
- JavaScript puro dentro de uma IIFE, sem framework. Estado global `S` (uf, mun, view, mobile, filtros...). Persistência leve com `store` (localStorage em try/catch).
- Mapa: Leaflet 1.9.4 (cdnjs) + OpenStreetMap. `ResizeObserver` chama `invalidateSize`.
- Navegação: `setView(v)` (computador, menu lateral) e `setMobile(m)` (celular, barra inferior), com `#hash` na URL. `aplicar()` re-renderiza a tela atual quando muda cidade/filtro.
- Dados carregados sob demanda por UF com `getJSON()` e cache em `Map`.

**Layout**
- Computador (≥ 821 px): menu lateral à esquerda (232 px) + barra de local no topo + conteúdo.
- Celular: barra de local no topo, uma tela por vez e **barra inferior com 9 botões** (rótulos curtos: Unidades, Mapa, Água, Remédios, Vacinas, Doenças, Sangue, Gastos, Painel). Fonte reduzida em telas ≤ 430 px e ≤ 380 px.
- Barra de local: Estado (select) + Município (campo com **lista de sugestões própria**) + botão de GPS (no celular só o ícone).

**Identidade visual**
- Fonte Inter. Cores em variáveis CSS no `:root`, com tema escuro (`prefers-color-scheme` + `[data-theme]`).
- Principal: petróleo `--accent:#06373A`; destaque verde `--verde:#0E9F6E`; fundo `--bg:#F4F6F8`; superfície branca; status `--ok`, `--warn`, `--bad`, `--none` (cada um com versão `-soft`).
- Cada módulo tem sua cor (no menu lateral e na barra inferior): água azul `#1F6FE0`, remédios roxo `#7A3E8F`, sangue vermelho `#D7263D`, doenças oliva `#65751D`, gastos âmbar `#B7791F`. No tema escuro, versões mais claras.
- Ícones: sprite SVG "duotone" (`<symbol id="d-...">` com classes `.da` cor principal, `.db` cor clara, `.dw` branco), coloridos via `--c1/--c2`. No cabeçalho de cada aba, um "tile" quadrado com degradê (`.ptile`).
- Logo: alfinete de mapa verde com cruz branca e estrela âmbar.
- Componentes recorrentes: `.box` (caixa), `.kpis/.kpi` (indicadores), `.rs-card` (cards do Painel), pílulas `.rs-pill ok/warn/bad`, tabelas `.munres` (linhas `.r-bad/.r-warn` destacadas), barras horizontais, gráficos de colunas em SVG feitos à mão (rótulo no topo, linha de referência tracejada, tooltip via `<title>`), aviso `.warnbar`, dicas `rotuloTip()` com textos em `DICAS`.
- Categorias de gráfico com paleta validada (azul `#2a78d6`, laranja `#eb6834`, verde-água `#1baf7a`, amarelo `#eda100`, cinza para "não especificado"), sempre com legenda e tabela de números ao lado.

**Comportamentos já resolvidos**
- **Sugestões de município próprias** (a `<datalist>` nativa fica feia no WebView do Android): sem acento, busca pelo começo e pelo meio, até 8 itens, ao tocar no campo ele esvazia e mostra a cidade atual como dica; se sair sem digitar, volta.
- **Puxar para atualizar** feito em JS (o WebView não tem), ativo só no app/instalado, desligado no mapa e em campos.
- **Ficha da unidade** em janela (bottom sheet no celular): botão voltar do Android fecha (via `history.pushState`/`popstate`).
- **Exportar CSV**: função `salvar()`; dentro do APK usa a ponte `window.SaudeJaAndroid.salvar(nome, base64, tipo)` e grava em Downloads.
- **Cards do Painel**: borda vermelha (`rs-alerta`) para problema sério, laranja (`rs-atencao`) para atenção; card inteiro clicável leva ao módulo.
- **Dados parciais/atrasados**: sempre explicar na tela (ex.: "ano em curso, parcial", "semanas recentes incompletas", "município atrasado no SIOPS").

---

## 4. Coleta de dados

**Convenções dos scripts**
- Só biblioteca padrão (urllib, json, csv, zipfile, concurrent.futures). Retentativas com espera, e retomada de downloads grandes com **HTTP Range**.
- Arquivos grandes (CSV de 260 MB a 4 GB) são **lidos em fluxo, sem gravar no disco**; ficam só os totais por município.
- Saída: `public/data/<tema>/<UF>.json` compacto (listas em vez de objetos, chaves curtas) + `meta.json` com `gerado_em`, períodos e `ufs` (lista de UFs coletadas; o app mostra "ainda não há dados de X" com botão para ir ao estado disponível).
- Parâmetro `--uf MT`, `--uf MT,GO` ou `--uf todas`. Os `.bat` têm a linha `set UFS=MT`.
- Caches em `dados/` para não baixar de novo o que não muda (anos fechados, meses já lidos).

**Fontes e particularidades aprendidas**
- **apidadosabertos.saude.gov.br**: catálogo em `/v1/static/swagger.json`. Várias bases estão abandonadas (equipamentos e profissionais do CNES param em 2008–2011; SRAG da API não tem 2026). **Sempre conferir datas antes de usar.**
- **OpenDataSUS / S3** (`s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/...`): arquivos publicados com a data no nome; não dá para listar a pasta, então descobrimos o nome tentando datas (HEAD) dos últimos dias.
- **SIOPS** (`siops-consulta-publica-api.saude.gov.br/v1`): por município/ano/bimestre; 404 = não homologado. Municípios atrasam: buscar o **último bimestre enviado** e marcar o atraso.
- **IBGE** (`servicodados.ibge.gov.br`) **não responde aos servidores do GitHub** (fora do Brasil). Solução: o 7º dígito do código IBGE é calculado (pesos 1-2-1-2-1-2, soma dos algarismos, módulo 10) com 9 exceções conhecidas: 2201919, 2201988, 2202251, 2611533, 3117836, 3152131, 4305871, 5203939, 5203962.
- **InfoDengue** (`info.dengue.mat.br/api/alertcity`): ótimo e semanal; o campo `notif_accum_year` não é confiável (somar semana a semana).
- O ambiente de trabalho do Claude não acessa sites do governo; para conferir fontes e gerar os dados de teste, use o navegador do app (pane) logado no PC.

---

## 5. Automação no GitHub

- `atualizar-dados.yml`: `schedule` (segunda 06:17 de Brasília), `workflow_dispatch` (botão "Run workflow") e `push` (só republica).
- Job **coletar**: cada coleta é um passo com `continue-on-error: true` e `timeout-minutes`; passo final escreve um **resumo** (success/failure por módulo) em `$GITHUB_STEP_SUMMARY`; commit dos dados com o usuário "saude-ja-bot".
- Job **publicar**: `actions/upload-pages-artifact` da pasta `public` + `deploy-pages`.
- **Concorrência separada**: `coleta` (uma por vez) e `pages` (publicação), para uma mudança no site não ficar presa atrás de uma coleta de 30 min.
- Configuração no GitHub: Settings → Actions → General → **Read and write permissions**; Settings → Pages → Source: **GitHub Actions**. Repositório **público** (Pages e minutos grátis).
- O GitHub às vezes **pula ou atrasa** rodadas agendadas (principalmente as primeiras): conferir na segunda e disparar manualmente se preciso.
- Todos os sites do governo usados responderam do GitHub, exceto o IBGE.

---

## 6. App Android (APK)

- Pasta `android/`: Gradle 8.10.2, Android Gradle Plugin 8.7.3, compileSdk/targetSdk 35, minSdk 24, **Java**, sem bibliotecas.
- `MainActivity`: um `WebView` que abre o site publicado (`SITE`, `HOST`, `CAMINHO` no topo do arquivo); links externos (telefone, WhatsApp, mapas) abrem fora; permissão de localização para o GPS; botão voltar navega; página "Sem conexão"; margens para as barras do sistema (Android 15); ponte `salvar()` para gravar arquivos em Downloads; user agent com `SaudeJaApp/1.0`.
- Ícone adaptativo (fundo petróleo + logo) gerado a partir do SVG.
- Gerar: Android Studio → File → Open `D:\...\android` → ☰ → Build → **Generate Signed App Bundle or APK** → APK → release. Chave em `D:\Chaves\saudeja.jks` (alias **saudej**). **Cada app novo deve ter a sua chave**; guardar cópia e senhas.
- O APK só precisa ser refeito se mudar ícone, nome, endereço do site ou permissões. Todo o resto vem do site.
- O APK tem ~52 KB (é só o "envelope").
- `android.yml` compila no GitHub a cada mudança na pasta e oferece um APK de teste em Actions → Artifacts.

---

## 7. Lições aprendidas (não repetir)

1. Conferir se a fonte está **viva e atual** antes de prometer um módulo.
2. Sites do governo podem **bloquear acesso de fora do Brasil**: evitar depender deles na rotina do GitHub (ou ter plano B).
3. Arquivos de dados grandes: ler em fluxo e guardar só agregados; manter cada JSON publicado bem abaixo de 50 MB.
4. Mostrar **o período real** de cada dado; quando o órgão atrasa, dizer isso com destaque.
5. No ano em curso, comparar com o estado **no mesmo período**; comparar parcial com ano inteiro engana (indicar "ano inteiro").
6. GitHub Pages guarda arquivos por 10 min: o service worker usa `cache: "no-cache"` para conferir a versão nova a cada abertura, e o registro usa `updateViaCache: "none"`.
7. Componentes nativos do navegador (datalist, pull-to-refresh) se comportam diferente no WebView: testar no APK.
8. IDs repetidos entre abas quebram telas: prefixar IDs por módulo (ex.: `#a-` água, `#ar-` doenças, `#t-` transparência).
9. Disco C: cheio derruba o Android Studio: manter SDK, Gradle e emuladores no D:.
10. Testar sempre: celular (360 e 412 px) e computador, tema claro e escuro, e o fluxo completo (escolher cidade → módulo → card do Painel).

---

## 8. Checklist para começar o Educa Já

1. Criar a pasta `D:\educaja` e o repositório `educa-ja` (público) seguindo a mesma estrutura.
2. Copiar do Saúde Já: `scripts/montar_site.py`, o esqueleto do `src/index.src.html` (barra de local, menus, Painel, componentes, tokens), `sw.js`, `manifest`, a rotina do GitHub e o projeto `android/` (trocar pacote `br.educaja.app`, nome, endereço, cores e ícone; gerar chave nova `D:\Chaves\educaja.jks`).
3. Definir identidade visual própria (cor principal e logo), mantendo o mesmo padrão de componentes.
4. Levantar e **testar** as fontes de dados da Educação (lista inicial abaixo), começando pelo MT.
5. Construir um módulo por vez, cada um com: coleta + `.bat` + passo na rotina + aba + card no Painel + CSV + fonte citada.

**Fontes da Educação para investigar (a verificar no início do projeto)**
- **INEP**: Censo Escolar (escolas, matrículas, infraestrutura, docentes; microdados anuais), Catálogo de Escolas (endereço e localização), IDEB e SAEB por escola e município, indicadores educacionais (distorção idade-série, aprovação, abandono).
- **FNDE**: repasses do PNAE (merenda), PDDE, transporte escolar (PNATE) e FUNDEB.
- **SIOPE** (o "SIOPS da Educação"): quanto cada município aplica em educação (mínimo constitucional de **25%** em manutenção e desenvolvimento do ensino) e uso do FUNDEB. Pode render um módulo de Transparência igual ao do Saúde Já.
- Portal **dados.gov.br** e dados abertos da Seduc-MT.
