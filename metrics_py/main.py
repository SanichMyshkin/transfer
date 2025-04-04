import os
import time
import logging
from datetime import datetime
from prometheus_client import start_http_server
from dotenv import load_dotenv
from proxyrepo_status import fetch_repositories_metrics
from repo_size import fetch_repository_sizes
from blobs_size import fetch_blob_metrics

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

load_dotenv()

NEXUS_API_URL = os.getenv("NEXUS_API_URL")
NEXUS_USERNAME = os.getenv("NEXUS_USERNAME")
NEXUS_PASSWORD = os.getenv("NEXUS_PASSWORD")
TIME_RUN_STORAGE = os.getenv("TIME_RUN_STORAGE")
DB_URL = os.getenv("DATABASE_URL")


def get_auth():
    """Возвращает кортеж с логином и паролем для Nexus"""
    return (NEXUS_USERNAME, NEXUS_PASSWORD)


def should_run_blob_metrics():
    return datetime.now().strftime("%H:%M") == TIME_RUN_STORAGE


def main():
    start_http_server(8000)
    auth = get_auth()
    logging.info("Метрики VictoriaMetrics доступны на :8000")

    while True:
        logging.info("Запуск сбора статуса репозиториев...")
        
        # Вызываем функцию для сбора статусов
        fetch_repositories_metrics(NEXUS_API_URL, auth)

        if should_run_blob_metrics():
            logging.info("Запуск сбора размера репозиториев и блобов...")
            fetch_blob_metrics(NEXUS_API_URL, auth)
            fetch_repository_sizes(NEXUS_API_URL, auth)

        time.sleep(30)


if __name__ == "__main__":
    main()
