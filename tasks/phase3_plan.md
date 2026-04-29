# Phase 3 计划

## 1. SOP 模板库

### 后端
- 新增 `sop_definitions/templates/` 目录存放预置模板
- 新增模板文件：
  - `electronics_assembly.yaml` — 电子组装
  - `quality_inspection.yaml` — 质量检测
  - `packaging.yaml` — 包装流程
  - `machine_operation.yaml` — 机器操作
- `api/sop.py` 新增：
  - `GET /api/sop/templates` — 列出模板
  - `POST /api/sop/templates/{id}/use` — 基于模板创建新 SOP

### 前端
- `SopEditor.vue` 增加"从模板创建"按钮
- 新增 `components/TemplateSelector.vue` — 模板选择弹窗

## 2. SOP 训练功能

### 核心思路
训练 = 录像 → 自动分析 → 生成 SOP → 手动优化 → 保存

### 后端
- 新增 `training/session.py` — 训练会话管理
  - `TrainingSession`: 录制帧、时间戳、检测结果
  - 开始/停止录制
  - 分析录制数据，识别步骤边界
- 新增 `training/analyzer.py` — 步骤自动识别
  - 基于检测结果变化识别步骤切换点
  - 聚类分析：相似检测结果归为同一步骤
  - 自动生成 step_id, name, rule
- 新增 `api/training.py` — 训练 API
  - `POST /api/training/start` — 开始训练（开始录像）
  - `POST /api/training/stop` — 停止训练（停止录像）
  - `GET /api/training/status` — 训练状态
  - `GET /api/training/result` — 获取分析结果（待生成的 SOP）
  - `POST /api/training/save` — 保存为正式 SOP
  - `PUT /api/training/step/{step_id}` — 修改步骤（手动调整）

### 前端
- 新增 `views/Training.vue` — 训练页面
  - 实时视频预览（带检测框）
  - 开始/停止训练按钮
  - 训练时长计时器
  - 训练状态指示
- 新增 `components/StepEditor.vue` — 步骤编辑器
  - 显示自动识别的步骤列表
  - 每步显示：步骤名、检测到的对象、关键帧缩略图
  - 支持：重命名、拖拽排序、删除、合并步骤
  - 支持：修改每步的 expected_objects、min_confidence
  - 保存按钮
- 路由新增 `/training`
- App.vue 导航新增 Training 链接

### 步骤自动识别算法
```
录制数据: [(timestamp, detections), ...]
1. 计算每帧的检测对象集合
2. 检测集合变化点（步骤切换边界）
3. 聚类：将相似帧归为同一步骤
4. 为每个步骤生成：
   - step_id: auto_step_N
   - name: 基于主要检测对象自动生成
   - rule.expected_objects: 该步骤中高频出现的对象
   - rule.min_confidence: 该步骤中对象的平均置信度
   - estimated_duration: 步骤持续时间
```

## 实施顺序
1. SOP 模板库（低复杂度，快速完成）
2. 训练后端（session + analyzer + API）
3. 训练前端（Training.vue + StepEditor.vue）

## 验证方式
1. 模板库：能从模板创建新 SOP
2. 训练：开始→录像→停止→看到自动识别的步骤
3. 编辑：能修改步骤名称、规则、排序
4. 保存：保存后在 SOP 列表中出现
