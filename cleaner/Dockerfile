# ТЕСТОВЫЙ ОБРАЗЕЦ!
FROM python:3.10-slim

# Рабочая директория внутри контейнера
WORKDIR /app

# Копируем зависимости
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения и папку с логами
COPY app/ ./app/
COPY logs/ ./logs/

# Опционально: если есть скрипт запуска или main.py
COPY main.py .

# Устанавливаем переменные окружения (по желанию)
ENV PYTHONUNBUFFERED=1

# Команда запуска — здесь предполагается, что есть main.py
CMD ["python", "main.py"]
