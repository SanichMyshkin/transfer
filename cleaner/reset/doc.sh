#!/bin/bash

set -e

# === НАСТРОЙКИ ===
NEXUS_REGISTRY="sanich.space:8086"

REPO_DOCKER="docker"    # с вложенной папкой docker/
REPO_ROOT=""            # корень репозитория

NGINX_IMAGE="nginx"
HELLO_IMAGE="hello-world"

# === СКАЧИВАЕМ ОБРАЗЫ ===
echo "Скачиваем образ $NGINX_IMAGE..."
docker pull $NGINX_IMAGE

echo "Скачиваем образ $HELLO_IMAGE..."
docker pull $HELLO_IMAGE

# === ОБРАЗЫ ДЛЯ ТЕСТА ===

# Вложенные пути (в docker/)
declare -A DOCKER_IMAGES=(
  ["nginx"]=$NGINX_IMAGE
  ["hello"]=$HELLO_IMAGE
  ["dev/nginx"]=$NGINX_IMAGE
  ["release/hello"]=$HELLO_IMAGE
  ["dev/europe/nginx"]=$NGINX_IMAGE
  ["test/asia/hello"]=$HELLO_IMAGE
)

# Путь без docker/ — пушим в корень
declare -A ROOT_IMAGES=(
  ["nginx"]=$NGINX_IMAGE
  ["hello-world"]=$HELLO_IMAGE
)

# Префиксы и количество тегов
PREFIXES=("dev" "test" "release" "custom" "")
TAGS_COUNT=3

# === PUSH ФУНКЦИЯ ===
function push_image_tags() {
  local image_name=$1
  local base_image=$2
  local repo=$3

  for prefix in "${PREFIXES[@]}"; do
    for i in $(seq 1 $TAGS_COUNT); do
      if [ -n "$prefix" ]; then
        TAG="${prefix}.v${i}"
      else
        TAG="v${i}"
      fi

      # Если репо задано (например, docker), включаем его в путь
      if [ -n "$repo" ]; then
        FULL_IMAGE="$NEXUS_REGISTRY/$repo/$image_name:$TAG"
      else
        FULL_IMAGE="$NEXUS_REGISTRY/$image_name:$TAG"
      fi

      echo "🏷️  Тегируем $base_image как $FULL_IMAGE"
      docker tag $base_image $FULL_IMAGE

      echo "📤 Пушим $FULL_IMAGE"
      docker push $FULL_IMAGE
    done
  done
}

# === PUSH В docker/ ===
for name in "${!DOCKER_IMAGES[@]}"; do
  push_image_tags "$name" "${DOCKER_IMAGES[$name]}" "$REPO_DOCKER"
done

# === PUSH В КОРЕНЬ РЕПОЗИТОРИЯ ===
for name in "${!ROOT_IMAGES[@]}"; do
  push_image_tags "$name" "${ROOT_IMAGES[$name]}" "$REPO_ROOT"
done
