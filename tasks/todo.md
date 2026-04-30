# Phase 4 完善计划

## P0-1: 命中帧确认机制（防误触发） ✅

**问题**: 当前 StateMachine 单次检测匹配即推进状态（PENDING→ACTIVE→COMPLETED），容易因单帧误检导致步骤跳过。

**方案**: 在 `StepRule` 中新增 `confirm_frames` 字段（默认 3），StateMachine 要求连续 N 帧检测到目标才确认步骤完成。

**修改文件**:
- `backend/sop/schema.py` — StepRule 增加 `confirm_frames: int = 3`
- `backend/sop/state_machine.py` — SopInstance 增加 `_consecutive_hits` 计数器，process_event 中累计连续命中次数，达到阈值才 complete_step；新增 reset_step_hits 方法；get_state_dict 包含命中进度
- `backend/config.py` — 新增 `default_confirm_frames: int = 3` 全局默认值
- `tests/test_state_machine.py` — 新增 4 个命中帧确认测试用例 + 修复 1 个旧测试
- `sop_definitions/templates/*.yaml` — 4 个模板中增加 confirm_frames: 3
- 全部 95 个测试通过

## P0-2: 自动截图归档 ✅

**问题**: 步骤完成时仅写 OperationRecord（无图像），无法事后回溯。

**方案**: 步骤完成时自动保存当前帧到 `screenshots/` 目录，OperationRecord 增加 `screenshot_path` 字段。

**修改文件**:
- `backend/models/record.py` — OperationRecord 增加 `screenshot_path` 字段
- `backend/models/database.py` — init_db 增加自动迁移逻辑，给已有表添加新列
- `backend/main.py` — on_detection 回调中，步骤完成时调用 save_screenshot 保存截图
- `backend/api/video.py` — 新增 `save_screenshot()` 函数和 `/video/screenshots/{filename}` 静态服务端点
- `backend/api/monitor.py` — records 响应中包含 screenshot_path
- `.gitignore` — 排除 screenshots/ 目录
- `frontend/src/views/History.vue` — 记录表格增加 Screenshot 列（View 按钮），点击弹出大图预览模态框

## P0-3: 日志导出（CSV） ✅

**问题**: History 页面仅展示，无法导出数据。

**方案**: 后端新增 CSV 导出接口，前端增加导出按钮。

**修改文件**:
- `backend/api/monitor.py` — 新增 `GET /api/monitor/records/export` CSV 导出端点（StreamingResponse）
- `frontend/src/views/History.vue` — 增加"Export CSV"按钮，带 SOP 筛选参数打开下载

## 实施顺序
1. P0-1 命中帧确认（后端核心逻辑）
2. P0-2 自动截图归档（后端+前端）
3. P0-3 日志导出（后端+前端）
4. 运行测试验证

## 验证方式
1. 命中帧：连续检测不到 N 帧时不推进状态，达到 N 帧后才完成
2. 截图：步骤完成后 `screenshots/` 目录有对应图片，History 页面可查看
3. 导出：点击 Export CSV 按钮下载包含筛选结果的 CSV 文件

## Review

**全部 P0 任务完成。** 修改了 10 个文件，新增 4 个测试用例，95 个测试全部通过。

### 变更汇总

| 文件 | 变更 |
|------|------|
| `backend/sop/schema.py` | StepRule 增加 `confirm_frames` 字段 |
| `backend/config.py` | 新增 `default_confirm_frames` 配置 |
| `backend/sop/state_machine.py` | 命中帧确认逻辑 + `reset_step_hits` + state_dict 命中进度 |
| `backend/models/record.py` | OperationRecord 增加 `screenshot_path` 列 |
| `backend/models/database.py` | 自动迁移：给已有表添加新列 |
| `backend/main.py` | 步骤完成时自动截图 + screenshot_path 写入记录 |
| `backend/api/video.py` | `save_screenshot()` + `/video/screenshots/{filename}` 端点 |
| `backend/api/monitor.py` | records 包含 screenshot_path + CSV 导出端点 |
| `frontend/src/views/History.vue` | 截图查看 + 大图预览 + Export CSV 按钮 |
| `sop_definitions/templates/*.yaml` | 4 个模板增加 confirm_frames: 3 |
| `tests/test_state_machine.py` | 4 个新测试 + 1 个旧测试修复 |
| `.gitignore` | 排除 screenshots/ 目录 |

---

## P1: LSTM 时序动作识别 ✅

