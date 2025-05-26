import logging
from prometheus_client import Gauge

from database.ports_query import fetch_docker_ports

# Метрика Prometheus
docker_repo_port_gauge = Gauge(
    "docker_repository_port_info",
    "Информация о портах и удалённых адресах docker-репозиториев Nexus",
    ["repository_name", "http_port", "remote_url", "repo_type"],
)


def fetch_docker_ports_metrics() -> None:
    try:
        result = fetch_docker_ports()
        logging.info(f"Получено {len(result)} docker-репозиториев из базы данных.")

        docker_repo_port_gauge.clear()

        for entry in result:
            repo_name = entry["repository_name"]
            http_port = entry["http_port"]
            remote_url = entry["remote_url"]

            logging.info(
                f"Репозиторий: {repo_name}, Порт: {http_port}, Удалённый URL: {remote_url}"
            )

            docker_repo_port_gauge.labels(
                repository_name=repo_name,
                http_port=str(http_port) if http_port is not None else "None",
                remote_url=remote_url if remote_url else "None",
                repo_type="Proxy" if remote_url else "Hosted",
            ).set(1)

        logging.info("Метрики по портам docker-репозиториев успешно обновлены.")

    except Exception as e:
        logging.error(f"Ошибка при сборе метрик портов docker-репозиториев: {e}")
