"""Pruebas E2E automatizadas en navegador Google Chrome con Selenium.

Variables de entorno soportadas:
- APP_BASE_URL: URL base del frontend/API Gateway (default: http://localhost:8000)
- SELENIUM_HEADLESS: "0" para abrir Chrome visible paso a paso (default), "1" para headless
- SELENIUM_STEP_DELAY: pausa opcional en segundos entre pasos visibles (default: 0.4 visible, 0 headless)
- SELENIUM_WAIT_SECONDS: timeout de WebDriverWait en segundos (default: 20)
"""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime, timedelta

import httpx
import pytest

pytestmark = pytest.mark.selenium

APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/")
DEFAULT_WAIT_SECONDS = int(os.getenv("SELENIUM_WAIT_SECONDS", "20"))
PASSENGER_NAME = "Prueba Selenium Chrome"


def _is_headless() -> bool:
    return os.getenv("SELENIUM_HEADLESS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _step_pause() -> None:
    default_delay = "0" if _is_headless() else "0.4"
    delay = float(os.getenv("SELENIUM_STEP_DELAY", default_delay))
    if delay > 0:
        time.sleep(delay)


def _import_selenium():
    try:
        from selenium import webdriver
        from selenium.common.exceptions import WebDriverException
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support import expected_conditions as ec
        from selenium.webdriver.support.ui import WebDriverWait
    except ImportError as exc:
        pytest.skip(
            "Selenium no está instalado en este entorno. "
            f"Instala con `pip install -r tests/requirements-selenium.txt` ({exc})"
        )

    return webdriver, ChromeOptions, By, Keys, WebDriverWait, ec, WebDriverException


def _ensure_app_available(base_url: str) -> None:
    health_url = f"{base_url}/health"
    try:
        response = httpx.get(health_url, timeout=3.0)
    except (httpx.HTTPError, OSError) as exc:
        pytest.skip(f"Aplicación no disponible en {health_url}: {exc}")

    if response.status_code != 200:
        pytest.skip(
            f"Healthcheck de la aplicación en {health_url} respondió HTTP {response.status_code}"
        )


@pytest.fixture(scope="module")
def chrome_driver():
    """Inicializa una sesión real de Google Chrome para la suite E2E."""
    (
        webdriver,
        ChromeOptions,
        _By,
        _Keys,
        _WebDriverWait,
        _ec,
        WebDriverException,
    ) = _import_selenium()
    _ensure_app_available(APP_BASE_URL)

    options = ChromeOptions()
    options.add_argument("--window-size=1440,960")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    if _is_headless():
        options.add_argument("--headless=new")

    try:
        driver = webdriver.Chrome(options=options)
    except WebDriverException as exc:
        pytest.skip(f"No fue posible iniciar Google Chrome / ChromeDriver: {exc}")

    driver.set_page_load_timeout(30)
    try:
        yield driver
    finally:
        driver.quit()


def _wait_for_airports_loaded(
    driver, by_cls, wait_cls, timeout: int = DEFAULT_WAIT_SECONDS
):
    def _has_airports(drv):
        badge = drv.find_element(by_cls.ID, "badge-airports-count")
        text = badge.text.strip()
        return text.isdigit() and int(text) > 0

    wait_cls(driver, timeout).until(_has_airports)


def _select_combobox_airport(
    driver,
    *,
    by_cls,
    keys_cls,
    wait_cls,
    ec_mod,
    text_input_id: str,
    listbox_id: str,
    hidden_input_id: str,
    toggle_btn_id: str,
    search_queries: tuple[str, ...],
) -> str:
    """Usa el combobox predictivo para filtrar y seleccionar un aeropuerto habilitado."""
    wait = wait_cls(driver, DEFAULT_WAIT_SECONDS)
    text_input = wait.until(ec_mod.element_to_be_clickable((by_cls.ID, text_input_id)))

    for query in search_queries:
        text_input.click()
        text_input.send_keys(keys_cls.CONTROL, "a")
        text_input.send_keys(keys_cls.BACKSPACE)
        if query:
            text_input.send_keys(query)
        else:
            toggle_btn = driver.find_element(by_cls.ID, toggle_btn_id)
            toggle_btn.click()

        wait.until(
            lambda drv: "d-none"
            not in (
                drv.find_element(by_cls.ID, listbox_id).get_attribute("class") or ""
            )
            and len(
                drv.find_elements(
                    by_cls.CSS_SELECTOR, f"#{listbox_id} .combobox-option"
                )
            )
            > 0
        )

        enabled_options = driver.find_elements(
            by_cls.CSS_SELECTOR, f"#{listbox_id} .combobox-option:not(.is-disabled)"
        )
        if enabled_options:
            enabled_options[0].click()
            wait.until(
                lambda drv: "d-none"
                in (
                    drv.find_element(by_cls.ID, listbox_id).get_attribute("class") or ""
                )
            )
            selected_value = (
                driver.find_element(by_cls.ID, hidden_input_id).get_attribute("value")
                or ""
            ).strip()
            if selected_value:
                _step_pause()
                return selected_value

    raise AssertionError(
        f"No se pudo seleccionar ningún aeropuerto habilitado en #{text_input_id}"
    )


def _set_datetime_local(driver, element, iso_local_value: str) -> None:
    """Asigna fecha en <input type='datetime-local'> de forma independiente del locale."""
    driver.execute_script(
        "arguments[0].value = arguments[1];"
        "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));"
        "arguments[0].dispatchEvent(new Event('change', { bubbles: true }));",
        element,
        iso_local_value,
    )


def test_01_carga_home_e_indicadores_sistema(chrome_driver):
    """Abre Chrome en APP_BASE_URL y valida título, topbar, indicadores y pestañas."""
    _wd, _opts, By, _Keys, WebDriverWait, ec, _exc = _import_selenium()
    wait = WebDriverWait(chrome_driver, DEFAULT_WAIT_SECONDS)

    chrome_driver.get(APP_BASE_URL)
    wait.until(ec.visibility_of_element_located((By.CSS_SELECTOR, "header.navbar")))

    assert "AeroItinerarios" in chrome_driver.title

    brand_heading = wait.until(
        ec.visibility_of_element_located((By.CSS_SELECTOR, ".navbar-brand h1"))
    )
    assert "AeroItinerarios" in brand_heading.text

    gateway_indicator = wait.until(
        ec.visibility_of_element_located((By.ID, "gateway-indicator"))
    )
    wait.until(
        lambda drv: "Gateway Activo"
        in drv.find_element(By.CSS_SELECTOR, "#gateway-indicator .status-label").text
    )
    assert gateway_indicator.is_displayed()

    circuit_indicator = wait.until(
        ec.visibility_of_element_located((By.ID, "circuit-indicator"))
    )
    circuit_text = chrome_driver.find_element(By.ID, "circuit-indicator-text").text
    assert circuit_indicator.is_displayed()
    assert circuit_text.startswith("Circuit:")

    expected_tabs = (
        "tab-btn-planner",
        "tab-btn-map",
        "tab-btn-itineraries",
        "tab-btn-monitoring",
    )
    for tab_btn_id in expected_tabs:
        tab_btn = wait.until(ec.visibility_of_element_located((By.ID, tab_btn_id)))
        assert tab_btn.is_displayed()

    _wait_for_airports_loaded(chrome_driver, By, WebDriverWait)
    _step_pause()


def test_02_mapa_plotly_y_catalogo_aeropuertos(chrome_driver):
    """Cambia a la pestaña Mapa/Catálogo, valida render Plotly JS y tabla + filtros."""
    _wd, _opts, By, _Keys, WebDriverWait, ec, _exc = _import_selenium()
    wait = WebDriverWait(chrome_driver, DEFAULT_WAIT_SECONDS)

    tab_map_btn = wait.until(ec.element_to_be_clickable((By.ID, "tab-btn-map")))
    tab_map_btn.click()

    wait.until(ec.visibility_of_element_located((By.CSS_SELECTOR, "#tab-map.active")))
    _step_pause()

    # Esperar a que Plotly JS renderice el gráfico interactivo en #map
    plotly_wait = WebDriverWait(chrome_driver, max(DEFAULT_WAIT_SECONDS, 25))
    plotly_plot = plotly_wait.until(
        ec.presence_of_element_located(
            (By.CSS_SELECTOR, "#map.js-plotly-plot, #map .js-plotly-plot")
        )
    )
    assert plotly_plot is not None
    plotly_wait.until(
        ec.presence_of_element_located((By.CSS_SELECTOR, "#map .plot-container"))
    )

    # Verificar que la tabla del catálogo tiene filas reales cargadas
    wait.until(
        lambda drv: len(
            drv.find_elements(
                By.CSS_SELECTOR, "#airports-catalog-tbody .btn-select-airport"
            )
        )
        >= 2
    )
    initial_rows = chrome_driver.find_elements(
        By.CSS_SELECTOR, "#airports-catalog-tbody tr"
    )
    initial_count = len(initial_rows)
    assert initial_count >= 2

    # Probar búsqueda por código IATA ("BOG")
    search_input = wait.until(
        ec.visibility_of_element_located((By.ID, "airport-search-input"))
    )
    search_input.clear()
    search_input.send_keys("BOG")
    _step_pause()

    wait.until(
        lambda drv: len(
            drv.find_elements(By.CSS_SELECTOR, "#airports-catalog-tbody tr")
        )
        < initial_count
        and "BOG" in drv.find_element(By.ID, "airports-catalog-tbody").text
    )

    # Limpiar búsqueda con el botón clear
    clear_btn = wait.until(
        ec.element_to_be_clickable((By.ID, "btn-clear-airport-search"))
    )
    clear_btn.click()
    wait.until(
        lambda drv: len(
            drv.find_elements(By.CSS_SELECTOR, "#airports-catalog-tbody tr")
        )
        == initial_count
    )

    # Probar filtro por categoría (Internacionales -> Todos)
    intl_chip = wait.until(
        ec.element_to_be_clickable(
            (By.CSS_SELECTOR, '.chip[data-filter="internacional"]')
        )
    )
    intl_chip.click()
    _step_pause()
    assert "active" in (intl_chip.get_attribute("class") or "")
    results_label = chrome_driver.find_element(By.ID, "airport-results-count").text
    assert "resultados" in results_label
    assert (
        len(chrome_driver.find_elements(By.CSS_SELECTOR, "#airports-catalog-tbody tr"))
        >= 1
    )

    all_chip = wait.until(
        ec.element_to_be_clickable((By.CSS_SELECTOR, '.chip[data-filter="all"]'))
    )
    all_chip.click()
    wait.until(
        lambda drv: len(
            drv.find_elements(By.CSS_SELECTOR, "#airports-catalog-tbody tr")
        )
        == initial_count
    )


def test_03_crear_y_eliminar_itinerario_flujo_completo(chrome_driver):
    """Crea un itinerario con combobox predictivos, lo valida en Mis Itinerarios y lo elimina."""
    _wd, _opts, By, Keys, WebDriverWait, ec, _exc = _import_selenium()
    wait = WebDriverWait(chrome_driver, DEFAULT_WAIT_SECONDS)

    planner_tab_btn = wait.until(ec.element_to_be_clickable((By.ID, "tab-btn-planner")))
    planner_tab_btn.click()
    wait.until(
        ec.visibility_of_element_located((By.CSS_SELECTOR, "#tab-planner.active"))
    )
    _wait_for_airports_loaded(chrome_driver, By, WebDriverWait)

    # Seleccionar origen y destino distintos usando los combobox predictivos
    origin_id = _select_combobox_airport(
        chrome_driver,
        by_cls=By,
        keys_cls=Keys,
        wait_cls=WebDriverWait,
        ec_mod=ec,
        text_input_id="origin_airport_input",
        listbox_id="origin-combobox-listbox",
        hidden_input_id="origin_airport",
        toggle_btn_id="origin-toggle-btn",
        search_queries=("BOG", "CTG", "CLO", ""),
    )
    dest_id = _select_combobox_airport(
        chrome_driver,
        by_cls=By,
        keys_cls=Keys,
        wait_cls=WebDriverWait,
        ec_mod=ec,
        text_input_id="destination_airport_input",
        listbox_id="destination-combobox-listbox",
        hidden_input_id="destination_airport",
        toggle_btn_id="destination-toggle-btn",
        search_queries=("MDE", "CLO", "BAQ", ""),
    )
    assert origin_id != dest_id

    route_warning_classes = (
        chrome_driver.find_element(By.ID, "route-warning").get_attribute("class") or ""
    )
    assert "d-none" in route_warning_classes

    # Llenar pasajero, fecha futura y duración
    passenger_input = wait.until(ec.visibility_of_element_located((By.ID, "user_name")))
    passenger_input.clear()
    passenger_input.send_keys(PASSENGER_NAME)
    wait.until(
        lambda drv: PASSENGER_NAME in drv.find_element(By.ID, "bp-passenger-name").text
    )

    future_dt = (datetime.now(UTC) + timedelta(days=5)).strftime("%Y-%m-%dT10:30")
    departure_input = chrome_driver.find_element(By.ID, "departure_date")
    _set_datetime_local(chrome_driver, departure_input, future_dt)

    duration_input = chrome_driver.find_element(By.ID, "duration_minutes")
    duration_input.clear()
    duration_input.send_keys("75")
    wait.until(lambda drv: "75" in drv.find_element(By.ID, "bp-duration-tag").text)
    _step_pause()

    # Enviar formulario y esperar confirmación (toast + recarga completa)
    submit_btn = wait.until(ec.element_to_be_clickable((By.ID, "btn-submit")))
    submit_btn.click()

    toast_el = wait.until(
        ec.visibility_of_element_located(
            (By.CSS_SELECTOR, "#toast-container .toast.toast-success")
        )
    )
    assert "Itinerario Confirmado" in toast_el.text
    wait.until(ec.element_to_be_clickable((By.ID, "btn-submit")))
    _step_pause()

    # Navegar a "Mis Itinerarios" y verificar que aparece el itinerario creado
    itineraries_tab_btn = wait.until(
        ec.element_to_be_clickable((By.ID, "tab-btn-itineraries"))
    )
    itineraries_tab_btn.click()
    wait.until(
        ec.visibility_of_element_located((By.CSS_SELECTOR, "#tab-itineraries.active"))
    )

    itinerary_search = wait.until(
        ec.visibility_of_element_located((By.ID, "itinerary-search-input"))
    )
    itinerary_search.clear()
    itinerary_search.send_keys(PASSENGER_NAME)
    _step_pause()

    def _matching_cards(drv):
        cards = drv.find_elements(
            By.CSS_SELECTOR, "#itineraries-cards-view .itinerary-item-card"
        )
        return [
            card
            for card in cards
            if PASSENGER_NAME
            in card.find_element(By.CSS_SELECTOR, ".passenger-info h4").text
        ]

    wait.until(lambda drv: len(_matching_cards(drv)) >= 1)
    matched_cards = _matching_cards(chrome_driver)
    before_delete_count = len(matched_cards)
    target_card = matched_cards[0]
    target_uuid_text = target_card.find_element(
        By.CSS_SELECTOR, ".uuid-tag"
    ).text.strip()

    # Abrir modal de eliminación y confirmar
    delete_btn = target_card.find_element(By.CSS_SELECTOR, ".btn-delete-itinerary")
    delete_btn.click()

    wait.until(
        lambda drv: "d-none"
        not in (drv.find_element(By.ID, "delete-modal").get_attribute("class") or "")
    )
    modal_passenger = chrome_driver.find_element(By.ID, "modal-passenger-name").text
    assert PASSENGER_NAME in modal_passenger
    _step_pause()

    confirm_delete_btn = wait.until(
        ec.element_to_be_clickable((By.ID, "btn-confirm-delete"))
    )
    confirm_delete_btn.click()

    wait.until(
        lambda drv: "d-none"
        in (drv.find_element(By.ID, "delete-modal").get_attribute("class") or "")
    )
    wait.until(lambda drv: len(_matching_cards(drv)) < before_delete_count)

    remaining_uuids = [
        card.find_element(By.CSS_SELECTOR, ".uuid-tag").text.strip()
        for card in _matching_cards(chrome_driver)
    ]
    assert target_uuid_text not in remaining_uuids

    itinerary_search.clear()
    _step_pause()


def test_04_monitoreo_y_auditoria_notificaciones(chrome_driver):
    """Navega a Monitoreo & Auditoría y valida paneles de salud y tabla de notificaciones."""
    _wd, _opts, By, _Keys, WebDriverWait, ec, _exc = _import_selenium()
    wait = WebDriverWait(chrome_driver, DEFAULT_WAIT_SECONDS)

    monitoring_tab_btn = wait.until(
        ec.element_to_be_clickable((By.ID, "tab-btn-monitoring"))
    )
    monitoring_tab_btn.click()
    wait.until(
        ec.visibility_of_element_located((By.CSS_SELECTOR, "#tab-monitoring.active"))
    )

    refresh_btn = wait.until(
        ec.element_to_be_clickable((By.ID, "btn-refresh-monitoring"))
    )
    refresh_btn.click()
    _step_pause()

    health_card_ids = (
        "card-health-gateway",
        "card-health-airport",
        "card-health-itinerary",
        "card-health-notification",
    )
    for card_id in health_card_ids:
        card = wait.until(ec.visibility_of_element_located((By.ID, card_id)))
        assert card.is_displayed()

    wait.until(
        lambda drv: drv.find_element(By.ID, "gw-health-status").text.strip()
        == "OPERATIVO"
    )
    wait.until(lambda drv: drv.find_element(By.ID, "gw-latency").text.strip() != "--")

    cb_state = chrome_driver.find_element(By.ID, "cb-health-state").text.strip()
    assert cb_state in {"CLOSED", "OPEN", "HALF_OPEN"}
    assert chrome_driver.find_element(By.ID, "redis-metric-status").text.strip() != ""
    assert chrome_driver.find_element(By.ID, "db-metric-status").text.strip() != ""
    assert chrome_driver.find_element(By.ID, "notifs-metric-total").text.strip() != ""

    notifications_table = wait.until(
        ec.visibility_of_element_located((By.ID, "notifications-table"))
    )
    assert notifications_table.is_displayed()

    log_rows = wait.until(
        lambda drv: drv.find_elements(By.CSS_SELECTOR, "#notifications-log-list tr")
    )
    assert len(log_rows) >= 1
    assert any(row.text.strip() for row in log_rows)
    _step_pause()
