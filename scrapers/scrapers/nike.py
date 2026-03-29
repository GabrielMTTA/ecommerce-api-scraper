import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_scraper import BaseScraper, ProductData, ScraperResult, ScraperStatus
from bs4 import BeautifulSoup
from typing import Optional
import re
import logging
import time

logger = logging.getLogger(__name__)


class NikeScraper(BaseScraper):
    """Scraper para Nike.com.br - usa Selenium (site e SPA client-side rendered)"""

    VALID_DOMAINS = [
        "nike.com.br",
        "nike.com",
    ]

    def __init__(self, timeout: int = 30, retries: int = 3):
        super().__init__(timeout=timeout, retries=retries)
        self._driver = None

    def _get_driver(self):
        """Inicializar undetected-chromedriver para bypass de bot protection"""
        if self._driver is None:
            import undetected_chromedriver as uc

            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--window-position=-32000,-32000')

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
        """Validar se URL e da Nike"""
        url_lower = url.lower()
        return any(domain in url_lower for domain in self.VALID_DOMAINS)

    def extract_product_code(self, url: str) -> Optional[str]:
        """Extrair codigo do produto da URL"""
        match = re.search(r'(\d{6})\.html', url)
        return match.group(1) if match else None

    def fetch_page_selenium(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch pagina usando Selenium para sites SPA"""
        try:
            driver = self._get_driver()
            self.logger.info(f"Carregando pagina via Selenium: {url}")
            driver.get(url)

            # Aguardar pagina carregar completamente
            time.sleep(5)

            # Aguardar elemento de preco aparecer
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, '[class*="Price"], [class*="price"]'))
                )
            except Exception:
                self.logger.warning("Timeout aguardando elemento de preco")

            html = driver.page_source
            self.logger.info(f"Pagina carregada via Selenium ({len(html)} bytes)")
            return BeautifulSoup(html, 'html.parser')

        except Exception as e:
            self.logger.error(f"Erro no Selenium: {e}")
            return None

    def _parse_price(self, text: str) -> Optional[float]:
        """Parsear texto de preco brasileiro para float"""
        try:
            cleaned = re.sub(r'[R$\s\u00a0\u202f]', '', text)
            cleaned = cleaned.replace('.', '').replace(',', '.')
            cleaned = re.split(r'[a-zA-Z%]', cleaned)[0].strip()
            if cleaned:
                return float(cleaned)
        except (ValueError, IndexError):
            pass
        return None

    def extract_price(self, soup: BeautifulSoup) -> Optional[float]:
        """Extrair preco atual do produto"""
        try:
            # Seletor 1: MainPrice (styled-component)
            main_price = soup.find(class_=re.compile(r'MainPrice'))
            if main_price:
                price = self._parse_price(main_price.get_text(strip=True))
                if price:
                    return price

            # Seletor 2: Buscar primeiro R$ em contexto de preco
            price_container = soup.find(class_=re.compile(r'PriceContainer|PriceBox|price-box'))
            if price_container:
                text = price_container.get_text(strip=True)
                match = re.search(r'R\$\s*([\d.,]+)', text)
                if match:
                    return self._parse_price('R$ ' + match.group(1))

            # Seletor 3: qualquer elemento com R$
            for el in soup.find_all(string=re.compile(r'R\$\s*[\d.,]+')):
                price = self._parse_price(el.strip())
                if price and price > 10:
                    return price

        except Exception as e:
            logger.error(f"Erro ao extrair preco: {e}")
        return None

    def extract_original_price(self, soup: BeautifulSoup) -> Optional[float]:
        """Extrair preco original (antes do desconto)"""
        try:
            # Preco riscado / RetailPrice
            old = soup.find(class_=re.compile(r'RetailPrice|OldPrice|ListPrice|line-through'))
            if old:
                price = self._parse_price(old.get_text(strip=True))
                if price:
                    return price

            # Segundo valor de R$ no container de preco
            container = soup.find(class_=re.compile(r'PriceContainer|PriceBox'))
            if container:
                prices = re.findall(r'R\$\s*([\d.,]+)', container.get_text())
                if len(prices) >= 2:
                    return self._parse_price('R$ ' + prices[1])

        except Exception:
            pass
        return None

    def extract_discount(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrair desconto"""
        try:
            disc = soup.find(class_=re.compile(r'Discount|off'))
            if disc:
                text = disc.get_text(strip=True)
                if '%' in text:
                    return text
        except Exception:
            pass
        return None

    def extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrair titulo do produto"""
        try:
            # Seletor 1: h1 do produto
            h1 = soup.find('h1')
            if h1:
                return h1.get_text(strip=True)

            # Seletor 2: OG title
            og = soup.find('meta', property='og:title')
            if og and og.get('content'):
                return og['content'].strip()

            # Seletor 3: title tag
            title = soup.find('title')
            if title:
                text = title.get_text(strip=True)
                return re.sub(r'\s*[-|].*Nike.*$', '', text).strip()

        except Exception as e:
            logger.error(f"Erro ao extrair titulo: {e}")
        return None

    def extract_image(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrair URL da imagem principal"""
        try:
            # Seletor 1: OG image
            og = soup.find('meta', property='og:image')
            if og and og.get('content'):
                return og['content']

            # Seletor 2: imagem do produto Nike CDN
            img = soup.find('img', src=re.compile(r'imgnike|akamaihd'))
            if img:
                return img.get('src')

            # Seletor 3: imagem principal
            img = soup.find('img', class_=re.compile(r'product|Product|main|Main'))
            if img:
                return img.get('src') or img.get('data-src')

        except Exception as e:
            logger.error(f"Erro ao extrair imagem: {e}")
        return None

    def extract_product_data(
        self, soup: BeautifulSoup, url: str
    ) -> Optional[ProductData]:
        """Extrair todos os dados do produto"""

        product_code = self.extract_product_code(url)
        title = self.extract_title(soup)
        price = self.extract_price(soup)
        image_url = self.extract_image(soup)
        original_price = self.extract_original_price(soup)
        discount = self.extract_discount(soup)

        if not title:
            logger.warning(f"Titulo nao encontrado para {url}")
            return None

        description = None
        if discount:
            description = discount

        return ProductData(
            title=title,
            price=price if price else 0.0,
            original_price=original_price,
            currency="BRL",
            image_url=image_url or "",
            product_url=url,
            source="Nike",
            product_id=f"NIKE-{product_code}" if product_code else f"NIKE-{abs(hash(url)) % (10**10)}",
            description=description,
            rating=None
        )

    def scrape(self, url: str) -> ScraperResult:
        """Scraping usando Selenium para sites SPA"""
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
    scraper = NikeScraper()
    print("NikeScraper carregado com sucesso")
