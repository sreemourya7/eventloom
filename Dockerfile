FROM node:22-bookworm-slim AS frontend
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/ backend/
RUN pip install --no-cache-dir --no-deps ./backend
COPY scripts/ scripts/
COPY data/ data/
COPY benchmarks/matcher_config.json benchmarks/matcher_config.json
COPY --from=frontend /web/dist frontend/dist
RUN useradd --create-home --uid 10001 eventloom && chown -R eventloom:eventloom /app
USER eventloom
EXPOSE 8000
CMD ["sh", "-c", "python scripts/initialize.py && uvicorn eventloom.api:app --host 0.0.0.0 --port 8000 --workers 1"]
