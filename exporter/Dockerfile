FROM python:3.10-slim

RUN python3 -m venv /app/.venv

WORKDIR /app
COPY . .

RUN /app/.venv/bin/pip install --no-cache-dir -r requirements.txt


ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

EXPOSE 8000

CMD ["python", "main.py"]
