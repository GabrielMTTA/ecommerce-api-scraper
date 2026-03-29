import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_scraper import BaseScraper, ProductData
from bs4 import BeautifulSoup
from typing import Optional
import re
import json
import logging

logger = logging.getLogger(__name__)


class NetshoesScraper(BaseScraper):
    """Scraper para Netshoes - usa requests + dataLayer parsing"""

    VALID_DOMAINS = [
        "netshoes.com.br",
    ]

    def validate_url(self, url: str) -> bool:
        url_lower = url.lower()
        return any(domain in url_lower for domain in self.VALID_DOMAINS)

    def _extract_datalayer(self, soup: BeautifulSoup) -> Optional[dict]:
        """Extrair dados do produto do dataLayer push"""
        try:
            for script in soup.find_all('script'):
                text = script.string or ''
                if 'dataLayer.push' in text and 'ecommerce' in text:
                    match = re.search(r'dataLayer\.push\((\{.*?\})\)\s*$', text, re.DOTALL | re.MULTILINE)
                    if match:
                        raw = match.group(1)
                        data = json.loads(raw)
                        ecommerce = data.get('ecommerce', {})
                        detail = ecommerce.get('detail', {})
                        products = detail.get('products', [])
                        if products:
                            return products[0]
        except Exception as e:
            logger.error(f"Erro ao parsear dataLayer: {e}")
        return None

    def extract_product_data(self, soup: BeautifulSoup, url: str) -> Optional[ProductData]:
        """Extrair dados do produto"""

        dl = self._extract_datalayer(soup)

        if dl:
            title_raw = dl.get('name', '')
            variant = dl.get('variant', '')
            title = f"{title_raw} - {variant}" if variant else title_raw

            try:
                price = float(dl.get('price', 0))
            except (ValueError, TypeError):
                price = 0.0

            try:
                list_price = float(dl.get('listPrice', 0))
            except (ValueError, TypeError):
                list_price = None

            original_price = list_price if list_price and list_price > price else None

            sku = dl.get('skuFather', dl.get('id', ''))
            brand = dl.get('brand', '')
            discount_text = dl.get('discountPercent', '')

            # Imagem do OG (mais confiavel que dataLayer que tem URL duplicada)
            og_img = soup.find('meta', property='og:image')
            image_url = og_img['content'] if og_img and og_img.get('content') else None

            if not image_url:
                # Fallback: corrigir URL duplicada do dataLayer
                raw_img = dl.get('image', '')
                if 'static.netshoes.com.br' in raw_img:
                    image_url = 'https://static.netshoes.com.br' + raw_img.split('static.netshoes.com.br')[-1]

            # Descricao
            description = None
            og_desc = soup.find('meta', property='og:description')
            if og_desc and og_desc.get('content'):
                description = og_desc['content'][:500]

            if discount_text:
                discount_label = f"{discount_text} OFF"
                if description:
                    description = f"{discount_label} | {description}"
                else:
                    description = discount_label

            # Rating
            rating = None
            rating_el = soup.find(class_=re.compile(r'rating|stars', re.I))
            if rating_el:
                rating_text = rating_el.get('aria-label', '') or rating_el.get_text(strip=True)
                match = re.search(r'([\d,]+)', rating_text)
                if match:
                    try:
                        rating = float(match.group(1).replace(',', '.'))
                    except ValueError:
                        pass

            if not title:
                logger.warning(f"Titulo nao encontrado para {url}")
                return None

            if not image_url:
                logger.warning(f"Imagem nao encontrada para {url}")
                return None

            return ProductData(
                title=title,
                price=price,
                original_price=original_price,
                currency="BRL",
                image_url=image_url,
                product_url=url,
                source="Netshoes",
                product_id=f"NS-{sku}" if sku else f"NS-{abs(hash(url)) % (10 ** 10)}",
                description=description,
                rating=rating,
                availability=True,
            )

        # Fallback: HTML puro
        h1 = soup.find('h1')
        title = h1.get_text(strip=True) if h1 else None
        og_img = soup.find('meta', property='og:image')
        image_url = og_img['content'] if og_img and og_img.get('content') else None

        if not title or not image_url:
            logger.warning(f"Dados essenciais nao encontrados para {url}")
            return None

        return ProductData(
            title=title,
            price=0.0,
            original_price=None,
            currency="BRL",
            image_url=image_url,
            product_url=url,
            source="Netshoes",
            product_id=f"NS-{abs(hash(url)) % (10 ** 10)}",
            description=None,
            rating=None,
        )


if __name__ == "__main__":
    scraper = NetshoesScraper()
    print("NetshoesScraper carregado com sucesso")
