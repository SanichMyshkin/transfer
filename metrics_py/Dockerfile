FROM python:3.11-slim

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml ./

RUN uv pip install --system --no-deps pyproject.toml

COPY . .

EXPOSE 8000

CMD ["uv", "run", "main.py"]
