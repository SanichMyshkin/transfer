import requests
import socket
import logging
import urllib3
import time
from prometheus_client import Gauge, Info
from requests.exceptions import RequestException, ConnectionError

# Отключение предупреждений об SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Метрика статуса репозитория
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
        "redirected",
    ],
)

# Метрика количества по типам
REPO_COUNT = Gauge("nexus_repo_count", "Количество репозиториев по типу", ["repo_type"])

# Информация о редиректах
REDIRECT_INFO = Info(
    "nexus_repo_redirect_info", "Информация о редиректах для каждого репозитория"
)

# Логирование
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}


def safe_get(url, auth=None, timeout=15, verify=False, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.get(
                url,
                auth=auth,
                headers=HEADERS,
                timeout=timeout,
                verify=verify,
                allow_redirects=True,
            )
            return response
        except ConnectionError as e:
            wait = 2**attempt
            logger.warning(
                f"⚠️ [{url}] Попытка {attempt + 1} не удалась (ConnectionError), жду {wait}s..."
            )
            time.sleep(wait)
        except RequestException as e:
            logger.warning(f"❌ Ошибка запроса к {url}: {e}")
            break
    return None


def get_all_repositories(nexus_url, auth):
    endpoint = f"{nexus_url}/service/rest/v1/repositories"
    response = safe_get(endpoint, auth=auth)

    if response is None or response.status_code != 200:
        logger.error("❌ Не удалось получить список репозиториев")
        return []

    repos = response.json()

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


def format_status(code, error_text=None):
    if code == 200:
        return "✅"
    elif code == 401:
        return "✅ (401)"
    elif error_text:
        return f"❌ ({error_text})"
    else:
        return f"❌ ({code})"


def check_url_status(name, url, auth=None, check_dns=False):
    if not url:
        return "❌ (url is empty)", False, ""

    if check_dns and not is_domain_resolvable(url):
        return "❌ (domain not resolvable)", False, ""

    response = safe_get(url, auth=auth)
    if response is None:
        return "❌ (request failed)", False, ""

    redirected = len(response.history) > 0
    redirect_chain = ""

    if redirected:
        logger.info(f"🔁 {name} редиректы:")
        chain = []
        for resp in response.history:
            loc = resp.headers.get("Location", "<unknown>")
            logger.info(f"➡️ {resp.status_code} → {loc}")
            chain.append(f"{resp.status_code} → {loc}")
        redirect_chain = " > ".join(chain)

    final_status = response.status_code
    final_url = response.url
    logger.info(f"🔚 {name} финальный URL: {final_url} (статус: {final_status})")

    return format_status(final_status), redirected, redirect_chain


def check_docker_remote(repo_name, base_url):
    status, redirected, redirect_info = check_url_status(
        f"{repo_name} (remote docker)", base_url, check_dns=True
    )
    if status.startswith("✅"):
        return status, redirected, redirect_info

    if not base_url.endswith("/v2"):
        url_with_v2 = base_url.rstrip("/") + "/v2"
        logger.info(f"🔄 Повторная проверка с /v2: {url_with_v2}")
        return check_url_status(
            f"{repo_name} (remote docker /v2)", url_with_v2, check_dns=True
        )

    return status, redirected, redirect_info


def update_prometheus_metrics(
    repo, nexus_status, remote_status, redirected, redirect_info
):
    healthy = nexus_status.startswith("✅") and remote_status.startswith("✅")

    REPO_STATUS.labels(
        repo_name=repo["name"],
        repo_format=repo["type"],
        nexus_url=repo["url"],
        remote_url=repo["remote"] or "",
        nexus_status=nexus_status,
        remote_status=remote_status,
        redirected=str(redirected).lower(),
    ).set(1 if healthy else 0)

    if redirect_info:
        REDIRECT_INFO.info({repo["name"]: redirect_info})

    status_icon = "✅" if healthy else "❌"
    logger.info(f"📦 Статус репозитория {repo['name']}: {status_icon}")
    return {
        "repo": repo["name"],
        "nexus": nexus_status,
        "remote": remote_status,
        "status": status_icon,
        "redirected": redirected,
        "redirect_chain": redirect_info,
    }


def fetch_status(repo, auth):
    nexus_status, nexus_redirected, nexus_redirect_info = check_url_status(
        f"{repo['name']} (Nexus)", repo["url"], auth=auth
    )

    if repo["remote"]:
        if repo["type"] == "docker":
            remote_status, remote_redirected, remote_redirect_info = (
                check_docker_remote(repo["name"], repo["remote"])
            )
        else:
            remote_status, remote_redirected, remote_redirect_info = check_url_status(
                f"{repo['name']} (remote)", repo["remote"], check_dns=True
            )
    else:
        remote_status, remote_redirected, remote_redirect_info = (
            "❌ (no remote URL)",
            False,
            "",
        )

    was_redirected = nexus_redirected or remote_redirected
    redirect_chain_combined = " | ".join(
        filter(None, [nexus_redirect_info, remote_redirect_info])
    )

    return update_prometheus_metrics(
        repo, nexus_status, remote_status, was_redirected, redirect_chain_combined
    )


def fetch_repositories_metrics(nexus_url, auth):
    REPO_STATUS.clear()
    repos = get_all_repositories(nexus_url, auth)
    return [fetch_status(repo, auth) for repo in repos]
