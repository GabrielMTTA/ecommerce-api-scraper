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
    - Docker/Render: uses Xvfb virtual display (non-headless, bypasses anti-bot)
    - Local Windows: off-screen window (non-headless, bypasses anti-bot)
    Both modes run Chrome as a real browser to avoid Akamai WAF detection.
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
        logger.info("Docker/Render detected - using Xvfb virtual display")
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-extensions')

        chrome_bin = os.environ.get('CHROME_BIN', '/usr/bin/google-chrome-stable')
        if os.path.exists(chrome_bin):
            options.binary_location = chrome_bin

        # Detect installed Chrome version to avoid driver mismatch
        chrome_version = None
        try:
            import subprocess
            result = subprocess.run(
                [chrome_bin, '--version'], capture_output=True, text=True, timeout=5
            )
            version_match = __import__('re').search(r'(\d+)', result.stdout)
            if version_match:
                chrome_version = int(version_match.group(1))
                logger.info(f"Chrome version detected: {chrome_version}")
        except Exception:
            pass

        driver = uc.Chrome(
            options=options,
            headless=False,
            use_subprocess=True,
            version_main=chrome_version,
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
