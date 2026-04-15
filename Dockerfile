FROM node:22-slim AS frontend

WORKDIR /build
COPY package.json package-lock.json tailwind.config.js ./
COPY ui/src/ ui/src/
COPY ui/templates/ ui/templates/
RUN npm ci && npm run build

FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main

COPY . .
COPY --from=frontend /build/ui/static/css/ ui/static/css/
COPY --from=frontend /build/ui/static/js/ ui/static/js/
