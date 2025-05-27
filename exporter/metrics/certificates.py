import logging
from prometheus_client import Gauge
from metrics.utlis.api import get_from_nexus

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(module)s - %(message)s"
)
logger = logging.getLogger(__name__)

CERT_MATCH_STATUS = Gauge(
    "nexus_cert_url_match",
    "Совпадение SSL-сертификатов с remote URL в proxy-репозиториях Nexus",
    ["repo_name", "remote_url", "subject_common_name", "match_level"],
)


def match_level(cert_cn: str, remote_url: str) -> int:
    if not cert_cn or not remote_url:
        return 0
    base = cert_cn.strip("*.")  # wildcard
    if base in remote_url:
        return 1
    short = base.split(".")[0]
    if short in remote_url:
        return 2
    return 0


def update_cert_match_metrics(nexus_url: str, auth: tuple):
    CERT_MATCH_STATUS.clear()

    certs = get_from_nexus(nexus_url, "security/ssl/truststore", auth)
    if not certs:
        logger.warning(
            f"⚠️ Не удалось получить сертификаты с {nexus_url} или получен пустой список. "
            f"Возможно Nexus выключен. Прерываем сбор метрик."
        )
        return

    repos = get_from_nexus(nexus_url, "repositories", auth)
    if not repos:
        logger.error(
            f"❌ Не удалось получить репозитории с {nexus_url} или получен пустой список. "
            f"Прерываем сбор SSL метрик."
        )
        return

    logger.info(f"🔐 Получено сертификатов: {len(certs)}")
    logger.info(f"📦 Получено proxy-репозиториев: {len(repos)}")

    repos = [
        {
            "name": r["name"],
            "remote": r.get("attributes", {}).get("proxy", {}).get("remoteUrl", ""),
        }
        for r in repos
        if r.get("type") == "proxy"
    ]

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
                f"🔍 Repo: {name} → {remote} | Ни один сертификат не подходит | Уровень совпадения: 0"
            )
