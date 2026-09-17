# Quick Start Guide (English)

## System Overview
AI-powered SOP (Standard Operating Procedure) compliance monitoring system that uses computer vision to verify if operators are following standard procedures.

## Quick Setup (3 Steps)

### 1. Install Dependencies
```bash
# Install Python packages
pip install -r requirements.txt

# Install Node.js packages
cd frontend && npm install
```

### 2. Start the System
```bash
# Option A: All-in-one (Recommended)
./scripts/run_spa.sh
# Opens at: http://localhost:8000

# Option B: Development mode (separate frontend/backend)
./scripts/run_dev.sh
# Frontend: http://localhost:5173
# Backend: http://localhost:8000

# Option C: Docker
./scripts/run_docker.sh
```

### 3. Login
- Username: `admin`
- Password: `admin123`
- **Important**: Change password after first login!

## Main Features
- 📹 Real-time video monitoring with AI detection
- 🤖 YOLOv8 object detection (80+ classes)
- ✋ MediaPipe hand tracking
- 🧠 LSTM action recognition
- 📝 Visual SOP editor
- 📊 Automatic compliance reporting

## Default Admin Credentials
**Username:** `admin`  
**Password:** `admin123`

⚠️ **Security Warning:** Change default password in production!

## Documentation
- [Full English Documentation](README.md)
- [中文文档](README_zh.md)

## Support
For issues or questions, please check the documentation or submit an issue on GitHub.
