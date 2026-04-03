# IA Juridica

Sistema de Inteligencia Artificial para Advocacia Brasileira com RAG, integracao CNJ DataJud e geracao de peticoes via OpenAI.

## Funcionalidades

- **Pesquisa Juridica RAG** - Busca semantica em jurisprudencia, doutrina e legislacao com ChromaDB + SentenceTransformers
- **Consulta CNJ DataJud** - Consulta processual em tempo real nos tribunais brasileiros (STF, STJ, TRFs, TJs)
- **Geracao de Peticoes com IA** - Criacao automatizada de pecas processuais (inicial, contestacao, recurso, HC, embargos, etc.)
- **Pesquisa Unificada** - Busca simultanea em STF, STJ, TST, LexML, Planalto e base local
- **Gestao de Processos** - Acompanhamento, movimentacoes e sincronizacao com CNJ
- **Gestao de Documentos** - Upload, conversao (PDF/DOCX), extracao de texto e analise com IA
- **Exportacao** - Peticoes em DOCX e PDF com formatacao juridica profissional
- **Painel Admin** - Gestao de usuarios, logs de auditoria, configuracoes e modelos LLM
- **Auditoria Completa** - Log imutavel de todas as operacoes (LGPD compliance)
- **MCP Server** - Ferramentas de execucao controlada para automacao juridica
- **WhatsApp** - Triagem automatica de clientes via Evolution API

## Arquitetura

| Componente | Tecnologia | Porta |
|---|---|---|
| Backend API | FastAPI (async) | 8000 |
| Frontend Web | Flask + Jinja2 + Bootstrap 5 | 5000 |
| Banco de Dados | PostgreSQL 15 / SQLite (dev) | 5432 |
| Vector Store | ChromaDB | - |
| LLM | OpenAI (GPT-4o-mini) | - |
| Embeddings | SentenceTransformers | - |

## Inicio Rapido (Desenvolvimento Local)

### Pre-requisitos

- Python 3.11+
- pip

### Instalacao

```bash
# Clonar e entrar no diretorio
cd ia-juridica

# Criar ambiente virtual
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Instalar dependencias
pip install -r requirements.txt

# Configurar variaveis de ambiente
# Edite app/.env e adicione sua OPENAI_API_KEY

# Iniciar aplicacao
python run.py
```

### Acesso

- **Frontend:** http://localhost:5000
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

### Credenciais Padrao

- Email: `advogado@iajuridica.com.br`
- Senha: `senha123`

## Deploy no Heroku

```bash
# Login
heroku login

# Criar app
heroku create ia-juridica

# Configurar variaveis
heroku config:set OPENAI_API_KEY=sk-...
heroku config:set SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
heroku config:set CNJ_API_KEY=sua-chave-cnj

# Adicionar PostgreSQL
heroku addons:create heroku-postgresql:essential-0

# Deploy
git push heroku main
```

## Docker

```bash
# Desenvolvimento completo com Docker
docker-compose up -d --build

# Acessar em http://localhost (via Nginx)
```

## Estrutura do Projeto

```
ia-juridica/
├── app/
│   ├── backend/app/          # FastAPI Backend
│   │   ├── api/              # Rotas da API (14 routers)
│   │   ├── core/             # Config, DB, Security, LLM
│   │   ├── models/           # SQLAlchemy Models
│   │   ├── schemas/          # Pydantic Schemas
│   │   └── services/         # Business Logic Services
│   ├── frontend/             # Flask Frontend
│   │   ├── templates/        # Jinja2 Templates
│   │   └── static/           # CSS, JS
│   └── data/                 # Uploads, Vector DB, Outputs
├── run.py                    # Launcher local
├── Procfile                  # Heroku
├── gunicorn_config.py        # Gunicorn config
├── requirements.txt          # Python dependencies
├── Dockerfile                # Container build
├── docker-compose.yml        # Full stack
└── README.md
```

## API Endpoints Principais

| Metodo | Endpoint | Descricao |
|---|---|---|
| POST | /api/auth/login | Autenticacao |
| POST | /api/rag/search | Pesquisa semantica RAG |
| POST | /api/rag/consulta-ia | Consulta juridica com IA |
| POST | /api/cnj/processo | Consulta CNJ DataJud |
| POST | /api/peticoes/gerar | Geracao de peticao com IA |
| POST | /api/peticoes/ | Criar peticao manual |
| GET | /api/peticoes/ | Listar peticoes |
| POST | /api/documentos/upload | Upload de documentos |
| GET | /api/admin/usuarios | Listar usuarios (admin) |
| GET | /api/audit/logs | Logs de auditoria |
| POST | /api/pesquisa/ | Pesquisa juridica unificada |
| GET | /health | Health check |

## Licenca

MIT License - veja [LICENSE](LICENSE)
