#!/bin/bash
# XHS Project 停止脚本

PROJECT_DIR="/xhs-project"
PID_FILE="$PROJECT_DIR/.pids"

echo "===== XHS Project 停止脚本 ====="

if [ -f "$PID_FILE" ]; then
    # 读取PID（可能只有一个或两个）
    PIDS=$(cat "$PID_FILE")

    for PID in $PIDS; do
        if [ -n "$PID" ] && [ "$PID" -gt 0 ]; then
            echo "停止进程 (PID: $PID)..."
            kill $PID 2>/dev/null
        fi
    done

    # 同时杀掉可能的子进程
    pkill -f "node.*nuxt" 2>/dev/null
    pkill -f "python.*scheduler" 2>/dev/null
    pkill -f "python.*main.py" 2>/dev/null

    rm -f "$PID_FILE"
    echo "服务已停止"
else
    echo "未找到 PID 文件，尝试按进程名停止..."
    pkill -f "node.*nuxt" 2>/dev/null
    pkill -f "python.*scheduler" 2>/dev/null
    pkill -f "python.*main.py" 2>/dev/null
    echo "已尝试停止相关进程"
fi