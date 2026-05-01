# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

## Project Overview

**AI SOP Monitor** — AI 实时 SOP 合规监控系统。通过摄像头采集画面，使用 YOLOv8 目标检测 + MediaPipe 手部关键点 + LSTM 时序分类器，实时判断操作人员是否按标准作业流程（SOP）执行操作。

- **后端**: FastAPI + SQLAlchemy + SQLite + PyTorch
- **前端**: Vue 3 + Pinia + Vue Router + TailwindCSS + ECharts + Vite
- **AI**: YOLOv8 (目标检测) + MediaPipe Hand Landmarker (手部关键点) + LSTM (时序动作识别)
- **版本**: 0.1.0

## Development Commands

### Backend

```bash
# 安装依赖
pip install -r requirements.txt

# 启动后端
cd backend && python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 运行所有测试
python -m pytest tests/ -v

# 运行单个测试文件
python -m pytest tests/test_api.py -v

# 运行单个测试
python -m pytest tests/test_state_machine.py::TestStateMachine::test_basic_transition -v
```

### Frontend

```bash
# 安装依赖
cd frontend && npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 类型检查
npx vue-tsc --noEmit
```

### Docker

```bash
# 构建并启动
docker-compose up --build

# 停止
docker-compose down
```

### 一键启动（脚本）

```bash
# 同时启动前后端
bash scripts/run_all.sh

# 仅后端
bash scripts/run_backend.sh

# 仅前端
bash scripts/run_frontend.sh
```

## Environment Configuration

所有配置通过环境变量设置，前缀为 `SOP_`。参见 `backend/config.py`：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SOP_CAMERA_DEVICE` | 0 | 摄像头设备索引 |
| `SOP_CAMERA_DEVICES` | "" | 多摄像头设备ID（逗号分隔） |
| `SOP_CAMERA_FPS` | 15 | 采集帧率 |
| `SOP_MODEL_PATH` | models/yolov8n.pt | YOLO 模型路径 |
| `SOP_CONFIDENCE_THRESHOLD` | 0.5 | 检测置信度阈值 |
| `SOP_INFERENCE_INTERVAL` | 0.5 | 推理间隔（秒） |
| `SOP_DEFAULT_CONFIRM_FRAMES` | 3 | 确认步骤所需的连续命中帧数 |
| `SOP_STRICT_ORDER` | false | 是否严格按顺序执行步骤 |
| `SOP_ALERT_COOLDOWN` | 30 | 重复告警冷却时间（秒） |
| `SOP_SECRET_KEY` | (内置默认) | JWT 签名密钥 |
| `SOP_TOKEN_EXPIRE_MINUTES` | 480 | JWT 过期时间 |
| `SOP_DEFAULT_ADMIN_PASSWORD` | admin123 | 默认管理员密码 |

## High-Level Architecture

### 数据流

```
Camera(s) → CameraCapture (thread) → ImagePreprocessor → YOLOv8 Detector
                                                          ↓
                                                   MediaPipe HandExtractor
                                                          ↓
                                                   GestureClassifier
                                                          ↓
                                                   FeatureFusion (YOLO + hand = 286-dim)
                                                          ↓
                                                   LSTM MultiScaleVoter (可选)
                                                          ↓
                                                   RuleEngine.evaluate()
                                                          ↓
                                                   StateMachineEngine.process_event()
                                                          ↓
                                        ┌─────────────────┼─────────────────┐
                                   AlertManager      DB Record (SQLite)    WebSocket → Frontend
                                        ↓
                                   Screenshot saved
```

### 后端模块结构

```
backend/
├── main.py                    # FastAPI 入口，lifespan 管理
├── config.py                  # Pydantic Settings (SOP_ 前缀环境变量)
├── api/                       # REST API 路由层
│   ├── auth.py               # JWT 认证 (login, me)
│   ├── ws.py                 # WebSocket 实时推送 + 心跳
│   ├── sop.py                # SOP CRUD + 模板
│   ├── monitor.py            # 状态、告警、记录、CSV 导出、Top3 候选
│   ├── video.py              # MJPEG 流、截图、多摄像头
│   ├── video_analysis.py     # 视频文件上传 + 离线分析
│   ├── alert_config.py       # 告警规则 CRUD
│   ├── stats.py              # 统计 (时序、检测、汇总)
│   └── training.py           # 训练会话 + LSTM 训练
├── camera/                    # 摄像头采集
│   ├── capture.py            # OpenCV 线程化采集
│   ├── multi_camera.py       # 多摄像头管理器
│   └── preprocessor.py       # 图像预处理 (ROI, resize, JPEG)
├── inference/                 # AI 推理
│   ├── detector.py           # YOLOv8 检测器 (含 mock 降级)
│   ├── engine.py             # 采集→预处理→检测流水线
│   ├── class_mapping.py      # SOP 语义名 → COCO 类别映射
│   ├── hand_extractor.py     # MediaPipe 手部关键点提取
│   ├── gesture_classifier.py # 手势分类 (grab/point/pick_up/put_down/open)
│   ├── feature_fusion.py     # YOLO + 手部特征融合
│   ├── lstm_classifier.py    # StepLSTM 模型 + MultiScaleVoter
│   ├── lstm_trainer.py       # LSTM 合成数据训练
│   └── mock_data.py          # 合成训练数据生成
├── extractor/                 # 事件提取
│   ├── event.py              # SopEvent 数据类
│   └── rule_engine.py        # 检测结果 → SOP 事件映射
├── sop/                       # SOP 管理
│   ├── schema.py             # Pydantic 模型 (SopDefinition, SopStep, StepRule)
│   ├── sop_manager.py        # YAML 文件 CRUD
│   └── state_machine.py      # SOP 状态机 (命中帧确认)
├── alert/                     # 告警管理
│   └── manager.py            # 告警去重、升级、规则
├── training/                  # 训练
│   ├── session.py            # 训练录制会话
│   └── analyzer.py           # 步骤自动识别
└── models/                    # 数据模型
    ├── database.py           # SQLite 初始化、迁移、种子数据
    ├── record.py             # OperationRecord ORM
    └── user.py               # User ORM
