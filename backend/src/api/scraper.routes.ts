import { Router, Request, Response } from 'express';
import Joi from 'joi';
import { scraperService } from '../services/scraper.service.js';
import { store } from '../services/store.service.js';

const router = Router();

const scrapeSchema = Joi.object({
  url: Joi.string().uri().required().messages({
    'string.uri': 'URL invalida',
    'any.required': 'URL e obrigatoria',
  }),
});

// POST /api/scrape - Run scraper on a URL
router.post('/scrape', async (req: Request, res: Response) => {
  const { error, value } = scrapeSchema.validate(req.body);
  if (error) {
    res.status(400).json({
      error: error.details[0].message,
      supported_domains: scraperService.getSupportedDomains(),
    });
    return;
  }

  const { url } = value;
  const job = store.createJob(url);
  store.updateJob(job.id, { status: 'running' });

  try {
    const result = await scraperService.runScraper(url);

    if (result.status === 'success' && result.data) {
      store.addProduct(result.data);
    }

    store.updateJob(job.id, {
      status: result.status === 'success' ? 'completed' : 'failed',
      result,
      completedAt: new Date().toISOString(),
    });

    res.json({
      job_id: job.id,
      ...result,
    });
  } catch (err) {
    store.updateJob(job.id, {
      status: 'failed',
      completedAt: new Date().toISOString(),
    });

    res.status(500).json({
      job_id: job.id,
      error: 'Erro interno ao executar scraper',
    });
  }
});

// GET /api/products - List all scraped products
router.get('/products', (_req: Request, res: Response) => {
  const source = _req.query.source as string | undefined;
  const products = store.getProducts(source);

  res.json({
    products,
    count: products.length,
  });
});

// GET /api/products/:productId - Get single product
router.get('/products/:productId', (req: Request, res: Response) => {
  const product = store.getProductById(req.params.productId);

  if (!product) {
    res.status(404).json({ error: 'Produto nao encontrado' });
    return;
  }

  res.json(product);
});

// GET /api/scrape/supported - List supported domains
router.get('/scrape/supported', (_req: Request, res: Response) => {
  res.json({
    domains: scraperService.getSupportedDomains(),
  });
});

// GET /api/jobs - List all scrape jobs
router.get('/jobs', (_req: Request, res: Response) => {
  res.json({
    jobs: store.getJobs(),
    count: store.getJobs().length,
  });
});

export default router;
