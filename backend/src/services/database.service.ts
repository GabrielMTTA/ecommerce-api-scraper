import { Pool, PoolConfig } from 'pg';
import pino from 'pino';

const logger = pino();

export class DatabaseService {
  private pool: Pool;

  constructor() {
    const isProduction = process.env.NODE_ENV === 'production';

    const config: PoolConfig = {
      host: process.env.DB_HOST || 'localhost',
      port: parseInt(process.env.DB_PORT || '5432'),
      database: process.env.DB_NAME,
      user: process.env.DB_USER,
      password: process.env.DB_PASSWORD,
      max: isProduction ? 20 : 10,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 2000,
      ...(isProduction ? {
        ssl: {
          rejectUnauthorized: true,
          ca: process.env.DB_SSL_CA
        }
      } : {})
    };

    this.pool = new Pool(config);

    this.pool.on('error', (err: Error) => {
      logger.error('Erro inesperado no pool de conexões:', err);
    });
  }

  async connect(): Promise<boolean> {
    try {
      const client = await this.pool.connect();
      await client.query('SELECT NOW()');
      client.release();
      logger.info('Conexão com banco de dados estabelecida');
      return true;
    } catch (err) {
      logger.error('Falha ao conectar ao banco de dados:', err);
      return false;
    }
  }

  async query(text: string, values?: unknown[]): Promise<unknown> {
    const start = Date.now();
    try {
      const result = await this.pool.query(text, values);
      const duration = Date.now() - start;

      if (duration > 1000) {
        logger.warn(`Consulta lenta (${duration}ms): ${text.substring(0, 50)}...`);
      }

      return result;
    } catch (err) {
      logger.error('Erro na query:', { err, text });
      throw err;
    }
  }

  async disconnect(): Promise<void> {
    await this.pool.end();
    logger.info('Pool de conexões fechado');
  }

  getPool(): Pool {
    return this.pool;
  }
}

export const db = new DatabaseService();
