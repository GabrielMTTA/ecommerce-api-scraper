import { execFile } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';
import pino from 'pino';
import { ScraperResult } from '../models/scraper.types.js';

const logger = pino();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const SUPPORTED_DOMAINS = [
  'mercadolivre.com.br',
  'mercadolibre.com',
  'meli.la',
  'nike.com.br',
  'nike.com',
  'amazon.com.br',
  'amazon.com',
  'adidas.com.br',
  'adidas.com',
  'centauro.com.br',
  'netshoes.com.br',
];

export class ScraperService {
  private _pythonPath?: string;
  private _scrapersDir?: string;
  private _runnerScript?: string;
  private activeProcesses = 0;
  private maxConcurrent = 3;

  private get scrapersDir(): string {
    if (!this._scrapersDir) {
      this._scrapersDir = process.env.SCRAPERS_DIR
        || path.resolve(__dirname, '../../../../scrapers');
    }
    return this._scrapersDir;
  }

  private get pythonPath(): string {
    if (!this._pythonPath) {
      this._pythonPath = process.env.PYTHON_PATH
        || path.join(this.scrapersDir, 'venv', process.platform === 'win32' ? 'Scripts' : 'bin', 'python');
    }
    return this._pythonPath;
  }

  private get runnerScript(): string {
    if (!this._runnerScript) {
      this._runnerScript = path.join(this.scrapersDir, 'run_scraper.py');
    }
    return this._runnerScript;
  }

  getSupportedDomains(): string[] {
    return SUPPORTED_DOMAINS;
  }

  runDiagnostic(): Promise<Record<string, unknown>> {
    return new Promise((resolve) => {
      execFile(
        this.pythonPath,
        ['-c', `
import sys, os, json
result = {}
result['python'] = sys.version
result['platform'] = sys.platform
result['display'] = os.environ.get('DISPLAY', 'not set')
result['chrome_bin'] = os.environ.get('CHROME_BIN', 'not set')

# Check Chrome
import shutil
chrome = shutil.which('google-chrome-stable') or shutil.which('google-chrome') or shutil.which('chromium-browser')
result['chrome_found'] = chrome

# Check Xvfb
xvfb = shutil.which('Xvfb')
result['xvfb_found'] = xvfb

# Check if display works
import subprocess
try:
    p = subprocess.run(['xdpyinfo', '-display', ':99'], capture_output=True, timeout=5)
    result['display_active'] = p.returncode == 0
except:
    result['display_active'] = 'xdpyinfo not available'

# Try Chrome
try:
    import undetected_chromedriver as uc
    result['uc_version'] = uc.__version__ if hasattr(uc, '__version__') else 'unknown'
except ImportError as e:
    result['uc_error'] = str(e)

print(json.dumps(result))
`],
        {
          cwd: this.scrapersDir,
          timeout: 30000,
          env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
        },
        (error, stdout, stderr) => {
          if (error) {
            resolve({ error: error.message, stderr: stderr?.substring(0, 500) });
            return;
          }
          try {
            resolve(JSON.parse(stdout.trim()));
          } catch {
            resolve({ stdout, stderr: stderr?.substring(0, 500) });
          }
        }
      );
    });
  }

  runScraper(url: string): Promise<ScraperResult> {
    return new Promise((resolve, reject) => {
      if (this.activeProcesses >= this.maxConcurrent) {
        resolve({
          status: 'retry',
          data: null,
          error: `Limite de ${this.maxConcurrent} scrapers simultaneos atingido. Tente novamente.`,
          retry_after: 10,
          timestamp: new Date().toISOString(),
          attempt: 1,
        });
        return;
      }

      this.activeProcesses++;
      logger.info({ url, active: this.activeProcesses }, 'Spawning scraper process');

      const child = execFile(
        this.pythonPath,
        [this.runnerScript, url],
        {
          cwd: this.scrapersDir,
          timeout: 180000,
          maxBuffer: 5 * 1024 * 1024,
          env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
        },
        (error, stdout, stderr) => {
          this.activeProcesses--;

          if (stderr) {
            logger.info({ stderr: stderr.substring(0, 500) }, 'Scraper stderr output');
          }

          if (error && !stdout) {
            logger.error({ error: error.message }, 'Scraper process failed');
            resolve({
              status: 'failed',
              data: null,
              error: error.message,
              retry_after: null,
              timestamp: new Date().toISOString(),
              attempt: 1,
            });
            return;
          }

          try {
            const result: ScraperResult = JSON.parse(stdout.trim());
            logger.info({ status: result.status, product_id: result.data?.product_id }, 'Scraper completed');
            resolve(result);
          } catch (parseError) {
            logger.error({ stdout: stdout.substring(0, 200) }, 'Failed to parse scraper output');
            resolve({
              status: 'failed',
              data: null,
              error: `Erro ao parsear resultado do scraper: ${stdout.substring(0, 100)}`,
              retry_after: null,
              timestamp: new Date().toISOString(),
              attempt: 1,
            });
          }
        }
      );

      child.on('error', (err) => {
        this.activeProcesses--;
        logger.error({ error: err.message }, 'Failed to spawn scraper');
        reject(err);
      });
    });
  }
}

export const scraperService = new ScraperService();
