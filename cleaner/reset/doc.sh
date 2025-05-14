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
echo "🔽 Скачиваем образы..."
docker pull $SOURCE_IMAGE
docker pull $HELLO_IMAGE
docker pull $NGINX_IMAGE

# === UBI: ТЕГИ И PUSH ===
for env in dev test master release; do
  for i in {1..5}; do
    TAG="${env}-.v${i}"
    echo "🏷️  Тегируем UBI как $TARGET_IMAGE:$TAG"
    docker tag $SOURCE_IMAGE $TARGET_IMAGE:$TAG
    echo "📤 Пушим $TARGET_IMAGE:$TAG"
    docker push $TARGET_IMAGE:$TAG
  done
done

# === UBI: latest и dev-latest ===
echo "🏷️  Тегируем UBI как latest и dev-latest"
docker tag $SOURCE_IMAGE $TARGET_IMAGE:latest
docker push $TARGET_IMAGE:latest

docker tag $SOURCE_IMAGE $TARGET_IMAGE:dev-latest
docker push $TARGET_IMAGE:dev-latest

# === HELLO-WORLD: ТЕГИ И PUSH ===
for i in {1..5}; do
  docker tag $HELLO_IMAGE $HELLO_TARGET_IMAGE:release.v${i}
  docker push $HELLO_TARGET_IMAGE:release.v${i}

  docker tag $HELLO_IMAGE $HELLO_TARGET_IMAGE:hello-world.v${i}
  docker push $HELLO_TARGET_IMAGE:hello-world.v${i}
done

# === HELLO-WORLD: latest и dev-latest ===
docker tag $HELLO_IMAGE $HELLO_TARGET_IMAGE:latest
docker push $HELLO_TARGET_IMAGE:latest

docker tag $HELLO_IMAGE $HELLO_TARGET_IMAGE:dev-latest
docker push $HELLO_TARGET_IMAGE:dev-latest

# === NGINX: ТЕГИ И PUSH ===
for i in {1..5}; do
  docker tag $NGINX_IMAGE $NGINX_TARGET_IMAGE:release.v${i}
  docker push $NGINX_TARGET_IMAGE:release.v${i}

  docker tag $NGINX_IMAGE $NGINX_TARGET_IMAGE:test.v${i}
  docker push $NGINX_TARGET_IMAGE:test.v${i}
done

# === NGINX: latest и dev-latest ===
docker tag $NGINX_IMAGE $NGINX_TARGET_IMAGE:latest
docker push $NGINX_TARGET_IMAGE:latest

docker tag $NGINX_IMAGE $NGINX_TARGET_IMAGE:dev-latest
docker push $NGINX_TARGET_IMAGE:dev-latest
