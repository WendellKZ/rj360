# RJ360

Sistema de acompanhamento e gestao de **recuperacao judicial** para pequenas e
medias empresas, com modulo de **prospeccao de clientes**.

A consultoria acompanha varias empresas em RJ pelo painel interno; cada cliente
entra num portal proprio e ve apenas o andamento do seu processo, em linguagem
simples.

## O que ja existe

**Painel interno**

- Cadastro de empresas, contatos e responsaveis.
- Processo de RJ com os marcos da Lei 11.101/2005: distribuicao, deferimento do
  processamento (art. 52), edital, plano (art. 53), objecoes (art. 55), AGC,
  concessao (art. 58) e encerramento (art. 63).
- **Geracao automatica de prazos legais** a partir das datas informadas
  (60 dias do plano, 15 dias de habilitacoes, 30 dias de objecoes, stay period
  de 180/360 dias, 2 anos de fiscalizacao).
- Agenda de prazos com alerta de vencimento e marcacao de cumprimento.
- Linha do tempo de andamentos, quadro de credores por classe, documentos e
  controle das parcelas do plano.
- Painel com indicadores: processos por fase, prazos criticos, stay period
  proximo do fim, proximas assembleias e funil de prospeccao.

**Portal do cliente**

- Acesso restrito a propria empresa.
- Andamentos e documentos marcados como visiveis ao cliente.
- Proximos prazos e situacao atual do processo.

**Importacao do quadro de credores**

- Planilha .xlsx ou .csv, com cabecalho em portugues e valores no formato
  brasileiro (`1.234,56`).
- Previa na tela antes de gravar: linhas validas de um lado, linhas com
  problema e o motivo do outro.
- Credor ja cadastrado (mesmo CPF/CNPJ, ou mesmo nome quando nao ha documento)
  pode ser atualizado, mantido ou duplicado — voce escolhe no envio.
- Planilha modelo para download, com instrucoes na segunda aba.

**Integracao com o tribunal (DataJud/CNJ)**

- Importacao das movimentacoes pela API publica do CNJ, por processo ou em lote.
- Cada movimento vira um andamento com o codigo da tabela do CNJ; rodar de novo
  nao duplica nada.
- Historico de cada sincronizacao (o que veio, quantos andamentos novos, erros).

**Alertas de prazo por e-mail**

- Resumo diario para cada responsavel, separado em atrasados, vencem hoje e a
  vencer, com link direto para o processo.
- Prazo sem responsavel vai para os e-mails de supervisao.
- O mesmo prazo nao e avisado duas vezes no mesmo dia, mas volta no dia
  seguinte enquanto estiver pendente.

**Prospeccao**

- Funil com estagios (novo, contato, diagnostico, proposta, negociacao).
- Leads com situacao juridica (pre-crise, extrajudicial, RJ em curso...),
  origem, valor estimado, responsavel e proximo contato.
- Registro de atividades e **conversao do lead em empresa cliente** em um clique.

## Stack

- Python 3.11+ e Django 5.2
- PostgreSQL (SQLite funciona para desenvolvimento)
- Templates Django + HTMX + Tailwind (via CDN)
- WhiteNoise para arquivos estaticos

## Como rodar

