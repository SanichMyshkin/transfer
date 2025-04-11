import requests
import socket
import logging
import urllib3
from prometheus_client import Gauge

# Отключение предупреждений об SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Прометеус метрики
REPO_STATUS = Gauge(
    "nexus_proxy_repo_status",
    "Статус репозитория в Nexus",
    [
        "repo_name",
        "repo_format",
        "nexus_url",
        "remote_url",
        "nexus_status",
        "remote_status",
    ],
)

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_all_repositories(nexus_url, auth):
    """Получает список прокси-репозиториев из Nexus"""
    endpoint = f"{nexus_url}/service/rest/v1/repositories"

    try:
        response = requests.get(endpoint, auth=auth, timeout=10, verify=False)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"❌ Ошибка при запросе Nexus: {e}")
        return []

    repos = response.json()
    return [
        {
            "name": repo["name"],
            "url": f"{nexus_url}service/rest/repository/browse/{repo['name']}/",
            "type": repo["format"],
            "remote": (
                f"{repo.get('attributes', {}).get('proxy', {}).get('remoteUrl', '')}/v2"
                if repo["format"] == "docker"
                else repo.get("attributes", {}).get("proxy", {}).get("remoteUrl", "")
            ),
        }
        for repo in repos
        if repo["type"] == "proxy"
    ]


def is_domain_resolvable(url):
    """Проверяет разрешение доменного имени"""
    try:
        domain = url.split("/")[2]
        socket.gethostbyname(domain)
        return True
    except Exception:
        logger.warning(f"❌ Невозможно разрешить домен: {url}")
        return False


def check_url_status(name, url, auth=None, check_dns=False):
    """Универсальная проверка URL"""
    if check_dns and not is_domain_resolvable(url):
        return "❌"

    try:
        response = requests.get(url, auth=auth, timeout=10, verify=False)
        if response.status_code in (200, 401):
            logger.info(f"✅ {name} доступен: {response.status_code}")
            return f"✅ ({response.status_code})" if response.status_code != 200 else "✅"
        else:
            logger.warning(f"⚠️ {name} вернул {response.status_code}")
            return f"❌ ({response.status_code})"
    except requests.RequestException as e:
        logger.warning(f"❌ Ошибка доступа к {name}: {e}")
        return "❌"


def update_prometheus_metrics(repo, nexus_status, remote_status):
    """Обновляет метрику Prometheus"""
    overall_status = "✅ Рабочий" if "✅" in nexus_status and "✅" in remote_status else "❌ Проблема"

    REPO_STATUS.labels(
        repo_name=repo["name"],
        repo_format=repo["type"],
        nexus_url=repo["url"],
        remote_url=repo["remote"] or "",
        nexus_status=nexus_status,
        remote_status=remote_status,
    ).set(1 if overall_status == "✅ Рабочий" else 0)

    logger.info(f"Статус репозитория {repo['name']}: {overall_status}")
    return {
        "repo": repo["name"],
        "nexus": nexus_status,
        "remote": remote_status,
        "status": overall_status,
    }


def fetch_status(repo, auth):
    """Проверяет статус Nexus и remote репозитория"""
    nexus_status = check_url_status(f"{repo['name']} (Nexus)", repo["url"], auth=auth)
    remote_status = (
        check_url_status(f"{repo['name']} (remote)", repo["remote"], check_dns=True)
        if repo["remote"]
        else "❌"
    )
    return update_prometheus_metrics(repo, nexus_status, remote_status)


def fetch_repositories_metrics(nexus_url, auth):
    """Проверяет все прокси-репозитории"""
    repos = get_all_repositories(nexus_url, auth)
    return [fetch_status(repo, auth) for repo in repos]
