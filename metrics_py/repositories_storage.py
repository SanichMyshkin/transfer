import requests
import logging
from prometheus_client import Gauge
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# Метрика для размеров репозиториев
REPO_STORAGE = Gauge(
    "nexus_repo_size",
    "Total size of Nexus repositories in bytes",
    ["repo_name", "repo_type"],
)


def nexus_api_call(nexus_url, endpoint, auth):
    url = f"{nexus_url}{endpoint}"
    try:
        response = requests.get(url, auth=auth, verify=False)
        if response.status_code == 200:
            return response.json()
        else:
            logging.warning(f"Ошибка при запросе {endpoint}: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при вызове {endpoint}: {e}")
        return None


def get_repo_size(nexus_url, repo_name, auth):
    total_size = 0
    continuation_token = None

    while True:
        endpoint = f"/service/rest/v1/components?repository={repo_name}"
        if continuation_token:
            endpoint += f"&continuationToken={continuation_token}"

        response = nexus_api_call(nexus_url, endpoint, auth)
        if not response:
            break

        for component in response.get("items", []):
            for asset in component.get("assets", []):
                total_size += asset.get("fileSize", 0)

        continuation_token = response.get("continuationToken")
        if not continuation_token:
            break

    logging.info(f"Репозиторий '{repo_name}': size={total_size}")
    return total_size


def fetch_repository_sizes(nexus_url, auth):
    logging.info("Получение списка репозиториев для расчета размера...")

    repositories = nexus_api_call(nexus_url, "/service/rest/v1/repositories", auth)

    if repositories:
        for repo in repositories:
            repo_name = repo["name"]
            repo_type = repo.get("type", "unknown")
            repo_size = get_repo_size(nexus_url, repo_name, auth)

            REPO_STORAGE.labels(repo_name=repo_name, repo_type=repo_type).set(repo_size)
