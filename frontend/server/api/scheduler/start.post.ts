import { spawn } from 'child_process'
import fs from 'fs'

const PID_FILE = '/xhs-project/.scheduler.pid'
const LOG_DIR = '/xhs-project/logs'

export default defineEventHandler(async (event) => {
  try {
    // 检查是否已经在运行
    if (fs.existsSync(PID_FILE)) {
      const pid = parseInt(fs.readFileSync(PID_FILE, 'utf-8').trim(), 10)
      if (pid > 0) {
        try {
          process.kill(pid, 0)
          return { success: false, error: '调度器已在运行', running: true, pid }
        } catch {
          // 进程不存在，删除旧的PID文件
          fs.unlinkSync(PID_FILE)
        }
      }
    }

    // 启动调度器
    const scriptPath = '/xhs-project/backend/main.py'
    const pythonPath = '/xhs-project/backend/venv/bin/python'

    // 确保 logs 目录存在
    if (!fs.existsSync(LOG_DIR)) {
      fs.mkdirSync(LOG_DIR, { recursive: true })
    }

    const child = spawn(pythonPath, [scriptPath, 'start-scheduler'], {
      cwd: '/xhs-project/backend',
      detached: true,
      stdio: ['ignore', fs.openSync(`${LOG_DIR}/scheduler.log`, 'a'), fs.openSync(`${LOG_DIR}/scheduler.log`, 'a')]
    })

    child.unref()

    const pid = child.pid

    // 写入 PID 文件
    fs.writeFileSync(PID_FILE, String(pid))

    console.log(`[scheduler] 调度器已启动 (PID: ${pid})`)
    return { success: true, message: '调度器已启动', running: true, pid }
  } catch (error: any) {
    console.error('[scheduler] 启动调度器失败:', error)
    return { success: false, error: error.message || '启动失败' }
  }
})