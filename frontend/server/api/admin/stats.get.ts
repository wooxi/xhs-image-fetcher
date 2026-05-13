import { getPool } from '../../utils/db'

export default defineEventHandler(async () => {
  const pool = getPool()

  try {
    const [totalPosts] = await pool.query('SELECT COUNT(*) as count FROM notes')
    const [totalKeywords] = await pool.query('SELECT COUNT(*) as count FROM keywords')
    const [autoKeywords] = await pool.query('SELECT COUNT(*) as count FROM keywords WHERE auto_search = TRUE')
    const [todayPosts] = await pool.query('SELECT COUNT(*) as count FROM notes WHERE DATE(created_at) = CURDATE()')
    const [totalImages] = await pool.query('SELECT COALESCE(SUM(JSON_LENGTH(images)), 0) as count FROM notes WHERE images IS NOT NULL')
    const [recentLogs] = await pool.query('SELECT COUNT(*) as count FROM search_logs WHERE created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)')
    const [topKeywords] = await pool.query('SELECT keyword, COUNT(*) as count FROM notes GROUP BY keyword ORDER BY count DESC LIMIT 5')

    return {
      success: true,
      stats: {
        totalPosts: (totalPosts as any[])[0].count,
        totalImages: (totalImages as any[])[0].count,
        totalKeywords: (totalKeywords as any[])[0].count,
        autoKeywords: (autoKeywords as any[])[0].count,
        todayPosts: (todayPosts as any[])[0].count,
        recentLogs: (recentLogs as any[])[0].count,
        topKeywords: topKeywords as any[]
      }
    }
  } catch (error: any) {
    return {
      success: false,
      error: error.message || '获取统计失败'
    }
  }
})
