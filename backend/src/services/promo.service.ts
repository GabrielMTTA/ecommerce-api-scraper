import { ProductData } from '../models/scraper.types.js';
import https from 'https';
import http from 'http';
import path from 'path';
import fs from 'fs';

const IMAGES_DIR = path.resolve(process.cwd(), 'images');

function ensureImagesDir(): void {
  if (!fs.existsSync(IMAGES_DIR)) {
    fs.mkdirSync(IMAGES_DIR, { recursive: true });
  }
}

function formatPrice(value: number): string {
  return value.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

export function generatePromoText(product: ProductData): string {
  const lines: string[] = [];

  lines.push('🔥🔥🔥 *PROMOÇÃO* 🔥🔥🔥');
  lines.push('');

  // Titulo em destaque
  lines.push(`*${product.title}*`);
  lines.push('');

  // Precos
  if (product.original_price && product.original_price > product.price && product.price > 0) {
    const discount = Math.round((1 - product.price / product.original_price) * 100);
    lines.push(`❌ ~De ${formatPrice(product.original_price)}~`);
    lines.push(`✅ *Por ${formatPrice(product.price)}*`);
    lines.push(`💰 *${discount}% OFF* 💰`);
  } else if (product.price > 0) {
    lines.push(`💲 *${formatPrice(product.price)}* 💲`);
  }

  lines.push('');

  // Rating se houver
  if (product.rating) {
    const stars = '⭐'.repeat(Math.round(product.rating));
    lines.push(`${stars} ${product.rating}/5`);
  }

  // Disponibilidade
  if (!product.availability) {
    lines.push('⚠️ Produto indisponível ⚠️');
  }

  // Fonte
  lines.push(`🏪 ${product.source}`);
  lines.push('');

  // Link
  lines.push(`🔗 ${product.product_url}`);
  lines.push('');
  lines.push('🔥🔥🔥🔥🔥🔥🔥🔥🔥🔥');

  return lines.join('\n');
}

export async function downloadImage(imageUrl: string, productId: string): Promise<string> {
  ensureImagesDir();

  // Determinar extensao
  const urlPath = new URL(imageUrl).pathname;
  let ext = path.extname(urlPath).split('?')[0] || '.jpg';
  if (ext.length > 5) ext = '.jpg';

  const safeName = productId.replace(/[^a-zA-Z0-9_-]/g, '_');
  const filename = `${safeName}${ext}`;
  const filepath = path.join(IMAGES_DIR, filename);

  return new Promise((resolve, reject) => {
    const client = imageUrl.startsWith('https') ? https : http;

    const request = client.get(imageUrl, { timeout: 15000 }, (response) => {
      // Follow redirects
      if (response.statusCode && response.statusCode >= 300 && response.statusCode < 400 && response.headers.location) {
        downloadImage(response.headers.location, productId).then(resolve).catch(reject);
        return;
      }

      if (response.statusCode !== 200) {
        reject(new Error(`HTTP ${response.statusCode} ao baixar imagem`));
        return;
      }

      const fileStream = fs.createWriteStream(filepath);
      response.pipe(fileStream);

      fileStream.on('finish', () => {
        fileStream.close();
        resolve(filepath);
      });

      fileStream.on('error', (err) => {
        fs.unlink(filepath, () => {});
        reject(err);
      });
    });

    request.on('error', reject);
    request.on('timeout', () => {
      request.destroy();
      reject(new Error('Timeout ao baixar imagem'));
    });
  });
}
