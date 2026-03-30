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


class AdidasScraper(BaseScraper):
    """Scraper para Adidas Brasil - usa Selenium + LD+JSON structured data"""

    VALID_DOMAINS = [
        "adidas.com.br",
        "adidas.com",
    ]

    def __init__(self, timeout: int = 30, retries: int = 3):
        super().__init__(timeout=timeout, retries=retries)
        self._driver = None

    def _get_driver(self):
        """Inicializar undetected-chromedriver para bypass de bot protection"""
        if self._driver is None:
            from chrome_utils import create_driver
            self._driver = create_driver()
            self._driver.set_page_load_timeout(self.timeout + 15)
        return self._driver

    def validate_url(self, url: str) -> bool:
        url_lower = url.lower()
        return any(domain in url_lower for domain in self.VALID_DOMAINS)

    def extract_product_code(self, url: str) -> Optional[str]:
        """Extrair codigo do produto (SKU) da URL - ex: /JR9936.html"""
        match = re.search(r'/([A-Z0-9]{6,10})\.html', url)
        return match.group(1) if match else None

    def fetch_page_selenium(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch pagina usando Selenium para bypass anti-bot"""
        try:
            driver = self._get_driver()
            self.logger.info(f"Carregando pagina via Selenium: {url}")
            driver.get(url)

            time.sleep(5)

            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'h1, [class*="price"], script[type="application/ld+json"]'))
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
            cleaned = re.sub(r'[R$\s\xa0Preço com desconto]', '', text)
            cleaned = cleaned.replace('.', '').replace(',', '.')
            cleaned = re.split(r'[a-zA-Z%]', cleaned)[0].strip()
            if cleaned:
                return float(cleaned)
        except (ValueError, IndexError):
            pass
        return None

    def extract_price(self, soup: BeautifulSoup) -> Optional[float]:
        """Extrair preco do produto"""
        try:
            # Seletor 1: mainPrice styled-component
            main_price = soup.find('div', class_=re.compile(r'_mainPrice_'))
            if main_price:
                span = main_price.find('span')
                if span:
                    price = self._parse_price_text(span.get_text(strip=True))
                    if price:
                        return price

            # Seletor 2: sale-color (preco com desconto)
            sale = soup.find('span', class_=re.compile(r'_sale-color_'))
            if sale:
                price = self._parse_price_text(sale.get_text(strip=True))
                if price:
                    return price

            # Seletor 3: priceComponent
            price_comp = soup.find('div', class_=re.compile(r'_priceComponent_'))
            if price_comp:
                text = price_comp.get_text(strip=True)
                match = re.search(r'R\$\s*([\d.,]+)', text)
                if match:
                    return self._parse_price_text('R$ ' + match.group(1))

        except Exception as e:
            logger.error(f"Erro ao extrair preco: {e}")
        return None

    def extract_original_price(self, soup: BeautifulSoup) -> Optional[float]:
        """Extrair preco original (antes desconto)"""
        try:
            original = soup.find('div', class_=re.compile(r'_originalPrice_'))
            if original:
                span = original.find('span')
                if span:
                    text = span.get_text(strip=True)
                    match = re.search(r'R\$\s*([\d.,]+)', text)
                    if match:
                        return self._parse_price_text('R$ ' + match.group(1))

            # priceHistory
            history = soup.find('div', class_=re.compile(r'_priceHistory_'))
            if history:
                text = history.get_text(strip=True)
                match = re.search(r'R\$\s*([\d.,]+)', text)
                if match:
                    return self._parse_price_text('R$ ' + match.group(1))

        except Exception:
            pass
        return None

    def extract_discount(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrair porcentagem de desconto"""
        try:
            disc = soup.find(string=re.compile(r'-\d+%'))
            if disc:
                match = re.search(r'-?\d+%', disc.strip())
                if match:
                    return match.group(0) + ' OFF'
        except Exception:
            pass
        return None

    def extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrair titulo do produto"""
        try:
            h1 = soup.find('h1')
            if h1:
                return h1.get_text(strip=True)

            og = soup.find('meta', property='og:title')
            if og and og.get('content'):
                text = og['content'].strip()
                return re.sub(r'\s*[-|].*adidas.*$', '', text, flags=re.I).strip()

        except Exception as e:
            logger.error(f"Erro ao extrair titulo: {e}")
        return None

    def extract_image(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrair URL da imagem principal"""
        try:
            og = soup.find('meta', property='og:image')
            if og and og.get('content'):
                return og['content']

            img = soup.find('img', src=re.compile(r'assets\.adidas\.com'))
            if img:
                return img.get('src')

        except Exception as e:
            logger.error(f"Erro ao extrair imagem: {e}")
        return None

    def extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrair descricao do produto"""
        try:
            og_desc = soup.find('meta', property='og:description')
            if og_desc and og_desc.get('content'):
                return og_desc['content'][:500]

            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                return meta_desc['content'][:500]

        except Exception:
            pass
        return None

    def extract_product_data(self, soup: BeautifulSoup, url: str) -> Optional[ProductData]:
        """Extrair dados do produto - prioriza LD+JSON, fallback para HTML"""

        ld_data = self._extract_ld_json(soup)
        product_code = self.extract_product_code(url)

        if ld_data:
            # Extrair do LD+JSON (dados estruturados e confiaveis)
            title = ld_data.get('name', '').strip()
            sku = ld_data.get('sku', product_code)

            offers = ld_data.get('offers', {})
            price = offers.get('price')
            if isinstance(price, str):
                try:
                    price = float(price)
                except ValueError:
                    price = None
            currency = offers.get('priceCurrency', 'BRL')
            availability = 'InStock' in offers.get('availability', '')

            images = ld_data.get('image', [])
            image_url = images[0] if images else None

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

            # Preco original e desconto do HTML (LD+JSON so tem preco atual)
            original_price = self.extract_original_price(soup)
            discount = self.extract_discount(soup)

            if not title:
                title = self.extract_title(soup)

            if not image_url:
                image_url = self.extract_image(soup)

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
                source="Adidas",
                product_id=f"ADIDAS-{sku}" if sku else f"ADIDAS-{abs(hash(url)) % (10 ** 10)}",
                description=description,
                rating=rating,
                availability=availability,
            )

        # Fallback: extrair tudo do HTML
        title = self.extract_title(soup)
        price = self.extract_price(soup)
        image_url = self.extract_image(soup)
        original_price = self.extract_original_price(soup)
        discount = self.extract_discount(soup)
        description = self.extract_description(soup)

        if not title:
            logger.warning(f"Titulo nao encontrado para {url}")
            return None

        if not image_url:
            logger.warning(f"Imagem nao encontrada para {url}")
            return None

        if discount and description:
            description = f"{discount} | {description}"
        elif discount:
            description = discount

        return ProductData(
            title=title,
            price=price if price else 0.0,
            original_price=original_price,
            currency="BRL",
            image_url=image_url,
            product_url=url,
            source="Adidas",
            product_id=f"ADIDAS-{product_code}" if product_code else f"ADIDAS-{abs(hash(url)) % (10 ** 10)}",
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
    scraper = AdidasScraper()
    print("AdidasScraper carregado com sucesso")
