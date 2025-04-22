import logging
from hurry.filesize import size
from psycopg2 import sql

from db.connection import get_db_connection

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def get_repository_sizes():
    """Функция для вычисления размера репозиториев"""

    repos_size = {}
    conn = None

    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Получаем имена всех таблиц типа *_content_repository
            cur.execute(
                "SELECT tablename FROM pg_catalog.pg_tables WHERE tablename LIKE %s;",
                ("%_content_repository",),
            )
            content_repository_tables_names = [x[0] for x in cur.fetchall()]

            for content_repo in content_repository_tables_names:
                repo_type = content_repo.replace("_content_repository", "")
                query = sql.SQL(
                    """
                    SELECT r.name, SUM(blob_size)
                    FROM {} t_ab
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

    except Exception as e:
        logging.error(f"❌ Ошибка при получении размеров репозиториев: {e}")
    finally:
        if conn:
            conn.close()

    return repos_size
