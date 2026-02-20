import os

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from yahoo_crawler.config import CrawlerConfig


class WebDriverFactory:
    def __init__(self, config: CrawlerConfig) -> None:
        self._config = config

    def create(self) -> webdriver.Chrome:
        options = Options()
        options.page_load_strategy = "eager"
        if self._config.headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-component-update")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-domain-reliability")
        options.add_argument("--disable-sync")
        options.add_argument("--metrics-recording-only")
        options.add_argument("--no-first-run")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        service = Service(log_path="NUL" if os.name == "nt" else os.devnull)
        driver = webdriver.Chrome(options=options, service=service)
        driver.set_page_load_timeout(self._config.page_load_timeout_seconds)
        return driver
