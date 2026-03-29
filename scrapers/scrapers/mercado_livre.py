import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_scraper import BaseScraper, ProductData
from bs4 import BeautifulSoup
from typing import Optional
import re
import logging

logger = logging.getLogger(__name__)


class MercadoLivreScraper(BaseScraper):
    """Scraper para Mercado Livre"""

    BASE_URL = "https://www.mercadolivre.com.br"

    def validate_url(self, url: str) -> bool:
        """Validar se URL é do Mercado Livre"""
        return "mercadolivre.com.br" in url.lower()

    def extract_product_id(self, url: str) -> Optional[str]:
        """Extrair ID do produto da URL"""
        match = re.search(r'MLB(\d+)', url)
        return f"MLB{match.group(1)}" if match else None

    def extract_price(self, soup: BeautifulSoup) -> Optional[float]:
        """Extrair preço do produto"""
        try:
            price_selectors = [
                soup.find('span', class_='price-tag-fraction'),
                soup.find('div', class_='ui-pdp-price__second-line'),
                soup.find('span', {'data-testid': 'price-main'})
            ]

            for selector in price_selectors:
                if selector:
                    price_text = selector.get_text(strip=True)
                    price = re.sub(r'[^\d,]', '', price_text).replace(',', '.')
                    return float(price)

        except Exception as e:
            logger.error(f"Erro ao extrair preço: {e}")

        return None

    def extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrair título do produto"""
        try:
            title = soup.find('h1', class_='ui-pdp-title')
            return title.get_text(strip=True) if title else None
        except Exception as e:
            logger.error(f"Erro ao extrair título: {e}")
        return None

    def extract_image(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrair URL da imagem principal"""
        try:
            img = soup.find('img', class_='gallery-image-container')
            return img.get('src') or img.get('data-src') if img else None
        except Exception as e:
            logger.error(f"Erro ao extrair imagem: {e}")
        return None

    def extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrair descrição do produto"""
        try:
            desc = soup.find('section', {'data-testid': 'description'})
            return desc.get_text(strip=True)[:500] if desc else None
        except Exception:
            return None

    def extract_rating(self, soup: BeautifulSoup) -> Optional[float]:
        """Extrair avaliação do produto"""
        try:
            rating = soup.find('div', class_='ui-pdp-review')
            if rating:
                rating_text = rating.get_text(strip=True)
                numbers = re.findall(r'\d+\.\d+|\d+', rating_text)
                if numbers:
                    return float(numbers[0])
        except Exception:
            pass
        return None

    def extract_product_data(
        self, soup: BeautifulSoup, url: str
    ) -> Optional[ProductData]:
        """Extrair todos os dados do produto"""

        product_id = self.extract_product_id(url)
        if not product_id:
            logger.warning(f"Não foi possível extrair ID do produto de {url}")
            return None

        title = self.extract_title(soup)
        price = self.extract_price(soup)
        image_url = self.extract_image(soup)

        # Validação mínima
        if not all([title, price, image_url]):
            logger.warning(f"Dados incompletos para {url}")
            return None

        return ProductData(
            title=title,  # type: ignore
            price=price,  # type: ignore
            original_price=None,
            currency="BRL",
            image_url=image_url,  # type: ignore
            product_url=url,
            source="Mercado Livre",
            product_id=product_id,
            description=self.extract_description(soup),
            rating=self.extract_rating(soup)
        )


if __name__ == "__main__":
    scraper = MercadoLivreScraper()
    print("MercadoLivreScraper carregado com sucesso")
