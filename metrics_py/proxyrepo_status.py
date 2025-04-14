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

REPO_COUNT = Gauge("nexus_repo_count", "Количество репозиториев по типу", ["repo_type"])

# Логирование
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_all_repositories(nexus_url, auth):
    """Получает список репозиториев из Nexus"""
    endpoint = f"{nexus_url}/service/rest/v1/repositories"

    try:
        response = requests.get(endpoint, auth=auth, timeout=10, verify=False)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"❌ Ошибка при запросе Nexus: {e}")
        return []

    repos = response.json()

    # Подсчёт репозиториев по типам
    type_counts = {}
    for repo in repos:
        repo_type = repo.get("type", "unknown")
        type_counts[repo_type] = type_counts.get(repo_type, 0) + 1

    for repo_type, count in type_counts.items():
        REPO_COUNT.labels(repo_type=repo_type).set(count)
        logger.info(f"📊 Репозиториев типа '{repo_type}': {count}")

    proxy_repos = [
        {
            "name": repo["name"],
            "url": f"{nexus_url}service/rest/repository/browse/{repo['name']}/",
            "type": repo["format"],
            "remote": repo.get("attributes", {}).get("proxy", {}).get("remoteUrl", ""),
        }
        for repo in repos
        if repo["type"] == "proxy"
    ]

    logger.info(f"🔍 Найдено proxy-репозиториев: {len(proxy_repos)}")

    return proxy_repos


def is_domain_resolvable(url):
    try:
        domain = url.split("/")[2]
        socket.gethostbyname(domain)
        return True
    except Exception:
        logger.warning(f"❌ Невозможно разрешить домен: {url}")
        return False


def check_url_status(name, url, auth=None, check_dns=False):
    if not url:
        return "❌ URL пуст"

    if check_dns and not is_domain_resolvable(url):
        return "❌ domain is not valid"

    try:
        session = requests.Session()
        response = session.get(
            url, auth=auth, timeout=10, verify=False, allow_redirects=True
        )

        # Лог редиректов
        history = response.history
        if history:
            logger.info(f"🔁 {name} редиректы:")
            for resp in history:
                logger.info(f"➡️ {resp.status_code} → {resp.headers.get('Location')}")

        final_status = response.status_code
        final_url = response.url

        if final_status in (200, 401):
            logger.info(
                f"✅ {name} доступен: {final_status}, финальный URL: {final_url}"
            )
            return "✅"
        else:
            logger.warning(f"⚠️ {name} финальный статус: {final_status}")
            return f"❌ ({final_status})"

    except requests.RequestException as e:
        logger.warning(f"❌ Ошибка доступа к {name}: {e}")
        return f"❌ ({e})"


def check_docker_remote(repo_name, base_url):
    """Проверяем docker remote URL сначала без /v2, потом с /v2"""
    status = check_url_status(f"{repo_name} (remote docker)", base_url, check_dns=True)
    if "✅" in status:
        return status

    # Пробуем с /v2
    if not base_url.endswith("/v2"):
        url_with_v2 = base_url.rstrip("/") + "/v2"
        logger.info(f"🔄 Повторная проверка с /v2: {url_with_v2}")
        return check_url_status(
            f"{repo_name} (remote docker /v2)", url_with_v2, check_dns=True
        )

    return status


def update_prometheus_metrics(repo, nexus_status, remote_status):
    overall_status = (
        "✅ Рабочий"
        if "✅" in nexus_status and "✅" in remote_status
        else "❌ Проблема"
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


def fetch_status(repo, auth):
    nexus_status = check_url_status(f"{repo['name']} (Nexus)", repo["url"], auth=auth)

    if repo["remote"]:
        if repo["type"] == "docker":
            remote_status = check_docker_remote(repo["name"], repo["remote"])
        else:
            remote_status = check_url_status(
                f"{repo['name']} (remote)", repo["remote"], check_dns=True
            )
    else:
        remote_status = "❌"

    return update_prometheus_metrics(repo, nexus_status, remote_status)


def fetch_repositories_metrics(nexus_url, auth):
    repos = get_all_repositories(nexus_url, auth)
    return [fetch_status(repo, auth) for repo in repos]
