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
  const body = await readBody(event)
  const keyword = body.keyword?.trim()
  const auto_search = body.auto_search ?? true
  const search_interval = body.search_interval ?? 24

  if (!keyword) {
    return {
      success: false,
      error: '关键词不能为空'
    }
  }

  const connection = await mysql.createConnection(dbConfig)

  try {
    // 如果启用自动搜索，计算并设置next_search_time
    let nextSearchTime: Date | null = null
    if (auto_search) {
      // 下次搜索时间 = 当前时间 + 搜索间隔（小时）
      nextSearchTime = new Date(Date.now() + search_interval * 3600 * 1000)
    }

    const updateSql = `
      UPDATE keywords
      SET auto_search = ?, search_interval = ?, status = 'active',
          next_search_time = ?, retry_count = 0, last_error = NULL
      WHERE keyword = ?
    `
    const [result] = await connection.execute(updateSql, [auto_search, search_interval, nextSearchTime, keyword])

    const affectedRows = (result as any).affectedRows

    if (affectedRows > 0) {
      return {
        success: true,
        keyword,
        auto_search,
        search_interval,
        next_search_time: nextSearchTime ? nextSearchTime.toISOString() : null,
        message: auto_search ? '已启用自动搜索' : '已更新配置'
      }
    } else {
      return {
        success: false,
        error: '关键词不存在'
      }
    }
  } catch (error: any) {
    return {
      success: false,
      error: error.message || '更新失败'
    }
  } finally {
    await connection.end()
  }
})