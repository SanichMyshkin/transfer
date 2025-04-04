import requests
import asyncio
import aiohttp
import socket

# Конфигурация Nexus
NEXUS_URL = "http://sanich.space"
NEXUS_API = f"{NEXUS_URL}/service/rest/v1/repositories"
AUTH = ("admin", "admin123")
HEADERS = {"User-Agent": "Mozilla/5.0"}  # Для обхода блокировок


def get_all_repositories():
    """Получает список только прокси-репозиториев из Nexus"""
    try:
        response = requests.get(NEXUS_API, auth=AUTH, timeout=10, headers=HEADERS)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ Ошибка при запросе Nexus: {e}")
        return []

    repos = response.json()
    result = []

    for repo in repos:
        if repo["type"] == "proxy":  # Фильтруем только прокси-репозитории
            repo_url = f"{NEXUS_URL}/service/rest/repository/browse/{repo['name']}/"
            
            # Формируем remote_url с учетом типа репозитория
            if repo["format"] == "docker":
                remote_url = f"{repo.get('attributes', {}).get('proxy', {}).get('remoteUrl', '')}/v2"
            else:
                remote_url = repo.get("attributes", {}).get("proxy", {}).get("remoteUrl", "")

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
        print(f"❌ Невозможно разрешить домен: {domain}")
        return False


async def fetch_status(session, repo):
    """Асинхронная проверка доступности репозитория и его удаленного источника"""
    nexus_status = "❌"
    remote_status = "N/A"

    # Проверка локального репозитория в Nexus
    try:
        async with session.get(
            repo["url"], timeout=10, auth=aiohttp.BasicAuth(*AUTH)
        ) as response:
            if response.status == 200:
                nexus_status = "✅"
            else:
                print(f"⚠️ {repo['name']} (Nexus) вернул {response.status}")
    except asyncio.TimeoutError:
        print(f"⏳ Таймаут Nexus для {repo['name']}")

    # Обработка remote_url для docker
    remote_url = repo["remote"]
    if remote_url == "https://registry-1.docker.io":
        remote_url += "/v2"

    # Проверка удаленного источника (если есть)
    if remote_url and is_domain_resolvable(remote_url):
        try:
            async with session.get(remote_url, timeout=10) as response:
                if response.status == 200 or response.status == 401:  # Считаем 401 как успешный ответ
                    remote_status = "✅"
                else:
                    print(f"⚠️ {repo['name']} (remote) вернул {response.status}")
        except asyncio.TimeoutError:
            print(f"⏳ Таймаут remote для {repo['name']}")

    overall_status = (
        "✅ Рабочий"
        if nexus_status == "✅" and remote_status == "✅"
        else "❌ Проблема"
    )
    return {
        "repo": repo["name"],
        "nexus": nexus_status,
        "remote": remote_status,
        "status": overall_status,
    }


async def check_all_repositories(repos):
    """Запускает проверку всех репозиториев асинхронно"""
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        tasks = [fetch_status(session, repo) for repo in repos]
        results = await asyncio.gather(*tasks)
        return results


def main():
    repos = get_all_repositories()  # Получаем только прокси-репозитории
    results = asyncio.run(check_all_repositories(repos))

    print("\n===== ОТЧЕТ О ПРОВЕРКЕ ПРОКСИ-РЕПОЗИТОРИЕВ =====\n")
    print(f"{'Репозиторий':<25} {'Nexus':<10} {'Remote':<10} {'Статус':<20}")
    print("=" * 70)
    for result in results:
        print(
            f"{result['repo']:<25} {result['nexus']:<10} {result['remote']:<10} {result['status']:<20}"
        )
    print("\n" + "=" * 70 + "\n")


if __name__ == "__main__":
    main()
