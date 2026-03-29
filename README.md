# Ecommerce API Scraper

API robusta para scraping de e-commerce com geracao automatica de textos promocionais e imagens para redes sociais.

## Visao Geral

Sistema completo para monitoramento de produtos em plataformas de e-commerce. Coleta automatizada de dados (preco, titulo, imagem, disponibilidade, avaliacao), download de imagens e geracao de texto promocional pronto para WhatsApp/redes sociais.

### Arquitetura

```
                    +-------------------+
                    |   Express API     |
                    |   (Node.js/TS)    |
                    +--------+----------+
                             |
              +--------------+--------------+
              |              |              |
     +--------v-----+  +----v----+  +------v-------+
     | Promo Service |  |  Store  |  | Scraper Svc  |
     | (texto+img)   |  | (dados) |  | (child_proc) |
     +--------------+  +---------+  +------+-------+
                                           |
                                  +--------v--------+
                                  | Python Scrapers  |
                                  | (BS4 + Selenium) |
                                  +-----------------+
```

## Lojas Suportadas

| Loja | Metodo | Anti-Bot Bypass |
|------|--------|-----------------|
| Mercado Livre | requests + BeautifulSoup | Nao necessario |
| Amazon | requests + BeautifulSoup | Nao necessario |
| Nike | undetected-chromedriver | Akamai WAF |
| Adidas | undetected-chromedriver + LD+JSON | Akamai WAF |
| Centauro | undetected-chromedriver + LD+JSON | Akamai WAF |

> Os scrapers com Selenium rodam em modo oculto (off-screen) — o navegador nao aparece na tela.

## Tecnologias

| Camada | Tecnologia |
|--------|-----------|
| Backend API | Node.js, Express, TypeScript (strict mode) |
| Scrapers | Python 3.11, BeautifulSoup, Selenium, undetected-chromedriver |
| Anti-Bot | Chrome off-screen (bypass Akamai WAF sem headless) |
| Armazenamento | In-memory store (preparado para PostgreSQL) |
| Containerizacao | Docker, Docker Compose |
| CI/CD | GitHub Actions |

## Estrutura do Projeto

```
ecommerce-api-scraper/
├── backend/                    # API Node.js/TypeScript
│   ├── src/
│   │   ├── index.ts            # Servidor Express (Helmet, CORS, Rate Limit)
│   │   ├── api/
│   │   │   └── scraper.routes.ts    # Endpoints da API (scrape, products, jobs, images)
│   │   ├── models/
│   │   │   └── scraper.types.ts     # Interfaces TypeScript
│   │   └── services/
│   │       ├── scraper.service.ts   # Ponte Node.js <-> Python (child_process)
│   │       ├── store.service.ts     # Armazenamento in-memory
│   │       ├── promo.service.ts     # Gerador de texto promo + download de imagem
│   │       └── database.service.ts  # Pool de conexoes PostgreSQL
│   ├── images/                 # Imagens de produtos baixadas
│   ├── Dockerfile              # Multi-stage build, usuario nao-root
│   ├── package.json
│   └── tsconfig.json
├── scrapers/                   # Scrapers Python
│   ├── base_scraper.py         # Classe base abstrata com retry e rate limit
│   ├── run_scraper.py          # Runner CLI (ponte Node.js -> Python)
│   ├── scrapers/
│   │   ├── mercado_livre.py    # Scraper Mercado Livre (+ meli.la short URLs)
│   │   ├── amazon.py           # Scraper Amazon Brasil
│   │   ├── nike.py             # Scraper Nike (Selenium)
│   │   ├── adidas.py           # Scraper Adidas (Selenium + LD+JSON)
│   │   └── centauro.py         # Scraper Centauro (Selenium + LD+JSON)
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
└── .gitignore                  # Padroes de seguranca
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

### Endpoints

| Metodo | Rota | Descricao |
|--------|------|-----------|
| `POST` | `/api/scrape` | Scrape de produto por URL |
| `GET` | `/api/products` | Lista todos os produtos coletados |
| `GET` | `/api/products/:id` | Busca produto por ID |
| `GET` | `/api/jobs` | Lista jobs de scraping |
| `GET` | `/api/scrape/supported` | Dominios suportados |
| `GET` | `/api/images/:filename` | Download da imagem do produto |
| `GET` | `/health` | Health check |

### Scrape de Produto

```bash
curl -X POST http://localhost:3000/api/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.amazon.com.br/dp/B0B11JGD2P"}'
```

Resposta:
```json
{
  "job_id": "uuid",
  "status": "success",
  "data": {
    "title": "HyperX Alloy Origins Core - Mechanical Gaming Keyboard",
    "price": 412.84,
    "original_price": 599.00,
    "currency": "BRL",
    "image_url": "https://m.media-amazon.com/images/I/61fjJX9Jq2L.jpg",
    "source": "Amazon",
    "product_id": "B0B11JGD2P",
    "rating": 4.7,
    "availability": true
  },
  "promo_text": "🔥🔥🔥 *PROMOÇÃO* 🔥🔥🔥\n\n*HyperX Alloy Origins Core*\n\n❌ ~De R$ 599,00~\n✅ *Por R$ 412,84*\n💰 *31% OFF* 💰\n\n⭐⭐⭐⭐⭐ 4.7/5\n🏪 Amazon\n\n🔗 https://...\n\n🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥",
  "image_download_url": "/api/images/B0B11JGD2P.jpg"
}
```

### Texto Promocional (WhatsApp)

A API gera automaticamente um texto formatado para WhatsApp:

```
🔥🔥🔥 *PROMOÇÃO* 🔥🔥🔥

