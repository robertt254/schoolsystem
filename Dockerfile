# Stage 1: Build the Vue frontend
FROM node:22-alpine AS build-frontend
WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./

# Empty string = relative URLs, so the SPA calls /api/... on the same origin
# as the FastAPI backend (same container, same domain on Render).
ENV VITE_API_URL=""
ENV NODE_ENV=production

RUN npm run build


# Stage 2: FastAPI backend — also serves the compiled frontend
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./backend/

# Copy built frontend into the expected location
COPY --from=build-frontend /app/frontend/dist ./frontend/dist

# Allow `import auth`, `import models`, etc. without package prefixes
ENV PYTHONPATH=/app/backend

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
