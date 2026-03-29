from abc import ABC, abstractmethod
from typing import Dict, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
from datetime import datetime
from dataclasses import dataclass
import hashlib
from bs4 import BeautifulSoup
from enum import Enum
import time
import random

# Logging configurado
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ScraperStatus(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"
    INVALID_URL = "invalid_url"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"


@dataclass
class ProductData:
    """Classe para representar dados de produto"""
    title: str
    price: float
    original_price: Optional[float]
    currency: str
    image_url: str
    product_url: str
    source: str
    product_id: str
    description: Optional[str] = None
    rating: Optional[float] = None
    availability: bool = True
    scrape_timestamp: Optional[str] = None

    def __post_init__(self):
        if not self.scrape_timestamp:
            self.scrape_timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict:
        return {
            'title': self.title,
            'price': self.price,
            'original_price': self.original_price,
            'currency': self.currency,
            'image_url': self.image_url,
            'product_url': self.product_url,
            'source': self.source,
            'product_id': self.product_id,
            'description': self.description,
            'rating': self.rating,
            'availability': self.availability,
            'scrape_timestamp': self.scrape_timestamp
        }

    def get_checksum(self) -> str:
        """Gera hash para detectar mudanças"""
        data = f"{self.product_id}|{self.price}|{self.availability}"
        return hashlib.md5(data.encode()).hexdigest()


@dataclass
class ScraperResult:
    """Resultado do scraping"""
    status: ScraperStatus
    data: Optional[ProductData] = None
    error: Optional[str] = None
    retry_after: Optional[int] = None
    timestamp: Optional[str] = None
    attempt: int = 1

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()

    def to_dict(self) -> Dict:
        return {
            'status': self.status.value,
            'data': self.data.to_dict() if self.data else None,
            'error': self.error,
            'retry_after': self.retry_after,
            'timestamp': self.timestamp,
            'attempt': self.attempt
        }


class BaseScraper(ABC):
    """Base class para todos os scrapers"""

    def __init__(self, timeout: int = 30, retries: int = 3):
        self.timeout = timeout
        self.retries = retries
        self.session = self._create_session()
        self.logger = logging.getLogger(self.__class__.__name__)

    def _create_session(self) -> requests.Session:
        """Cria sessão HTTP com retry strategy"""
        session = requests.Session()

        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
            backoff_factor=1
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Headers realistas
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Language': 'pt-BR,pt;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })

        return session

    def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch página com retry e tratamento de erro"""
        for attempt in range(self.retries):
            try:
                # Delay aleatório para evitar rate limit
                time.sleep(random.uniform(1, 3))

                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True
                )

                response.raise_for_status()

                self.logger.info(f"Página carregada: {url}")
                return BeautifulSoup(response.content, 'html.parser')

            except requests.exceptions.Timeout:
                self.logger.warning(
                    f"Timeout na tentativa {attempt + 1}/{self.retries}"
                )
                if attempt < self.retries - 1:
                    wait_time = 2 ** attempt
                    self.logger.info(
                        f"Aguardando {wait_time}s antes de nova tentativa..."
                    )
                    time.sleep(wait_time)

            except requests.exceptions.ConnectionError as e:
                self.logger.error(f"Erro de conexão: {e}")
                if attempt < self.retries - 1:
                    time.sleep(5)

            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    self.logger.warning("Rate limit detectado (429)")
                    return None
                elif e.response is not None and e.response.status_code == 403:
                    self.logger.warning("Acesso bloqueado (403)")
                    return None
                else:
                    status = e.response.status_code if e.response else 'unknown'
                    self.logger.error(f"HTTP Error: {status}")

        return None

    @abstractmethod
    def extract_product_data(
        self, soup: BeautifulSoup, url: str
    ) -> Optional[ProductData]:
        """Método abstrato para extrair dados do produto"""
        pass

    @abstractmethod
    def validate_url(self, url: str) -> bool:
        """Validar se URL é da plataforma correta"""
        pass

    def scrape(self, url: str) -> ScraperResult:
        """Método principal de scraping com validação"""

        # Validar URL
        if not self.validate_url(url):
            return ScraperResult(
                status=ScraperStatus.INVALID_URL,
                error=f"URL inválida para {self.__class__.__name__}"
            )

        # Fazer fetch
        soup = self.fetch_page(url)
        if not soup:
            return ScraperResult(
                status=ScraperStatus.FAILED,
                error="Não foi possível carregar a página",
                retry_after=300
            )

        # Extrair dados
        try:
            product_data = self.extract_product_data(soup, url)

            if not product_data:
                return ScraperResult(
                    status=ScraperStatus.FAILED,
                    error="Não foi possível extrair dados do produto"
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
        """Cleanup"""
        if hasattr(self, 'session'):
            self.session.close()
