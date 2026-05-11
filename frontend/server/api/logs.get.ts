import { getPool, formatDateTime } from '../utils/db'

interface SearchLog {
  id: number
  execution_id: string | null
  keyword: string
  posts_found: number
  posts_inserted: number
  posts_skipped: number
  images_found: number
  images_uploaded: number
  images_failed: number
  duration_seconds: number
  error_message: string | null
  created_at: string
  log_count?: number
}

export default defineEventHandler(async (event) => {
  const query = getQuery(event)
  const keyword = query.keyword as string | undefined
  const limit = Number(query.limit) || 50

  const pool = getPool()

  try {
    let sql: string
    let params: any[] = []

    if (keyword && keyword.trim()) {
      sql = `
        SELECT sl.id, sl.execution_id, sl.keyword, sl.posts_found, sl.posts_inserted, sl.posts_skipped,
               sl.images_found, sl.images_uploaded, sl.images_failed,
               sl.duration_seconds, sl.error_message, sl.created_at,
               (SELECT COUNT(*) FROM execution_logs WHERE execution_id = sl.execution_id) as log_count
        FROM search_logs sl
        WHERE sl.keyword = ?
        ORDER BY sl.created_at DESC
        LIMIT ?
      `
      params = [keyword.trim(), limit]
    } else {
      sql = `
        SELECT sl.id, sl.execution_id, sl.keyword, sl.posts_found, sl.posts_inserted, sl.posts_skipped,
               sl.images_found, sl.images_uploaded, sl.images_failed,
               sl.duration_seconds, sl.error_message, sl.created_at,
               (SELECT COUNT(*) FROM execution_logs WHERE execution_id = sl.execution_id) as log_count
        FROM search_logs sl
        ORDER BY sl.created_at DESC
        LIMIT ?
      `
      params = [limit]
    }

    const [rows] = await pool.query(sql, params)

    const logs: SearchLog[] = (rows as any[]).map(row => ({
      ...row,
      created_at: formatDateTime(row.created_at) || String(row.created_at),
      log_count: row.log_count || 0
    }))

    return {
      success: true,
      logs,
      total: logs.length
    }
  } catch (error: any) {
    return {
      success: false,
      error: error.message || '获取搜索日志失败'
    }
  }
})