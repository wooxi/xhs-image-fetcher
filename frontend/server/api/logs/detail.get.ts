import mysql from 'mysql2/promise'

// 数据库配置
const dbConfig = {
  host: process.env.DB_HOST || '192.168.100.4',
  port: Number(process.env.DB_PORT) || 3306,
  user: process.env.DB_USER || 'root',
  password: process.env.DB_PASSWORD || 'ulikem00n',
  database: process.env.DB_DATABASE || 'xhs_notes'
}

export default defineEventHandler(async (event) => {
  const query = getQuery(event)
  const executionId = query.execution_id as string

  if (!executionId) {
    return { success: false, error: '缺少 execution_id 参数' }
  }

  try {
    const conn = await mysql.createConnection(dbConfig)

    // 获取统计信息
    const [summaryRows] = await conn.execute(
      `SELECT * FROM search_logs WHERE execution_id = ? LIMIT 1`,
      [executionId]
    )

    const summary = summaryRows[0]

    if (!summary) {
      await conn.end()
      return { success: false, error: '执行记录不存在', execution_id: executionId }
    }

    // 获取详细日志
    const [logRows] = await conn.execute(
      `SELECT id, execution_id, keyword, log_type, message, created_at
       FROM execution_logs
       WHERE execution_id = ?
       ORDER BY created_at ASC`,
      [executionId]
    )

    await conn.end()

    // 转换 datetime 为字符串
    const logs = logRows.map(row => ({
      id: row.id,
      execution_id: row.execution_id,
      keyword: row.keyword,
      log_type: row.log_type,
      message: row.message,
      created_at: row.created_at instanceof Date ? row.created_at.toISOString() : row.created_at
    }))

    return {
      success: true,
      execution_id: executionId,
      summary: {
        id: summary.id,
        keyword: summary.keyword,
        posts_found: summary.posts_found,
        posts_inserted: summary.posts_inserted,
        posts_skipped: summary.posts_skipped,
        images_found: summary.images_found,
        images_uploaded: summary.images_uploaded,
        images_failed: summary.images_failed,
        duration_seconds: summary.duration_seconds,
        error_message: summary.error_message,
        created_at: summary.created_at instanceof Date ? summary.created_at.toISOString() : summary.created_at
      },
      logs: logs,
      log_count: logs.length
    }
  } catch (error) {
    console.error('[logs/id.get] 获取执行详情失败:', error)
    return { success: false, error: error.message || '查询失败', execution_id: executionId }
  }
})