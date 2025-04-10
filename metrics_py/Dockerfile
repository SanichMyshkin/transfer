FROM python:3.10-slim

# Устанавливаем системные зависимости и обновляем сертификаты
RUN apt-get update && apt-get install -y \
    ca-certificates \
    gcc \
    libffi-dev \
    libpq-dev \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем рабочую директорию — в дальнейшем она будет монтироваться как volume
WORKDIR /wdata/nexus/nexus-metric

# Создаём виртуальное окружение внутри volume
RUN python3 -m venv /wdata/nexus/nexus-metric/.venv

# Устанавливаем переменные окружения для виртуального окружения
ENV VIRTUAL_ENV=/wdata/nexus/nexus-metric/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Устанавливаем зависимости (можно убрать, если будет выполняться в entrypoint)
COPY requirements.txt .
RUN $VIRTUAL_ENV/bin/pip install --no-cache-dir -r requirements.txt

# Открываем порт
EXPOSE 8000

# Команда по умолчанию — запуск приложения
CMD ["python", "main.py"]
