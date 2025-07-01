import logging
from typing import Optional
from prometheus_client import Gauge

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(module)s - %(message)s",
)
logger = logging.getLogger(__name__)

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


def parse_task_status(last_result: Optional[str]) -> tuple[int, str, str]:
    if last_result == "OK":
        return 1, "✅", "Успешно"
    elif last_result == "ERROR":
        return -1, "❌", "Ошибка"
    elif last_result is None:
        return 2, "⏳", "Не запускалась"
    return -1, "⚠️", f"Неизвестно ({last_result})"


def export_tasks_to_metrics(tasks: list) -> None:
    TASK_INFO.clear()
    for task in tasks:
        task_id = task.get("id", "N/A")
        task_name = task.get("name", "N/A")
        task_type = task.get("type", "N/A")
        last_result = task.get("lastRunResult")
        value, icon, label = parse_task_status(last_result)
        try:
            TASK_INFO.labels(
                id=task_id,
                name=str(task_name),
                type=task_type,
                message=str(task.get("message", "N/A")),
                current_state=task.get("currentState", "N/A"),
                last_run_result=last_result or "null",
                next_run=task.get("nextRun") or "null",
                last_run=task.get("lastRun") or "null",
            ).set(value)
            logger.info(f"📊 [{icon}] Задача '{task_name}' ({task_type}): {label}")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при экспорте метрик для задачи {task_id}: {e}", exc_info=True)
    logger.info("✅ Экспорт метрик задач завершён.")


def fetch_task_metrics(task_data: dict | None) -> None:
    if not task_data or "items" not in task_data:
        logger.error("❌ Не удалось собрать метрики задач. Пропускаем сбор метрик!")
        return
    logger.info("📥 Получены данные задач Nexus. Начинаем экспорт в метрики...")
    export_tasks_to_metrics(task_data["items"])


def extract_blob_name(task: dict) -> Optional[str]:
    props = task.get("properties", {})
    if "blobStoreName" in props:
        return props["blobStoreName"]
    message = task.get("message")
    if message:
        try:
            return message.split()[1]
        except IndexError:
            logger.warning(f"⚠️ Невозможно извлечь blobName из сообщения: '{message}'")
    return None


def _get_blobstore_tasks(data: dict) -> list:
    if not data or "items" not in data:
        logger.error("❌ Невалидный формат данных задач")
        return []
    return [
        task for task in data["items"]
        if task.get("type") in ("blobstore.delete-temp-files", "blobstore.compact")
    ]


def filter_blobstore_task_details(data: dict | None) -> dict:
    result = {}
    type_task_map = {
        "blobstore.delete-temp-files": "delete",
        "blobstore.compact": "compact",
    }

    for task in _get_blobstore_tasks(data):
        task_type = task.get("type")
        task_kind = type_task_map[task_type]
        blob_name = extract_blob_name(task)

        if not blob_name:
            logger.warning(f"❌ Задача '{task_kind}' не найдена или не задан blobName: {task.get('name', 'N/A')}")
            continue

        value, icon, label = parse_task_status(task.get("lastRunResult"))

        if blob_name not in result:
            result[blob_name] = {"delete": 0, "compact": 0}

        result[blob_name][task_kind] = value
        logger.info(f"🧹 [{icon}] Задача '{task_kind}' для blob '{blob_name}': {label}")

    logger.info("✅ Анализ задач blobstore завершён.")
    return result


def filter_blobstore_tasks_presence_only(data: dict | None) -> dict:
    result = {}
    type_task_map = {
        "blobstore.delete-temp-files": "delete",
        "blobstore.compact": "compact",
    }

    for task in _get_blobstore_tasks(data):
        task_type = task.get("type")
        task_kind = type_task_map[task_type]
        blob_name = extract_blob_name(task)

        if not blob_name:
            logger.info(f"ℹ️ Пропущена задача без blobName: {task.get('name', 'N/A')}")
            continue

        if blob_name not in result:
            result[blob_name] = {"delete": 0, "compact": 0}

        result[blob_name][task_kind] = 1
        logger.info(f"✅ Обнаружена задача '{task_kind}' для blob '{blob_name}'")

    logger.info("✅ Обнаружение наличия задач завершено.")
    return result
