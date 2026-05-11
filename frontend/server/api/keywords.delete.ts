import mysql from 'mysql2/promise'

// 数据库配置
const dbConfig = {
  host: process.env.DB_HOST || '192.168.100.4',
  port: Number(process.env.DB_PORT) || 3306,
  user: process.env.DB_USER || 'root',
  password: process.env.DB_PASSWORD || '',
  database: process.env.DB_DATABASE || 'xhs_notes'
}

export default defineEventHandler(async (event) => {
  const body = await readBody(event).catch(() => null)

  const keyword = body?.keyword?.trim()

  if (!keyword) {
    return {
      success: false,
      error: '关键词不能为空'
    }
  }

  const connection = await mysql.createConnection(dbConfig)

  try {
    // 删除关联的搜索日志和执行日志
    await connection.execute('DELETE FROM search_logs WHERE keyword = ?', [keyword])
    await connection.execute('DELETE FROM execution_logs WHERE keyword = ?', [keyword])
    // 删除关键词
    const [result] = await connection.execute('DELETE FROM keywords WHERE keyword = ?', [keyword])

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
  } finally {
    await connection.end()
  }
})
