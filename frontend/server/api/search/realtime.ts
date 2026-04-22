import mysql from 'mysql2/promise'
import { spawn, ChildProcess } from 'child_process'
import path from 'path'

// 数据库配置
const dbConfig = {
  host: process.env.DB_HOST || '192.168.100.4',
  port: Number(process.env.DB_PORT) || 3306,
  user: process.env.DB_USER || 'root',
  password: process.env.DB_PASSWORD || 'ulikem00n',
  database: process.env.DB_DATABASE || 'xhs_notes'
}

// 搜索任务状态存储（内存）
const searchTasks: Map<string, {
  keyword: string
  limit: number
  status: 'running' | 'completed' | 'failed'
  logs: Array<{ time: string; message: string; type: 'info' | 'success' | 'error' }>
  startTime: Date
  endTime?: Date
  postsFound: number
  postsInserted: number
  imagesUploaded: number
  imagesFailed: number
}> = new Map()

export default defineEventHandler(async (event) => {
  const query = getQuery(event)
  const action = query.action as string || 'start'
  const keyword = query.keyword as string

  // 获取任务状态
  if (action === 'status') {
    const taskId = query.taskId as string
    if (taskId && searchTasks.has(taskId)) {
      return { success: true, task: searchTasks.get(taskId) }
    }
    // 返回所有运行中的任务
    const runningTasks = Array.from(searchTasks.entries())
      .filter(([_, task]) => task.status === 'running')
      .map(([id, task]) => ({ id, ...task }))
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
    const limit = Number(query.limit) || 5
    const uploadImages = query.upload === 'true'
    const taskId = `search_${Date.now()}_${keyword}`

    // 初始化任务状态
    const task = {
      keyword,
      limit,
      status: 'running' as const,
      logs: [] as Array<{ time: string; message: string; type: 'info' | 'success' | 'error' }>,
      startTime: new Date(),
      postsFound: 0,
      postsInserted: 0,
      imagesUploaded: 0,
      imagesFailed: 0
    }
    searchTasks.set(taskId, task)

    // 启动后台搜索进程（使用venv中的Python）
    const scriptPath = '/xhs-project/backend/main.py'
    const pythonPath = '/xhs-project/backend/venv/bin/python'
    const args = ['search-detail', keyword, '--limit', String(limit)]
    if (uploadImages) {
      args.push('--upload-images')
    }

    const child = spawn(pythonPath, [scriptPath, ...args], {
      cwd: '/xhs-project/backend',
      env: { ...process.env, PYTHONUNBUFFERED: '1' },
      stdio: ['ignore', 'pipe', 'pipe']
    })

    // 解析日志输出
    const parseLogLine = (line: string) => {
      const time = new Date().toLocaleTimeString()

      // 解析不同类型的日志
      if (line.includes('✅') || line.includes('成功')) {
        task.logs.push({ time, message: line.trim(), type: 'success' })
      } else if (line.includes('❌') || line.includes('失败') || line.includes('错误')) {
        task.logs.push({ time, message: line.trim(), type: 'error' })
      } else if (line.includes('📷') || line.includes('下载') || line.includes('上传') || line.includes('处理')) {
        task.logs.push({ time, message: line.trim(), type: 'info' })
      } else if (line.includes('[main]') || line.includes('[xhs_cdp]')) {
        // 解析关键信息
        if (line.includes('搜索到')) {
          const match = line.match(/搜索到 (\d+) 条/)
          if (match) task.postsFound = Number(match[1])
        }
        if (line.includes('成功入库')) {
          const match = line.match(/成功入库 (\d+) 条/)
          if (match) task.postsInserted = Number(match[1])
        }
        if (line.includes('图片上传完成')) {
          const successMatch = line.match(/成功 (\d+)/)
          const failMatch = line.match(/失败 (\d+)/)
          if (successMatch) task.imagesUploaded = Number(successMatch[1])
          if (failMatch) task.imagesFailed = Number(failMatch[1])
        }
        task.logs.push({ time, message: line.trim(), type: 'info' })
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
          task.logs.push({
            time: new Date().toLocaleTimeString(),
            message: line.trim(),
            type: 'error'
          })
        }
      })
    })

    child.on('close', (code) => {
      task.status = code === 0 ? 'completed' : 'failed'
      task.endTime = new Date()

      // 更新数据库关键词的最后搜索时间
      mysql.createConnection(dbConfig).then(conn => {
        conn.execute('UPDATE keywords SET last_search_time = NOW() WHERE keyword = ?', [keyword])
        conn.end()
      }).catch(() => {})
    })

    child.unref()

    return {
      success: true,
      taskId,
      keyword,
      limit,
      message: '搜索任务已启动',
      logsUrl: `/api/search/realtime?action=status&taskId=${taskId}`
    }
  }

  return { success: false, error: '未知操作' }
})