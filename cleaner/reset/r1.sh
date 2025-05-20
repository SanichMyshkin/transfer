#!/bin/bash

# === НАСТРОЙКИ ===
SOURCE_IMAGE="registry.access.redhat.com/ubi8/ubi"
NEXUS_REGISTRY="sanich.space:8086"
REPOSITORY="docker"
TARGET_IMAGE="$NEXUS_REGISTRY/$REPOSITORY/ubi-test"

# === СКАЧИВАЕМ ОБРАЗ ===
echo "Скачиваем образ $SOURCE_IMAGE..."
docker pull $SOURCE_IMAGE

# === PUSH С ТЕГАМИ r1- ===
for i in {1..3}; do
  TAG="r1-v${i}"
  echo "🔄 Создаём и пушим тег $TAG..."
  docker tag $SOURCE_IMAGE $TARGET_IMAGE:$TAG
  docker push $TARGET_IMAGE:$TAG
done

# === PUSH С ТЕГАМИ r- ===
for i in {1..3}; do
  TAG="r-v${i}"
  echo "🔄 Создаём и пушим тег $TAG..."
  docker tag $SOURCE_IMAGE $TARGET_IMAGE:$TAG
  docker push $TARGET_IMAGE:$TAG
done

# === PUSH ОБРАЗОВ БЕЗ ПРЕФИКСА ===
for i in {1..3}; do
  TAG="plain-v${i}"
  echo "🔄 Создаём и пушим тег без префикса: $TAG..."
  docker tag $SOURCE_IMAGE $TARGET_IMAGE:$TAG
  docker push $TARGET_IMAGE:$TAG
done

# === PUSH latest ===
echo "🔒 Создаём и пушим тег latest..."
docker tag $SOURCE_IMAGE $TARGET_IMAGE:latest
docker push $TARGET_IMAGE:latest

# === PUSH r1-latest ===
echo "🔒 Создаём и пушим тег r1-latest..."
docker tag $SOURCE_IMAGE $TARGET_IMAGE:r1-latest
docker push $TARGET_IMAGE:r1-latest
