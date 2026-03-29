"""
Runner script - bridge between Node.js child_process and Python scrapers.
Usage: python run_scraper.py <url>
Output: JSON ScraperResult to stdout
Logs: stderr (via logging)
"""
import sys
import json
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger('run_scraper')

SUPPORTED_SCRAPERS = {
    'mercadolivre.com.br': 'mercado_livre',
    'mercadolibre.com': 'mercado_livre',
    'meli.la': 'mercado_livre',
    'nike.com.br': 'nike',
    'nike.com': 'nike',
}


def detect_scraper(url: str) -> str | None:
    """Detect which scraper to use based on URL domain."""
    url_lower = url.lower()
    for domain, scraper_name in SUPPORTED_SCRAPERS.items():
        if domain in url_lower:
            return scraper_name
    return None


def run(url: str) -> dict:
    """Run the appropriate scraper and return result as dict."""
    scraper_name = detect_scraper(url)

    if not scraper_name:
        return {
            'status': 'invalid_url',
            'data': None,
            'error': f'URL nao suportada. Dominios suportados: {", ".join(SUPPORTED_SCRAPERS.keys())}',
            'retry_after': None,
            'timestamp': datetime.utcnow().isoformat(),
            'attempt': 1
        }

    if scraper_name == 'mercado_livre':
        from scrapers.mercado_livre import MercadoLivreScraper
        scraper = MercadoLivreScraper(timeout=30, retries=2)
    elif scraper_name == 'nike':
        from scrapers.nike import NikeScraper
        scraper = NikeScraper(timeout=45, retries=1)
    else:
        return {
            'status': 'failed',
            'data': None,
            'error': f'Scraper "{scraper_name}" nao implementado',
            'retry_after': None,
            'timestamp': datetime.utcnow().isoformat(),
            'attempt': 1
        }

    logger.info(f'Using {scraper_name} scraper for: {url}')
    result = scraper.scrape(url)
    return result.to_dict()


def main():
    if len(sys.argv) < 2:
        error_result = {
            'status': 'failed',
            'data': None,
            'error': 'URL nao fornecida. Uso: python run_scraper.py <url>',
            'retry_after': None,
            'timestamp': datetime.utcnow().isoformat(),
            'attempt': 1
        }
        print(json.dumps(error_result, ensure_ascii=False))
        sys.exit(1)

    url = sys.argv[1]
    logger.info(f'Scraping URL: {url}')

    try:
        result = run(url)
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0)
    except Exception as e:
        logger.error(f'Erro inesperado: {e}', exc_info=True)
        error_result = {
            'status': 'failed',
            'data': None,
            'error': str(e),
            'retry_after': None,
            'timestamp': datetime.utcnow().isoformat(),
            'attempt': 1
        }
        print(json.dumps(error_result, ensure_ascii=False))
        sys.exit(1)


if __name__ == '__main__':
    main()
