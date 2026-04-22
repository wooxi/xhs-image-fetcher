// 调度器状态 API
// 返回当前调度器的运行状态、任务队列等信息

import mysql from 'mysql2/promise'

interface SchedulerStatus {
  running: boolean
  peakTimeActive: boolean
  currentHour: number
  peakHours: Array<[number, number]>
  taskQueue: Array<{
    keyword: string
    status: string
    auto_search: boolean
    search_interval: number
    next_search_time: string | null
    last_search_time: string | null
    retry_count: number
    priority: string
  }>
  recentLogs: Array<{
    keyword: string
    posts_found: number
    posts_inserted: number
    duration_seconds: number
    created_at: string
    error_message: string | null
  }>
}

export default defineEventHandler(async (event): Promise<SchedulerStatus> => {
  // 获取数据库配置
  const config = useRuntimeConfig()

  const dbConfig = {
    host: config.dbHost || process.env.DB_HOST || 'localhost',
    port: parseInt(config.dbPort || process.env.DB_PORT || '3306'),
    user: config.dbUser || process.env.DB_USER || 'root',
    password: config.dbPassword || process.env.DB_PASSWORD || '',
    database: config.dbDatabase || process.env.DB_DATABASE || 'xhs_notes'
  }

  try {
    const conn = await mysql.createConnection(dbConfig)

    // 获取自动搜索的关键词（任务队列）
    const [keywords] = await conn.execute(`
      SELECT keyword, status, auto_search, search_interval,
             next_search_time, last_search_time, retry_count, priority
      FROM keywords
      WHERE auto_search = TRUE
      ORDER BY priority DESC, next_search_time ASC
    `)

    // 获取最近5条执行日志
    const [logs] = await conn.execute(`
      SELECT keyword, posts_found, posts_inserted, duration_seconds, created_at, error_message
      FROM search_logs
      ORDER BY created_at DESC
      LIMIT 5
    `)

    await conn.end()

    // 计算高峰时段
    const currentHour = new Date().getHours()
    const peakHours: Array<[number, number]> = [[12, 14], [18, 22]]
    const peakTimeActive = peakHours.some(([start, end]) => currentHour >= start && currentHour < end)

    return {
      running: true, // 假设调度器在运行（实际需要从进程状态获取）
      peakTimeActive,
      currentHour,
      peakHours,
      taskQueue: (keywords as any[]).map(k => ({
        keyword: k.keyword,
        status: k.status,
        auto_search: Boolean(k.auto_search),
        search_interval: parseFloat(k.search_interval || 0),
        next_search_time: k.next_search_time ? k.next_search_time.toISOString() : null,
        last_search_time: k.last_search_time ? k.last_search_time.toISOString() : null,
        retry_count: k.retry_count || 0,
        priority: k.priority || 'normal'
      })),
      recentLogs: (logs as any[]).map(l => ({
        keyword: l.keyword,
        posts_found: l.posts_found || 0,
        posts_inserted: l.posts_inserted || 0,
        duration_seconds: l.duration_seconds || 0,
        created_at: l.created_at ? l.created_at.toISOString() : '',
        error_message: l.error_message || null
      }))
    }

  } catch (error: any) {
    console.error('[scheduler/status] 数据库查询失败:', error)

    // 返回默认状态
    return {
      running: false,
      peakTimeActive: false,
      currentHour: new Date().getHours(),
      peakHours: [[12, 14], [18, 22]],
      taskQueue: [],
      recentLogs: []
    }
  }
})