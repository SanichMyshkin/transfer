import logging
from urllib.parse import urlparse
from hurry.filesize import size
import psycopg2
from psycopg2 import sql

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def get_repository_sizes(db_url):
    """Функция для вычисления размера репозиториев"""
    if not db_url:
        logging.error("❌ Переменная окружения DATABASE_URL не задана. Пропуск подсчёта размеров.")
        return {}

    repos_size = {}
    conn = None

    try:
        db_params = urlparse(db_url)
        conn_params = {
            "host": db_params.hostname,
            "database": db_params.path.lstrip("/"),
            "user": db_params.username,
            "password": db_params.password,
            "port": db_params.port or 5432,
        }

        conn = psycopg2.connect(**conn_params)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tablename FROM pg_catalog.pg_tables WHERE tablename LIKE %s;",
                ("%_content_repository",),
            )
            content_repository_tables_names = [x[0] for x in cur.fetchall()]

            for content_repo in content_repository_tables_names:
                repo_type = content_repo.replace("_content_repository", "")
                query = sql.SQL(
                    """
                    SELECT r.name, SUM(blob_size) FROM {} t_ab
                    JOIN {} t_a ON t_ab.asset_blob_id = t_a.asset_blob_id
                    JOIN {} t_cr ON t_cr.repository_id = t_a.repository_id
                    JOIN repository r ON t_cr.config_repository_id = r.id
                    GROUP BY r.name;
                    """
                ).format(
                    sql.Identifier(f"{repo_type}_asset_blob"),
                    sql.Identifier(f"{repo_type}_asset"),
                    sql.Identifier(f"{repo_type}_content_repository"),
                )
                cur.execute(query)
                repos_size.update(dict(cur.fetchall()))

            if repos_size:
                total_size = sum(repos_size.values())
                for repo_name, repo_size in repos_size.items():
                    logging.info(f"{repo_name}: {size(repo_size)}")
                logging.info(f"Общий размер: {size(total_size)}")
            else:
                logging.info("Репозитории не найдены или их размер 0.")

    except psycopg2.OperationalError as e:
        logging.error(f"❌ Не удалось подключиться к БД. Проверьте параметры подключения: {e}")
    except psycopg2.Error as e:
        logging.error(f"❌ Ошибка работы с базой данных: {e}")
    except Exception as e:
        logging.error(f"❌ Неожиданная ошибка: {e}")
    finally:
        if conn:
            conn.close()

    return repos_size