### 1. Ambiente

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env     # Windows: copy .env.example .env
```

### 2. Banco

Com Docker (recomendado):

```bash
docker compose up -d
```

O container publica o Postgres na porta **5433** do host, para nao conflitar com
um Postgres ja instalado na maquina (que costuma ocupar a 5432).

Sem Docker, edite o `.env`:

```
DATABASE_URL=sqlite:///db.sqlite3
```

### 3. Migracoes e dados de exemplo

```bash
python manage.py migrate
python manage.py seed_demo          # dados ficticios para explorar o sistema
python manage.py createsuperuser    # seu acesso de administrador
```

O `seed_demo` cria dois usuarios com a senha `rj360demo`:

| usuario    | perfil        | ve o que                          |
|------------|---------------|-----------------------------------|
| `analista` | equipe interna| todas as empresas e processos     |
| `cliente`  | portal        | apenas a empresa vinculada        |

### 4. Subir

```bash
python manage.py runserver
```

- Painel interno: http://localhost:8000/
- Portal do cliente: http://localhost:8000/portal/
- Admin: http://localhost:8000/admin/

### Testes

```bash
python manage.py test
```

## Importacao do quadro de credores

Na pagina do processo, em Quadro de credores, use **Importar planilha de
credores**. Baixe a planilha modelo na propria tela.

Colunas obrigatorias: **Credor**, **Classe** e **Valor**. Opcionais: CPF/CNPJ,
Valor habilitado, Situacao, Sujeito a RJ, Observacoes. A ordem nao importa (a
leitura e pelo cabecalho) e colunas a mais sao ignoradas.

A classe aceita `I`, `II`, `III`, `IV`, o numero (`1` a `4`) ou o nome
(trabalhista, garantia real, quirografario, ME/EPP). Valor aceita
`1.234,56`, `1234.56` ou `R$ 1.234,56` — mas um texto sem numero e recusado
com o numero da linha, em vez de virar zero em silencio.

Nada e gravado no envio: o arquivo fica guardado, a previa mostra o que sera
importado e so a confirmacao grava. O historico das importacoes fica no admin.

## Login por codigo (portal do cliente)

O cliente entra sem senha: informa o e-mail ou o celular cadastrado e recebe um
codigo de seis digitos. A equipe interna continua entrando por usuario e senha.

Como funciona, do lado da seguranca:

- o codigo e sorteado com `secrets` e guardado como **hash**, nunca em claro;
- vale 10 minutos, serve uma unica vez, e um pedido novo invalida o anterior;
- 5 tentativas erradas queimam o codigo; 3 pedidos em 15 minutos bloqueiam novos envios;
- a tela responde a mesma coisa para contato existente ou nao, para nao revelar cadastro.

O envio usa o canal de `CANAL_CODIGO_ACESSO` no `.env` — hoje `email` (usa o
mesmo SMTP dos alertas). Para WhatsApp, basta implementar o envio em
`apps/accounts/codigos.py::_enviar`; o resto do fluxo nao muda.

## Integracao com o DataJud (CNJ)

A API publica do CNJ expoe os metadados processuais de todos os tribunais. A
chave de acesso e publica, mas nao fica no codigo: pegue em
[datajud-wiki.cnj.jus.br/api-publica/acesso](https://datajud-wiki.cnj.jus.br/api-publica/acesso/)
e coloque no `.env`:

```
DATAJUD_API_KEY=sua-chave-aqui
```

O processo precisa ter a **sigla do tribunal** preenchida no padrao do CNJ. O
sistema valida contra a lista oficial de endpoints:

- Superiores: `TST`, `TSE`, `STJ`, `STM` (o STF nao tem endpoint publico)
- Federal: `TRF1` a `TRF6`
- Estadual: `TJSP`, `TJRJ`, ... e `TJDFT`
- Trabalho: `TRT1` a `TRT24`
- Eleitoral: `TRE-SP`, `TRE-RJ`, ... e `TRE-DFT`
- Militar estadual: `TJMMG`, `TJMRS`, `TJMSP`

Se o indice do tribunal for diferente da sigla, use o campo "sigla no DataJud"
para sobrescrever.

Na pagina do processo ha o botao **Sincronizar com o tribunal**. Em lote:

```bash
python manage.py sync_datajud                    # processos em curso
python manage.py sync_datajud --processo 12
python manage.py sync_datajud --numero 1002345-12.2025.8.26.0114
python manage.py sync_datajud --todos            # inclui encerrados
```

Para rodar diariamente, agende o comando no Agendador de Tarefas do Windows ou
no cron do servidor.

Cuidados embutidos:

- Andamentos importados entram **restritos a equipe**. So aparecem no portal do
  cliente depois de liberados, ou se voce mudar
  `DATAJUD_ANDAMENTOS_VISIVEIS_CLIENTE=True` no `.env`.
- Processo que o tribunal marcou com **nivel de sigilo** nunca vai para o
  portal, mesmo com a opcao acima ligada.
- A data do movimento e gravada como o tribunal informou, sem conversao de
  fuso — converter poderia jogar um ato da meia-noite para o dia anterior.

## Alertas de prazo por e-mail

Configure o SMTP no `.env`:

```
EMAIL_HOST=smtp.suaempresa.com.br
EMAIL_PORT=587
EMAIL_HOST_USER=nao-responda@suaempresa.com.br
EMAIL_HOST_PASSWORD=sua-senha
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=RJ360 <nao-responda@suaempresa.com.br>
NOTIFICACOES_SUPERVISAO=voce@suaempresa.com.br
SITE_URL=https://rj360.suaempresa.com.br
```

Com `EMAIL_HOST` vazio, as mensagens saem no terminal em vez de serem
enviadas — da para ver o resultado antes de ligar o SMTP.

```bash
python manage.py alertar_prazos --simular              # mostra sem enviar
python manage.py alertar_prazos --para voce@email.com  # tudo para um endereco
python manage.py alertar_prazos                        # envio real
python manage.py alertar_prazos --dias 30              # janela maior
```

Quem recebe o que: cada prazo vai para o **responsavel** cadastrado nele. Prazo
sem responsavel (ou com responsavel sem e-mail) vai para `NOTIFICACOES_SUPERVISAO`.

### Agendar no Windows

No Agendador de Tarefas, crie uma tarefa diaria (ex.: 8h) com:

- Programa: `C:\Users\SEU-USUARIO\Documents\rj360\.venv\Scripts\python.exe`
- Argumentos: `manage.py alertar_prazos`
- Iniciar em: `C:\Users\SEU-USUARIO\Documents\rj360`

Mesma receita para o `sync_datajud`. Em servidor Linux, use o cron.

### Termo de uso da API

O [Termo de Uso do CNJ](https://datajud-wiki.cnj.jus.br/api-publica/termo-uso)
diz que a API e fornecida "exclusivamente para fins legais, **nao comerciais** e
autorizados" (clausula 3.3) e que o usuario concorda em "nao modificar,
distribuir, vender ou explorar comercialmente a API ou qualquer informacao
derivada dela" (clausula 3.8). O CNJ tambem nao garante precisao nem
atualidade dos dados (clausula 3.6).

Antes de usar a integracao em um servico cobrado do cliente, avalie isso com o
juridico. Alternativas: consulta oficial no sistema do tribunal, contrato com
um provedor licenciado de dados processuais, ou uso restrito a conferencia
interna da equipe.

## Estrutura

```
config/               configuracao do Django (settings, urls, wsgi)
apps/
  core/               base, validadores (CNPJ, numero CNJ), filtros, painel
  accounts/           usuario customizado (interno x cliente) e permissoes
  empresas/           empresas clientes e contatos
  processos/          processo de RJ, prazos, andamentos, credores, documentos
  crm/                leads, funil de prospeccao e atividades
  portal/             visao do cliente
templates/            telas (Tailwind + HTMX)
```

## Decisoes de projeto

- **Prazos legais sao gerados, nunca sobrescritos**: se o prazo ja existe, o
  sistema respeita o cadastro manual. O controle final e sempre humano.
- **Visibilidade explicita**: andamentos e documentos so aparecem no portal se
  marcados como visiveis ao cliente.
- **Origem de cada andamento fica registrada** (`fonte`): lancamento manual ou
  importacao do tribunal. A deduplicacao usa um identificador estavel do
  movimento, entao sincronizar varias vezes e seguro.

## Proximos passos

Veja [ROADMAP.md](ROADMAP.md).

## Aviso

O sistema organiza informacoes e prazos, mas nao substitui a analise juridica.
Os prazos calculados seguem a contagem simples em dias corridos a partir das
datas informadas e devem ser conferidos pelo advogado responsavel.
