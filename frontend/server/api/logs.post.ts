import mysql from 'mysql2/promise'

// 数据库配置
const dbConfig = {
  host: process.env.DB_HOST || '192.168.100.4',
  port: Number(process.env.DB_PORT) || 3306,
  user: process.env.DB_USER || 'root',
  password: process.env.DB_PASSWORD || 'ulikem00n',
  database: process.env.DB_DATABASE || 'xhs_notes'
}

// 日志类型枚举
const validLogTypes = ['info', 'success', 'error', 'image', 'main']

export default defineEventHandler(async (event) => {
  // 只接受 POST 请求
  const method = getMethod(event)
  if (method !== 'POST') {
    return { success: false, error: '仅支持 POST 请求' }
  }

  try {
    const body = await readBody(event)

    // 验证必填字段
    if (!body.execution_id) {
      return { success: false, error: '缺少 execution_id' }
    }

    if (!body.keyword) {
      return { success: false, error: '缺少 keyword' }
    }

    const logType = body.log_type || 'info'
    if (!validLogTypes.includes(logType)) {
      return { success: false, error: `无效的 log_type: ${logType}` }
    }

    const message = body.message || ''

    // 写入数据库
    const conn = await mysql.createConnection(dbConfig)

    const [result] = await conn.execute(
      `INSERT INTO execution_logs (execution_id, keyword, log_type, message) VALUES (?, ?, ?, ?)`,
      [body.execution_id, body.keyword, logType, message]
    )

    await conn.end()

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