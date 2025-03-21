import os
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth

load_dotenv()

NEXUS_API_URL = "http://sanich.space/service/rest/v1/repositories"
NEXUS_USERNAME = os.getenv("NEXUS_USERNAME")
NEXUS_PASSWORD = os.getenv("NEXUS_PASSWORD")


def check_repository_status(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return "Работает"
        else:
            return f"Ошибка {response.status_code}"
    except requests.exceptions.RequestException as e:
        return f"Ошибка запроса: {e}"


def show_repo(repositories):
    print(f"Получено {len(repositories)} репозиториев:")
    for repo in repositories:
        repo_name = repo["name"]
        repo_url = repo["url"] + "/"
        status = check_repository_status(repo_url)
        print(f"Репозиторий: {repo_name} | URL: {repo_url} | Статус: {status}")


def fetch_repositories():
    try:
        response = requests.get(
            NEXUS_API_URL, auth=HTTPBasicAuth(NEXUS_USERNAME, NEXUS_PASSWORD)
        )
        response.raise_for_status()

        repositories = response.json()
        print(repositories)
        show_repo(repositories)

    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении репозиториев: {e}")


def main():
    fetch_repositories()


if __name__ == "__main__":
    main()
