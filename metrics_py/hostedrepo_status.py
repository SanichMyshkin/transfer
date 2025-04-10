import requests
import logging
import urllib3
from prometheus_client import Gauge

# Отключение предупреждений об SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Настройка логирования
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Создание метрики для статуса репозиториев
REPO_STATUS = Gauge(
    "nexus_static_repo_status", 
    "Status of hosted repositories", 
    ["repository", "url", "type", "format"]
)

# Функция для получения списка репозиториев через API
def get_all_repositories(nexus_url, auth):
    """Получает все репозитории через API Nexus"""
    repos_url = f"{nexus_url}service/rest/v1/repositories"
    try:
        response = requests.get(repos_url, auth=auth, timeout=10, verify=False)
        if response.status_code == 200:
            repos_data = response.json()
            logger.info(f"✅ Получены репозитории: {len(repos_data)}")
            return repos_data
        else:
            logger.warning(
                f"⚠️ Ошибка при получении списка репозиториев, статус: {response.status_code}"
            )
            return []
    except Exception as e:
        logger.warning(f"❌ Ошибка при запросе репозиториев: {str(e)}")
        return []

# Функция для проверки репозитория
def check_repo_status(repo_url, repo_name, auth, repo_type, repo_format):
    """Проверяет статус репозитория через GET-запрос"""
    check_url = f"{repo_url}service/rest/repository/browse/{repo_name}"
    try:
        response = requests.get(check_url, auth=auth, timeout=10, verify=False)
        if response.status_code == 200:
            logger.info(
                f"✅ Репозиторий {repo_name} работает. Статус {response.status_code}"
            )
            REPO_STATUS.labels(
                repository=repo_name, url=check_url, type=repo_type, format=repo_format
            ).set(1)
        else:
            logger.warning(
                f"⚠️ Ошибка при проверке репозитория {repo_name}, статус: {response.status_code}"
            )
            REPO_STATUS.labels(
                repository=repo_name, url=check_url, type=repo_type, format=repo_format
            ).set(0)
    except Exception as e:
        logger.warning(f"❌ Ошибка при проверке репозитория {repo_name}: {str(e)}")
        REPO_STATUS.labels(
            repository=repo_name, url=check_url, type=repo_type, format=repo_format
        ).set(0)

# Основная функция для мониторинга репозиториев
def monitor_hosted_repos(nexus_url, auth):
    repos_data = get_all_repositories(nexus_url, auth)
    hosted_repos = [
        repo for repo in repos_data if repo["type"] in ["hosted", "group"]
    ]

    if hosted_repos:
        logger.info(f"📦 Проверяем репозитории: {', '.join([repo['name'] for repo in hosted_repos])}")
        for repo in hosted_repos:
            check_repo_status(
                nexus_url,
                repo["name"],
                auth,
                repo["type"],
                repo.get("format", "unknown")
            )
    else:
        logger.warning("⚠️ Не найдено репозиториев типа hosted или group.")

# Основная функция запуска
def fetch_static_status(nexus_url, auth):
    monitor_hosted_repos(nexus_url, auth)
