import logging
import urllib3
import requests
from requests import Session
from prometheus_client import Gauge

# Отключаем предупреждения о небезопасных HTTPS-запросах
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(module)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Метрика Prometheus для задач
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

# Сессия HTTP
session: Session = requests.Session()


def get_json_from_nexus(
    nexus_url: str, endpoint: str, auth: tuple
) -> dict | list | None:
    """
    Выполняет GET-запрос к указанному endpoint на Nexus.

    :param nexus_url: Базовый URL Nexus
    :param endpoint: API endpoint
    :param auth: Кортеж с (username, password)
    :return: Ответ в формате JSON, либо None в случае ошибки
    """
    url = f"{nexus_url.rstrip('/')}{endpoint}"
    logger.info(f"📡 Запрос к Nexus: {url}")
    try:
        response = session.get(url, auth=auth, verify=False, timeout=15)
        if response.status_code == 200:
            logger.info(f"✅ Ответ от Nexus получен: {url}")
            return response.json()
        logger.error(f"❌ Код {response.status_code} от {url}: {response.text}")
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Ошибка при запросе {url}: {e}", exc_info=True)
    return None


def export_tasks_to_metrics(tasks: list) -> None:
    """
    Экспортирует только задачи типа blobstore (delete-temp-files, compact) в метрики Prometheus.

    :param tasks: Список задач Nexus
    """
    TASK_INFO.clear()

    # Только интересующие типы задач
    filtered_tasks = [
        task for task in tasks
        if task.get("type") in ("blobstore.delete-temp-files", "blobstore.compact")
    ]
    logger.info(f"📊 Обновляем метрики для {len(filtered_tasks)} задач")

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
        except Exception as e:
            logger.warning(f"⚠️ Ошибка метрики для {task_id}: {e}", exc_info=True)

    logger.info("✅ Метрики задач обновлены.")



def fetch_task_metrics(nexus_url: str, auth: tuple) -> None:
    """
    Загружает задачи Nexus и экспортирует их в Prometheus.

    :param nexus_url: URL Nexus API
    :param auth: Кортеж (username, password)
    """
    task_data = get_json_from_nexus(nexus_url, "/service/rest/v1/tasks", auth)
    if not task_data or "items" not in task_data:
        logger.error("❌ Ответ пустой или неверного формата")
        return

    export_tasks_to_metrics(task_data["items"])


def extract_blob_name(message: str | None) -> str | None:
    """
    Извлекает имя blob из сообщения задачи.

    :param message: Строка message из задачи
    :return: Имя blob или None, если извлечение невозможно
    """
    if not message:
        return None
    try:
        return message.split()[1]
    except IndexError:
        logger.warning(f"⚠️ Невозможно извлечь blobName из сообщения: {message}")
        return None


def filter_blobstore_tasks(data: dict) -> dict:
    """
    Фильтрует задачи типа blobstore и формирует статус delete и compact по каждому blob.

    :param data: JSON с задачами Nexus
    :return: Словарь {blob_name: {"delete": int, "compact": int}}
    """
    result = {}
    type_task_map = {
        "blobstore.delete-temp-files": "delete",
        "blobstore.compact": "compact",
    }

    if not isinstance(data, dict) or "items" not in data:
        logger.error("❌ Невалидный формат данных задач")
        return result

    for task in data["items"]:
        task_type = task.get("type")
        if task_type not in type_task_map:
            continue  # Только интересующие типы

        last_result = task.get("lastRunResult")
        blob_name = task.get("blobName") or extract_blob_name(task.get("message"))

        if not blob_name:
            continue  # Пропускаем задачи без имени blob

        status = 1 if last_result == "OK" else -1 if last_result == "ERROR" else 0

        if blob_name not in result:
            result[blob_name] = {"delete": 0, "compact": 0}

        result[blob_name][type_task_map[task_type]] = status
        logger.info(f"🔎 {type_task_map[task_type]} для {blob_name}: {status}")

    return result
