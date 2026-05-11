# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

小红书内容采集系统，包含后端爬虫/采集器和前端 Nuxt 展示界面。

## Architecture

- **backend/** - Python 后端，包含图片处理器、调度器等
- **frontend/** - Nuxt 3 前端，包含页面和 API 路由

## Key Commands

- `bash start.sh` - 启动整个项目
- `bash stop.sh` - 停止项目

## File Structure

- `backend/image_processor.py` - 图片上传到图床处理
- `backend/scheduler.py` - 定时调度任务
- `frontend/app/pages/` - 页面组件
- `frontend/server/api/` - API 路由
