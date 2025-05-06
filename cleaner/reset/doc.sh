#!/bin/bash

# === НАСТРОЙКИ ===
SOURCE_IMAGE="registry.access.redhat.com/ubi8/ubi"
NEXUS_REGISTRY="sanich.space:8082"
REPOSITORY="docker"
TARGET_IMAGE="$NEXUS_REGISTRY/$REPOSITORY/ubi"

# === СКАЧИВАЕМ ОБРАЗ ===
echo "Скачиваем образ $SOURCE_IMAGE..."
docker pull $SOURCE_IMAGE

# === ТЕГИ И PUSH ===
for env in dev test master release; do
  for i in {1..5}; do
    TAG="${env}-ubi.v${i}"
    echo "Создаём и пушим тег $TAG..."
    docker tag $SOURCE_IMAGE $TARGET_IMAGE:$TAG
    docker push $TARGET_IMAGE:$TAG
  done
done

echo "Все теги (dev, test, master, release) успешно отправлены в Nexus: $NEXUS_REGISTRY"
