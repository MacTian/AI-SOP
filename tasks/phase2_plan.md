# Phase 2 计划

## 1. 接入真实 YOLO 模型
- 安装 ultralytics: `pip install ultraviolet`
- 改造 `backend/inference/detector.py`:
  - `load_model()` 加载真实 YOLOv8 模型
  - `detect()` 返回真实检测结果
  - 保留 mock fallback（模型不存在时）
- 改造 `backend/inference/engine.py`:
  - 检测结果带 bbox 画框
  - 返回标注后的帧用于视频流
- 更新 config.py 添加 model_path 配置

## 2. 前端实时联动
- 改造 `useWebSocket.js`:
  - 处理 sop_event 类型消息
  - 处理 alert 类型消息
  - 自动更新 store
- 改造 `stores/monitor.js`:
  - 接收 WebSocket 事件实时更新 activeSops
  - 接收 alert 事件实时更新 alerts 列表
- 改造 `Dashboard.vue`:
  - 实时刷新 SOP 进度
  - 实时显示新告警
  - 连接状态指示器
- 改造 `VideoStream.vue`:
  - 显示检测框 overlay

## 3. 完善告警系统
- 改造 `backend/alert/manager.py`:
  - 支持多级告警规则配置
  - 告警升级机制（重复触发→升级级别）
- 新增 `backend/api/alert_config.py`:
  - 告警规则 CRUD 接口
- 前端 `components/AlertPanel.vue`:
  - 告警声音提示（Web Audio API）
  - 告警弹窗（toast 通知）
  - 告警详情展开
- 新增 `frontend/src/components/AlertToast.vue`:
  - 全局 toast 通知组件

## 4. ECharts 数据可视化
- 新增 `frontend/src/components/StatsChart.vue`:
  - 检测事件时序图（ECharts line chart）
  - SOP 完成率饼图
  - 步骤耗时柱状图
- 改造 `Dashboard.vue`:
  - 添加统计图表区域
- 后端新增 `api/stats.py`:
  - `/api/stats/detections` 检测统计数据
  - `/api/stats/sop/{id}/completion` SOP 完成率

## 实施顺序
1 → 3 → 2 → 4（先确保后端数据通，再做前端联动和可视化）

## 验证方式
1. YOLO: 视频流中能看到真实检测框
2. 实时联动: Dashboard 自动更新进度和告警
3. 命警: 重复违规时级别升级，前端有声音+弹窗
4. 可视化: Dashboard 显示统计图表
