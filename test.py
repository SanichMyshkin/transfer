import requests
import random
import string

# Логин и пароль от Nexus
NEXUS_USER = "admin"
NEXUS_PASS = "admin123"

# Список proxy-репозиториев
"""

"""

PROXY_REPOSITORIES = {
    "apt": "http://sanich.space/repository/apt-proxy",
    "cargo": "http://sanich.space/repository/cargo-proxy",
    "cocoapods": "http://sanich.space/repository/cocoapods-proxy",
    "composer": "http://sanich.space/repository/composer-proxy",
    "conan": "http://sanich.space/repository/conan-proxy",
    "conda": "http://sanich.space/repository/conda-proxy",
    "go": "http://sanich.space/repository/go-proxy",
    "huggingface": "http://sanich.space/repository/huggingface-proxy",
    "maven2": "http://sanich.space/repository/maven2-proxy",
    "npm": "http://sanich.space/repository/npm-proxy",
    "nuget": "http://sanich.space/repository/nuget-proxy",
    "p2": "http://sanich.space/repository/p2-proxy",
    "pypi": "http://sanich.space/repository/pypi-proxy",
    "r": "http://sanich.space/repository/r-proxy",
    "rubygems": "http://sanich.space/repository/rubygems-proxy",
    "yum": "http://sanich.space/repository/yum-proxy",
    "raw": "http://sanich.space/repository/raw-proxy",
    "docker": "http://sanich.space/repository/docker-proxy",
    "helm": "http://sanich.space/repository/helm-proxy",
}

# Список hosted-репозиториев
HOSTED_REPOSITORIES = {"raw": "http://sanich.space/repository/raw-hosted"}

# Тестовые файлы для разных типов репозиториев
PROXY_TEST_PATHS = {
    "apt": "/dists/stable/Release",
    "cargo": "/index/config.json",
    "cocoapods": "/all_pods.txt",
    "composer": "/packages.json",
    "conan": "/v1/ping",
    "conda": "/repodata.json",
    "docker": "/v2/",
    "go": "/mod/",
    "helm": "/index.yaml",
    "huggingface": "/datasets.json",
    "maven2": "/org/apache/maven/maven-metadata.xml",
    "npm": "/-/ping",
    "nuget": "/v3/index.json",
    "p2": "/compositeContent.xml",
    "pypi": "/simple/pip/",
    "r": "/src/contrib/PACKAGES",
    "rubygems": "/latest_specs.4.8.gz",
    "yum": "/repodata/repomd.xml",
    "raw": "/random-nonexistent-file.txt",
}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def check_proxy_repositories():
    """Проверяет работоспособность proxy-репозиториев Nexus."""
    for repo_type, repo_url in PROXY_REPOSITORIES.items():
        test_path = PROXY_TEST_PATHS.get(repo_type, "/random-nonexistent-file.txt")
        url = f"{repo_url}{test_path}"

        print(f"[INFO] Проверяем {repo_url} (тестовый путь: {test_path})")

        try:
            response = requests.get(url, headers=HEADERS, timeout=5)
            print(f"[DEBUG] {repo_url} → Код ответа: {response.status_code}")
            if response.status_code == 401:  # Пробуем с авторизацией
                print(
                    f"[WARN] {repo_url} требует авторизацию, пробуем заново с логином..."
                )
                response = requests.get(
                    url, headers=HEADERS, auth=(NEXUS_USER, NEXUS_PASS), timeout=5
                )
                print(
                    f"[DEBUG] {repo_url} (с авторизацией) → Код ответа: {response.status_code}"
                )

            if response.status_code == 200:
                print(f"[OK] {repo_url} корректно проксирует запрос ({test_path})")
            elif response.status_code in [403, 404]:
                print(
                    f"[WARN] {repo_url} доступен, но {test_path} не найден ({response.status_code})"
                )
            elif response.status_code == 502:
                print(f"[ERROR] {repo_url} НЕ ПРОКСИРУЕТ (502 Bad Gateway)")
            elif response.status_code == 401:
                print(
                    f"[ERROR] {repo_url} требует авторизации, но логин/пароль не подходят!"
                )
            else:
                print(f"[ERROR] {repo_url} НЕ РАБОТАЕТ (код {response.status_code})")
            print("\n" + "=" * 15)
        except requests.RequestException as e:
            print(f"[ERROR] {repo_url} НЕ ОТВЕЧАЕТ: {e}")


def generate_random_filename():
    """Генерирует случайное имя файла"""
    return "".join(random.choices(string.ascii_letters + string.digits, k=10)) + ".txt"


def check_hosted_repositories():
    """Проверяет работоспособность hosted-репозиториев Nexus."""
    for repo_type, repo_url in HOSTED_REPOSITORIES.items():
        filename = generate_random_filename()
        file_url = f"{repo_url}/{filename}"
        file_content = "Test file for Nexus hosted repository check"

        print(f"[INFO] Загружаем файл {filename} в {repo_url}...")

        try:
            upload_response = requests.put(
                file_url,
                headers=HEADERS,
                auth=(NEXUS_USER, NEXUS_PASS),
                data=file_content,
            )
            print(f"[DEBUG] Загрузка файла → Код ответа: {upload_response.status_code}")

            if upload_response.status_code not in [200, 201]:
                print(
                    f"[ERROR] Не удалось загрузить файл в {repo_url} (код {upload_response.status_code})"
                )
                continue

            print(f"[INFO] Пробуем скачать файл из {file_url}...")
            download_response = requests.get(
                file_url, headers=HEADERS, auth=(NEXUS_USER, NEXUS_PASS)
            )
            print(
                f"[DEBUG] Скачивание файла → Код ответа: {download_response.status_code}"
            )

            if (
                download_response.status_code == 200
                and download_response.text == file_content
            ):
                print(f"[OK] {repo_url} работает корректно")
            else:
                print(f"[ERROR] Файл не скачался правильно из {repo_url}!")

            print(f"[INFO] Удаляем файл {filename} из {repo_url}...")
            delete_response = requests.delete(
                file_url, headers=HEADERS, auth=(NEXUS_USER, NEXUS_PASS)
            )
            print(f"[DEBUG] Удаление файла → Код ответа: {delete_response.status_code}")

            if delete_response.status_code in [200, 204]:
                print(f"[OK] Файл успешно удалён из {repo_url}")
            else:
                print(
                    f"[ERROR] Не удалось удалить файл из {repo_url} (код {delete_response.status_code})"
                )
            print("\n")
        except requests.RequestException as e:
            print(f"[ERROR] Ошибка при работе с {repo_url}: {e}")


if __name__ == "__main__":
    print("🔍 Начинаем проверку Nexus proxy-репозиториев...")
    check_proxy_repositories()
    # print("\n🔍 Начинаем проверку Nexus hosted-репозиториев...")
    # check_hosted_repositories()
    # print("✅ Проверка завершена.")


import ssl
import socket

hostname = 'nexus.fc.uralsibbank.ru'
port = 443

# Создаём SSL-контекст с указанием сертификата
context = ssl.create_default_context(cafile='/etc/ssl/certs/py_ca.pem')

# Устанавливаем соединение
with socket.create_connection((hostname, port)) as sock:
    with context.wrap_socket(sock, server_hostname=hostname) as ssock:
        print(f"SSL connection established: {ssock.version()}")