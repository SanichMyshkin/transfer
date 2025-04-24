import logging
import urllib3
import requests
from requests.exceptions import RequestException, Timeout, HTTPError
from requests import Session
from prometheus_client import Gauge

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Логгер
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

# HTTP-сессия
session: Session = requests.Session()


def get_json_from_nexus(nexus_url: str, endpoint: str, auth: tuple) -> dict | list | None:
    url = f"{nexus_url.rstrip('/')}{endpoint}"
    logger.info(f"📡 Запрос к Nexus: {url}")
    
    try:
        response = session.get(url, auth=auth, verify=False, timeout=15)
        response.raise_for_status()  # Проверка на HTTP ошибки (4xx, 5xx)

        logger.info(f"✅ Ответ от Nexus получен: {url} (Код: {response.status_code})")
        return response.json()
    
    except Timeout:
        logger.error(f"⏳ Тайм-аут при запросе к {url}. Сервер не отвечает в течение установленного времени (15 секунд).")
    except HTTPError as http_err:
        logger.error(f"❌ Ошибка HTTP {http_err.response.status_code} при запросе к {url}: {http_err}")
    except RequestException as req_err:
        logger.error(f"❌ Общая ошибка при запросе к {url}: {req_err}", exc_info=True)
    except Exception as e:
        logger.error(f"❌ Неизвестная ошибка при запросе к {url}: {str(e)}", exc_info=True)
    
    return None


def export_tasks_to_metrics(tasks: list) -> None:
    TASK_INFO.clear()

    filtered_tasks = [
        task for task in tasks
        if task.get("type") in ("blobstore.delete-temp-files", "blobstore.compact")
    ]

    for task in filtered_tasks:
        task_id = task.get("id", "N/A")
        task_name = task.get("name", "N/A")
        last_result = task.get("lastRunResult")
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
            logger.info(f"📊 Обновляем метрики для задачи - {task_name} статус {last_result}")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка метрики для {task_id}: {e}", exc_info=True)

    logger.info("✅ Метрики задач обновлены.")


def fetch_task_metrics(task_data: dict | None) -> None:
    if not task_data or "items" not in task_data:
        logger.error("❌ Не удалось загрузить задачи с Nexus")
        return
    export_tasks_to_metrics(task_data["items"])


def extract_blob_name(message: str | None) -> str | None:
    if not message:
        return None
    try:
        return message.split()[1]
    except IndexError:
        logger.warning(f"⚠️ Невозможно извлечь blobName из сообщения: {message}")
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
            continue

        status = 1 if last_result == "OK" else -1 if last_result == "ERROR" else 0

        if blob_name not in result:
            result[blob_name] = {"delete": 0, "compact": 0}

        result[blob_name][type_task_map[task_type]] = status
        logger.info(f"🔎 {type_task_map[task_type]} для {blob_name}: {status}")

    return result
