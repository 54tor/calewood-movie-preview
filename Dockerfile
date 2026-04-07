FROM --platform=linux/amd64 python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN useradd --create-home --uid 1000 docker-user

COPY docker/entrypoint.py /app/entrypoint.py

USER docker-user

ENTRYPOINT ["python", "/app/entrypoint.py"]
