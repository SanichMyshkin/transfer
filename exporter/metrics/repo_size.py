import logging

from prometheus_client import Gauge
from database.repository_query import get_repository_sizes, get_repository_data
from metrics.tasks import filter_blobstore_tasks_presence_only  # ✅ заменили

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(module)s - %(message)s"
)
logger = logging.getLogger(__name__)

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


def fetch_repository_metrics(task_data: dict) -> list:
    logger.info("🔄 Сбор информации о репозиториях и метриках...")

    try:
        repo_size = get_repository_sizes()
        repo_data = get_repository_data()
    except Exception as e:
        logger.error(f"❌ Ошибка при получении данных из БД: {e}")
        return []

    if not repo_data:
        logger.error("❌ Не удалось получить данные о репозиториях — метрики не будут обновлены")
        return []

    for repo in repo_data:
        repo["size"] = repo_size.get(repo.get("repository_name"), 0)

    try:
        # ✅ Получаем только информацию о наличии задач
        task_statuses = filter_blobstore_tasks_presence_only(task_data)
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке задач blobstore: {e}")
        task_statuses = {}

    # Очищаем метрики перед обновлением
    REPO_STORAGE.clear()

    for repo in repo_data:
        blob_name = repo.get("blob_store_name")
        presence_flags = task_statuses.get(blob_name, {"delete": 0, "compact": 0})
        repo.update(presence_flags)

        # Обновляем метрики
        REPO_STORAGE.labels(
            repo_name=repo.get("repository_name", "unknown"),
            repo_type=repo.get("repository_type", "unknown"),
            repo_format=repo.get("format", "unknown"),
            repo_blob_name=blob_name,
            repo_cleanup=repo.get("cleanup_policy", "N/A"),
            delete_temp_status=str(repo.get("delete", 0)),
            compact_status=str(repo.get("compact", 0)),
        ).set(float(repo.get("size", 0)))

    logger.info("✅ Метрики репозиториев собраны успешно")
    return repo_data
