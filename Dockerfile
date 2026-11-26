# Multi-stage Dockerfile for AI SOP Monitor
# Stage 1: Build frontend
FROM node:18-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Python backend
FROM python:3.10-slim-bookworm

WORKDIR /app

# Install system dependencies for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN pip install --no-cache-dir --index-url "$PIP_INDEX_URL" \
    fastapi uvicorn[standard] opencv-python-headless numpy \
    pydantic pydantic-settings aiofiles python-multipart \
    pyyaml sqlalchemy \
    python-jose[cryptography] passlib[bcrypt] \
    filelock typing-extensions sympy networkx jinja2 fsspec pillow nvidia-ml-py \
    && pip install --no-cache-dir \
        --index-url https://download.pytorch.org/whl/cpu \
        torch torchvision \
    && pip install --no-cache-dir --index-url "$PIP_INDEX_URL" \
        ultralytics mediapipe

# Copy backend code
COPY backend/ backend/
COPY sop_definitions/ sop_definitions/
COPY backend/inference/models/ backend/inference/models/

# Copy built frontend from stage 1
COPY --from=frontend-build /app/static/ static/

# Create directories
RUN mkdir -p screenshots data

# Environment
ENV SOP_CAMERA_DEVICE=0
ENV SOP_MODEL_PATH=yolo26n.pt
ENV SOP_DATABASE_URL=sqlite:///./sop_monitor.db
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python3", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
