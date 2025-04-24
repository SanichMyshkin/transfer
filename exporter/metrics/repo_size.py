import logging
import urllib3

from prometheus_client import Gauge
from database.repository_query import get_repository_sizes, get_repository_data
from metrics.utlis.tasks import filter_blobstore_tasks

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(module)s - %(message)s"
)
logger = logging.getLogger(__name__)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REPO_STORAGE = Gauge(
    "nexus_repo_size",
    "Total size of Nexus repositories in bytes",
    [
        "repo_name",
        "repo_type",
        "repo_format",
        "repo_blob_name",
        "repo_cleanup",
        "delete_temp_status",
        "compact_status",
    ],
)


def fetch_repository_metrics(nexus_url: str, auth: tuple, task_data: dict | None) -> list:
    logger.info("🔄 Сбор информации о репозиториях и метриках...")

    repo_size = get_repository_sizes()
    repo_data = get_repository_data()

    for repo in repo_data:
        repo["size"] = repo_size.get(repo.get("repository_name"), 0)

    if not task_data or "items" not in task_data:
        logger.error(f"🚫 Не удалось достучаться до Nexus: {nexus_url}")
        task_statuses = {}
    else:
        task_statuses = filter_blobstore_tasks(task_data)

    for repo in repo_data:
        blob_name = repo.get("blob_store_name")
        repo.update(task_statuses.get(blob_name, {"delete": -2, "compact": -2}))

        REPO_STORAGE.labels(
            repo_name=repo.get("repository_name", "unknown"),
            repo_type=repo.get("repository_type", "unknown"),
            repo_format=repo.get("format", "unknown"),
            repo_blob_name=blob_name,
            repo_cleanup=repo.get("cleanup_policies", "N/A"),
            delete_temp_status=str(repo.get("delete", -2)),
            compact_status=str(repo.get("compact", -2)),
        ).set(float(repo.get("size", 0)))

    logger.info("✅ Метрики репозиториев собраны")
    return repo_data
