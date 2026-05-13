import { getPool } from '../../utils/db'

export default defineEventHandler(async (event) => {
  const body = await readBody(event)
  const keyword = body.keyword?.trim()

  if (!keyword) {
    return {
      success: false,
      error: '关键词不能为空'
    }
  }

  const pool = getPool()

  try {
    const [result] = await pool.execute(
      'UPDATE keywords SET auto_search = FALSE WHERE keyword = ?',
      [keyword]
    )

    const affectedRows = (result as any).affectedRows

    if (affectedRows > 0) {
      return {
        success: true,
        keyword,
        auto_search: false,
        message: '已禁用自动搜索'
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
      error: error.message || '禁用失败'
    }
  }
})
