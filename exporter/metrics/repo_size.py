import logging

from prometheus_client import Gauge
from database.repository_query import get_repository_sizes, get_repository_data
from database.jobs_query import get_jobs_data

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(module)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Единая метрика с двумя лейблами: внутренняя и внешняя политика
REPO_STORAGE = Gauge(
    "nexus_repo_size",
    "Total size of Nexus repositories in bytes",
    [
        "repo_name",
        "repo_type",
        "repo_format",
        "repo_blob_name",
        "internal_cleanup_policy",  # внутренняя политика
        "custom_cleaner_url",       # внешняя политика
        "delete_temp_status",
        "compact_status",
    ],
)

# Разрешённые типы задач
ALLOWED_TASK_TYPES = {
    "blobstore.delete-temp-files": "delete",
    "blobstore.compact": "compact",
}

# Внешние политики (repo_name -> URL)
def get_external_policies():
    return {
        "docker-habor": "https://nexus.sanich.space/#browse/browse:docker-habor",
        "comunda-docker": "https://sanich.space",
        "nuget.org-proxy": 'https://wikipedia.com'
    }

def fetch_repository_metrics() -> list:
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
        task_data = get_jobs_data()
    except Exception as e:
        logger.error(f"❌ Ошибка при получении задач из БД: {e}")
        task_data = []

    # Задачи по blobStore
    task_statuses = {}
    for task in task_data:
        task_type = task.get(".typeId")
        blob_name = task.get("blobstoreName")
        if task_type in ALLOWED_TASK_TYPES and blob_name:
            status_key = ALLOWED_TASK_TYPES[task_type]
            if blob_name not in task_statuses:
                task_statuses[blob_name] = {"delete": 0, "compact": 0}
            task_statuses[blob_name][status_key] = 1

    external_links = get_external_policies()

    REPO_STORAGE.clear()

    for repo in repo_data:
        repo_name = repo.get("repository_name", "unknown")
        blob_name = repo.get("blob_store_name", "")
        internal_policy = repo.get("cleanup_policy") or ""
        presence_flags = task_statuses.get(blob_name, {"delete": 0, "compact": 0})
        repo.update(presence_flags)

        # Определяем политики
        if repo_name in external_links:
            custom_cleaner_url = external_links[repo_name]
            internal_policy = ""  # внешняя политика заменяет внутреннюю
        else:
            custom_cleaner_url = ""

        # Лог
        logger.info(
            f"📦 Репозиторий: {repo_name} | blob: {blob_name} | "
            f"delete: {'✅' if repo.get('delete') else '❌'} | "
            f"compact: {'✅' if repo.get('compact') else '❌'} | "
            f"internal: {internal_policy or '—'} | external: {custom_cleaner_url or '—'}"
        )

        # Метрика
        try:
            size = float(repo.get("size", 0) or 0)
        except (ValueError, TypeError):
            logger.warning(f"⚠️ Невозможно преобразовать размер репозитория {repo_name} в число")
            size = 0.0

        REPO_STORAGE.labels(
            repo_name=repo_name,
            repo_type=repo.get("repository_type", "unknown"),
            repo_format=repo.get("format", "unknown"),
            repo_blob_name=blob_name,
            internal_cleanup_policy=internal_policy,
            custom_cleaner_url=custom_cleaner_url,
            delete_temp_status=str(repo.get("delete", 0)),
            compact_status=str(repo.get("compact", 0)),
        ).set(size)

    logger.info("✅ Метрики репозиториев собраны успешно")
    return repo_data
