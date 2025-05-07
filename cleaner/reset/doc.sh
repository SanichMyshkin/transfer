#!/bin/bash

# === НАСТРОЙКИ ===
SOURCE_IMAGE="registry.access.redhat.com/ubi8/ubi"
HELLO_IMAGE="hello-world"
NEXUS_REGISTRY="sanich.space:8082"
REPOSITORY="docker"
TARGET_IMAGE="$NEXUS_REGISTRY/$REPOSITORY/ubi"
HELLO_TARGET_IMAGE="$NEXUS_REGISTRY/$REPOSITORY/hello-wold"

# === СКАЧИВАЕМ ОБРАЗЫ ===
echo "Скачиваем образ $SOURCE_IMAGE..."
docker pull $SOURCE_IMAGE

echo "Скачиваем образ $HELLO_IMAGE..."
docker pull $HELLO_IMAGE

# === ТЕГИ И PUSH ДЛЯ UBI ===
for env in dev test master release; do
  for i in {1..5}; do
    TAG="${env}-ubi.v${i}"
    echo "Создаём и пушим тег $TAG..."
    docker tag $SOURCE_IMAGE $TARGET_IMAGE:$TAG
    docker push $TARGET_IMAGE:$TAG
  done
done

# === ТЕГИ И PUSH ДЛЯ HELLO-WORLD ===
for i in {1..5}; do
  TAG="release-hello-world.v${i}"
  echo "Создаём и пушим тег $TAG..."
  docker tag $HELLO_IMAGE $HELLO_TARGET_IMAGE:$TAG
  docker push $HELLO_TARGET_IMAGE:$TAG

  TAG_NO_PREFIX="hello-world.v${i}"
  echo "Создаём и пушим тег $TAG_NO_PREFIX..."
  docker tag $HELLO_IMAGE $HELLO_TARGET_IMAGE:$TAG_NO_PREFIX
  docker push $HELLO_TARGET_IMAGE:$TAG_NO_PREFIX
done
