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
- **Entrada manual dos andamentos** nesta fase. A estrutura ja tem o campo
  `fonte` preparado para a integracao com a API publica do CNJ/DataJud.

## Proximos passos

Veja [ROADMAP.md](ROADMAP.md).

## Aviso

O sistema organiza informacoes e prazos, mas nao substitui a analise juridica.
Os prazos calculados seguem a contagem simples em dias corridos a partir das
datas informadas e devem ser conferidos pelo advogado responsavel.
