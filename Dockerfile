# Stage 1: build the React app into static files.
FROM node:24-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: the Python server. It also serves the built React files (WhiteNoise).
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_DEBUG=0

# The backend is at /app/backend and the React build at /app/frontend/dist.
# settings.py looks for it in that place.
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend /app/frontend/dist /app/frontend/dist

# Run as a normal user, not as root.
RUN useradd --system --no-create-home appuser
USER appuser

# One worker, so the in-memory weather cache is shared. Eight threads handle parallel requests.
# The timeout is above the longest weather wait (90 s, plus one retry).
CMD exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 8 --timeout 200
