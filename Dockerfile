# ====== STAGE 1: BUILD ======
FROM node:18-slim AS builder

WORKDIR /app/backend

COPY backend/package*.json ./
RUN npm ci

COPY backend/tsconfig.json ./
COPY backend/src ./src
RUN npm run build && npm prune --omit=dev

# ====== STAGE 2: RUNTIME ======
FROM node:18-slim

# Install Python, pip, and Chrome dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    wget \
    gnupg \
    unzip \
    curl \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    libu2f-udev \
    libvulkan1 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install Google Chrome
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy backend build
COPY --from=builder /app/backend/node_modules ./backend/node_modules
COPY --from=builder /app/backend/dist ./backend/dist
COPY --from=builder /app/backend/package*.json ./backend/

# Copy scrapers
COPY scrapers/ ./scrapers/

# Install Python dependencies
RUN python3 -m venv /app/scrapers/venv \
    && /app/scrapers/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /app/scrapers/venv/bin/pip install --no-cache-dir \
       requests==2.31.0 \
       beautifulsoup4==4.12.2 \
       lxml==4.9.3 \
       selenium==4.15.1 \
       undetected-chromedriver \
       python-dotenv==1.0.0 \
       urllib3==2.1.0

# Create images directory
RUN mkdir -p /app/backend/images

# Environment defaults
ENV NODE_ENV=production \
    PORT=3000 \
    SCRAPERS_DIR=/app/scrapers \
    PYTHON_PATH=/app/scrapers/venv/bin/python \
    PYTHONIOENCODING=utf-8 \
    CHROME_BIN=/usr/bin/google-chrome-stable \
    DISPLAY=:99

WORKDIR /app/backend

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD node -e "require('http').get('http://localhost:3000/health', (r) => {if (r.statusCode !== 200) throw new Error()})" || exit 1

COPY entrypoint.sh /app/entrypoint.sh
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
