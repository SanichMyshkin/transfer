import requests
import socket
import logging
from prometheus_client import Gauge

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

# Настройка логирования
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def get_all_repositories(nexus_url, auth):
    """Получает список только прокси-репозиторов из Nexus"""
    nexus_endpoint = f"{nexus_url}/service/rest/v1/repositories"
    
    try:
        response = requests.get(nexus_endpoint, auth=auth, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"❌ Ошибка при запросе Nexus: {e}")
        return []

    repos = response.json()
    result = []

    for repo in repos:
        if repo["type"] == "proxy":
            repo_url = f"{nexus_url}service/rest/repository/browse/{repo['name']}/"

            if repo["format"] == "docker":
                remote_url = f"{repo.get('attributes', {}).get('proxy', {}).get('remoteUrl', '')}/v2"
            else:
                remote_url = repo.get("attributes", {}).get("proxy", {}).get("remoteUrl", "")

            result.append(
                {
                    "name": repo["name"],
                    "url": repo_url,
                    "type": repo["format"],
                    "remote": remote_url if repo.get("type") == "proxy" else None,
                }
            )
    return result


def is_domain_resolvable(url):
    """Проверяет, можно ли разрешить доменное имя"""
    try:
        domain = url.split("/")[2]
        socket.gethostbyname(domain)
        return True
    except Exception:
        logger.warning(f"❌ Невозможно разрешить домен: {url}")
        return False


def fetch_status(repo, auth):
    """Проверка доступности репозитория и его удаленного источника"""
    nexus_status = "❌"
    remote_status = "❌"

    # Проверка локального репозитория
    try:
        response = requests.get(repo["url"], auth=auth, timeout=10)
        if response.status_code == 200:
            nexus_status = "✅"
            logger.info(f"✅ Репозиторий {repo['name']} доступен в Nexus.")
        else:
            logger.warning(f"⚠️ {repo['name']} (Nexus) вернул {response.status_code}")
    except requests.RequestException:
        logger.warning(f"❌ Ошибка доступа к Nexus для {repo['name']}")

    # Проверка удалённого источника
    if repo["remote"] and is_domain_resolvable(repo["remote"]):
        try:
            response = requests.get(repo["remote"], timeout=10)
            if response.status_code == 200:
                remote_status = "✅"
                logger.info(f"✅ Репозиторий {repo['name']} доступен по удалённому источнику.")
            elif response.status_code == 401 and repo["type"] == "docker":
                remote_status = "✅ (401)"
                logger.info(f"✅ Репозиторий {repo['name']} вернул 401 (норма для Docker).")
            else:
                logger.warning(f"⚠️ {repo['name']} (remote) вернул {response.status_code}")
        except requests.RequestException:
            logger.warning(f"❌ Ошибка доступа к remote для {repo['name']}")

    if repo["type"] == "docker" and remote_status == "✅ (401)":
        overall_status = "✅ Рабочий"
    else:
        overall_status = (
            "✅ Рабочий" if nexus_status == "✅" and remote_status == "✅" else "❌ Проблема"
        )

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


def check_all_repositories(nexus_url, auth):
    """Проверяет все прокси-репозитории последовательно"""
    repos = get_all_repositories(nexus_url, auth)
    results = []
    for repo in repos:
        result = fetch_status(repo, auth)
        results.append(result)
    return results


def fetch_repositories_metrics(nexus_url, auth):
    """Главная функция для внешнего использования"""
    return check_all_repositories(nexus_url, auth)
