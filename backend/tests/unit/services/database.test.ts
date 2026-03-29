import { DatabaseService } from '../../../src/services/database.service.js';

// Mock pg module
jest.mock('pg', () => {
  const mockClient = {
    query: jest.fn().mockResolvedValue({ rows: [{ now: new Date() }] }),
    release: jest.fn(),
  };
  const mockPool = {
    connect: jest.fn().mockResolvedValue(mockClient),
    query: jest.fn().mockResolvedValue({ rows: [{ id: 1 }] }),
    end: jest.fn().mockResolvedValue(undefined),
    on: jest.fn(),
  };
  return {
    Pool: jest.fn(() => mockPool),
  };
});

// Mock pino
jest.mock('pino', () => {
  return jest.fn(() => ({
    info: jest.fn(),
    error: jest.fn(),
    warn: jest.fn(),
    debug: jest.fn(),
  }));
});

describe('DatabaseService', () => {
  let dbService: DatabaseService;

  beforeEach(() => {
    jest.clearAllMocks();
    process.env.NODE_ENV = 'test';
    dbService = new DatabaseService();
  });

  describe('constructor', () => {
    it('should initialize successfully', () => {
      expect(dbService).toBeDefined();
    });

    it('should create pool with production SSL config', () => {
      process.env.NODE_ENV = 'production';
      const prodService = new DatabaseService();
      expect(prodService).toBeDefined();
    });
  });

  describe('connect', () => {
    it('should return true on successful connection', async () => {
      const result = await dbService.connect();
      expect(result).toBe(true);
    });
  });

  describe('query', () => {
    it('should execute query successfully', async () => {
      const result = await dbService.query('SELECT * FROM users WHERE id = $1', [1]);
      expect(result).toEqual({ rows: [{ id: 1 }] });
    });
  });

  describe('disconnect', () => {
    it('should close pool connection', async () => {
      await dbService.disconnect();
      const pool = dbService.getPool();
      expect(pool.end).toHaveBeenCalled();
    });
  });

  describe('getPool', () => {
    it('should return the pool instance', () => {
      const pool = dbService.getPool();
      expect(pool).toBeDefined();
    });
  });
});
