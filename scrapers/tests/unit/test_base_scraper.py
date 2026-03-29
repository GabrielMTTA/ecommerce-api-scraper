import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
from unittest.mock import patch
from bs4 import BeautifulSoup
import responses
from base_scraper import BaseScraper, ProductData, ScraperResult, ScraperStatus


# Scraper concreto para testes
class TestScraper(BaseScraper):
    def validate_url(self, url: str) -> bool:
        return "example.com" in url

    def extract_product_data(self, soup, url):
        title = soup.find('h1')
        price = soup.find('span', class_='price')

        if not title or not price:
            return None

        return ProductData(
            title=title.get_text(),
            price=float(price.get_text().replace('$', '')),
            original_price=None,
            currency="USD",
            image_url="https://example.com/image.jpg",
            product_url=url,
            source="Test Source",
            product_id="TEST-001"
        )


class TestProductData:
    def test_product_data_creation(self):
        product = ProductData(
            title="Test Product",
            price=100.0,
            original_price=150.0,
            currency="BRL",
            image_url="https://example.com/img.jpg",
            product_url="https://example.com/product",
            source="Test",
            product_id="TEST-001"
        )

        assert product.title == "Test Product"
        assert product.price == 100.0
        assert product.currency == "BRL"

    def test_product_to_dict(self):
        product = ProductData(
            title="Test",
            price=100.0,
            original_price=None,
            currency="BRL",
            image_url="url",
            product_url="url",
            source="Test",
            product_id="TEST-001"
        )

        data = product.to_dict()
        assert isinstance(data, dict)
        assert data['title'] == "Test"
        assert data['price'] == 100.0

    def test_get_checksum(self):
        product = ProductData(
            title="Test",
            price=100.0,
            original_price=None,
            currency="BRL",
            image_url="url",
            product_url="url",
            source="Test",
            product_id="TEST-001",
            availability=True
        )

        checksum = product.get_checksum()
        assert isinstance(checksum, str)
        assert len(checksum) == 32  # MD5 hash length


class TestBaseScraper:
    def test_scraper_initialization(self):
        scraper = TestScraper(timeout=30, retries=3)
        assert scraper.timeout == 30
        assert scraper.retries == 3
        assert scraper.session is not None

    @responses.activate
    def test_fetch_page_success(self):
        url = "https://example.com/product"
        html_content = "<html><h1>Test Product</h1></html>"

        responses.add(
            responses.GET,
            url,
            body=html_content,
            status=200
        )

        scraper = TestScraper(retries=1)
        with patch('time.sleep'):  # Skip delays in tests
            soup = scraper.fetch_page(url)

        assert soup is not None
        assert soup.find('h1').get_text() == "Test Product"

    def test_validate_url(self):
        scraper = TestScraper()

        assert scraper.validate_url("https://example.com/product") is True
        assert scraper.validate_url("https://other.com/product") is False

    @responses.activate
    def test_scrape_success(self):
        url = "https://example.com/product-123"
        html = """
        <html>
            <h1>Test Product</h1>
            <span class="price">$99.99</span>
        </html>
        """

        responses.add(responses.GET, url, body=html, status=200)

        scraper = TestScraper(retries=1)
        with patch('time.sleep'):
            result = scraper.scrape(url)

        assert result.status == ScraperStatus.SUCCESS
        assert result.data is not None
        assert result.data.title == "Test Product"
        assert result.data.price == 99.99

    def test_scrape_invalid_url(self):
        scraper = TestScraper()
        result = scraper.scrape("https://invalid-domain.com/product")

        assert result.status == ScraperStatus.INVALID_URL
        assert result.error is not None

    def test_scraper_result_to_dict(self):
        result = ScraperResult(
            status=ScraperStatus.SUCCESS,
            data=None,
            error="Test error"
        )

        data = result.to_dict()
        assert data['status'] == 'success'
        assert data['error'] == "Test error"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=base_scraper"])