**问题**: 仅靠单帧 YOLO + 规则匹配，无法处理动作时序关系，步骤识别不稳定。

**方案**: 集成 MediaPipe 手部关键点 + LSTM 时序分类器 + 多尺度窗口投票。

### 新增文件

| 文件 | 功能 |
|------|------|
| `backend/inference/hand_extractor.py` | MediaPipe HandLandmarker 手部 21 关键点提取（126 维特征） |
| `backend/inference/feature_fusion.py` | YOLO 检测特征（80 类 count+conf）+ 手部特征融合（206 维） |
| `backend/inference/lstm_classifier.py` | LSTM 分类器 + MultiScaleVoter 多尺度窗口投票 |
| `backend/inference/mock_data.py` | 合成训练数据生成（模拟 5 步 SOP 的检测+手部特征） |
| `backend/inference/lstm_trainer.py` | LSTM 模型训练器（PyTorch） |
| `backend/inference/models/hand_landmarker.task` | MediaPipe 手部检测模型（7.5MB） |
| `tests/test_lstm.py` | 13 个测试（手部提取、特征融合、LSTM、投票、数据生成、训练） |

### 修改文件

| 文件 | 变更 |
|------|------|
| `backend/api/training.py` | 新增 `/api/training/lstm/train` 和 `/api/training/lstm/status` 端点 |
| `backend/main.py` | 初始化 LstmTrainer 并注入 training API |
| `frontend/src/views/Training.vue` | 新增 LSTM 训练面板（参数配置、训练按钮、进度条、结果显示） |

### 验证
- 108 个测试全部通过（含 13 个新增 LSTM 测试）
- 前端构建成功
- 合成数据训练 30 epochs，准确率可达 90%+

---

## P3: Docker 部署 + 多摄像头 + 顺序约束 ✅

### P3-1: Docker 部署
- Dockerfile（多阶段构建：前端 build + 后端运行）
- docker-compose.yml（单服务，含设备挂载、卷映射、环境变量）
- requirements.txt（Python 依赖清单）
- main.py 增加静态文件服务（SPA catch-all 路由）

### P3-2: 多摄像头支持
- config 新增 `camera_devices` 字段（逗号分隔设备号列表）
- `backend/camera/multi_camera.py` — MultiCameraManager，每个摄像头独立推理线程
- `backend/api/video.py` — 新增 `/video/cameras` 和 `/video/stream/{camera_id}` 端点
- `tests/test_multi_camera.py` — 9 个测试用例

### P3-3: 顺序约束强化
- config 新增 `strict_order` 字段（默认 False）
- StateMachineEngine 接收 strict_order 参数并传递给 SopInstance
- SopInstance.process_event 中 strict_order 模式下拒绝非当前步骤事件
- `tests/test_state_machine.py` — 新增 4 个 strict_order 测试

### 验证
- 121 个测试全部通过（含 13 个新增测试）

---

## P2: 视频文件分析 + Top3 候选显示 ✅

### P2-1: 视频文件分析

**问题**: 仅支持摄像头实时流，无法分析录制的视频文件。

**方案**: 新增视频上传分析端点，逐帧检测并匹配 SOP 规则。

**新增文件**:
- `backend/api/video_analysis.py` — `POST /api/video/analyze` 端点，接受视频文件上传，逐帧 YOLO 检测 + SOP 规则匹配，返回时间线匹配结果

**修改文件**:
- `backend/main.py` — 导入并注册 video_analysis_router，注入 detector/preprocessor/rule_engine/sop_manager
- `frontend/src/views/Dashboard.vue` — 视频流下方增加文件上传控件，显示分析结果（时长、采样帧数、匹配事件、时间线）

### P2-2: Top3 候选步骤显示

**问题**: 用户无法看到系统当前识别的候选步骤及置信度。

**方案**: 每次检测后计算所有 SOP 步骤的匹配分数，保留 Top3 并在 Dashboard 展示。

**修改文件**:
- `backend/api/monitor.py` — 新增 `_latest_candidates` 缓存、`update_candidates()` 函数、`GET /api/monitor/detection/candidates` 端点
- `backend/main.py` — on_detection 回调中计算所有步骤匹配分数（score = avg_conf × match_ratio），排序取 Top3，调用 update_candidates
- `frontend/src/views/Dashboard.vue` — 新增 Top Detection Candidates 区域，显示 Top3 候选（排名、步骤名、SOP、置信度、匹配对象），每 3 秒轮询更新

### 验证
- 108 个测试全部通过
- 前端构建成功
