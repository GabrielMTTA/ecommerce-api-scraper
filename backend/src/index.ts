import express, { Express, Request, Response, NextFunction } from 'express';
import helmet from 'helmet';
import cors from 'cors';
import rateLimit from 'express-rate-limit';
import pino from 'pino';
import pinoHttp from 'pino-http';
import dotenv from 'dotenv';
import { v4 as uuidv4 } from 'uuid';
import scraperRouter from './api/scraper.routes.js';

// Carregar variáveis de ambiente
dotenv.config();

// Logger
const logger = pino({
  level: process.env.LOG_LEVEL || 'info',
  transport: {
    target: 'pino-pretty',
    options: {
      colorize: true,
      singleLine: true,
      translateTime: 'SYS:standard'
    }
  }
});

const app: Express = express();
const PORT = process.env.PORT || 3000;

// ====== MIDDLEWARE DE SEGURANÇA ======

// Helmet - headers de segurança HTTP
app.use(helmet());

// CORS - configuração restritiva
app.use(cors({
  origin: process.env.CORS_ORIGIN || 'http://localhost:3000',
  credentials: true,
  methods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
  allowedHeaders: ['Content-Type', 'Authorization']
}));

// Rate Limiting
const limiter = rateLimit({
  windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS || '900000'),
  max: parseInt(process.env.RATE_LIMIT_MAX_REQUESTS || '100'),
  message: 'Muitas requisições, tente novamente mais tarde',
  standardHeaders: true,
  legacyHeaders: false,
  skip: (req) => req.path === '/health'
});

app.use(limiter);

// Logger HTTP
app.use(pinoHttp({ logger }));

// Middleware para adicionar Request ID
app.use((req: Request, res: Response, next: NextFunction) => {
  const requestId = req.headers['x-request-id'] as string || uuidv4();
  res.setHeader('X-Request-ID', requestId);
  res.locals.requestId = requestId;
  next();
});

// Body parser com limite
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ limit: '10mb', extended: true }));

// ====== ROTAS ======

// Health check
app.get('/health', (_req: Request, res: Response) => {
  res.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    version: process.env.npm_package_version,
    environment: process.env.NODE_ENV
  });
});

// Status da aplicação
app.get('/status', (_req: Request, res: Response) => {
  res.json({
    status: 'running',
    uptime: process.uptime(),
    memory: process.memoryUsage(),
    pid: process.pid
  });
});

// ====== API ROUTES ======
app.use('/api', scraperRouter);

// ====== TRATAMENTO DE ERROS ======

// 404 Handler
app.use((req: Request, res: Response) => {
  res.status(404).json({
    error: 'Rota não encontrada',
    path: req.path,
    method: req.method,
    requestId: res.locals.requestId
  });
});

// Global Error Handler
app.use((err: Error & { status?: number }, req: Request, res: Response, _next: NextFunction) => {
  logger.error({
    err: err,
    requestId: res.locals.requestId,
    path: req.path,
    method: req.method
  });

  res.status(err.status || 500).json({
    error: err.message || 'Erro interno do servidor',
    requestId: res.locals.requestId,
    ...(process.env.NODE_ENV === 'development' && { stack: err.stack })
  });
});

// ====== STARTUP ======

if (process.env.NODE_ENV !== 'test') {
  const server = app.listen(PORT, () => {
    logger.info(`Servidor iniciado na porta ${PORT}`);
    logger.info(`Ambiente: ${process.env.NODE_ENV}`);
  });

  // Graceful shutdown
  process.on('SIGTERM', () => {
    logger.info('SIGTERM recebido, encerrando gracefully...');
    server.close(() => {
      logger.info('Servidor encerrado');
      process.exit(0);
    });
  });
}

export default app;
