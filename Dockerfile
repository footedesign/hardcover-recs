FROM python:3.11-slim AS python-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY backend /app/backend
COPY hardcover /app/hardcover
COPY scripts /app/scripts
COPY docker /app/docker

RUN chmod +x /app/docker/*.sh


FROM python-base AS pipeline

USER appuser


FROM python-base AS backend

USER appuser

ENTRYPOINT ["/app/docker/backend-entrypoint.sh"]


FROM node:20-slim AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend /app/frontend
RUN npm run build


FROM node:20-slim AS frontend

WORKDIR /app/frontend

COPY --from=frontend-build --chown=node:node /app/frontend/dist /app/frontend/dist
COPY --from=frontend-build --chown=node:node /app/frontend/node_modules /app/frontend/node_modules
COPY --from=frontend-build --chown=node:node /app/frontend/package.json /app/frontend/package.json
COPY --chown=node:node docker/frontend-entrypoint.sh /app/docker/frontend-entrypoint.sh

RUN chmod +x /app/docker/frontend-entrypoint.sh

USER node

ENTRYPOINT ["/app/docker/frontend-entrypoint.sh"]
