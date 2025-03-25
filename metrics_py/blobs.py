import requests
import humanize
from prometheus_client import Gauge

# Метрики
BLOB_STORAGE_USAGE = Gauge(
    "nexus_blob_storage_usage",
    "Total used and available space in Nexus blob stores",
    ["blob_name", "metric_type"]
)


def fetch_blob_metrics(nexus_url, auth):
    """Получает список blobstore и обновляет метрики."""
    try:
        response = requests.get(f"{nexus_url}/service/rest/v1/blobstores", auth=auth)
        response.raise_for_status()
        blobstores = response.json()

        for blob in blobstores:
            used_size = blob["totalSizeInBytes"]
            available_size = blob["availableSpaceInBytes"]

            print(f"Blobstore: {blob['name']}")
            print(f"  - Занято: {humanize.naturalsize(used_size, binary=True)}")
            print(f"  - Доступно: {humanize.naturalsize(available_size, binary=True)}")

            BLOB_STORAGE_USAGE.labels(blob_name=blob["name"], metric_type="used").set(used_size)
            BLOB_STORAGE_USAGE.labels(blob_name=blob["name"], metric_type="available").set(available_size)

    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении данных о blobstore: {e}")
