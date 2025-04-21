import requests
import logging
from prometheus_client import Gauge
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Метрики
BLOB_STORAGE_USAGE = Gauge(
    "nexus_blob_storage_usage",
    "Total used and available space in Nexus blob stores",
    ["blob_name", "metric_type", "blob_type", "blob_count"],
)


def fetch_blob_metrics(nexus_url, auth):
    """Получает список blobstore и обновляет метрики."""
    logging.info("Получение списка blobstores...")

    try:
        response = requests.get(
            f"{nexus_url}/service/rest/v1/blobstores", auth=auth, verify=False, timeout=10
        )
        response.raise_for_status()
        blobstores = response.json()

        # Очистка всех старых лейблов — влияет только на runtime, история остаётся в TSDB (например, в VictoriaMetrics)
        BLOB_STORAGE_USAGE.clear()

        for blob in blobstores:
            used_size = blob["totalSizeInBytes"]
            available_size = blob["availableSpaceInBytes"]

            logging.info(
                f"Blobstore '{blob['name']}': used={used_size}, available={available_size}, type={blob['type']}, count={blob['blobCount']}"
            )

            BLOB_STORAGE_USAGE.labels(
                blob_name=blob["name"],
                metric_type="used",
                blob_count=blob["blobCount"],
                blob_type=blob["type"],
            ).set(used_size)

            BLOB_STORAGE_USAGE.labels(
                blob_name=blob["name"],
                metric_type="available",
                blob_count=blob["blobCount"],
                blob_type=blob["type"],
            ).set(available_size)

    except requests.exceptions.ConnectionError:
        logging.error("❌ Не удалось подключиться к API Nexus. Проверьте доступность сервера.")
    except requests.exceptions.Timeout:
        logging.error("⏳ Время ожидания подключения к API Nexus истекло.")
    except requests.exceptions.HTTPError as e:
        logging.error(f"⚠️ Ошибка HTTP при запросе к API Nexus: {e.response.status_code} - {e.response.reason}")
    except requests.exceptions.RequestException as e:
        logging.error(f"❗ Произошла ошибка при запросе к API Nexus: {e}")
