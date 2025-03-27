import requests
import logging
from prometheus_client import Gauge
from url_normalize import url_normalize

# Метрики
REPO_STATUS = Gauge(
    "nexus_repo_status",
    "HTTP status of Nexus repositories",
    ["repo_name", "repo_type", "repo_format", "repo_url"],
)

REMOTE_STATUS = Gauge(
    "nexus_proxy_remote_status",
    "Direct status code from remoteUrl of proxy repo",
    ["repo_name", "remote_url"],
)


def check_url_status(url):
    try:
        response = requests.get(url, timeout=15)
        return response.status_code
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при обращении к {url}: {e}")
        return 0


def fetch_repositories_metrics(nexus_url, auth):
    logging.info("Получение списка репозиториев...")

    try:
        response = requests.get(f"{nexus_url}/service/rest/v1/repositories", auth=auth)
        response.raise_for_status()
        repositories = response.json()

        for repo in repositories:
            # normal_url = url_normalize(nexus_url + "/service/rest/v1/search?repository="+ repo.get("name"))# так посути проверяет что внутри реп
            normal_url = url_normalize(repo.get("url"))  # так выдает 404 в raw
            status_code = check_url_status(normal_url + "/")

            repo_name = repo.get("name", "unknown")
            repo_type = repo.get("type", "unknown")
            repo_format = repo.get("format", "unknown")
            repo_url = repo.get("url", "unknown")

            logging.info(f"Репозиторий '{repo_name}': status={status_code}")

            remote_url = repo.get("attributes", {}).get("proxy", {}).get("remoteUrl")
            if repo_type == "proxy" and remote_url:
                remote_status = check_url_status(url_normalize(remote_url))
                REMOTE_STATUS.labels(repo_name=repo_name, remote_url=remote_url).set(
                    remote_status
                )
                logging.info(f"→ Proxy '{repo_name}' remote status: {remote_status}")

            REPO_STATUS.labels(
                repo_name=repo_name,
                repo_type=repo_type,
                repo_format=repo_format,
                repo_url=repo_url,
            ).set(status_code)

    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при получении репозиториев: {e}")
