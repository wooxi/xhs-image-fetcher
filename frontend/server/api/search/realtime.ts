import mysql from 'mysql2/promise'
import { spawn, ChildProcess } from 'child_process'
import path from 'path'
import { getPool, formatDateTime } from '../../utils/db'

// 写入单条执行日志到数据库
const writeLogToDb = async (executionId: string, keyword: string, logType: string, message: string) => {
  try {
    const pool = getPool()
    await pool.execute(
      `INSERT INTO execution_logs (execution_id, keyword, log_type, message) VALUES (?, ?, ?, ?)`,
      [executionId, keyword, logType, message]
    )
  } catch (error) {
    console.error('[realtime] 写入日志失败:', error)
  }
}

// 写入搜索结果统计到数据库
const writeSearchResultToDb = async (
  executionId: string,
  keyword: string,
  postsFound: number,
  postsInserted: number,
  postsSkipped: number,
  imagesFound: number,
  imagesUploaded: number,
  imagesFailed: number,
  durationSeconds: number,
  errorMessage: string | null
) => {
  try {
    const pool = getPool()
    await pool.execute(
      `INSERT INTO search_logs (
        execution_id, keyword, posts_found, posts_inserted, posts_skipped,
        images_found, images_uploaded, images_failed,
        duration_seconds, error_message
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [executionId, keyword, postsFound, postsInserted, postsSkipped,
       imagesFound, imagesUploaded, imagesFailed,
       durationSeconds, errorMessage]
    )
    console.log('[realtime] 已写入搜索结果统计:', executionId)
  } catch (error) {
    console.error('[realtime] 写入搜索结果失败:', error)
  }
}

// 搜索任务状态存储（内存）
const MAX_TASKS = 200  // 限制最大任务数量，防止内存无限增长
const TASK_CLEANUP_AGE = 3600000 // 1小时

const searchTasks: Map<string, {
  keyword: string
  limit: number
  executionId: string
  status: 'running' | 'completed' | 'failed'
  logs: Array<{ time: string; message: string; type: 'info' | 'success' | 'error' }>
  startTime: Date
  endTime?: Date
  postsFound: number
  postsInserted: number
  postsSkipped: number
  imagesFound: number
  imagesUploaded: number
  imagesFailed: number
}> = new Map()

// 清理超过1小时的已完成任务，并限制总任务数量
const cleanupOldTasks = () => {
  const now = new Date()
  for (const [id, task] of searchTasks.entries()) {
    if (task.status !== 'running' && task.endTime) {
      const age = now.getTime() - new Date(task.endTime).getTime()
      if (age > TASK_CLEANUP_AGE) {
        searchTasks.delete(id)
      }
    }
  }
  // 如果任务数量超过上限，删除最早的已完成任务
  if (searchTasks.size > MAX_TASKS) {
    const completedTasks = Array.from(searchTasks.entries())
      .filter(([_, t]) => t.status !== 'running')
      .sort((a, b) => new Date(a[1].startTime).getTime() - new Date(b[1].startTime).getTime())
    const toRemove = searchTasks.size - MAX_TASKS
    for (let i = 0; i < toRemove && i < completedTasks.length; i++) {
      searchTasks.delete(completedTasks[i][0])
    }
  }
}

// 清理残留的Python搜索子进程
const cleanupOrphanProcesses = () => {
  try {
    const { execSync } = require('child_process')
    const result = execSync('ps aux | grep "[m]ain.py search-detail" | awk \'{print $2}\'', { encoding: 'utf-8' })
    const pids = result.trim().split('\n').filter(Boolean)
    if (pids.length > 0) {
      console.log(`[realtime] 清理 ${pids.length} 个残留Python子进程`)
      for (const pid of pids) {
        try { execSync(`kill -9 ${pid}`) } catch {}
      }
    }
  } catch {}
}

export default defineEventHandler(async (event) => {
  const query = getQuery(event)
  const action = query.action as string || 'status'
  const keyword = query.keyword as string

  // 清理旧任务和残留的Python子进程
  if (action === 'status' && !globalThis.__orphanCleanupRan) {
    globalThis.__orphanCleanupRan = true
    cleanupOrphanProcesses()
  }

  // 清理旧任务
  cleanupOldTasks()

  // 获取任务状态
  if (action === 'status') {
    const taskId = query.taskId as string
    if (taskId && searchTasks.has(taskId)) {
      return { success: true, task: searchTasks.get(taskId) }
    }
    // 返回所有运行中的任务（供前端轮询）
    const runningTasks = Array.from(searchTasks.entries())
      .filter(([_, task]) => task.status === 'running')
      .map(([id, task]) => ({
        id,
        executionId: task.executionId,
        keyword: task.keyword,
        limit: task.limit,
        status: task.status,
        logs: task.logs,
        startTime: task.startTime,
        postsFound: task.postsFound,
        postsInserted: task.postsInserted,
        imagesUploaded: task.imagesUploaded,
        imagesFailed: task.imagesFailed
      }))
    return { success: true, tasks: runningTasks }
  }

  // 获取最近任务历史
  if (action === 'history') {
    const tasks = Array.from(searchTasks.entries())
      .filter(([_, task]) => task.status !== 'running')
      .slice(-10)
      .map(([id, task]) => ({ id, ...task }))
    return { success: true, tasks }
  }

  // 启动搜索任务
  if (action === 'start' && keyword) {
    const limit = Number(query.limit) || 2
    const uploadImages = query.upload === 'true'
    const taskId = `search_${Date.now()}_${keyword}`
    const executionId = `exec_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    // 初始化任务状态
    const task = {
      keyword,
      limit,
      executionId,
      status: 'running' as const,
      logs: [] as Array<{ time: string; message: string; type: 'info' | 'success' | 'error' }>,
      startTime: new Date(),
      postsFound: 0,
      postsInserted: 0,
      postsSkipped: 0,
      imagesFound: 0,
      imagesUploaded: 0,
      imagesFailed: 0
    }
    searchTasks.set(taskId, task)

    // 记录启动日志
    writeLogToDb(executionId, keyword, 'info', `开始搜索关键词: ${keyword}, 数量: ${limit}`)

    // 启动后台搜索进程（使用venv中的Python）
    const backendDir = process.env.BACKEND_DIR || '/xhs-project/backend'
    const pythonPath = process.env.PYTHON_PATH || `${backendDir}/venv/bin/python`
    const scriptPath = `${backendDir}/main.py`
    // 默认上传图片到图床
    const args = ['search-detail', keyword, '--limit', String(limit), '--upload-images']

    const child = spawn(pythonPath, [scriptPath, ...args], {
      cwd: backendDir,
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
      stdio: ['ignore', 'pipe', 'pipe']
    })

    // 解析日志输出 - 优化日志解析逻辑，同时写入数据库
    let jsonBuffer = '' // 用于合并 JSON 输出

    const parseLogLine = (line: string) => {
      const time = new Date().toLocaleTimeString('zh-CN', { hour12: false })

      // 获取时间戳格式 [HH:MM:SS +Xs]
      const timeMatch = line.match(/\[(\d{2}:\d{2}:\d{2})\s+\+\d+s\]/)
      const logTime = timeMatch ? timeMatch[1] : time

      // 清理日志行
      const cleanLine = line.replace(/\[\d{2}:\d{2}:\d{2}\s+\+\d+s\]\s*/, '').trim()

      // 跳过空行
      if (!cleanLine) return

      // 处理 JSON 输出（合并成完整消息）
      if (cleanLine.startsWith('{') || cleanLine.startsWith('}') || jsonBuffer) {
        if (cleanLine.startsWith('{')) {
          jsonBuffer = cleanLine
        } else {
          jsonBuffer += cleanLine
        }
        // 检查是否是完整的 JSON
        if (cleanLine.endsWith('}') || (jsonBuffer && jsonBuffer.includes('"success"') && jsonBuffer.includes('}'))) {
          // 尝试解析 JSON
          try {
            const jsonStr = jsonBuffer.trim()
            if (jsonStr.endsWith('}')) {
              const parsed = JSON.parse(jsonStr)
              const msgType = parsed.success ? 'success' : 'error'
              const message = parsed.success
                ? `搜索完成: 入库 ${parsed.inserted || 0} 条`
                : `搜索失败: ${parsed.error || '未知错误'}`
              task.logs.push({ time: logTime, message, type: msgType })
              writeLogToDb(executionId, keyword, msgType, message)
              jsonBuffer = ''
            }
          } catch {
            // JSON 不完整，继续累积
          }
        }
        return
      }

      let logType: 'info' | 'success' | 'error' = 'info'

      // 成功消息
      if (cleanLine.includes('✅') || cleanLine.includes('成功入库') || cleanLine.includes('上传成功')) {
        logType = 'success'
        task.logs.push({ time: logTime, message: cleanLine, type: 'success' })
        // 写入数据库
        writeLogToDb(executionId, keyword, 'success', cleanLine)
        // 解析入库数量
        if (cleanLine.includes('成功入库')) {
          const match = cleanLine.match(/成功入库 (\d+)/)
          if (match) task.postsInserted = Number(match[1])
        }
      }
      // 错误消息
      else if (cleanLine.includes('❌') || cleanLine.includes('失败') || cleanLine.includes('错误') || cleanLine.includes('超时')) {
        logType = 'error'
        task.logs.push({ time: logTime, message: cleanLine, type: 'error' })
        // 写入数据库
        writeLogToDb(executionId, keyword, 'error', cleanLine)
      }
      // 图片处理日志
      else if (cleanLine.includes('📷') || cleanLine.includes('下载') || cleanLine.includes('上传')) {
        task.logs.push({ time: logTime, message: cleanLine, type: 'info' })
        // 写入数据库
        writeLogToDb(executionId, keyword, 'image', cleanLine)

        // 解析进度
        if (cleanLine.includes('下载第') && cleanLine.includes('张图片')) {
          const match = cleanLine.match(/下载第(\d+)\/(\d+)张/)
          if (match) {
            const current = Number(match[1])
            const total = Number(match[2])
            // 更新发现的图片总数（取最大值）
            if (total > task.imagesFound) {
              task.imagesFound = total
            }
          }
        }
        // 解析帖子图片总数
        if (cleanLine.includes('共') && cleanLine.includes('张图片')) {
          const match = cleanLine.match(/共\s*(\d+)\s*张图片/)
          if (match) {
            const total = Number(match[1])
            task.imagesFound += total
          }
        }
        if (cleanLine.includes('上传成功')) {
          task.imagesUploaded++
        }
        if (cleanLine.includes('上传失败')) {
          task.imagesFailed++
        }
      }
      // 主流程日志
      else if (cleanLine.includes('[main]') || cleanLine.includes('[xhs_cdp]')) {
        task.logs.push({ time: logTime, message: cleanLine, type: 'info' })
        // 写入数据库
        writeLogToDb(executionId, keyword, 'main', cleanLine)

        // 解析搜索结果数量
        if (cleanLine.includes('搜索到') || cleanLine.includes('获取到')) {
          const match = cleanLine.match(/(?:搜索到|获取到) (\d+)/)
          if (match) task.postsFound = Number(match[1])
        }
        if (cleanLine.includes('成功入库')) {
          const match = cleanLine.match(/成功入库 (\d+)/)
          if (match) task.postsInserted = Number(match[1])
        }
        if (cleanLine.includes('跳过')) {
          const match = cleanLine.match(/跳过 (\d+)/)
          if (match) task.postsSkipped = Number(match[1])
        }
      }
      // 帖子开始处理
      else if (cleanLine.includes('==========')) {
        task.logs.push({ time: logTime, message: cleanLine, type: 'info' })
        writeLogToDb(executionId, keyword, 'info', cleanLine)
      }
      // 其他日志
      else if (cleanLine.length > 0 && !cleanLine.startsWith('{') && !cleanLine.startsWith('}')) {
        task.logs.push({ time: logTime, message: cleanLine, type: 'info' })
        writeLogToDb(executionId, keyword, 'info', cleanLine)
      }

      // 限制日志数量（保留最近100条）
      if (task.logs.length > 100) {
        task.logs = task.logs.slice(-100)
      }
    }

    child.stdout?.on('data', (data) => {
      const lines = data.toString().split('\n')
      lines.forEach(parseLogLine)
    })

    child.stderr?.on('data', (data) => {
      const lines = data.toString().split('\n')
      lines.forEach(line => {
        if (line.trim()) {
          const errorMsg = line.trim()
          task.logs.push({
            time: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
            message: errorMsg,
            type: 'error'
          })
          writeLogToDb(executionId, keyword, 'error', errorMsg)
        }
      })
    })

    child.on('close', (code) => {
      task.status = code === 0 ? 'completed' : 'failed'
      task.endTime = new Date()

      const durationSeconds = Math.round((task.endTime.getTime() - task.startTime.getTime()) / 1000)

      writeSearchResultToDb(
        executionId,
        keyword,
        task.postsFound,
        task.postsInserted,
        task.postsSkipped,
        task.imagesFound,
        task.imagesUploaded,
        task.imagesFailed,
        durationSeconds,
        code !== 0 ? `进程退出码: ${code}` : null
      )

      // 更新数据库关键词的最后搜索时间
      getPool().execute('UPDATE keywords SET last_search_time = NOW() WHERE keyword = ?', [keyword])
        .catch(() => {})
    })

    child.unref()

    return {
      success: true,
      taskId,
      executionId,
      keyword,
      limit,
      message: '搜索任务已启动',
      logsUrl: `/api/search/realtime?action=status&taskId=${taskId}`
    }
  }

  return { success: false, error: '未知操作' }
})