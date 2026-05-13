import { getPool, getLskyConfig } from '../../utils/db'
import fs from 'fs'
import path from 'path'

// 图片存储目录
const IMAGES_DIR = '/xhs-project/backend/downloaded_images'

// 删除图床图片
const deleteFromLsky = async (imageUrl: string, lskyUrl: string, lskyToken: string, storedKey?: string): Promise<boolean> => {
  try {
    if (!lskyUrl || !lskyToken) {
      console.log(`[delete] 图床配置缺失: URL=${lskyUrl || '无'}, TOKEN=${lskyToken ? '有' : '无'}`)
      return false
    }

    let key = storedKey || ''

    // 如果没有存储的 key，尝试从 URL 正则提取
    if (!key) {
      // URL 格式: http://192.168.100.3:5021/i/2026/04/26/69ed00144cfd9.jpg
      // key 是文件名部分（不含扩展名）：69ed00144cfd9
      const patterns = [
        /\/i\/\d{4}\/\d{2}\/\d{2}\/([a-f0-9]+)\.(jpg|jpeg|png|gif|webp)/i,
        /\/i\/.+\/([a-f0-9]+)\.(jpg|jpeg|png|gif|webp)/i,
        /\/([a-f0-9]{8,})\.(jpg|jpeg|png|gif|webp)/i,
      ]

      for (const pattern of patterns) {
        const match = imageUrl.match(pattern)
        if (match) {
          key = match[1]
          break
        }
      }

      if (!key) {
        console.log(`[delete] 无法从URL提取key: ${imageUrl}`)
        return false
      }
    }

    console.log(`[delete] 使用key: ${key} (${storedKey ? '存储的key' : 'URL提取'})`)

    // 调用图床删除 API
    const deleteRes = await fetch(`${lskyUrl}/api/v1/images/${key}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${lskyToken}`,
        'Accept': 'application/json'
      }
    })

    if (deleteRes.ok) {
      const deleteData = await deleteRes.json()
      if (deleteData.status) {
        console.log(`[delete] 图床图片已删除: ${key}`)
        return true
      } else {
        console.log(`[delete] 图床删除失败: ${deleteData.message}`)
        return false
      }
    } else {
      console.log(`[delete] 图床API请求失败: HTTP ${deleteRes.status}`)
      return false
    }
  } catch (error) {
    console.error('[delete] 图床删除异常:', error)
    return false
  }
}

// 解析 images 字段，兼容新旧格式
// 旧格式: ["url1", "url2"]
// 新格式: [{"url": "url1", "key": "key1"}, {"url": "url2", "key": "key2"}]
const parseImages = (imagesJson: any): Array<{ url: string; key?: string }> => {
  if (!imagesJson) return []

  try {
    let parsed: any[] = []

    if (Array.isArray(imagesJson)) {
      parsed = imagesJson
    } else if (typeof imagesJson === 'string') {
      if (imagesJson.startsWith('[')) {
        parsed = JSON.parse(imagesJson)
      } else if (imagesJson.startsWith('http')) {
        parsed = [imagesJson]
      } else {
        try {
          const result = JSON.parse(imagesJson)
          if (Array.isArray(result)) {
            parsed = result
          } else if (typeof result === 'string') {
            parsed = [result]
          }
        } catch {
          console.log(`[delete] 图片数据格式无法识别`)
          return []
        }
      }
    }

    return parsed.map(item => {
      if (typeof item === 'string') {
        return { url: item }
      }
      if (typeof item === 'object' && item.url) {
        return { url: item.url, key: item.key || undefined }
      }
      return null
    }).filter(Boolean) as Array<{ url: string; key?: string }>
  } catch (e) {
    console.error('[delete] 解析图片数据失败:', e)
    return []
  }
}

export default defineEventHandler(async (event) => {
  const body = await readBody(event)
  const postId = body.id

  if (!postId) {
    return { success: false, error: '缺少帖子ID' }
  }

  try {
    const pool = getPool()

    const [rows] = await pool.execute(
      'SELECT id, images FROM notes WHERE id = ?',
      [postId]
    )

    if (!Array.isArray(rows) || rows.length === 0) {
      return { success: false, error: '帖子不存在' }
    }

    const post = rows[0] as any
    const images = parseImages(post.images)

    console.log(`[delete] 解析到 ${images.length} 张图片`)

    // 获取图床配置（通过 Nuxt runtimeConfig）
    const lskyConfig = getLskyConfig()

    let deletedCount = 0
    let failedCount = 0

    for (const img of images) {
      if (!img.url || !img.url.startsWith('http')) continue

      // 删除图床图片（优先使用存储的 key）
      const deleted = await deleteFromLsky(img.url, lskyConfig.url, lskyConfig.token, img.key)
      console.log(`[delete] 图片 ${img.url.substring(0, 50)}... 删除结果: ${deleted}`)

      if (deleted) {
        deletedCount++
      } else {
        failedCount++
      }

      // 删除本地图片文件（如果有）
      const localMatch = img.url.match(/\/images\/(.+)$/)
      if (localMatch) {
        const localPath = path.join(IMAGES_DIR, localMatch[1])
        if (fs.existsSync(localPath)) {
          fs.unlinkSync(localPath)
          console.log(`[delete] 已删除本地图片: ${localPath}`)
        }
      }
    }

    // 删除数据库记录
    await pool.execute('DELETE FROM notes WHERE id = ?', [postId])

    console.log(`[delete] 已删除帖子: ${postId}, 图床图片: ${deletedCount}成功/${failedCount}失败`)
    return {
      success: true,
      message: '帖子已删除',
      imagesDeleted: deletedCount,
      imagesFailed: failedCount
    }
  } catch (error: any) {
    console.error('[delete] 删除失败:', error)
    return { success: false, error: error.message || '删除失败' }
  }
})
