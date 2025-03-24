import os
import time
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth
from url_normalize import url_normalize
from prometheus_client import start_http_server, Gauge

load_dotenv()

NEXUS_API_URL = "http://sanich.space/service/rest/v1/repositories"
NEXUS_USERNAME = os.getenv("NEXUS_USERNAME")
NEXUS_PASSWORD = os.getenv("NEXUS_PASSWORD")

# Метрика для хранения статусов репозиториев
REPO_STATUS = Gauge("nexus_repo_status", "HTTP status of Nexus repositories", ["repo_name", "repo_type"])

def check_repository_status(url):
    """Проверяет статус репозитория по URL."""
    try:
        response = requests.get(url)
        return response.status_code
    except requests.exceptions.RequestException:
        return 0  # 0 означает ошибку соединения

def fetch_repositories():
    """Получает список репозиториев и обновляет метрики."""
    try:
        response = requests.get(
            NEXUS_API_URL, auth=HTTPBasicAuth(NEXUS_USERNAME, NEXUS_PASSWORD)
        )
        response.raise_for_status()
        repositories = response.json()

        for repo in repositories:
            normal_url = url_normalize(repo.get("url"))
            status_code = check_repository_status(normal_url + "/")

            repo_name = repo.get("name", "unknown")
            repo_type = repo.get("type", "unknown")

            # Обновляем метрику
            REPO_STATUS.labels(repo_name=repo_name, repo_type=repo_type).set(status_code)

    except requests.exceptions.RequestException as e:
        print(f"Ошибка при получении репозиториев: {e}")

def main():
    # Запускаем HTTP-сервер для метрик на порту 8000
    start_http_server(8000)
    print("Prometheus метрики доступны на http://localhost:8000")

    # Бесконечный цикл для обновления метрик
    while True:
        fetch_repositories()
        time.sleep(30)  # Обновляем метрики каждые 30 секунд

if __name__ == "__main__":
    main()