*HyperX Alloy Origins Core - Mechanical Gaming Keyboard*

❌ ~De R$ 599,00~
✅ *Por R$ 412,84*
💰 *31% OFF* 💰

⭐⭐⭐⭐⭐ 4.7/5
🏪 Amazon

🔗 https://www.amazon.com.br/dp/B0B11JGD2P

🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥
```

### Download da Imagem

```bash
curl -O http://localhost:3000/api/images/B0B11JGD2P.jpg
```

### Listar Produtos Coletados

```bash
curl http://localhost:3000/api/products

# Filtrar por loja
curl http://localhost:3000/api/products?source=Amazon
```

### Dominios Suportados

```bash
curl http://localhost:3000/api/scrape/supported
```

```json
{
  "domains": [
    "mercadolivre.com.br", "mercadolibre.com", "meli.la",
    "nike.com.br", "nike.com",
    "amazon.com.br", "amazon.com",
    "adidas.com.br", "adidas.com",
    "centauro.com.br"
  ]
}
```

## Como Funciona

1. Voce envia uma URL de produto via `POST /api/scrape`
2. A API detecta a loja automaticamente e spawna o scraper Python correto
3. O scraper coleta: titulo, preco, preco original, desconto, imagem, avaliacao, disponibilidade
4. A API gera o texto promocional formatado para WhatsApp (com emojis e markdown)
5. A imagem do produto e baixada e salva localmente
6. Tudo e retornado na resposta: dados brutos + texto promo + link para download da imagem

## Seguranca

- **Headers HTTP** seguros via Helmet (CSP, X-Frame-Options, HSTS, etc.)
- **Rate limiting** configuravel (100 req/15min por padrao)
- **CORS** restritivo com origem configuravel
- **Validacao de entrada** com Joi (URLs validadas antes do scraping)
- **Anti-injection** via `child_process.execFile` (sem shell injection)
- **Limite de concorrencia** maximo de 3 scrapers simultaneos
- **Timeout** de 90 segundos por scrape
- **Containers** executam como usuario nao-root
- **Multi-stage builds** para imagens Docker menores e seguras
- **Graceful shutdown** para encerramento limpo do servidor

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

## Proximos Passos

- [ ] Migrar armazenamento in-memory para PostgreSQL
- [ ] Adicionar cache Redis para evitar scrapes repetidos
- [ ] Integrar envio automatico para WhatsApp Business API
- [ ] Adicionar mais lojas (Netshoes, Magalu, Casas Bahia)
- [ ] Dashboard web para visualizar produtos coletados
- [ ] Agendamento automatico de scraping (cron jobs)

## Licenca

MIT
