import mysql from 'mysql2/promise'
import { readFileSync, existsSync } from 'fs'

// 统一的数据库模块
// 使用连接池避免每次请求都创建/销毁连接

let pool: mysql.Pool | null = null

const getDbConfig = () => {
  const config = useRuntimeConfig()
  return {
    host: config.dbHost || process.env.DB_HOST,
    port: parseInt(String(config.dbPort || process.env.DB_PORT || '3306')),
    user: config.dbUser || process.env.DB_USER,
    password: config.dbPassword || process.env.DB_PASSWORD,
    database: config.dbDatabase || process.env.DB_DATABASE,
    waitForConnections: true,
    connectionLimit: 10,
    queueLimit: 0
  }
}

export const getPool = (): mysql.Pool => {
  if (!pool) {
    pool = mysql.createPool(getDbConfig())
  }
  return pool
}

// 兼容旧的连接方法（用于需要手动管理连接的场景）
export const createDbConnection = async () => {
  return await mysql.createConnection(getDbConfig())
}

export const getDbConfigPlain = () => getDbConfig()

export const getLskyConfig = () => {
  const config = useRuntimeConfig()
  let url = config.lskyProUrl || process.env.LSKY_PRO_URL
  let token = config.lskyProToken || process.env.LSKY_PRO_TOKEN

  if (!url || !token) {
    try {
      const envPath = '/xhs-project/.env'
      if (existsSync(envPath)) {
        const envContent = readFileSync(envPath, 'utf-8')
        for (const line of envContent.split('\n')) {
          const trimmed = line.trim()
          if (!url && trimmed.startsWith('LSKY_PRO_URL=')) {
            url = trimmed.substring('LSKY_PRO_URL='.length)
          }
          if (!token && trimmed.startsWith('LSKY_PRO_TOKEN=')) {
            token = trimmed.substring('LSKY_PRO_TOKEN='.length)
          }
        }
      }
    } catch (e) {
      console.error('[db] 读取.env文件失败:', e)
    }
  }

  return { url: url || '', token: token || '' }
}

export const formatDateTime = (value: any): string | null => {
  if (!value) return null
  const d = value instanceof Date ? value : new Date(value)
  return isNaN(d.getTime()) ? null : d.toISOString()
}
