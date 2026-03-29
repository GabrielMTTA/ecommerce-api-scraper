import { ProductData, ScrapeJob, ScraperResult } from '../models/scraper.types.js';
import { v4 as uuidv4 } from 'uuid';

export class StoreService {
  private products: Map<string, ProductData> = new Map();
  private jobs: Map<string, ScrapeJob> = new Map();

  addProduct(product: ProductData): void {
    this.products.set(product.product_id, product);
  }

  getProducts(source?: string): ProductData[] {
    const all = Array.from(this.products.values());
    if (source) {
      return all.filter(p => p.source.toLowerCase() === source.toLowerCase());
    }
    return all;
  }

  getProductById(productId: string): ProductData | undefined {
    return this.products.get(productId);
  }

  createJob(url: string): ScrapeJob {
    const job: ScrapeJob = {
      id: uuidv4(),
      url,
      status: 'pending',
      result: null,
      createdAt: new Date().toISOString(),
      completedAt: null,
    };
    this.jobs.set(job.id, job);
    return job;
  }

  updateJob(id: string, updates: { status?: ScrapeJob['status']; result?: ScraperResult; completedAt?: string }): void {
    const job = this.jobs.get(id);
    if (job) {
      Object.assign(job, updates);
    }
  }

  getJob(id: string): ScrapeJob | undefined {
    return this.jobs.get(id);
  }

  getJobs(): ScrapeJob[] {
    return Array.from(this.jobs.values());
  }
}

export const store = new StoreService();
