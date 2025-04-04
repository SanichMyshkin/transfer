import aiohttp
import logging
from prometheus_client import Gauge
import asyncio

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
async def get_all_repositories(session, nexus_url, auth):
    """Получает все репозитории через API Nexus"""
    repos_url = f"{nexus_url}service/rest/v1/repositories"  # Убедитесь, что URL правильный
    try:
        async with session.get(
            repos_url, auth=aiohttp.BasicAuth(*auth), timeout=10
        ) as response:
            if response.status == 200:
                repos_data = await response.json()
                logger.info(f"✅ Получены репозитории: {len(repos_data)}")
                return repos_data
            else:
                logger.warning(
                    f"⚠️ Ошибка при получении списка репозиториев, статус: {response.status}"
                )
                return []
    except Exception as e:
        logger.warning(f"❌ Ошибка при запросе репозиториев: {str(e)}")
        return []


# Функция для проверки репозитория
async def check_repo_status(session, repo_url, repo_name, auth, repo_type, repo_format):
    """Проверяет статус репозитория через GET-запрос"""
    try:
        # Формируем URL для проверки
        check_url = f"{repo_url}service/rest/repository/browse/{repo_name}"

        # Отправляем GET-запрос для проверки доступности репозитория
        async with session.get(
            check_url, auth=aiohttp.BasicAuth(*auth), timeout=10
        ) as response:
            if response.status == 200:
                # Если статус 200, репозиторий доступен
                logger.info(
                    f"✅ Репозиторий {repo_name} работает. Статус {response.status}"
                )
                # Записываем метрику с дополнительными данными
                REPO_STATUS.labels(
                    repository=repo_name, url=check_url, type=repo_type, format=repo_format
                ).set(1)
            else:
                # Если не 200, репозиторий не работает
                logger.warning(
                    f"⚠️ Ошибка при проверке репозитория {repo_name}, статус: {response.status}"
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
async def monitor_hosted_repos(nexus_url, auth):
    async with aiohttp.ClientSession() as session:
        # Получаем список всех репозиториев
        repos_data = await get_all_repositories(session, nexus_url, auth)

        # Фильтруем репозитории по типу hosted и group
        hosted_repos = [
            repo for repo in repos_data if repo["type"] in ["hosted", "group"]
        ]

        # Если репозитории найдены, проверяем их статус
        if hosted_repos:
            logger.info(f"📦 Проверяем репозитории: {', '.join([repo['name'] for repo in hosted_repos])}")
            tasks = []
            for repo in hosted_repos:
                # Для каждого репозитория передаем имя, url, тип и формат
                tasks.append(
                    check_repo_status(
                        session, 
                        nexus_url, 
                        repo["name"], 
                        auth, 
                        repo["type"], 
                        repo.get("format", "unknown")  # Добавляем формат, если он существует
                    )
                )
            await asyncio.gather(*tasks)
        else:
            logger.warning("⚠️ Не найдено репозиториев типа hosted или group.")


# Основная функция запуска
def fetch_static_status(nexus_url, auth):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(monitor_hosted_repos(nexus_url, auth))

