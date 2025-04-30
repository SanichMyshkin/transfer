import ssl
import socket
from urllib.parse import urlparse
from pathlib import Path
import requests
import certifi
import os

CERTS_DIR = Path("custom_certs")
COMBINED_CA = Path("combined_custom_ca.pem")

def download_cert(url):
    hostname = urlparse(url).hostname
    if not hostname:
        print(f"[!] Невалидный URL: {url}")
        return None

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
                print(f"[✓] Сертификат сохранён для {hostname}")
                return cert_path
    except Exception as e:
        print(f"[✗] Ошибка при получении сертификата с {url}: {e}")
        return None

def combine_certs():
    with open(COMBINED_CA, "w") as out:
        # Сначала доверенные от certifi
        with open(certifi.where(), "r") as f:
            out.write(f.read())
        # Потом кастомные
        for cert_file in CERTS_DIR.glob("*.pem"):
            with open(cert_file, "r") as f:
                out.write(f.read())
    print(f"[✓] Объединённый CA-файл сохранён: {COMBINED_CA.resolve()}")

def check_url_with_cert(url):
    try:
        response = requests.get(url, verify=str(COMBINED_CA), timeout=10)
        print(f"[✔] {url} — SSL ОК, HTTP {response.status_code}")
    except requests.exceptions.SSLError as e:
        print(f"[SSL ✗] {url} — SSL ошибка: {e}")
    except requests.exceptions.RequestException as e:
        print(f"[HTTP ✗] {url} — ошибка запроса: {e}")

def main():
    # === Пример входных данных ===
    urls = [
        "https://self-signed.badssl.com/",
        "https://expired.badssl.com/",
        "https://sha256.badssl.com/",
        "https://wrong.host.badssl.com/",
        "https://untrusted-root.badssl.com/",
        "https://google.com/",
    ]

    print("🔄 Скачиваем сертификаты...")
    for url in urls:
        download_cert(url)

    print("\n📦 Объединяем сертификаты...")
    combine_certs()

    print("\n🔍 Проверяем URL с новыми сертификатами...")
    for url in urls:
        check_url_with_cert(url)

if __name__ == "__main__":
    main()
