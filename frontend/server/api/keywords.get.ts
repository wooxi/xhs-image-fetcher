import { getPool, formatDateTime } from '../utils/db'

interface Keyword {
  id: number
  keyword: string
  status: string
  auto_search: boolean
  search_interval: number
  last_search_time: string | null
  priority: string
  retry_count: number
  last_error: string | null
  next_search_time: string | null
  created_at: string
  updated_at: string
}

export default defineEventHandler(async () => {
  const pool = getPool()

  try {
    const sql = `
      SELECT id, keyword, status, auto_search, search_interval,
             last_search_time, priority, retry_count, last_error,
             next_search_time, created_at, updated_at
      FROM keywords
      ORDER BY priority DESC, created_at DESC
    `

    const [rows] = await pool.query(sql)

    const keywords: Keyword[] = (rows as any[]).map(row => ({
      ...row,
      auto_search: Boolean(row.auto_search),
      last_search_time: formatDateTime(row.last_search_time),
      next_search_time: formatDateTime(row.next_search_time),
      created_at: formatDateTime(row.created_at),
      updated_at: formatDateTime(row.updated_at),
      search_interval: parseFloat(row.search_interval) || 0
    }))

    return {
      success: true,
      keywords
    }
  } catch (error: any) {
    return {
      success: false,
      error: error.message || '获取搜索词列表失败'
    }
  }
})