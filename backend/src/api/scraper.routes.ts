import { Router, Request, Response } from 'express';
import Joi from 'joi';
import path from 'path';
import { scraperService } from '../services/scraper.service.js';
import { store } from '../services/store.service.js';
import { generatePromoText, downloadImage } from '../services/promo.service.js';

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

    // Gerar texto promo e baixar imagem se sucesso
    let promo_text: string | null = null;
    let image_path: string | null = null;
    let image_download_url: string | null = null;

    if (result.status === 'success' && result.data) {
      promo_text = generatePromoText(result.data);

      try {
        image_path = await downloadImage(result.data.image_url, result.data.product_id);
        const filename = path.basename(image_path);
        image_download_url = `/api/images/${filename}`;
      } catch (imgErr) {
        // Imagem falhou mas scraping funcionou - nao e erro critico
      }
    }

    res.json({
      job_id: job.id,
      ...result,
      promo_text,
      image_download_url,
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

// GET /api/images/:filename - Serve product image for download
router.get('/images/:filename', (req: Request, res: Response) => {
  const imagesDir = path.resolve(process.cwd(), 'images');
  const filename = path.basename(req.params.filename); // prevent path traversal
  const filepath = path.join(imagesDir, filename);

  res.download(filepath, filename, (err) => {
    if (err) {
      res.status(404).json({ error: 'Imagem nao encontrada' });
    }
  });
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
