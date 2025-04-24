import logging
import requests
import urllib3
from prometheus_client import Gauge

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Prometheus метрика
BLOB_STORAGE_USAGE = Gauge(
    "nexus_blob_storage_usage",
    "Total used and available space in Nexus blob stores",
    ["blob_name", "metric_type", "blob_type", "blob_count"],
)


def get_blobstores(nexus_url: str, auth: tuple) -> list:
    """Получает список blobstores из Nexus API."""
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=3)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    response = session.get(
        f"{nexus_url}/service/rest/v1/blobstores",
        auth=auth,
        verify=False,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def update_metrics(blobstores: list) -> None:
    """Обновляет метрики Prometheus по полученным blobstores."""
    BLOB_STORAGE_USAGE.clear()
    for blob in blobstores:
        BLOB_STORAGE_USAGE.labels(
            blob_name=blob["name"],
            metric_type="used",
            blob_count=str(blob["blobCount"]),
            blob_type=blob["type"],
        ).set(blob["totalSizeInBytes"])

        BLOB_STORAGE_USAGE.labels(
            blob_name=blob["name"],
            metric_type="available",
            blob_count=str(blob["blobCount"]),
            blob_type=blob["type"],
        ).set(blob["availableSpaceInBytes"])

        logging.info(
            f"[{blob['name']}] used: {blob['totalSizeInBytes']} | available: {blob['availableSpaceInBytes']} | type: {blob['type']} | count: {blob['blobCount']}"
        )


def fetch_blob_metrics(nexus_url: str, auth: tuple) -> None:
    """Основная функция — получение blobstore и обновление метрик."""
    logging.info("Запрос blobstore из Nexus...")
    try:
        blobstores = get_blobstores(nexus_url, auth)
        update_metrics(blobstores)
    except requests.exceptions.ConnectionError:
        logging.error("❌ Не удалось подключиться к API Nexus.")
    except requests.exceptions.Timeout:
        logging.error("⏳ Таймаут при подключении к API Nexus.")
    except requests.exceptions.HTTPError as e:
        logging.error(f"⚠️ HTTP ошибка: {e.response.status_code} - {e.response.reason}")
    except requests.exceptions.RequestException as e:
        logging.error(f"❗ Ошибка запроса: {e}")
