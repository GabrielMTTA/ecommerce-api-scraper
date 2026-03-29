import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from base_scraper import BaseScraper, ProductData
from bs4 import BeautifulSoup
from typing import Optional
import re
import logging

logger = logging.getLogger(__name__)


class AmazonScraper(BaseScraper):
    """Scraper para Amazon Brasil"""

    VALID_DOMAINS = [
        "amazon.com.br",
        "amazon.com",
    ]

    def __init__(self, timeout: int = 30, retries: int = 3):
        super().__init__(timeout=timeout, retries=retries)
        # Amazon precisa de headers mais completos
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cache-Control': 'max-age=0',
            'Sec-Ch-Ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
        })

    def validate_url(self, url: str) -> bool:
        url_lower = url.lower()
        return any(domain in url_lower for domain in self.VALID_DOMAINS)

    def extract_product_id(self, url: str, soup: BeautifulSoup) -> Optional[str]:
        """Extrair ASIN da URL"""
        # Padrao /dp/ASIN
        match = re.search(r'/dp/([A-Z0-9]{10})', url)
        if match:
            return match.group(1)
        # Padrao /gp/product/ASIN
        match = re.search(r'/gp/product/([A-Z0-9]{10})', url)
        if match:
            return match.group(1)
        # Fallback: hash da URL
        return f"AMZ-{abs(hash(url)) % (10 ** 10)}"

    def _parse_price_text(self, text: str) -> Optional[float]:
        """Parsear texto de preco Amazon (R$XX,YY)"""
        try:
            cleaned = re.sub(r'[R$\s\xa0]', '', text)
            cleaned = cleaned.replace('.', '').replace(',', '.')
            cleaned = re.split(r'[a-zA-Z%]', cleaned)[0].strip()
            if cleaned:
                return float(cleaned)
        except (ValueError, IndexError):
            pass
        return None

    def extract_price(self, soup: BeautifulSoup) -> Optional[float]:
        """Extrair preco do produto Amazon"""
        try:
            # Seletor 1: preco principal (deal ou normal)
            price_whole = soup.find('span', class_='a-price-whole')
            if price_whole:
                whole = price_whole.get_text(strip=True).replace('.', '').rstrip(',')
                fraction_el = price_whole.find_next_sibling('span', class_='a-price-fraction')
                fraction = fraction_el.get_text(strip=True) if fraction_el else '00'
                try:
                    return float(f"{whole}.{fraction}")
                except ValueError:
                    pass

            # Seletor 2: priceblock_dealprice ou priceblock_ourprice
            for price_id in ['priceblock_dealprice', 'priceblock_ourprice', 'price_inside_buybox', 'newBuyBoxPrice']:
                el = soup.find('span', id=price_id)
                if el:
                    price = self._parse_price_text(el.get_text(strip=True))
                    if price:
                        return price

            # Seletor 3: corePrice_feature_div
            core_price = soup.find('div', id='corePrice_feature_div')
            if core_price:
                price_span = core_price.find('span', class_='a-offscreen')
                if price_span:
                    price = self._parse_price_text(price_span.get_text(strip=True))
                    if price:
                        return price

            # Seletor 4: qualquer a-offscreen dentro de apexPriceToPay
            apex = soup.find('span', class_='apexPriceToPay') or soup.find('span', id='apexPriceToPay')
            if apex:
                offscreen = apex.find('span', class_='a-offscreen')
                if offscreen:
                    price = self._parse_price_text(offscreen.get_text(strip=True))
                    if price:
                        return price

            # Seletor 5: busca generica por a-price
            price_el = soup.find('span', class_='a-price')
            if price_el:
                offscreen = price_el.find('span', class_='a-offscreen')
                if offscreen:
                    price = self._parse_price_text(offscreen.get_text(strip=True))
                    if price:
                        return price

        except Exception as e:
            logger.error(f"Erro ao extrair preco: {e}")
        return None

    def extract_original_price(self, soup: BeautifulSoup) -> Optional[float]:
        """Extrair preco original (antes desconto)"""
        try:
            # Preco riscado: basisPrice ou a-text-price
            basis = soup.find('span', class_='basisPrice')
            if basis:
                offscreen = basis.find('span', class_='a-offscreen')
                if offscreen:
                    price = self._parse_price_text(offscreen.get_text(strip=True))
                    if price:
                        return price

            # a-text-price com data-a-strike
            strike = soup.find('span', class_='a-price', attrs={'data-a-strike': 'true'})
            if strike:
                offscreen = strike.find('span', class_='a-offscreen')
                if offscreen:
                    price = self._parse_price_text(offscreen.get_text(strip=True))
                    if price:
                        return price

        except Exception:
            pass
        return None

    def extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrair titulo do produto"""
        try:
            # productTitle span
            title = soup.find('span', id='productTitle')
            if title:
                return title.get_text(strip=True)

            # og:title
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                return og_title['content'].strip()

            # title tag
            title_tag = soup.find('title')
            if title_tag:
                text = title_tag.get_text(strip=True)
                return re.sub(r'\s*[-|:]?\s*Amazon\.com\.br.*$', '', text).strip()

        except Exception as e:
            logger.error(f"Erro ao extrair titulo: {e}")
        return None

    def extract_image(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrair URL da imagem principal"""
        try:
            # landingImage
            img = soup.find('img', id='landingImage')
            if img:
                # data-old-hires tem a imagem em alta resolucao
                hires = img.get('data-old-hires')
                if hires:
                    return hires
                return img.get('src')

            # og:image
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                return og_image['content']

            # imgTagWrapperId
            wrapper = soup.find('div', id='imgTagWrapperId')
            if wrapper:
                img = wrapper.find('img')
                if img:
                    return img.get('data-old-hires') or img.get('src')

            # Qualquer imagem amazon media
            img = soup.find('img', src=re.compile(r'images-na\.ssl-images-amazon\.com|m\.media-amazon\.com'))
            if img:
                return img.get('src')

        except Exception as e:
            logger.error(f"Erro ao extrair imagem: {e}")
        return None

    def extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrair descricao do produto"""
        try:
            # Feature bullets
            feature_div = soup.find('div', id='feature-bullets')
            if feature_div:
                bullets = feature_div.find_all('span', class_='a-list-item')
                items = [b.get_text(strip=True) for b in bullets if b.get_text(strip=True)]
                if items:
                    return ' | '.join(items[:5])

            # productDescription
            desc_div = soup.find('div', id='productDescription')
            if desc_div:
                return desc_div.get_text(strip=True)[:500]

            # og:description
            og_desc = soup.find('meta', property='og:description')
            if og_desc and og_desc.get('content'):
                return og_desc['content'][:500]

            # meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                return meta_desc['content'][:500]

        except Exception:
            pass
        return None

    def extract_rating(self, soup: BeautifulSoup) -> Optional[float]:
        """Extrair avaliacao do produto"""
        try:
            rating_el = soup.find('span', id='acrPopover')
            if rating_el:
                title = rating_el.get('title', '')
                match = re.search(r'([\d,]+)\s*de\s*5', title)
                if match:
                    return float(match.group(1).replace(',', '.'))

            # Fallback: i.a-icon-star span
            star = soup.find('i', class_=re.compile(r'a-icon-star'))
            if star:
                text = star.get_text(strip=True)
                match = re.search(r'([\d,]+)', text)
                if match:
                    return float(match.group(1).replace(',', '.'))
        except Exception:
            pass
        return None

    def extract_availability(self, soup: BeautifulSoup) -> bool:
        """Verificar disponibilidade"""
        try:
            avail = soup.find('div', id='availability')
            if avail:
                text = avail.get_text(strip=True).lower()
                if 'indisponível' in text or 'unavailable' in text or 'esgotado' in text:
                    return False
            return True
        except Exception:
            return True

    def extract_product_data(self, soup: BeautifulSoup, url: str) -> Optional[ProductData]:
        """Extrair todos os dados do produto Amazon"""
        product_id = self.extract_product_id(url, soup)
        title = self.extract_title(soup)
        price = self.extract_price(soup)
        image_url = self.extract_image(soup)
        original_price = self.extract_original_price(soup)
        rating = self.extract_rating(soup)
        availability = self.extract_availability(soup)

        if not title:
            logger.warning(f"Titulo nao encontrado para {url}")
            return None

        if not image_url:
            logger.warning(f"Imagem nao encontrada para {url}")
            return None

        description = self.extract_description(soup)

        # Calcular desconto se houver
        if original_price and price and original_price > price:
            discount_pct = round((1 - price / original_price) * 100)
            discount_text = f"{discount_pct}% OFF"
            if description:
                description = f"{discount_text} | {description}"
            else:
                description = discount_text

        return ProductData(
            title=title,
            price=price if price else 0.0,
            original_price=original_price,
            currency="BRL",
            image_url=image_url,
            product_url=url,
            source="Amazon",
            product_id=product_id or f"AMZ-{abs(hash(url)) % (10 ** 10)}",
            description=description,
            rating=rating,
            availability=availability,
        )


if __name__ == "__main__":
    scraper = AmazonScraper()
    print("AmazonScraper carregado com sucesso")
