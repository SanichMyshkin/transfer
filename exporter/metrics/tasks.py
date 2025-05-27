import logging
from prometheus_client import Gauge

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(module)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Метрика задач
TASK_INFO = Gauge(
    "nexus_task_info",
    "Raw info about all Nexus tasks",
    [
        "id",
        "name",
        "type",
        "message",
        "current_state",
        "last_run_result",
        "next_run",
        "last_run",
    ],
)


def export_tasks_to_metrics(tasks: list) -> None:
    TASK_INFO.clear()

    filtered_tasks = [
        task
        for task in tasks
        if task.get("type") in ("blobstore.delete-temp-files", "blobstore.compact")
    ]

    for task in filtered_tasks:
        task_id = task.get("id", "N/A")
        task_name = task.get("name", "N/A")
        last_result = task.get("lastRunResult")
        result_icon = "✅" if last_result == "OK" else "❌" if last_result == "ERROR" else "⚠️"
        value = 0 if last_result == "OK" else 1 if last_result else -1

        try:
            TASK_INFO.labels(
                id=task_id,
                name=str(task_name),
                type=task.get("type", "N/A"),
                message=str(task.get("message", "N/A")),
                current_state=task.get("currentState", "N/A"),
                last_run_result=last_result or "null",
                next_run=task.get("nextRun") or "null",
                last_run=task.get("lastRun") or "null",
            ).set(value)

            logger.info(f"📊 Задача: {task_name} | Тип: {task.get('type')} | Статус: {result_icon} {last_result}")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при экспорте метрик для задачи {task_id}: {e}", exc_info=True)

    logger.info("📈 Метрики задач Nexus обновлены.")


def fetch_task_metrics(task_data: dict | None) -> None:
    if not task_data or "items" not in task_data:
        logger.error("❌ Не удалось собрать метрики задач. Пропускаем сбор метрик!")
        return
    logger.info("📥 Получены данные задач Nexus, начинаем экспорт в метрики...")
    export_tasks_to_metrics(task_data["items"])


def extract_blob_name(message: str | None) -> str | None:
    if not message:
        return None
    try:
        return message.split()[1]
    except IndexError:
        logger.warning(f"⚠️ Невозможно извлечь blobName из сообщения: '{message}'")
        return None


def filter_blobstore_tasks(data: dict | None) -> dict:
    result = {}
    type_task_map = {
        "blobstore.delete-temp-files": "delete",
        "blobstore.compact": "compact",
    }

    if not data or "items" not in data:
        logger.error("❌ Невалидный формат данных задач")
        return result

    for task in data["items"]:
        task_type = task.get("type")
        if task_type not in type_task_map:
            continue

        last_result = task.get("lastRunResult")
        blob_name = task.get("blobName") or extract_blob_name(task.get("message"))

        if not blob_name:
            logger.warning(f"⚠️ Пропущена задача без blobName: {task.get('name', 'N/A')}")
            continue

        status = 1 if last_result == "OK" else -1 if last_result == "ERROR" else 0
        status_icon = "✅" if status == 1 else "❌" if status == -1 else "⚠️"

        if blob_name not in result:
            result[blob_name] = {"delete": 0, "compact": 0}

        result[blob_name][type_task_map[task_type]] = status

        logger.info(f"🧹 Задача '{type_task_map[task_type]}' для blob '{blob_name}': {status_icon} {last_result or 'unknown'}")

    logger.info("🔍 Анализ задач blobstore завершён.")
    return result
