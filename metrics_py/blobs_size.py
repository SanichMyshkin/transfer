import requests
import logging
from prometheus_client import Gauge
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


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
            f"{nexus_url}/service/rest/v1/blobstores", auth=auth, verify=False
        )
        response.raise_for_status()
        blobstores = response.json()

        for blob in blobstores:
            used_size = blob["totalSizeInBytes"]
            available_size = blob["availableSpaceInBytes"]

            logging.info(
                f"Blobstore '{blob['name']}': used={used_size}, available={available_size}"
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

    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при получении данных о blobstore: {e}")
