# AI SOP Monitor

AI 实时 SOP 合规监控系统。通过摄像头采集画面，使用 YOLOv8 进行目标检测，结合状态机和规则引擎，实时判断操作人员是否按照标准作业流程（SOP）执行操作。

## 功能特性

- **实时视频流** — MJPEG 摄像头画面，叠加 YOLO 检测框
- **SOP 状态机** — 自动跟踪 SOP 步骤进度，支持超时检测
- **规则引擎** — 可配置的检测规则（目标类型、置信度、数量要求）
- **告警系统** — 多级告警（info/warning/error/critical），支持升级机制和声音提示
- **数据可视化** — ECharts 图表：检测时序、状态分布、完成率统计
- **WebSocket 实时推送** — 前端自动刷新进度和告警
- **SOP 管理** — YAML 格式定义，REST API CRUD，前端可视化编辑

## 系统要求

| 组件 | 要求 |
|------|------|
| Python | 3.10+ |
| Node.js | 18+ |
| 摄像头 | USB 摄像头（/dev/video0） |
| 操作系统 | Ubuntu 22.04 |
| GPU | 可选（有 CUDA 则自动使用 GPU 推理） |

## 快速开始

### 1. 安装依赖

```bash
# Python 依赖
pip install fastapi uvicorn opencv-python numpy pydantic pydantic-settings \
    aiofiles python-multipart pyyaml sqlalchemy ultralytics

# Node.js 依赖（需先安装 nvm）
source ~/.nvm/nvm.sh && nvm use 18
cd frontend && npm install
```

### 2. 启动服务

```bash
# 方式一：同时启动前后端
./scripts/run_all.sh

# 方式二：分别启动
./scripts/run_backend.sh    # 后端 → http://localhost:8000
./scripts/run_frontend.sh   # 前端 → http://localhost:5173
```

### 3. 访问系统

| 地址 | 说明 |
|------|------|
| http://localhost:5173 | 前端 Dashboard |
| http://localhost:8000/docs | Swagger API 文档 |
| http://localhost:8000/video/stream | MJPEG 视频流 |
| ws://localhost:8000/ws | WebSocket 连接 |

## 项目结构

```
sop-monitor/
├── backend/
│   ├── main.py                 # FastAPI 入口，生命周期管理
│   ├── config.py               # Pydantic Settings 配置
│   ├── camera/
│   │   ├── capture.py          # OpenCV 摄像头采集线程
│   │   └── preprocessor.py     # 图像预处理（resize, ROI）
│   ├── inference/
│   │   ├── detector.py         # YOLOv8 检测器（支持 mock fallback）
│   │   └── engine.py           # 推理引擎（采集→预处理→检测→标注）
│   ├── extractor/
│   │   ├── event.py            # SopEvent 数据类
│   │   └── rule_engine.py      # 检测结果→SOP 步骤事件映射
│   ├── sop/
│   │   ├── schema.py           # SOP Pydantic 模型定义
│   │   ├── state_machine.py    # SOP 状态机引擎
│   │   └── sop_manager.py      # SOP YAML 文件 CRUD
│   ├── alert/
│   │   └── manager.py          # 告警管理（去重、升级、规则配置）
│   ├── api/
│   │   ├── ws.py               # WebSocket 实时推送
│   │   ├── sop.py              # SOP REST API
│   │   ├── monitor.py          # 监控数据 + 操作记录查询
│   │   ├── video.py            # MJPEG 视频流 + 截图
│   │   ├── alert_config.py     # 告警规则 CRUD
│   │   └── stats.py            # 统计数据 API（ECharts 数据源）
│   └── models/
│       ├── database.py         # SQLite 初始化
│       └── record.py           # OperationRecord ORM
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── Dashboard.vue   # 主监控面板
│   │   │   ├── SopEditor.vue   # SOP 编辑页
│   │   │   └── History.vue     # 历史记录页
│   │   ├── components/
│   │   │   ├── VideoStream.vue # 视频流组件
│   │   │   ├── SopProgress.vue # SOP 进度组件
│   │   │   ├── AlertPanel.vue  # 告警面板
│   │   │   ├── AlertToast.vue  # 全局 toast 弹窗 + 声音
│   │   │   └── StatsChart.vue  # ECharts 统计图表
│   │   ├── composables/
│   │   │   └── useWebSocket.js # 自动重连 WebSocket
│   │   ├── stores/
│   │   │   └── monitor.js      # Pinia 状态管理
│   │   └── router/
│   │       └── index.js        # Vue Router
│   └── vite.config.js          # Vite 配置（含 API 代理）
├── sop_definitions/
│   └── example_assembly.yaml   # 示例 SOP（5 步 PCB 组装）
├── scripts/
│   ├── run_backend.sh
│   ├── run_frontend.sh
│   └── run_all.sh
└── tests/                      # 65 个测试用例
```

## SOP 定义文件

SOP 使用 YAML 格式定义，存放在 `sop_definitions/` 目录下：

