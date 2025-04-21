from urllib.parse import urlparse
import psycopg2
from prometheus_client import Gauge
import logging


# Gauge метрика: количество тегов на образ с перечислением тегов
docker_tags_gauge = Gauge(
    "docker_image_tags_info",
    "Docker image tags count with tag list",
    ["image_name", "tags"],
)


def fetch_docker_tags_metrics(db_url: str):
    try:
        db_params = urlparse(db_url)
        conn_params = {
            "host": db_params.hostname,
            "database": db_params.path.lstrip("/"),
            "user": db_params.username,
            "password": "****",  # не логируем пароль
            "port": db_params.port or 5432,
        }

        logging.debug(
            f"Connecting to DB with params: host={db_params.hostname}, db={db_params.path.lstrip('/')}, user={db_params.username}, port={db_params.port or 5432}"
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
                logging.debug("Executing SELECT query on docker_component...")
                cur.execute("SELECT attributes FROM docker_component;")
                result = cur.fetchall()

        logging.info(f"Fetched {len(result)} rows from docker_component.")

        tags_dict = {}
        skipped = 0

        for row in result:
            attrs = row[0].get("docker")
            if not attrs:
                skipped += 1
                continue

            name = attrs.get("imageName")
            tag = attrs.get("imageTag")
            if not name or not tag:
                skipped += 1
                continue

            tags_dict.setdefault(name, set()).add(tag)

        logging.info(
            f"Processed {len(tags_dict)} images. Skipped {skipped} rows due to missing data."
        )

        # Сброс старых меток
        docker_tags_gauge.clear()

        for name, tags in tags_dict.items():
            tag_list = sorted(tags)
            tag_str = "; ".join(tag_list)
            count = len(tags)

            logging.debug(f"Image: {name} | Tags ({count}): {tag_str}")
            docker_tags_gauge.labels(image_name=name, tags=tag_str).set(count)

        logging.info(f"Updated metrics for {len(tags_dict)} docker images.")

    except Exception as e:
        logging.error(f"Error while fetching docker tags: {e}")



'''

SELECT 
    dc.name AS image_name,
    dc.version AS image_tag,
    r.name AS repository_name
FROM 
    docker_component dc
JOIN 
    docker_content_repository dcr ON dc.repository_id = dcr.repository_id
JOIN 
    repository r ON dcr.config_repository_id = r.id;

'''