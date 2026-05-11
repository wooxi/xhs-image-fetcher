import fs from 'fs'
import path from 'path'

const PID_FILE = '/xhs-project/.scheduler.pid'

export default defineEventHandler(async (event) => {
  try {
    // 检查 PID 文件是否存在
    if (!fs.existsSync(PID_FILE)) {
      return { success: false, error: '调度器未运行或PID文件不存在', running: false }
    }

    // 读取 PID
    const pid = parseInt(fs.readFileSync(PID_FILE, 'utf-8').trim(), 10)

    if (!pid || pid <= 0) {
      return { success: false, error: '无效的PID', running: false }
    }

    // 检查进程是否存在
    try {
      process.kill(pid, 0) // 发送信号0检查进程是否存在
    } catch (e) {
      // 进程不存在，删除PID文件
      fs.unlinkSync(PID_FILE)
      return { success: false, error: '调度器进程已不存在', running: false }
    }

    // 发送 SIGTERM 信号终止进程
    try {
      process.kill(pid, 'SIGTERM')
      console.log(`[scheduler] 发送终止信号到进程 ${pid}`)

      // 等待进程结束（最多等待5秒）
      let attempts = 0
      while (attempts < 50) {
        try {
          process.kill(pid, 0)
          // 进程仍然存在，继续等待
          await new Promise(resolve => setTimeout(resolve, 100))
          attempts++
        } catch {
          // 进程已结束
          break
        }
      }

      // 删除 PID 文件
      if (fs.existsSync(PID_FILE)) {
        fs.unlinkSync(PID_FILE)
      }

      console.log(`[scheduler] 调度器已停止 (PID: ${pid})`)
      return { success: true, message: '调度器已停止', running: false }
    } catch (e: any) {
      console.error(`[scheduler] 终止进程失败:`, e)
      return { success: false, error: `终止进程失败: ${e.message}`, running: true }
    }
  } catch (error: any) {
    console.error('[scheduler] 停止调度器失败:', error)
    return { success: false, error: error.message || '停止失败' }
  }
})