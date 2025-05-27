import logging
import requests
import urllib3
from requests.exceptions import SSLError, RequestException, ConnectionError

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120 Safari/537.36"
    )
}

session = requests.Session()
adapter = requests.adapters.HTTPAdapter(max_retries=0)
session.mount("https://", adapter)
session.mount("http://", adapter)


def safe_get_json(url: str, auth: tuple, timeout: int = 20):
    try:
        response = session.get(url, auth=auth, headers=HEADERS, timeout=timeout, verify=True)
        response.raise_for_status()
        return response.json()
    except SSLError as ssl_err:
        logger.warning(f"⚠️ SSL ошибка при запросе к {url}: {ssl_err}")
        try:
            response = session.get(url, auth=auth, headers=HEADERS, timeout=timeout, verify=False)
            logger.warning(f"⚠️ Использован verify=False для {url}")
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            logger.error(f"❌ Ошибка запроса без verify: {e}")
            return []
    except (ConnectionError, RequestException) as e:
        logger.error(f"❌ Ошибка подключения к {url}: {e}")
        return []


def safe_get_raw(url: str, auth: tuple = None, timeout: int = 20):
    try:
        response = session.get(url, auth=auth, headers=HEADERS, timeout=timeout, verify=True, allow_redirects=True)
        return response, None
    except SSLError as ssl_err:
        logger.warning(f"⚠️ SSL ошибка при обращении к {url}: {ssl_err}")
        try:
            response = session.get(url, auth=auth, headers=HEADERS, timeout=timeout, verify=False, allow_redirects=True)
            logger.warning(f"⚠️ Использован verify=False для {url}")
            return response, None
        except RequestException as e:
            logger.warning(f"❌ Ошибка (без verify) при обращении к {url}: {e}")
            return None, e
    except ConnectionError as e:
        logger.warning(f"❌ Ошибка подключения к {url}: {e}")
        return None, e
    except RequestException as e:
        logger.warning(f"❌ Ошибка запроса к {url}: {e}")
        return None, e


def get_certificates(nexus_url: str, auth: tuple) -> list:
    return safe_get_json(f"{nexus_url}/service/rest/v1/security/ssl/truststore", auth)


def get_repositories(nexus_url: str, auth: tuple) -> list:
    return safe_get_json(f"{nexus_url}/service/rest/v1/repositories", auth)
