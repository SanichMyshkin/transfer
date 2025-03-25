import os
import time
from prometheus_client import start_http_server
from dotenv import load_dotenv
from repositories import fetch_repositories_metrics
from blobs import fetch_blob_metrics

load_dotenv()

NEXUS_API_URL = os.getenv('NEXUS_API_URL')
NEXUS_USERNAME = os.getenv("NEXUS_USERNAME")
NEXUS_PASSWORD = os.getenv("NEXUS_PASSWORD")


def get_auth():
    """Возвращает данные для аутентификации."""
    return (NEXUS_USERNAME, NEXUS_PASSWORD)


def main():
    start_http_server(8000)
    auth = get_auth()

    while True:
        fetch_repositories_metrics(NEXUS_API_URL, auth)
        fetch_blob_metrics(NEXUS_API_URL, auth)
        time.sleep(30)


if __name__ == "__main__":
    main()
