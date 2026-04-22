#!/bin/bash
# XHS Project 一键启动脚本
# 启动前端 Nuxt 应用（包含所有API）
# 可选：启动后台调度器

PROJECT_DIR="/xhs-project"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
LOG_DIR="$PROJECT_DIR/logs"

# 确保 logs 目录存在
mkdir -p "$LOG_DIR"

# 是否启动调度器（可选）
START_SCHEDULER=${1:-"no"}  # 默认不启动，传入 "scheduler" 参数启动

echo "===== XHS Project 启动脚本 ====="
echo ""

# 启动前端 Nuxt（包含所有API）
echo "启动前端服务 (端口 3000)..."
cd "$FRONTEND_DIR"
nohup ./start.sh > "$LOG_DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "前端 PID: $FRONTEND_PID"

# 等待前端启动
sleep 3

# 如果需要启动调度器
if [ "$START_SCHEDULER" = "scheduler" ]; then
    echo ""
    echo "启动后台调度器..."
    cd "$BACKEND_DIR"
    source venv/bin/activate
    nohup python main.py start-scheduler > "$LOG_DIR/scheduler.log" 2>&1 &
    SCHEDULER_PID=$!
    echo "调度器 PID: $SCHEDULER_PID"
fi

echo ""
echo "===== 服务启动完成 ====="
echo "- 前端 Web: http://192.168.100.6:5020"
echo "- 前端 API: http://192.168.100.6:5020/api/*"
echo "- 前端日志: $LOG_DIR/frontend.log"
if [ "$START_SCHEDULER" = "scheduler" ]; then
    echo "- 调度器日志: $LOG_DIR/scheduler.log"
fi
echo ""
echo "使用说明:"
echo "  - 访问 http://192.168.100.6:3000 打开网站"
echo "  - 前端API已集成在Nuxt服务中，无需单独后端"
echo "  - 如需自动定时搜索，运行: ./start.sh scheduler"
echo ""

# 保存PID
if [ "$START_SCHEDULER" = "scheduler" ]; then
    echo "$FRONTEND_PID $SCHEDULER_PID" > "$PROJECT_DIR/.pids"
else
    echo "$FRONTEND_PID" > "$PROJECT_DIR/.pids"
fi