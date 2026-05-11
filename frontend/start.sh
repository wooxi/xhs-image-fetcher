#!/bin/bash

# Nuxt 3 小红书风格网站启动脚本
# 端口: 5020

cd "$(dirname "$0")"

# 加载项目根目录的 .env 文件
if [ -f "../.env" ]; then
  echo "[+] 加载环境变量..."
  # 使用 while-read 代替 source，避免特殊字符（如 |）被 bash 解释
  while IFS='=' read -r key value; do
    # 跳过空行和注释
    [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
    # 去除行尾回车符
    value=$(echo "$value" | tr -d '\r')
    export "$key=$value"
  done < "../.env"
fi

echo "===== 小红书摄影展示网站启动脚本 ====="

# 检查 node_modules
if [ ! -d "node_modules" ]; then
  echo "[!] node_modules 不存在，正在安装依赖..."
  npm install
  npm install tailwindcss @nuxtjs/tailwindcss lucide-vue-next mysql2
fi

# 检查 .nuxt 目录
if [ ! -d ".nuxt" ]; then
  echo "[!] .nuxt 不存在，正在准备 Nuxt..."
  npm run postinstall
fi

echo "[+] 启动开发服务器 (端口 5020)..."
echo "[+] 访问地址: http://localhost:5020"
echo ""

# 启动服务
npm run dev