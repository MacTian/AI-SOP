# Multi-stage Dockerfile for AI SOP Monitor
# Stage 1: Build frontend
FROM node:18-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
RUN npm run build

# Stage 2: Python backend
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt* ./
RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] opencv-python-headless numpy \
    pydantic pydantic-settings aiofiles python-multipart \
    pyyaml sqlalchemy ultralytics mediapipe torch --extra-index-url https://download.pytorch.org/whl/cpu

# Copy backend code
COPY backend/ backend/
COPY sop_definitions/ sop_definitions/
COPY yolov8n.pt* ./
COPY backend/inference/models/ backend/inference/models/

# Copy built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist/ static/

# Create directories
RUN mkdir -p screenshots

# Environment
ENV SOP_CAMERA_DEVICE=0
ENV SOP_MODEL_PATH=yolov8n.pt
ENV SOP_DATABASE_URL=sqlite:///./sop_monitor.db
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python3", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
