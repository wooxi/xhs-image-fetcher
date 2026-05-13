import { getPool } from '../utils/db'

export default defineEventHandler(async (event) => {
  const body = await readBody(event).catch(() => null)
  const keyword = body?.keyword?.trim()

  if (!keyword) {
    return {
      success: false,
      error: '关键词不能为空'
    }
  }

  const pool = getPool()

  try {
    await pool.execute('DELETE FROM search_logs WHERE keyword = ?', [keyword])
    await pool.execute('DELETE FROM execution_logs WHERE keyword = ?', [keyword])
    const [result] = await pool.execute('DELETE FROM keywords WHERE keyword = ?', [keyword])

    const affectedRows = (result as any).affectedRows

    if (affectedRows > 0) {
      return {
        success: true,
        keyword,
        message: '关键词已删除'
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
      error: error.message || '删除关键词失败'
    }
  }
})
