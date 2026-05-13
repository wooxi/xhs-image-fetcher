import { getPool } from '../utils/db'

const validLogTypes = ['info', 'success', 'error', 'image', 'main']

export default defineEventHandler(async (event) => {
  const method = getMethod(event)
  if (method !== 'POST') {
    return { success: false, error: '仅支持 POST 请求' }
  }

  try {
    const body = await readBody(event)

    if (!body.execution_id) {
      return { success: false, error: '缺少 execution_id' }
    }
    if (!body.keyword) {
      return { success: false, error: '缺少 keyword' }
    }

    const logType = body.log_type || 'info'
    if (!validLogTypes.includes(logType)) {
      return { success: false, error: `无效的log_type: ${logType}` }
    }

    const message = body.message || ''
    const pool = getPool()

    const [result] = await pool.execute(
      'INSERT INTO execution_logs (execution_id, keyword, log_type, message) VALUES (?, ?, ?, ?)',
      [body.execution_id, body.keyword, logType, message]
    )

    return {
      success: true,
      id: result.insertId,
      execution_id: body.execution_id,
      log_type: logType
    }
  } catch (error) {
    console.error('[logs.post] 写入日志失败:', error)
    return { success: false, error: error.message || '写入失败' }
  }
})
