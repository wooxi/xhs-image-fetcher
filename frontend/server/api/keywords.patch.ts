import { getPool } from '../utils/db'

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

  const pool = getPool()

  try {
    let nextSearchTime: Date | null = null
    if (auto_search) {
      nextSearchTime = new Date(Date.now() + search_interval * 3600 * 1000)
    }

    const [result] = await pool.execute(
      `UPDATE keywords SET auto_search = ?, search_interval = ?, status = 'active',
       next_search_time = ?, retry_count = 0, last_error = NULL WHERE keyword = ?`,
      [auto_search, search_interval, nextSearchTime, keyword]
    )

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
  }
})
