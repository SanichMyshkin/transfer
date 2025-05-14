#!/bin/bash

# === НАСТРОЙКИ ===
SOURCE_IMAGE="registry.access.redhat.com/ubi8/ubi"
HELLO_IMAGE="hello-world"
NGINX_IMAGE="nginx"
NEXUS_REGISTRY="sanich.space:8086"
REPOSITORY="docker"

TARGET_IMAGE="$NEXUS_REGISTRY/$REPOSITORY/ubi"
HELLO_TARGET_IMAGE="$NEXUS_REGISTRY/$REPOSITORY/hello-world"
NGINX_TARGET_IMAGE="$NEXUS_REGISTRY/$REPOSITORY/nginx"

# === СКАЧИВАЕМ ОБРАЗЫ ===
echo "Скачиваем образ $SOURCE_IMAGE..."
docker pull $SOURCE_IMAGE

echo "Скачиваем образ $HELLO_IMAGE..."
docker pull $HELLO_IMAGE

echo "Скачиваем образ $NGINX_IMAGE..."
docker pull $NGINX_IMAGE

# === ТЕГИ И PUSH ДЛЯ UBI ===
for env in dev test master release; do
  for i in {1..5}; do
    TAG="${env}-.v${i}"
    echo "Создаём и пушим тег $TAG..."
    docker tag $SOURCE_IMAGE $TARGET_IMAGE:$TAG
    docker push $TARGET_IMAGE:$TAG
  done
done

# Добавляем и пушим latest тег для UBI
echo "Создаём и пушим тег latest для UBI..."
docker tag $SOURCE_IMAGE $TARGET_IMAGE:latest
docker push $TARGET_IMAGE:latest

# Добавляем и пушим dev-latest тег для UBI
echo "Создаём и пушим тег dev-latest для UBI..."
docker tag $SOURCE_IMAGE $TARGET_IMAGE:dev-latest
docker push $TARGET_IMAGE:dev-latest

# === ТЕГИ И PUSH ДЛЯ HELLO-WORLD ===
for i in {1..5}; do
  TAG="release.v${i}"
  echo "Создаём и пушим тег $TAG..."
  docker tag $HELLO_IMAGE $HELLO_TARGET_IMAGE:$TAG
  docker push $HELLO_TARGET_IMAGE:$TAG

  TAG_NO_PREFIX="hello-world.v${i}"
  echo "Создаём и пушим тег $TAG_NO_PREFIX..."
  docker tag $HELLO_IMAGE $HELLO_TARGET_IMAGE:$TAG_NO_PREFIX
  docker push $HELLO_TARGET_IMAGE:$TAG_NO_PREFIX
done

# Добавляем и пушим latest тег для hello-world
echo "Создаём и пушим тег latest для hello-world..."
docker tag $HELLO_IMAGE $HELLO_TARGET_IMAGE:latest
docker push $HELLO_TARGET_IMAGE:latest

# Добавляем и пушим dev-latest тег для hello-world
echo "Создаём и пушим тег dev-latest для hello-world..."
docker tag $HELLO_IMAGE $HELLO_TARGET_IMAGE:dev-latest
docker push $HELLO_TARGET_IMAGE:dev-latest

# === ТЕГИ И PUSH ДЛЯ NGINX ===
for i in {1..5}; do
  TAG="release.v${i}"
  echo "Создаём и пушим тег $TAG..."
  docker tag $NGINX_IMAGE $NGINX_TARGET_IMAGE:$TAG
  docker push $NGINX_TARGET_IMAGE:$TAG

  TAG_NO_PREFIX="test.v${i}"
  echo "Создаём и пушим тег $TAG_NO_PREFIX..."
  docker tag $NGINX_IMAGE $NGINX_TARGET_IMAGE:$TAG_NO_PREFIX
  docker push $NGINX_TARGET_IMAGE:$TAG_NO_PREFIX
done

# Добавляем и пушим latest тег для nginx
echo "Создаём и пушим тег latest для nginx..."
docker tag $NGINX_IMAGE $NGINX_TARGET_IMAGE:latest
docker push $NGINX_TARGET_IMAGE:latest

# Добавляем и пушим dev-latest тег для nginx
echo "Создаём и пушим тег dev-latest для nginx..."
docker tag $NGINX_IMAGE $NGINX_TARGET_IMAGE:dev-latest
docker push $NGINX_TARGET_IMAGE:dev-latest
