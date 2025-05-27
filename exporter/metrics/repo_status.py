import logging
import time
import socket
from prometheus_client import Gauge, Info
from metrics.utlis.api import get_repositories, safe_get_raw

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
REPO_COUNT = Gauge("nexus_repo_count", "Количество репозиториев по типу", ["repo_type"])
REDIRECT_INFO = Info("nexus_repo_redirect_info", "Информация о редиректах")

logger = logging.getLogger(__name__)


def is_domain_resolvable(url: str) -> bool:
    try:
        domain = url.split("/")[2]
        socket.gethostbyname(domain)
        return True
    except Exception:
        logger.warning(f"❌ Невозможно разрешить домен: {url}")
        return False


def format_status(code: int = None, error_text: str = None) -> str:
    if code == 200:
        return "✅"
    elif code == 401:
        return "✅ (401)"
    elif error_text:
        return f"❌ ({error_text})"
    else:
        return f"❌ ({code})"


def check_url_status(
    name: str, url: str, auth: tuple = None, check_dns: bool = False
) -> tuple:
    if not url:
        return "❌ (url is empty)", False, ""

    if check_dns and not is_domain_resolvable(url):
        return "❌ (domain not resolvable)", False, ""

    response, error = safe_get_raw(url, auth)

    if response is None:
        return format_status(None, str(error)), False, ""

    redirected = len(response.history) > 0
    redirect_chain = ""

    if redirected:
        chain = []
        for resp in response.history:
            loc = resp.headers.get("Location", "<unknown>")
            chain.append(f"{resp.status_code} → {loc}")
        redirect_chain = " > ".join(chain)
        logger.info(f"🔁 {name} редиректы: {redirect_chain}")

    logger.info(
        f"🔚 {name} финальный URL: {response.url} (статус: {response.status_code})"
    )
    return format_status(response.status_code), redirected, redirect_chain


def check_docker_remote(repo_name: str, base_url: str) -> tuple:
    status, redirected, redirect_info = check_url_status(
        f"{repo_name} (docker)", base_url, check_dns=True
    )
    if status.startswith("✅"):
        return status, redirected, redirect_info
    if not base_url.endswith("/v2"):
        return check_url_status(repo_name, base_url.rstrip("/") + "/v2", check_dns=True)
    return status, redirected, redirect_info


def fetch_status(repo: dict, auth: tuple) -> dict:
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

    return {
        "repo": repo,
        "nexus_status": nexus_status,
        "remote_status": remote_status,
        "redirected": nexus_redirected or remote_redirected,
        "redirect_chain": " | ".join(
            filter(None, [nexus_redirect_info, remote_redirect_info])
        ),
    }


def update_all_metrics(statuses: list):
    REPO_STATUS.clear()

    for status in statuses:
        repo = status["repo"]
        healthy = status["nexus_status"].startswith("✅") and status[
            "remote_status"
        ].startswith("✅")

        REPO_STATUS.labels(
            repo_name=repo["name"],
            repo_format=repo["type"],
            nexus_url=repo["url"],
            remote_url=repo["remote"] or "",
            nexus_status=status["nexus_status"],
            remote_status=status["remote_status"],
            redirected=str(status["redirected"]).lower(),
        ).set(1 if healthy else 0)

        if status["redirect_chain"]:
            REDIRECT_INFO.info({repo["name"]: status["redirect_chain"]})

        logger.info(
            f"📦 Статус репозитория {repo['name']}: {'✅' if healthy else '❌'}"
        )


def fetch_repositories_metrics(nexus_url: str, auth: tuple) -> list:
    start = time.perf_counter()

    raw_repos = get_repositories(nexus_url, auth)
    repos = [
        {
            "name": r["name"],
            "url": f"{nexus_url}service/rest/repository/browse/{r['name']}/",
            "type": r.get("format", ""),
            "remote": r.get("attributes", {}).get("proxy", {}).get("remoteUrl", ""),
        }
        for r in raw_repos
        if r.get("type") == "proxy"
    ]

    type_counts = {}
    for r in raw_repos:
        repo_type = r.get("type", "unknown")
        type_counts[repo_type] = type_counts.get(repo_type, 0) + 1

    for repo_type, count in type_counts.items():
        REPO_COUNT.labels(repo_type=repo_type).set(count)
        logger.info(f"📊 Репозиториев типа '{repo_type}': {count}")

    logger.info(
        f"🔍 Получено {len(repos)} proxy-репозиториев, начинаем проверку URL..."
    )

    statuses = [fetch_status(repo, auth) for repo in repos]
    logger.info(f"✅ Проверка завершена за {time.perf_counter() - start:.2f} секунд.")

    update_all_metrics(statuses)
    logger.info("📈 Метрики обновлены.")

    return statuses
