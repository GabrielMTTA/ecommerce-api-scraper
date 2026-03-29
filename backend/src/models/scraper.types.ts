export interface ProductData {
  title: string;
  price: number;
  original_price: number | null;
  currency: string;
  image_url: string;
  product_url: string;
  source: string;
  product_id: string;
  description: string | null;
  rating: number | null;
  availability: boolean;
  scrape_timestamp: string;
}

export interface ScraperResult {
  status: 'success' | 'failed' | 'retry' | 'invalid_url' | 'timeout' | 'blocked';
  data: ProductData | null;
  error: string | null;
  retry_after: number | null;
  timestamp: string;
  attempt: number;
}

export interface ScrapeJob {
  id: string;
  url: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  result: ScraperResult | null;
  createdAt: string;
  completedAt: string | null;
}
