import logging
from database.connection import get_db_connection

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(module)s - %(message)s"
)
logger = logging.getLogger(__name__)


def fetch_docker_ports():
    """
    Получает имя docker-репозитория, порт и удалённый URL из Nexus
    """
    conn = None
    docker_repos_info = []

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    r.name,
                    r.attributes
                FROM
                    repository r
                WHERE
                    r.recipe_name LIKE 'docker%';
            """)
            rows = cur.fetchall()

            for repo_name, attributes in rows:
                try:
                    http_port = attributes.get("docker", {}).get("httpPort")
                    remote_url = attributes.get("proxy", {}).get("remoteUrl")
                    docker_repos_info.append(
                        {
                            "repository_name": repo_name,
                            "http_port": int(http_port),
                            "remote_url": remote_url,
                        }
                    )
                except Exception as parse_error:
                    logger.warning(
                        f"⚠️ Ошибка при обработке атрибутов репозитория {repo_name}: {parse_error}"
                    )

    except Exception as e:
        logger.error(f"❌ Ошибка при запросе данных docker-репозиториев: {e}")
    finally:
        if conn:
            conn.close()

    return docker_repos_info
