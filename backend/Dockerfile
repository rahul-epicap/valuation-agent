FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
# Filter out Bloomberg Terminal SDK packages (not available outside Bloomberg workstations)
RUN grep -v -E "^(blpapi|blp)" requirements.txt > requirements-deploy.txt && \
    pip install --no-cache-dir -r requirements-deploy.txt
COPY backend/app/ ./app/
COPY backend/indices.json backend/tickers.json ./
COPY --from=frontend-build /frontend/out ./frontend/out/
EXPOSE 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
