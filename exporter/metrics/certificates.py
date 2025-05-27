import requests
import logging
import urllib3
from prometheus_client import Gauge

from requests.exceptions import SSLError, RequestException, ConnectionError

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CERT_MATCH_STATUS = Gauge(
    "nexus_cert_url_match",
    "Совпадение SSL-сертификатов с remote URL в proxy-репозиториях Nexus",
    ["repo_name", "remote_url", "subject_common_name", "match_level"],
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120 Safari/537.36"
    )
}

session = requests.Session()
adapter = requests.adapters.HTTPAdapter(max_retries=0)
session.mount("https://", adapter)
session.mount("http://", adapter)


def safe_get(url: str, auth: tuple, timeout: int = 20):
    try:
        response = session.get(
            url,
            auth=auth,
            headers=HEADERS,
            timeout=timeout,
            verify=True,
        )
        response.raise_for_status()
        return response.json()
    except SSLError as ssl_err:
        logger.warning(f"⚠️ SSL ошибка при запросе к {url}: {ssl_err}")
        try:
            response = session.get(
                url,
                auth=auth,
                headers=HEADERS,
                timeout=timeout,
                verify=False,
            )
            logger.warning(f"⚠️ Использован verify=False для {url}")
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            logger.error(f"❌ Ошибка запроса без verify: {e}")
            return []
    except (ConnectionError, RequestException) as e:
        logger.error(f"❌ Ошибка подключения к {url}: {e}")
        return []


def get_certificates(nexus_url: str, auth: tuple) -> list:
    endpoint = f"{nexus_url}/service/rest/v1/security/ssl/truststore"
    return safe_get(endpoint, auth)


def get_proxy_repositories(nexus_url: str, auth: tuple) -> list:
    endpoint = f"{nexus_url}/service/rest/v1/repositories"
    repos = safe_get(endpoint, auth)
    return [
        {
            "name": r["name"],
            "remote": r.get("attributes", {}).get("proxy", {}).get("remoteUrl", ""),
        }
        for r in repos
        if r.get("type") == "proxy"
    ]


def match_level(cert_cn: str, remote_url: str) -> int:
    if not cert_cn or not remote_url:
        return 0
    base = cert_cn.strip("*.")  # Убираем wildcard
    if base in remote_url:
        return 1
    short = base.split(".")[0]
    if short in remote_url:
        return 2
    return 0


def update_cert_match_metrics(nexus_url: str, auth: tuple):
    CERT_MATCH_STATUS.clear()

    certs = get_certificates(nexus_url, auth)
    repos = get_proxy_repositories(nexus_url, auth)

    logger.info(f"🔐 Получено сертификатов: {len(certs)}")
    logger.info(f"📦 Получено proxy-репозиториев: {len(repos)}")

    for repo in repos:
        remote = repo["remote"]
        name = repo["name"]
        matched = False

        for cert in certs:
            cn = cert.get("subjectCommonName", "")
            level = match_level(cn, remote)

            CERT_MATCH_STATUS.labels(
                repo_name=name,
                remote_url=remote,
                subject_common_name=cn,
                match_level=str(level),
            ).set(level)

            if level > 0:
                logger.info(
                    f"🔍 Repo: {name} → {remote} | Cert CN: {cn} | Уровень совпадения: {level}"
                )
                matched = True

        if not matched:
            logger.info(
                f"🔍 Repo: {name} → {remote} | Ни один сертификат не подходит | Уровень совпадения: {level}"
            )
