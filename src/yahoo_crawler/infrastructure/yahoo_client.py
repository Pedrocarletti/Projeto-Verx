import logging
from typing import List

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from yahoo_crawler.config import CrawlerConfig

LOGGER = logging.getLogger(__name__)


class YahooFinanceClient:
    ROW_SELECTOR = "tr[data-testid='data-table-v2-row']"
    REGION_BUTTON_SELECTOR = "button[data-ylk*='slk:Region']"
    REGION_OPTIONS_SELECTOR = "div.options"
    NEXT_PAGE_SELECTOR = "button[data-testid='next-page-button']"
    TOTAL_LABEL_SELECTOR = "div.paginationContainer div.total"

    def __init__(self, driver: WebDriver, config: CrawlerConfig) -> None:
        self._driver = driver
        self._config = config
        self._wait = WebDriverWait(self._driver, self._config.timeout_seconds)
        self._navigation_wait = WebDriverWait(self._driver, min(self._config.timeout_seconds, 15))

    def load_page(self) -> None:
        last_error = None
        for attempt in range(1, 4):
            try:
                self._driver.get(self._config.base_url)
                self._wait_for_table_ready()
                return
            except TimeoutException as exc:
                last_error = exc
                LOGGER.warning(
                    "Timeout while loading page (attempt %s/3). Retrying...",
                    attempt,
                )
                try:
                    self._driver.execute_script("window.stop();")
                except WebDriverException:
                    pass
        if last_error:
            raise last_error

    def close(self) -> None:
        self._driver.quit()

    def apply_region_filter(self, region: str) -> None:
        normalized_region = region.strip()
        if not normalized_region:
            raise ValueError("region cannot be empty.")

        LOGGER.info("Applying region filter: %s", normalized_region)
        previous_first_symbol = self._get_first_symbol()
        previous_total = self._get_total_label()

        self._open_region_menu()
        options_container = self._wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, self.REGION_OPTIONS_SELECTOR))
        )

        self._clear_selected_regions(options_container)
        checkbox = self._find_region_checkbox(options_container, normalized_region)
        self._safe_click(checkbox)
        self._click_apply_button()

        self._wait.until(
            lambda _: normalized_region.lower() in self._region_button_text().lower()
        )

        try:
            self._wait_for_table_update(
                previous_first_symbol=previous_first_symbol,
                previous_total=previous_total,
                region=normalized_region,
            )
        except TimeoutException:
            LOGGER.warning(
                "Table did not signal update after applying region '%s'. Continuing.",
                normalized_region,
            )

    def get_current_page_html(self) -> str:
        # Use only the table HTML to reduce BeautifulSoup parsing cost.
        try:
            row = self._driver.find_element(By.CSS_SELECTOR, self.ROW_SELECTOR)
            table = row.find_element(By.XPATH, "./ancestor::table[1]")
            table_html = table.get_attribute("outerHTML")
            if table_html:
                return table_html
        except (NoSuchElementException, StaleElementReferenceException):
            pass
        return self._driver.page_source

    def has_next_page(self) -> bool:
        try:
            button = self._driver.find_element(By.CSS_SELECTOR, self.NEXT_PAGE_SELECTOR)
            return button.get_attribute("disabled") is None
        except NoSuchElementException:
            return False

    def go_to_next_page(self) -> None:
        previous_first_symbol = self._get_first_symbol()
        previous_total = self._get_total_label()
        next_button = self._driver.find_element(By.CSS_SELECTOR, self.NEXT_PAGE_SELECTOR)
        self._safe_click(next_button)

        try:
            self._navigation_wait.until(
                lambda _: self._did_page_change(previous_first_symbol, previous_total)
            )
        except TimeoutException:
            LOGGER.warning(
                "Could not confirm page change quickly. Continuing."
            )
        self._wait_for_table_ready()

    def get_total_label(self) -> str:
        return self._get_total_label()

    def _wait_for_table_ready(self) -> None:
        self._wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.ROW_SELECTOR)))

    def _open_region_menu(self) -> None:
        last_error = None
        for _ in range(3):
            try:
                region_button = self._wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, self.REGION_BUTTON_SELECTOR))
                )
                self._driver.execute_script("arguments[0].scrollIntoView({block:'center'});", region_button)
                self._safe_click(region_button)

                self._wait.until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "input[data-testid^='filter-option-']")
                    )
                )
                return
            except TimeoutException as exc:
                last_error = exc
                continue

        if last_error:
            raise last_error

    def _clear_selected_regions(self, options_container: WebElement) -> None:
        checked = options_container.find_elements(
            By.CSS_SELECTOR, "input[type='checkbox']:checked"
        )
        for checkbox in checked:
            self._safe_click(checkbox)

    def _find_region_checkbox(
        self, options_container: WebElement, region: str
    ) -> WebElement:
        region_lower = region.lower()

        labels = options_container.find_elements(By.CSS_SELECTOR, "label")
        for label in labels:
            label_name = (label.get_attribute("title") or label.text or "").strip().lower()
            if label_name == region_lower:
                return label.find_element(By.CSS_SELECTOR, "input[type='checkbox']")

        # Fallback for when the argument is a country code (e.g. ar, us, br).
        if len(region_lower) <= 3:
            try:
                return options_container.find_element(
                    By.CSS_SELECTOR, "input[data-testid='filter-option-{0}']".format(region_lower)
                )
            except NoSuchElementException:
                pass

        available_regions = self._get_available_regions(labels)
        raise ValueError(
            "Region '{0}' not found. Available regions (sample): {1}".format(
                region, ", ".join(available_regions[:15])
            )
        )

    def _click_apply_button(self) -> None:
        apply_button = self._wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//button[normalize-space()='Apply' and not(@disabled)]")
            )
        )
        self._safe_click(apply_button)

    def _safe_click(self, element: WebElement) -> None:
        try:
            element.click()
        except (ElementClickInterceptedException, StaleElementReferenceException):
            self._driver.execute_script("arguments[0].click();", element)

    def _wait_for_table_update(
        self, previous_first_symbol: str, previous_total: str, region: str
    ) -> None:
        region_lower = region.lower()

        def _updated(_: WebDriver) -> bool:
            first_symbol = self._get_first_symbol()
            total_label = self._get_total_label()
            first_region = self._get_first_region()
            if first_symbol and previous_first_symbol and first_symbol != previous_first_symbol:
                return True
            if total_label and previous_total and total_label != previous_total:
                return True
            if first_region and first_region.lower() == region_lower:
                return True
            return False

        self._wait.until(_updated)

    def _region_button_text(self) -> str:
        return self._driver.find_element(
            By.CSS_SELECTOR, self.REGION_BUTTON_SELECTOR
        ).text.strip()

    def _get_first_symbol(self) -> str:
        try:
            return self._driver.find_element(
                By.CSS_SELECTOR,
                "{0} td[data-testid-cell='ticker'] span.symbol".format(self.ROW_SELECTOR),
            ).text.strip()
        except (NoSuchElementException, StaleElementReferenceException):
            return ""

    def _get_first_region(self) -> str:
        try:
            return self._driver.find_element(
                By.CSS_SELECTOR,
                "{0} td[data-testid-cell='region']".format(self.ROW_SELECTOR),
            ).text.strip()
        except (NoSuchElementException, StaleElementReferenceException):
            return ""

    def _get_total_label(self) -> str:
        try:
            return self._driver.find_element(By.CSS_SELECTOR, self.TOTAL_LABEL_SELECTOR).text.strip()
        except (NoSuchElementException, StaleElementReferenceException):
            return ""

    def _get_available_regions(self, labels: List[WebElement]) -> List[str]:
        names = []
        for label in labels:
            title = (label.get_attribute("title") or label.text or "").strip()
            if title:
                names.append(title)
        return names

    def _did_page_change(self, previous_first_symbol: str, previous_total: str) -> bool:
        current_first_symbol = self._get_first_symbol()
        if previous_first_symbol:
            return bool(
                current_first_symbol and current_first_symbol != previous_first_symbol
            )

        current_total = self._get_total_label()
        if previous_total:
            return bool(current_total and current_total != previous_total)
        return False
