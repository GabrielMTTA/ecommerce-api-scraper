# Ecommerce API Scraper

API robusta para scraping de e-commerce com posting automatico em redes sociais.

## Visao Geral

Sistema completo para monitoramento de produtos em plataformas de e-commerce, com coleta automatizada de dados (preco, titulo, imagem, disponibilidade) e publicacao automatica em redes sociais (WhatsApp, Instagram).

### Arquitetura

```
                    +-------------------+
                    |   Express API     |
                    |   (Node.js/TS)    |
                    +--------+----------+
                             |
                +------------+------------+
                |                         |
        +-------v-------+       +--------v--------+
        |  PostgreSQL    |       |     Redis       |
        |  (Produtos,    |       |  (Cache, Fila)  |
        |   Historico)   |       |                 |
        +----------------+       +--------+--------+
                                          |
                                 +--------v--------+
                                 | Scraper Workers  |
                                 |    (Python)      |
                                 +-----------------+
```

## Tecnologias

| Camada | Tecnologia |
|--------|-----------|
| Backend API | Node.js, Express, TypeScript (strict mode) |
| Scrapers | Python 3.11, BeautifulSoup, Selenium |
| Banco de Dados | PostgreSQL 15 |
| Cache/Fila | Redis 7 |
| Containerizacao | Docker, Docker Compose |
| CI/CD | GitHub Actions |
| Testes | Jest (Node.js), pytest (Python) |

## Estrutura do Projeto

```
ecommerce-api-scraper/
├── backend/                    # API Node.js/TypeScript
│   ├── src/
│   │   ├── index.ts            # Servidor Express (Helmet, CORS, Rate Limit)
│   │   └── services/
│   │       └── database.service.ts  # Pool de conexoes PostgreSQL
│   ├── tests/
│   │   ├── unit/               # Testes unitarios
│   │   └── e2e/                # Testes end-to-end
│   ├── Dockerfile              # Multi-stage build, usuario nao-root
│   ├── package.json
│   └── tsconfig.json
├── scrapers/                   # Scrapers Python
│   ├── base_scraper.py         # Classe base abstrata com retry e rate limit
│   ├── scrapers/
│   │   └── mercado_livre.py    # Scraper do Mercado Livre
│   ├── tests/
│   │   └── unit/               # Testes unitarios Python
│   ├── requirements.txt        # Dependencias com versoes fixas
│   └── Dockerfile              # Usuario nao-root
├── devops/
│   └── postgres/
│       └── init.sql            # Schema do banco (produtos, historico, posts)
├── .github/
│   └── workflows/
│       └── ci-cd.yml           # Pipeline CI/CD completo
├── docker-compose.yml          # Todos os servicos orquestrados
├── .env.example                # Template de variaveis de ambiente
├── .gitignore                  # Padroes de seguranca
└── DEPLOYMENT_CHECKLIST.md     # Checklist de deploy
```

## Pre-requisitos

- Node.js >= 18.0.0
- Python >= 3.10
- Docker e Docker Compose
- Git

## Instalacao

### 1. Clonar o repositorio

```bash
git clone https://github.com/GabrielMTTA/ecommerce-api-scraper.git
cd ecommerce-api-scraper
```

### 2. Configurar variaveis de ambiente

```bash
cp .env.example .env
# Editar .env com suas credenciais
```

### 3. Subir com Docker Compose (recomendado)

```bash
docker-compose up -d
```

Isso inicia todos os servicos:

| Servico | Porta |
|---------|-------|
| API Backend | `localhost:3000` |
| PostgreSQL | `localhost:5432` |
| Redis | `localhost:6379` |
| Scraper Workers | interno |

### 4. Instalacao manual (sem Docker)

**Backend:**

```bash
cd backend
npm install
npm run dev
```

**Scrapers:**

```bash
cd scrapers
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

## Uso da API

### Health Check

```bash
curl http://localhost:3000/health
```

Resposta:
```json
{
  "status": "healthy",
  "timestamp": "2026-03-29T12:00:00.000Z",
  "environment": "development"
}
```

### Status do Servidor

```bash
curl http://localhost:3000/status
```

Resposta:
```json
{
  "status": "running",
  "uptime": 3600,
  "memory": { "rss": 50000000, "heapUsed": 20000000 },
  "pid": 1234
}
```

## Testes

### Backend (Jest)

```bash
cd backend
npm test                # Todos os testes com cobertura
npm run test:unit       # Apenas unitarios
npm run test:e2e        # Apenas end-to-end
```

### Scrapers (pytest)

```bash
cd scrapers
source venv/bin/activate
python -m pytest tests/ -v --cov
```

### Resultados atuais

- **Jest:** 10/10 testes passando (6 unitarios + 4 E2E)
- **pytest:** 9/9 testes passando
- **TypeScript:** Compilacao limpa em modo strict

## Seguranca

O projeto segue boas praticas de seguranca DevSec:

- **Headers HTTP** seguros via Helmet (CSP, X-Frame-Options, HSTS, etc.)
- **Rate limiting** configuravel (100 req/15min por padrao)
- **CORS** restritivo com origem configuravel
- **Validacao** de variaveis de ambiente na inicializacao
- **SSL/TLS** para conexao com banco em producao
- **Containers** executam como usuario nao-root
- **Multi-stage builds** para imagens Docker menores e seguras
- **Dependencias** com versoes fixas e auditoria automatica
- **Graceful shutdown** para encerramento limpo do servidor

## Banco de Dados

O schema inclui as seguintes tabelas:

| Tabela | Descricao |
|--------|-----------|
| `products` | Produtos coletados (titulo, preco, imagem, fonte) |
| `price_history` | Historico de precos para rastreamento |
| `social_posts` | Posts publicados em redes sociais |
| `scrape_jobs` | Fila de jobs de scraping |

O schema e aplicado automaticamente via `devops/postgres/init.sql` ao iniciar o container.

## CI/CD

O pipeline do GitHub Actions executa automaticamente em push/PR para `main` e `develop`:

1. Verificacao de tipos TypeScript
2. Linting do backend
3. Testes do backend (Jest)
4. Testes dos scrapers (pytest)
5. Auditoria de seguranca (npm audit, bandit)
6. Build das imagens Docker
7. Push para GitHub Container Registry (apenas `main`)

## Scripts Disponiveis

### Backend

| Comando | Descricao |
|---------|-----------|
| `npm run dev` | Inicia servidor em modo desenvolvimento |
| `npm run build` | Compila TypeScript para JavaScript |
| `npm start` | Inicia servidor compilado |
| `npm test` | Executa todos os testes com cobertura |
| `npm run type-check` | Verifica tipos sem compilar |
| `npm run lint` | Analise estatica do codigo |

## Licenca

MIT
