import time
import logging

from config import get_auth
from config import NEXUS_API_URL, LAUNCH_INTERVAL

from prometheus_client import start_http_server

from metrics.repo_status import fetch_repositories_metrics
from metrics.repo_size import fetch_repository_metrics
from metrics.blobs_size import fetch_blob_metrics
from metrics.docker_tags import fetch_docker_tags_metrics
from metrics.utlis.tasks import fetch_task_metrics, get_json_from_nexus


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def main():
    start_http_server(8000)
    auth = get_auth()

    logging.info("Метрики VictoriaMetrics доступны на :8000")

    while True:
        logging.info("Запуск сбора статуса репозиториев типа Proxy...")
        fetch_repositories_metrics(NEXUS_API_URL, auth)

        logging.info("Запуск сбора размера блобов...")
        fetch_blob_metrics(NEXUS_API_URL, auth)

        logging.info("Получение задач Nexus...")
        task_data = get_json_from_nexus(NEXUS_API_URL, "/service/rest/v1/tasks", auth)

        logging.info("Запуск сбора размера репозиториев...")
        fetch_repository_metrics(NEXUS_API_URL, auth)

        logging.info("Запуск сбора задач...")
        fetch_task_metrics(task_data)

        logging.info("Запуск сбора Docker тегов...")
        fetch_docker_tags_metrics()

        time.sleep(LAUNCH_INTERVAL)


if __name__ == "__main__":
    main()
