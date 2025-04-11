import requests
import socket
import logging
import urllib3
from prometheus_client import Gauge
from requests.exceptions import RequestException

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

REPO_TYPE_COUNT = Gauge(
    "nexus_repo_type_count",
    "Количество репозиториев по типу",
    ["repo_type"],
)

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Заголовки для имитации браузера
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def get_all_repositories(nexus_url, auth):
    """Получает список всех репозиториев из Nexus"""
    endpoint = f"{nexus_url}/service/rest/v1/repositories"

    try:
        response = requests.get(endpoint, auth=auth, timeout=10, verify=False, headers=HEADERS)
        response.raise_for_status()
    except RequestException as e:
        logger.error(f"❌ Ошибка при запросе Nexus: {e}")
        return []

    repos = response.json()

    # Подсчёт количества репозиториев по типам
    type_counts = {}
    for repo in repos:
        repo_type = repo.get("type", "unknown")
        type_counts[repo_type] = type_counts.get(repo_type, 0) + 1

    for repo_type, count in type_counts.items():
        REPO_TYPE_COUNT.labels(repo_type=repo_type).set(count)

    logger.info(f"🔍 Найдено репозиториев: {sum(type_counts.values())} (из них proxy: {type_counts.get('proxy', 0)})")

    return [
        {
            "name": repo["name"],
            "url": f"{nexus_url}service/rest/repository/browse/{repo['name']}/",
            "type": repo["format"],
            "remote": repo.get("attributes", {}).get("proxy", {}).get("remoteUrl", "")
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
    if not url:
        return "❌ empty url"

    if check_dns and not is_domain_resolvable(url):
        return "❌ domain not resolvable"

    try:
        response = requests.get(url, auth=auth, timeout=10, verify=False, headers=HEADERS, allow_redirects=True)

        # Проверка на редиректы
        if response.history:
            logger.warning(f"⚠️ {name} имел редиректы: {response.history}")

        status_code = response.status_code
        if status_code in (200, 401):
            logger.info(f"✅ {name} доступен: {status_code}")
            return f"✅ redirect {status_code}" if response.history else f"✅ {status_code}"
        else:
            logger.warning(f"❌ {name} вернул {status_code}")
            return f"❌ {status_code}"

    except RequestException as e:
        logger.warning(f"❌ Ошибка доступа к {name}: {e}")
        return "❌ exception"


def update_prometheus_metrics(repo, nexus_status, remote_status):
    """Обновляет метрику Prometheus"""
    overall_status = "✅ Рабочий" if nexus_status.startswith("✅") and remote_status.startswith("✅") else "❌ Проблема"

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


def check_remote_docker(repo):
    """Специальная проверка Docker remote"""
    base_status = check_url_status(f"{repo['name']} (remote base)", repo["remote"], check_dns=True)
    if base_status.startswith("✅"):
        return base_status

    # Пробуем добавить /v2
    docker_v2_url = repo["remote"].rstrip("/") + "/v2"
    v2_status = check_url_status(f"{repo['name']} (remote /v2)", docker_v2_url, check_dns=True)
    return v2_status


def fetch_status(repo, auth):
    """Проверяет статус Nexus и remote репозитория"""
    nexus_status = check_url_status(f"{repo['name']} (Nexus)", repo["url"], auth=auth)

    if repo["remote"]:
        if repo["type"] == "docker":
            remote_status = check_remote_docker(repo)
        else:
            remote_status = check_url_status(f"{repo['name']} (remote)", repo["remote"], check_dns=True)
    else:
        remote_status = "❌ no remote url"

    return update_prometheus_metrics(repo, nexus_status, remote_status)


def fetch_repositories_metrics(nexus_url, auth):
    """Проверяет все прокси-репозитории"""
    repos = get_all_repositories(nexus_url, auth)
    return [fetch_status(repo, auth) for repo in repos]
