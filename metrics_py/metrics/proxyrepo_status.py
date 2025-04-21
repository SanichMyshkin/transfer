import requests
import socket
import logging
import urllib3
import time
from requests.exceptions import ConnectionError, RequestException
from prometheus_client import Gauge, Info

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
REDIRECT_INFO = Info("nexus_repo_redirect_info", "Информация о редиректах")

# Логирование
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
}


def safe_get(url, auth=None, timeout=15, verify=False, max_retries=3):
    last_error = None
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
            return response, None
        except ConnectionError as e:
            last_error = e
            wait = 2**attempt
            logger.warning(
                f"⚠️ [{url}] Попытка {attempt + 1} не удалась (ConnectionError), жду {wait}s..."
            )
            time.sleep(wait)
        except RequestException as e:
            last_error = e
            logger.warning(f"❌ Ошибка запроса к {url}: {e}")
            break
    return None, last_error


def get_all_repositories(nexus_url, auth):
    endpoint = f"{nexus_url}/service/rest/v1/repositories"

    try:
        response = requests.get(endpoint, auth=auth, timeout=10, verify=False)
        if response.status_code == 401:
            logger.error(f"❌ Доступ запрещён (401 Unauthorized) к {endpoint}")
            return []
        elif response.status_code == 403:
            logger.error(f"❌ Доступ запрещён (403 Forbidden) к {endpoint}")
            return []
        response.raise_for_status()
    except requests.ConnectionError as e:
        logger.error(f"❌ Невозможно подключиться к Nexus API: {e}")
        return []
    except requests.RequestException as e:
        logger.error(f"❌ Ошибка при запросе Nexus API: {e}")
        return []

    repos = response.json()
    type_counts = {}

    for repo in repos:
        repo_type = repo.get("type", "unknown")
        type_counts[repo_type] = type_counts.get(repo_type, 0) + 1

    for repo_type, count in type_counts.items():
        REPO_COUNT.labels(repo_type=repo_type).set(count)
        logger.info(f"📊 Репозиториев типа '{repo_type}': {count}")

    return [
        {
            "name": r["name"],
            "url": f"{nexus_url}service/rest/repository/browse/{r['name']}/",
            "type": r["format"],
            "remote": r.get("attributes", {}).get("proxy", {}).get("remoteUrl", ""),
        }
        for r in repos
        if r["type"] == "proxy"
    ]



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

    response, error = safe_get(url, auth=auth)

    if response is None:
        return format_status(None, str(error)), False, ""

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

    logger.info(
        f"🔚 {name} финальный URL: {response.url} (статус: {response.status_code})"
    )
    return format_status(response.status_code), redirected, redirect_chain


def check_docker_remote(repo_name, base_url):
    status, redirected, redirect_info = check_url_status(
        f"{repo_name} (remote docker)", base_url, check_dns=True
    )
    if status.startswith("✅"):
        return status, redirected, redirect_info

    if not base_url.endswith("/v2"):
        return check_url_status(
            f"{repo_name} (remote docker /v2)",
            base_url.rstrip("/") + "/v2",
            check_dns=True,
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

    logger.info(f"📦 Статус репозитория {repo['name']}: {'✅' if healthy else '❌'}")
    return {
        "repo": repo["name"],
        "nexus": nexus_status,
        "remote": remote_status,
        "status": "✅" if healthy else "❌",
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

    return update_prometheus_metrics(
        repo,
        nexus_status,
        remote_status,
        nexus_redirected or remote_redirected,
        " | ".join(filter(None, [nexus_redirect_info, remote_redirect_info])),
    )


def fetch_repositories_metrics(nexus_url, auth):
    REPO_STATUS.clear()
    repos = get_all_repositories(nexus_url, auth)
    return [fetch_status(repo, auth) for repo in repos]
