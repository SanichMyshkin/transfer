from urllib.parse import urlparse
import psycopg2
from prometheus_client import Gauge
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Метрика Prometheus: количество тегов у образа + список тегов
docker_tags_gauge = Gauge(
    "docker_image_tags_info",
    "Информация о Docker-образах и их тегах",
    ["image_name", "tags", "repository", "format", "blob"],
)


def process_docker_result(result):
    """
    Обрабатывает данные из БД и группирует образы по имени, тегам, репозиторию и формату.
    Возвращает список словарей.
    """
    tags_list = []

    for row in result:
        image = row[0]
        tag = row[1]
        repo = row[2]
        repo_format = row[3]
        blob_name = row[4]

        found = False
        for entry in tags_list:
            if (
                entry["image"] == image
                and entry["repoName"] == repo
                and entry["repoFormat"] == repo_format
                and entry["blobName"] == blob_name
            ):
                if tag not in entry["tags"]:
                    entry["tags"].append(tag)
                found = True
                break

        if not found:
            tags_list.append(
                {
                    "image": image,
                    "tags": [tag],
                    "repoName": repo,
                    "repoFormat": repo_format,
                    "blobName": blob_name,
                }
            )

    return tags_list


def fetch_docker_tags_metrics(db_url: str):
    try:
        db_params = urlparse(db_url)

        logging.info(
            f"Подключение к базе данных: хост={db_params.hostname}, порт={db_params.port or 5432}, база={db_params.path.lstrip('/')}, пользователь={db_params.username}"
        )

        real_conn_params = {
            "host": db_params.hostname,
            "database": db_params.path.lstrip("/"),
            "user": db_params.username,
            "password": db_params.password,
            "port": db_params.port or 5432,
        }

        with psycopg2.connect(**real_conn_params) as conn:
            with conn.cursor() as cur:
                logging.debug("Выполнение SQL-запроса к docker_component...")
                cur.execute("""
                    SELECT
                        dc.name AS component_name,
                        dc.version,
                        r.name AS repository_name,
                        r.recipe_name AS format,
                        (r.attributes::jsonb -> 'storage' ->> 'blobStoreName') AS blob_store_name
                    FROM
                        docker_component dc
                    JOIN
                        docker_content_repository dcr ON dc.repository_id = dcr.repository_id
                    JOIN
                        repository r ON dcr.config_repository_id = r.id;
                """)
                result = cur.fetchall()

        logging.info(f"Получено {len(result)} строк из базы данных.")

        grouped = process_docker_result(result)

        # Сброс старых меток
        docker_tags_gauge.clear()

        for entry in grouped:
            image = entry["image"]
            tags = sorted(entry["tags"])
            repo = entry["repoName"]
            repo_format = entry["repoFormat"]
            blob = entry["blobName"]

            tag_str = "; ".join(tags)
            tag_count = len(tags)

            logging.info(
                f"Образ: {image}, Репозиторий: {repo}, Теги ({tag_count}): {tag_str}"
            )

            docker_tags_gauge.labels(
                image_name=image,
                tags=tag_str,
                repository=repo,
                format=repo_format,
                blob=blob,
            ).set(tag_count)

        logging.info(f"Метрики обновлены для {len(grouped)} Docker-образов.")

    except Exception as e:
        logging.error(f"Ошибка при получении метрик Docker-образов: {e}")
