"""
Chrome driver utilities - auto-detects environment (local vs Docker/Render)
and configures undetected-chromedriver accordingly.
"""
import os
import logging

logger = logging.getLogger(__name__)


def is_docker() -> bool:
    """Detect if running inside a Docker container"""
    return (
        os.path.exists('/.dockerenv')
        or os.environ.get('RENDER', '') != ''
        or os.environ.get('DOCKER', '') != ''
    )


def create_driver():
    """
    Create an undetected-chromedriver instance.
    - Docker/Render: headless with extra flags for containerized Chrome
    - Local: off-screen window (not headless, bypasses all anti-bot)
    """
    import undetected_chromedriver as uc

    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--lang=pt-BR')

    in_container = is_docker()

    if in_container:
        logger.info("Docker/Render detected - using headless Chrome")
        options.add_argument('--headless=new')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-infobars')
        options.add_argument('--single-process')

        chrome_bin = os.environ.get('CHROME_BIN', '/usr/bin/google-chrome-stable')
        if os.path.exists(chrome_bin):
            options.binary_location = chrome_bin

        driver = uc.Chrome(
            options=options,
            headless=True,
            use_subprocess=True,
        )
    else:
        logger.info("Local environment - using off-screen Chrome")
        options.add_argument('--window-position=-32000,-32000')

        driver = uc.Chrome(
            options=options,
            headless=False,
            use_subprocess=True,
            version_main=146,
        )
        driver.minimize_window()

    return driver
