import time
import logging

from config import get_auth
from config import NEXUS_API_URL, LAUNCH_INTERVAL

from prometheus_client import start_http_server

from metrics.utlis.api import get_from_nexus
from metrics.repo_status import fetch_repositories_metrics
from metrics.repo_size import fetch_repository_metrics
from metrics.blobs_size import fetch_blob_metrics
from metrics.docker_tags import fetch_docker_tags_metrics
from metrics.tasks import fetch_task_metrics
from metrics.docker_ports import fetch_docker_ports_metrics
from metrics.certificates import update_cert_match_metrics

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(module)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    start_http_server(8000)
    auth = get_auth()

    logger.info("Метрики VictoriaMetrics доступны на :8000")

    while True:
        logger.info("Запуск сбора статуса репозиториев типа Proxy...")
        fetch_repositories_metrics(NEXUS_API_URL, auth)

        logger.info("Запуск сбора размера блобов...")
        fetch_blob_metrics(NEXUS_API_URL, auth)

        logger.info("Получение задач Nexus...")
        task_data = get_from_nexus(NEXUS_API_URL, "tasks", auth)

        logger.info("Запуск сбора размера репозиториев...")
        fetch_repository_metrics(task_data)

        logger.info("Запуск сбора задач...")
        fetch_task_metrics(task_data)

        logger.info("Запуск сбора Docker тегов...")
        fetch_docker_tags_metrics()

        logger.info("Запуск сбора Docker портов...")
        fetch_docker_ports_metrics()

        logger.info("Запуск сбора SSL сертификатов из Truststore...")
        update_cert_match_metrics(NEXUS_API_URL, auth)

        time.sleep(LAUNCH_INTERVAL)


if __name__ == "__main__":
    main()
