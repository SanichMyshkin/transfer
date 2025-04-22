import logging
from prometheus_client import Gauge

from database.tags_query import fetch_docker_tags_data

# Метрика Prometheus
docker_tags_gauge = Gauge(
    "docker_image_tags_info",
    "Информация о Docker-образах и их тегах",
    ["image_name", "tags", "repository", "format", "blob"],
)


def process_docker_result(result: list) -> list:
    tags_list: list = []

    for row in result:
        image, tag, repo, repo_format, blob_name = row

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


def fetch_docker_tags_metrics() -> None:
    try:
        result = fetch_docker_tags_data()
        logging.info(f"Получено {len(result)} строк из базы данных.")
        grouped = process_docker_result(result)

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
