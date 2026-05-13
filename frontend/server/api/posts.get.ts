import { getPool, formatDateTime } from '../utils/db'

interface Post {
  id: number
  title: string
  content: string
  url: string
  images: string[]
  likes: number
  collects: number
  comments: number
  author_name: string
  keyword: string
  publish_time: string
}

export default defineEventHandler(async (event) => {
  const query = getQuery(event)
  const page = Number(query.page) || 1
  const pageSize = Math.min(Math.max(Number(query.pageSize) || 20, 1), 100)
  const keyword = (query.keyword as string) || ''

  const offset = (page - 1) * pageSize
  const pool = getPool()

  try {
    let baseWhere = ''
    let params: any[] = []

    if (keyword && keyword.trim()) {
      const kw = keyword.trim()
      baseWhere = 'WHERE title LIKE ? OR keyword LIKE ? OR author_name LIKE ?'
      params = [`%${kw}%`, `%${kw}%`, `%${kw}%`]
    }

    const countSql = `SELECT COUNT(*) as total FROM notes ${baseWhere}`
    const [countRows] = await pool.query(countSql, params)
    const total = (countRows as any[])[0].total

    const dataSql = `SELECT
      id, title, content, url, images,
      likes, collects, comments, author_name,
      keyword, publish_time
     FROM notes
     ${baseWhere}
     ORDER BY publish_time DESC
     LIMIT ? OFFSET ?`

    const [rows] = await pool.query(dataSql, [...params, pageSize, offset])

    const posts: Post[] = (rows as any[]).map(row => {
      let imagesData = row.images
      if (typeof imagesData === 'string') {
        try {
          imagesData = JSON.parse(imagesData || '[]')
        } catch {
          imagesData = []
        }
      }
      if (!Array.isArray(imagesData)) {
        imagesData = []
      }
      const normalizedImages = imagesData.map((item: any) => {
        if (typeof item === 'string') return item
        if (typeof item === 'object' && item.url) return item.url
        return null
      }).filter(Boolean) as string[]

      return {
        ...row,
        images: normalizedImages
      }
    })

    return {
      posts,
      total,
      page,
      pageSize
    }
  } finally {
    // 连接池不需要手动关闭
  }
})