```

### 前端模块结构

```
frontend/src/
├── main.js                    # Vue 应用入口 (Pinia + Router)
├── App.vue                    # 根组件 (导航 + Toast)
├── router/index.js            # Vue Router (认证守卫)
├── stores/                    # Pinia 状态管理
│   ├── auth.js               # 认证状态
│   └── monitor.js            # 监控状态
├── api/http.js                # Axios 实例 + JWT 拦截器
├── composables/useWebSocket.js # 自动重连 WebSocket
├── views/                     # 页面
│   ├── Dashboard.vue          # 主监控 (视频、进度、告警、Top3、图表)
│   ├── SopEditor.vue          # SOP 创建/编辑/删除
│   ├── History.vue            # 操作记录 + 截图 + CSV 导出
│   ├── Training.vue           # 训练 + LSTM 训练
│   └── Login.vue              # 登录
└── components/                # 组件
    ├── VideoStream.vue        # MJPEG 视频流
    ├── SopProgress.vue        # SOP 步骤进度条
    ├── AlertPanel.vue         # 告警列表 + ACK
    ├── AlertToast.vue         # 全局 Toast + Web Audio
    ├── StatsChart.vue         # ECharts 图表
    ├── StepEditor.vue         # 拖拽步骤编辑器
    └── TemplateSelector.vue   # 模板选择弹窗
```

### SOP 定义 (YAML)

```yaml
sop_id: unique_id
name: "显示名称"
version: "1.0"
description: "..."
max_total_duration: 3600
steps:
  - step_id: step_1
    name: "步骤名称"
    order: 0
    estimated_duration: 30
    timeout: 120
    is_optional: false
    rule:
      expected_objects: ["board", "hand"]   # SOP 语义类别名
      expected_gestures: ["pick_up"]         # 手势名 (可选)
      min_confidence: 0.5
      required_count: 1
      confirm_frames: 3                      # 连续确认帧数
```

SOP 定义文件存放在 `sop_definitions/`，模板存放在 `sop_definitions/templates/`。

### 数据库 (SQLite)

- **users**: `id`, `username`(unique), `hashed_password`, `role`(admin/operator), `created_at`
- **operation_records**: `id`, `sop_id`(indexed), `step_id`, `step_name`, `status`, `confidence`, `details`(JSON), `screenshot_path`, `timestamp`
- 首次运行自动迁移，种子管理员 `admin/admin123`

## Key Design Patterns

1. **Mock 降级**: YOLO 检测器、手部关键点提取器、手势分类器均有 graceful mock 降级，无需 GPU 或摄像头即可开发和测试
2. **类别映射层**: SOP 语义名 (board, tool, solder) → COCO 可检测类的可配置映射
3. **命中帧确认**: 需要 `confirm_frames`（默认 3）连续匹配检测才推进步骤，防止单帧误触发
4. **严格顺序模式**: 可选 `strict_order` 配置，拒绝非当前步骤的事件
5. **多摄像头**: 每个摄像头独立采集+推理流水线，结果附带 camera ID 统一回调
6. **特征融合**: YOLO 特征 (80类 × count+confidence = 160维) + MediaPipe 手部关键点 (126维) = 286维融合特征向量
7. **双模交付**: FastAPI 同时服务 REST API 和构建后的 Vue SPA (catch-all 路由)

## Test Structure

125 个测试，覆盖 12 个测试文件：

| 文件 | 数量 | 覆盖范围 |
|------|------|----------|
| `test_api.py` | ~29 | 所有 REST 端点、认证 |
| `test_state_machine.py` | 18 | 状态转换、命中帧确认、严格顺序 |
| `test_rule_engine.py` | 8 | 规则匹配 |
| `test_alert_manager.py` | 13 | 告警级别、去重、升级、ACK |
| `test_detector.py` | 6 | Mock 检测、标注 |
| `test_sop_manager.py` | 6 | YAML CRUD |
| `test_sop_schema.py` | 4 | Pydantic 模型默认值 |
| `test_class_mapping.py` | 18 | 类别映射、手势分类器姿态 |
| `test_lstm.py` | 13 | 手部提取、特征、LSTM、投票、训练 |
| `test_multi_camera.py` | 9 | 设备解析、回调、错误处理 |
| `test_training.py` | 14 | 会话、分析器、步骤元数据 |

测试夹具定义在 `tests/conftest.py` (TestClient, auth_headers, sample_sop_data)。

## Project Conventions

- 代码注释和文档使用**中文**
- 变量名、函数名使用**英文**
- SOP 定义使用 **YAML** 格式
- API 认证使用 **JWT (HS256)**
- 前端使用 **Composition API** 风格
- 所有 API 响应格式: `{ "code": 0, "data": ..., "message": "ok" }`
