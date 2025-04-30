import ssl
import socket
import os
from urllib.parse import urlparse
from pathlib import Path
import requests
import certifi

CERTS_DIR = Path("custom_certs")
COMBINED_CA = Path("combined_custom_ca.pem")

# 1. Скачиваем и сохраняем SSL-сертификаты
def download_cert(url):
    hostname = urlparse(url).hostname
    port = 443

    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                der_cert = ssock.getpeercert(binary_form=True)
                pem_cert = ssl.DER_cert_to_PEM_cert(der_cert)

                CERTS_DIR.mkdir(exist_ok=True)
                cert_path = CERTS_DIR / f"{hostname}.pem"
                with open(cert_path, "w") as f:
                    f.write(pem_cert)
                print(f"[✓] Сертификат {hostname} сохранён.")
                return cert_path
    except Exception as e:
        print(f"[!] Не удалось получить сертификат для {url}: {e}")
        return None

# 2. Объединяем их в один .pem-файл + добавляем certifi CA
def combine_certs():
    with open(COMBINED_CA, "w") as out:
        # Сначала certifi корневые
        with open(certifi.where(), "r") as f:
            out.write(f.read())
        # Потом все наши
        for cert_file in CERTS_DIR.glob("*.pem"):
            with open(cert_file, "r") as f:
                out.write(f.read())
    print(f"[✓] Комбинированный CA сохранён: {COMBINED_CA}")

# 3. Запрос с использованием кастомного CA
def safe_get_custom_ca(url, **kwargs):
    try:
        r = requests.get(url, verify=str(COMBINED_CA), timeout=10, **kwargs)
        print(f"[OK] {url} — {r.status_code}")
    except requests.exceptions.SSLError as e:
        print(f"[SSL ❌] {url} — {e}")
    except Exception as e:
        print(f"[ERR] {url} — {e}")

# Пример использования
urls = [
    "https://some-custom-cert-site.com",
    "https://expired.badssl.com",  # пример проблемного SSL
]

# 1. Скачиваем серты
for url in urls:
    download_cert(url)

# 2. Комбинируем в один файл
combine_certs()

# 3. Делаем запросы
for url in urls:
    safe_get_custom_ca(url)
