FROM python:3.10-slim

# Устанавливаем системные зависимости и обновляем сертификаты
RUN apt-get update && apt-get install -y \
    ca-certificates \
    && update-ca-certificates \
    && apt-get install -y \
    gcc \
    libffi-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем зависимости для работы с Python и виртуальной средой
RUN python3 -m venv /app/.venv

# Копируем проектные файлы
WORKDIR /app
COPY . .

# Устанавливаем зависимости из requirements.txt
RUN /app/.venv/bin/pip install --no-cache-dir -r requirements.txt

# Настроим переменную окружения для активации виртуального окружения
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Открываем порт
EXPOSE 8000

# Запускаем приложение через обычный Python
CMD ["python", "main.py"]
