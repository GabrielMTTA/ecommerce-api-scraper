import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_scraper import BaseScraper, ProductData, ScraperResult, ScraperStatus
from bs4 import BeautifulSoup
from typing import Optional
import re
import json
import logging
import time

logger = logging.getLogger(__name__)


class CentauroScraper(BaseScraper):
    """Scraper para Centauro - usa Selenium + LD+JSON structured data"""

    VALID_DOMAINS = [
        "centauro.com.br",
    ]

    def __init__(self, timeout: int = 30, retries: int = 3):
        super().__init__(timeout=timeout, retries=retries)
        self._driver = None

    def _get_driver(self):
        """Inicializar undetected-chromedriver para bypass Akamai WAF"""
        if self._driver is None:
            import undetected_chromedriver as uc

            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--window-position=-32000,-32000')
            options.add_argument('--lang=pt-BR')

            self._driver = uc.Chrome(
                options=options,
                headless=False,
                use_subprocess=True,
                version_main=146,
            )
            self._driver.minimize_window()
            self._driver.set_page_load_timeout(self.timeout + 15)

        return self._driver

    def validate_url(self, url: str) -> bool:
        url_lower = url.lower()
        return any(domain in url_lower for domain in self.VALID_DOMAINS)

    def extract_product_code(self, url: str) -> Optional[str]:
        """Extrair codigo do produto da URL - ex: 997490"""
        match = re.search(r'-(\d{5,7})\.html', url)
        return match.group(1) if match else None

    def fetch_page_selenium(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch pagina usando Selenium para bypass anti-bot"""
        try:
            driver = self._get_driver()
            self.logger.info(f"Carregando pagina via Selenium: {url}")
            driver.get(url)

            time.sleep(6)

            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'h1, [class*="Price"], script[type="application/ld+json"]'))
                )
            except Exception:
                self.logger.warning("Timeout aguardando elemento de produto")

            html = driver.page_source
            self.logger.info(f"Pagina carregada via Selenium ({len(html)} bytes)")
            return BeautifulSoup(html, 'html.parser')

        except Exception as e:
            self.logger.error(f"Erro no Selenium: {e}")
            return None

    def _extract_ld_json(self, soup: BeautifulSoup) -> Optional[dict]:
        """Extrair dados estruturados LD+JSON do tipo Product"""
        try:
            scripts = soup.find_all('script', type='application/ld+json')
            for s in scripts:
                text = s.string or ''
                if '"Product"' in text:
                    data = json.loads(text)
                    if data.get('@type') == 'Product':
                        return data
        except Exception as e:
            logger.error(f"Erro ao parsear LD+JSON: {e}")
        return None

    def _parse_price_text(self, text: str) -> Optional[float]:
        """Parsear texto de preco brasileiro para float"""
        try:
            cleaned = re.sub(r'[R$\s\xa0]', '', text)
            cleaned = cleaned.replace('.', '').replace(',', '.')
            cleaned = re.split(r'[a-zA-Z]', cleaned)[0].strip()
            if cleaned:
                return float(cleaned)
        except (ValueError, IndexError):
            pass
        return None

    def extract_price_html(self, soup: BeautifulSoup) -> Optional[float]:
        """Extrair preco do HTML como fallback"""
        try:
            # CurrentPrice styled-component
            current = soup.find('p', class_=re.compile(r'CurrentPrice'))
            if current:
                price = self._parse_price_text(current.get_text(strip=True))
                if price:
                    return price

            # Price Container
            container = soup.find('section', class_=re.compile(r'Price.*Container'))
            if container:
                text = container.get_text(strip=True)
                match = re.search(r'R\$\s*([\d.,]+)', text)
                if match:
                    return self._parse_price_text('R$ ' + match.group(1))

        except Exception as e:
            logger.error(f"Erro ao extrair preco HTML: {e}")
        return None

    def extract_original_price(self, soup: BeautifulSoup) -> Optional[float]:
        """Extrair preco original (antes desconto)"""
        try:
            old = soup.find('p', class_=re.compile(r'OldPrice|OriginalPrice'))
            if old:
                price = self._parse_price_text(old.get_text(strip=True))
                if price:
                    return price
        except Exception:
            pass
        return None

    def extract_discount(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrair desconto"""
        try:
            disc = soup.find(class_=re.compile(r'Discount|Badge'))
            if disc:
                text = disc.get_text(strip=True)
                if '%' in text:
                    return text
        except Exception:
            pass
        return None

    def extract_product_data(self, soup: BeautifulSoup, url: str) -> Optional[ProductData]:
        """Extrair dados do produto - prioriza LD+JSON"""
        ld_data = self._extract_ld_json(soup)
        product_code = self.extract_product_code(url)

        if ld_data:
            title = ld_data.get('name', '').strip()
            sku = ld_data.get('sku', product_code)

            offers = ld_data.get('offers', {})
            # AggregateOffer usa lowPrice
            price = offers.get('lowPrice') or offers.get('price')
            if isinstance(price, str):
                try:
                    price = float(price)
                except ValueError:
                    price = None
            currency = offers.get('priceCurrency', 'BRL')

            availability_raw = offers.get('availability', '')
            if not availability_raw:
                availability_raw = str(offers.get('offerCount', 1))
            availability = 'InStock' in availability_raw or availability_raw not in ('0', '')

            images = ld_data.get('image', [])
            if isinstance(images, list):
                image_url = images[0] if images else None
            else:
                image_url = images

            description = ld_data.get('description', '')
            if description and len(description) > 500:
                description = description[:500]

            rating_data = ld_data.get('aggregateRating')
            rating = None
            if rating_data:
                try:
                    rating = float(rating_data.get('ratingValue', 0))
                except (ValueError, TypeError):
                    pass

            # Dados extras do HTML
            original_price = self.extract_original_price(soup)
            discount = self.extract_discount(soup)

            if not title:
                h1 = soup.find('h1')
                title = h1.get_text(strip=True) if h1 else None

            if not image_url:
                og = soup.find('meta', property='og:image')
                image_url = og['content'] if og else None

            if not title or not image_url:
                logger.warning(f"Dados essenciais nao encontrados para {url}")
                return None

            if discount and description:
                description = f"{discount} | {description}"
            elif discount:
                description = discount

            return ProductData(
                title=title,
                price=price if price else 0.0,
                original_price=original_price,
                currency=currency,
                image_url=image_url,
                product_url=url,
                source="Centauro",
                product_id=f"CTR-{sku}" if sku else f"CTR-{abs(hash(url)) % (10 ** 10)}",
                description=description,
                rating=rating,
                availability=availability,
            )

        # Fallback: HTML puro
        h1 = soup.find('h1')
        title = h1.get_text(strip=True) if h1 else None
        price = self.extract_price_html(soup)
        og = soup.find('meta', property='og:image')
        image_url = og['content'] if og else None
        original_price = self.extract_original_price(soup)
        discount = self.extract_discount(soup)

        og_desc = soup.find('meta', property='og:description')
        description = og_desc['content'][:500] if og_desc and og_desc.get('content') else None

        if not title or not image_url:
            logger.warning(f"Dados essenciais nao encontrados para {url}")
            return None

        if discount and description:
            description = f"{discount} | {description}"

        return ProductData(
            title=title,
            price=price if price else 0.0,
            original_price=original_price,
            currency="BRL",
            image_url=image_url,
            product_url=url,
            source="Centauro",
            product_id=f"CTR-{product_code}" if product_code else f"CTR-{abs(hash(url)) % (10 ** 10)}",
            description=description,
            rating=None,
        )

    def scrape(self, url: str) -> ScraperResult:
        """Scraping usando Selenium para bypass anti-bot"""
        if not self.validate_url(url):
            return ScraperResult(
                status=ScraperStatus.INVALID_URL,
                error=f"URL invalida para {self.__class__.__name__}"
            )

        soup = self.fetch_page_selenium(url)
        if not soup:
            return ScraperResult(
                status=ScraperStatus.FAILED,
                error="Nao foi possivel carregar a pagina",
                retry_after=300
            )

        try:
            product_data = self.extract_product_data(soup, url)
            if not product_data:
                return ScraperResult(
                    status=ScraperStatus.FAILED,
                    error="Nao foi possivel extrair dados do produto"
                )

            return ScraperResult(
                status=ScraperStatus.SUCCESS,
                data=product_data
            )
        except Exception as e:
            self.logger.error(f"Erro ao extrair dados: {e}", exc_info=True)
            return ScraperResult(
                status=ScraperStatus.FAILED,
                error=str(e)
            )

    def __del__(self):
        """Cleanup Selenium driver"""
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
        super().__del__()


if __name__ == "__main__":
    scraper = CentauroScraper()
    print("CentauroScraper carregado com sucesso")
