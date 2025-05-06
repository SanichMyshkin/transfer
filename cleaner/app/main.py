import logging
import requests
from config import BASE_URL, USER_NAME, PASSWORD
from cleaner import clear_repository

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def main():
    try:
        response = requests.get(
            f"{BASE_URL}/service/rest/v1/repositories", auth=(USER_NAME, PASSWORD)
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Не удалось получить список репозиториев: {e}")
        exit(1)

    result = [
        repo.get("name")
        for repo in data
        if repo.get("format") == "docker" and repo.get("type") == "hosted"
    ]

    if not result:
        logging.error("❌ Репозитории типа docker/hosted не найдены")
        exit(1)

    for repo_name in result:
        clear_repository(repo_name)


if __name__ == "__main__":
    main()
