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
    """Scraper para Mercado Livre - suporta URLs diretas, short links e paginas sociais"""

    VALID_DOMAINS = [
        "mercadolivre.com.br",
        "mercadolibre.com",
        "produto.mercadolivre.com.br",
        "meli.la",
    ]

    def validate_url(self, url: str) -> bool:
        """Validar se URL e do Mercado Livre ou short link meli.la"""
        url_lower = url.lower()
        return any(domain in url_lower for domain in self.VALID_DOMAINS)

    def resolve_url(self, url: str) -> str:
        """Resolver short URLs (meli.la) para URL final"""
        if "meli.la" in url.lower():
            try:
                response = self.session.get(url, allow_redirects=True, timeout=self.timeout)
                resolved = response.url
                self.logger.info(f"URL resolvida: {url} -> {resolved}")
                return resolved
            except Exception as e:
                self.logger.error(f"Erro ao resolver URL: {e}")
        return url

    def extract_product_id(self, url: str, soup: BeautifulSoup) -> Optional[str]:
        """Extrair ID do produto da URL ou da pagina"""
        # Tentar na URL
        match = re.search(r'MLB-?(\d+)', url)
        if match:
            return f"MLB{match.group(1)}"

        # Tentar nos links da pagina
        product_links = soup.find_all('a', href=re.compile(r'MLB-?\d+'))
        if product_links:
            href = product_links[0].get('href', '')
            match = re.search(r'MLB-?(\d+)', href)
            if match:
                return f"MLB{match.group(1)}"

        # Gerar ID a partir da URL se nada encontrado
        url_hash = abs(hash(url)) % (10 ** 10)
        return f"ML-{url_hash}"

    def _parse_price_text(self, text: str) -> Optional[float]:
        """Parsear texto de preco no formato R$XX,YY para float"""
        try:
            cleaned = re.sub(r'[R$\s]', '', text)
            cleaned = cleaned.replace('.', '').replace(',', '.')
            # Remover sufixos como "42% OFF"
            cleaned = re.split(r'[a-zA-Z%]', cleaned)[0].strip()
            if cleaned:
                return float(cleaned)
        except (ValueError, IndexError):
            pass
        return None

    def extract_price(self, soup: BeautifulSoup) -> Optional[float]:
        """Extrair preco do produto"""
        try:
            # Seletor 1: poly-price__current (paginas sociais/listagem)
            current_price = soup.find('span', class_='poly-price__current')
            if current_price:
                amount = current_price.find('span', class_=re.compile(r'^andes-money-amount\b'))
                if amount:
                    price = self._parse_price_text(amount.get_text(strip=True))
                    if price:
                        return price

            # Seletor 2: primeiro andes-money-amount com valor
            amounts = soup.find_all('span', class_=re.compile(r'^andes-money-amount\s'))
            for amount in amounts:
                classes = ' '.join(amount.get('class', []))
                if 'discount' in classes or 'previous' in classes:
                    continue
                price = self._parse_price_text(amount.get_text(strip=True))
                if price and price > 0:
                    return price

            # Seletor 3: price-tag-fraction (layout antigo)
            fraction = soup.find('span', class_='price-tag-fraction')
            if fraction:
                price_text = fraction.get_text(strip=True).replace('.', '')
                return float(price_text)

            # Seletor 4: ui-pdp-price (pagina de produto)
            price_el = soup.find('div', class_='ui-pdp-price__second-line')
            if price_el:
                price_text = price_el.get_text(strip=True)
                price = re.sub(r'[^\d,]', '', price_text).replace(',', '.')
                return float(price)

        except Exception as e:
            logger.error(f"Erro ao extrair preco: {e}")

        return None

    def extract_original_price(self, soup: BeautifulSoup) -> Optional[float]:
        """Extrair preco original (antes do desconto)"""
        try:
            # Seletor 1: poly-component__price com primeiro valor (preco cheio)
            poly_price = soup.find('div', class_='poly-component__price')
            if poly_price:
                amounts = poly_price.find_all('span', class_=re.compile(r'^andes-money-amount\s'))
                if len(amounts) >= 2:
                    # Primeiro e preco original, segundo e atual
                    first_text = amounts[0].get_text(strip=True)
                    price = self._parse_price_text(first_text)
                    if price:
                        return price

            # Seletor 2: preco riscado
            original = soup.find('span', class_=re.compile(r'andes-money-amount--previous'))
            if original:
                price = self._parse_price_text(original.get_text(strip=True))
                if price:
                    return price

            # Seletor 3: tag <s> com preco
            original = soup.find('s', class_=re.compile(r'price'))
            if original:
                price = self._parse_price_text(original.get_text(strip=True))
                if price:
                    return price
        except Exception:
            pass
        return None

    def extract_discount(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrair porcentagem de desconto"""
        try:
            discount = soup.find('span', class_=re.compile(r'andes-money-amount__discount'))
            if discount:
                return discount.get_text(strip=True)
        except Exception:
            pass
        return None

    def extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrair titulo do produto"""
        try:
            # Seletor 1: pagina de produto
            title = soup.find('h1', class_='ui-pdp-title')
            if title:
                return title.get_text(strip=True)

            # Seletor 2: OG meta tag
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                return og_title['content'].strip()

            # Seletor 3: primeiro h1 da pagina
            h1 = soup.find('h1')
            if h1:
                return h1.get_text(strip=True)

            # Seletor 4: title tag
            title_tag = soup.find('title')
            if title_tag:
                text = title_tag.get_text(strip=True)
                # Remover sufixo " | Mercado Livre"
                return re.sub(r'\s*\|.*$', '', text).strip()

        except Exception as e:
            logger.error(f"Erro ao extrair titulo: {e}")
        return None

    def extract_image(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrair URL da imagem principal"""
        try:
            # Seletor 1: OG image (mais confiavel)
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                return og_image['content']

            # Seletor 2: imagem da galeria
            img = soup.find('img', class_=re.compile(r'ui-pdp-image|gallery'))
            if img:
                return img.get('src') or img.get('data-src')

            # Seletor 3: qualquer imagem do mlstatic
            img = soup.find('img', src=re.compile(r'mlstatic\.com'))
            if img:
                return img.get('src')

        except Exception as e:
            logger.error(f"Erro ao extrair imagem: {e}")
        return None

    def extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrair descricao do produto"""
        try:
            # Seletor 1: secao de descricao
            desc = soup.find('section', {'data-testid': 'description'})
            if desc:
                return desc.get_text(strip=True)[:500]

            # Seletor 2: OG description
            og_desc = soup.find('meta', property='og:description')
            if og_desc and og_desc.get('content'):
                return og_desc['content'][:500]

            # Seletor 3: meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc and meta_desc.get('content'):
                return meta_desc['content'][:500]

        except Exception:
            pass
        return None

    def extract_product_data(
        self, soup: BeautifulSoup, url: str
    ) -> Optional[ProductData]:
        """Extrair todos os dados do produto"""

        product_id = self.extract_product_id(url, soup)
        title = self.extract_title(soup)
        price = self.extract_price(soup)
        image_url = self.extract_image(soup)
        original_price = self.extract_original_price(soup)
        discount = self.extract_discount(soup)

        # Validacao minima - titulo e imagem sao essenciais
        if not title:
            logger.warning(f"Titulo nao encontrado para {url}")
            return None

        if not image_url:
            logger.warning(f"Imagem nao encontrada para {url}")
            return None

        description = self.extract_description(soup)
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
            source="Mercado Livre",
            product_id=product_id or f"ML-{abs(hash(url)) % (10**10)}",
            description=description,
            rating=None
        )

    def scrape(self, url: str) -> 'ScraperResult':
        """Override para resolver short URLs antes de scraping"""
        from base_scraper import ScraperResult, ScraperStatus

        if not self.validate_url(url):
            return ScraperResult(
                status=ScraperStatus.INVALID_URL,
                error=f"URL invalida para {self.__class__.__name__}"
            )

        # Resolver short URL
        resolved_url = self.resolve_url(url)

        # Fazer fetch
        soup = self.fetch_page(resolved_url)
        if not soup:
            return ScraperResult(
                status=ScraperStatus.FAILED,
                error="Nao foi possivel carregar a pagina",
                retry_after=300
            )

        # Extrair dados
        try:
            product_data = self.extract_product_data(soup, resolved_url)

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


if __name__ == "__main__":
    scraper = MercadoLivreScraper()
    print("MercadoLivreScraper carregado com sucesso")
