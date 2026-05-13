import { getPool } from '../utils/db'

export default defineEventHandler(async (event) => {
  const body = await readBody(event)
  const keyword = body.keyword?.trim()
  const auto_search = body.auto_search ?? false
  const search_interval = body.search_interval ?? 24

  if (!keyword) {
    return {
      success: false,
      error: '关键词不能为空'
    }
  }

  if (keyword.length > 100) {
    return {
      success: false,
      error: '关键词长度不能超过100个字符'
    }
  }

  const pool = getPool()

  try {
    const [existing] = await pool.execute('SELECT id FROM keywords WHERE keyword = ?', [keyword])

    if ((existing as any[]).length > 0) {
      return {
        success: false,
        error: '关键词已存在'
      }
    }

    const [result] = await pool.execute(
      'INSERT INTO keywords (keyword, auto_search, search_interval) VALUES (?, ?, ?)',
      [keyword, auto_search, search_interval]
    )

    return {
      success: true,
      id: (result as any).insertId,
      keyword,
      auto_search,
      search_interval
    }
  } catch (error: any) {
    return {
      success: false,
      error: error.message || '添加关键词失败'
    }
  }
})
