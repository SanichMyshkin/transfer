import requests
import asyncio
import aiohttp
import socket
import logging
from prometheus_client import Gauge

# Прометеус метрики
REPO_STATUS = Gauge(
    "nexus_proxy_repo_status",
    "Статус репозитория в Nexus",
    [
        "repo_name",
        "repo_format",
        "nexus_url",
        "remote_url",
        "nexus_status",
        "remote_status",
    ],
)

# Настройка логирования
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def get_all_repositories(nexus_url, auth):
    """Получает список только прокси-репозиторов из Nexus"""
    # Формируем endpoint с учетом base URL
    nexus_endpoint = f"{nexus_url}/service/rest/v1/repositories"
    
    try:
        response = requests.get(nexus_endpoint, auth=auth, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"❌ Ошибка при запросе Nexus: {e}")
        return []

    repos = response.json()
    result = []

    for repo in repos:
        if repo["type"] == "proxy":  # Фильтруем только прокси-репозитории
            repo_url = f"{nexus_url}service/rest/repository/browse/{repo['name']}/"

            # Формируем remote_url с учетом типа репозитория
            if repo["format"] == "docker":
                remote_url = f"{repo.get('attributes', {}).get('proxy', {}).get('remoteUrl', '')}/v2"
            else:
                remote_url = (
                    repo.get("attributes", {}).get("proxy", {}).get("remoteUrl", "")
                )

            result.append(
                {
                    "name": repo["name"],
                    "url": repo_url,
                    "type": repo["format"],
                    "remote": remote_url if repo.get("type") == "proxy" else None,
                }
            )
    return result


def is_domain_resolvable(url):
    """Проверяет, можно ли разрешить доменное имя"""
    try:
        domain = url.split("/")[2]  # Извлекаем домен из URL
        socket.gethostbyname(domain)
        return True
    except socket.gaierror:
        logger.warning(f"❌ Невозможно разрешить домен: {domain}")
        return False


async def fetch_status(session, repo, auth):
    """Асинхронная проверка доступности репозитория и его удаленного источника"""
    nexus_status = "❌"
    remote_status = "❌"
    
    # Проверка локального репозитория в Nexus
    try:
        async with session.get(
            repo["url"], timeout=10, auth=aiohttp.BasicAuth(*auth)
        ) as response:
            if response.status == 200:
                nexus_status = "✅"
                logger.info(f"✅ Репозиторий {repo['name']} доступен в Nexus.")
            else:
                logger.warning(f"⚠️ {repo['name']} (Nexus) вернул {response.status}")
    except asyncio.TimeoutError:
        logger.warning(f"⏳ Таймаут Nexus для {repo['name']}")

    # Проверка удаленного источника (если есть)
    if repo["remote"] and is_domain_resolvable(repo["remote"]):
        try:
            async with session.get(repo["remote"], timeout=10) as response:
                if response.status == 200:
                    remote_status = "✅"
                    logger.info(f"✅ Репозиторий {repo['name']} доступен по удаленному источнику.")
                elif response.status == 401 and repo["type"] == "docker":
                    remote_status = "✅ (401)"  # Для Docker репозиториев считаем 401 нормой
                    logger.info(f"✅ Репозиторий {repo['name']} вернул 401 (что нормально для Docker).")
                else:
                    logger.warning(f"⚠️ {repo['name']} (remote) вернул {response.status}")
        except asyncio.TimeoutError:
            logger.warning(f"⏳ Таймаут remote для {repo['name']}")

    # Для Docker репозиториев с 401 статусом считаем, что все в порядке
    if repo["type"] == "docker" and remote_status == "✅ (401)":
        overall_status = "✅ Рабочий"
    else:
        overall_status = (
            "✅ Рабочий"
            if nexus_status == "✅" and remote_status == "✅"
            else "❌ Проблема"
        )

    # Публикация метрик в Prometheus
    REPO_STATUS.labels(
        repo_name=repo["name"],
        repo_format=repo["type"],
        nexus_url=repo["url"],
        remote_url=repo["remote"] or "",
        nexus_status=nexus_status,
        remote_status=remote_status,
    ).set(1 if overall_status == "✅ Рабочий" else 0)

    # Логирование итогового статуса репозитория
    logger.info(f"Статус репозитория {repo['name']}: {overall_status}")

    return {
        "repo": repo["name"],
        "nexus": nexus_status,
        "remote": remote_status,
        "status": overall_status,
    }


async def check_all_repositories(nexus_url, auth):
    """Запускает проверку всех репозиториев асинхронно"""
    repos = get_all_repositories(nexus_url, auth)
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_status(session, repo, auth) for repo in repos]
        results = await asyncio.gather(*tasks)
        return results


# Главная функция, которую можно вызвать из другого модуля
def fetch_repositories_metrics(nexus_url, auth):
    """Главная функция для внешнего использования"""
    loop = asyncio.get_event_loop()
    loop.run_until_complete(check_all_repositories(nexus_url, auth))