```yaml
sop_id: example_assembly
name: "PCB Assembly Example"
version: "1.0"
description: "示例 PCB 组装流程"
max_total_duration: 1800

steps:
  - step_id: step_1
    name: "拿起 PCB 板"
    order: 0
    estimated_duration: 15    # 预计耗时（秒）
    timeout: 60               # 超时时间（秒）
    rule:
      expected_objects: ["board", "hand"]   # 需要检测到的目标
      min_confidence: 0.6                   # 最低置信度
      required_count: 1                     # 最少检测数量

  - step_id: step_2
    name: "涂抹焊锡膏"
    order: 1
    timeout: 120
    rule:
      expected_objects: ["solder", "board"]
      min_confidence: 0.5
      required_count: 1
```

### 支持的检测目标（YOLOv8 默认 80 类）

常用目标：`person`, `hand`, `bottle`, `cup`, `knife`, `scissors`,
`book`, `cell phone`, `laptop`, `mouse`, `keyboard` 等。

可通过自定义训练模型扩展检测类别。

## API 接口

### SOP 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/sop/list` | 列出所有 SOP |
| GET | `/api/sop/{sop_id}` | 获取 SOP 详情 |
| POST | `/api/sop/` | 创建/更新 SOP |
| DELETE | `/api/sop/{sop_id}` | 删除 SOP |

### 监控数据

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/monitor/status` | 当前所有活跃 SOP 状态 |
| GET | `/api/monitor/sop/{sop_id}/state` | 单个 SOP 实例状态 |
| GET | `/api/monitor/alerts` | 最近告警列表 |
| POST | `/api/monitor/alerts/{id}/acknowledge` | 确认告警 |
| GET | `/api/monitor/records?limit=100&sop_id=xxx` | 操作记录查询 |

### 告警配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/alerts/rules` | 获取所有告警规则 |
| POST | `/api/alerts/rules` | 创建告警规则 |
| DELETE | `/api/alerts/rules/{sop_id}/{step_id}` | 删除规则 |
| POST | `/api/alerts/acknowledge-all` | 确认所有告警 |

### 统计数据

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/stats/summary` | 总体统计摘要 |
| GET | `/api/stats/detections?minutes=60` | 检测事件统计 |
| GET | `/api/stats/timeline?minutes=60&bucket_seconds=60` | 时序数据 |
| GET | `/api/stats/sop/{sop_id}/completion` | SOP 完成率 |

### 视频流

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/video/stream` | MJPEG 视频流（可直接用于 `<img src>`） |
| GET | `/video/snapshot` | 单帧 JPEG 截图 |

### WebSocket

连接 `ws://localhost:8000/ws`，接收 JSON 消息：

```json
// 心跳
{"type": "heartbeat", "connections": 2, "timestamp": "..."}

// SOP 事件
{"type": "sop_event", "payload": {"sop_id": "...", "step_id": "...", "status": "detected", ...}}

// 告警
{"type": "alert", "payload": {"alert_id": "...", "level": "warning", "message": "..."}}
```

## 配置项

通过环境变量或 `.env` 文件配置（前缀 `SOP_`）：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `SOP_CAMERA_DEVICE` | 0 | 摄像头设备号 |
| `SOP_CAMERA_FPS` | 15 | 采集帧率 |
| `SOP_CAMERA_WIDTH` | 640 | 画面宽度 |
| `SOP_CAMERA_HEIGHT` | 480 | 画面高度 |
| `SOP_MODEL_PATH` | models/yolov8n.pt | YOLO 模型路径 |
| `SOP_CONFIDENCE_THRESHOLD` | 0.5 | 检测置信度阈值 |
| `SOP_INFERENCE_INTERVAL` | 0.5 | 推理间隔（秒） |
| `SOP_SOP_DIR` | sop_definitions/ | SOP 定义目录 |
| `SOP_DATABASE_URL` | sqlite:///./sop_monitor.db | 数据库连接 |
| `SOP_ALERT_COOLDOWN` | 30 | 告警去重冷却（秒） |

## 测试

```bash
cd /home/mac/sop-monitor
python3 -m pytest tests/ -v
```

65 个测试覆盖：SOP schema、状态机、规则引擎、告警管理、检测器、SOP 管理、全部 API 端点。

## 运行流程

```
摄像头 → 采集线程 → 预处理 → YOLOv8 检测 → 规则引擎 → 状态机 → 告警管理
                                    ↓                              ↓
                              标注帧视频流                    数据库记录
                                    ↓                              ↓
                              MJPEG 推送                   WebSocket 广播
```

## 常见问题

**Q: 没有摄像头怎么测试？**
系统会自动进入 API-only 模式，所有 REST API 正常工作，视频流返回空。检测器默认使用 mock 模式返回模拟数据。

**Q: 如何使用自定义 YOLO 模型？**
将 `.pt` 文件放到项目目录，在 `.env` 中设置 `SOP_MODEL_PATH=path/to/model.pt`，重启后端即可。

**Q: 前端页面空白？**
确认后端已启动（:8000），Vite 代理配置会自动转发 `/api` 和 `/video` 请求到后端。
