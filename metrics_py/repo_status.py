import requests
import logging
from prometheus_client import Gauge
from url_normalize import url_normalize
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
        response = requests.get(url, timeout=15, verify=False)
        response.raise_for_status()  # Выбросит ошибку для 4xx и 5xx
        return response.status_code
    except requests.exceptions.HTTPError as http_err:
        logging.warning(f"HTTP ошибка при обращении к {url}: {http_err}")
    except requests.exceptions.RequestException as req_err:
        logging.error(f"Ошибка сети при обращении к {url}: {req_err}")
    return 0


def fetch_repositories_metrics(nexus_url, auth):
    logging.info("Получение списка репозиториев...")

    try:
        response = requests.get(f"{nexus_url}/service/rest/v1/repositories", auth=auth, verify=False)
        response.raise_for_status()
        repositories = response.json()

        for repo in repositories:
            repo_name = repo.get("name", "unknown")
            repo_type = repo.get("type", "unknown")
            repo_format = repo.get("format", "unknown")
            repo_url = repo.get("url")

            if repo_url:
                normal_url = url_normalize(repo_url.rstrip("/"))
                status_code = check_url_status(normal_url + "/")
            else:
                normal_url = None
                status_code = 0

            logging.info(f"Репозиторий '{repo_name}': status={status_code}")

            # Проверка Proxy Remote URL
            remote_url = repo.get("attributes", {}).get("proxy", {}).get("remoteUrl", None)
            if repo_type == "proxy" and remote_url:
                remote_status = check_url_status(url_normalize(remote_url))
                REMOTE_STATUS.labels(repo_name=repo_name, remote_url=remote_url).set(remote_status)
                logging.info(f"→ Proxy '{repo_name}' remote status: {remote_status}")

            # Запись в метрику
            REPO_STATUS.labels(
                repo_name=repo_name,
                repo_type=repo_type,
                repo_format=repo_format,
                repo_url=repo_url if repo_url else "unknown",
            ).set(status_code)

    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при получении репозиториев: {e}")
