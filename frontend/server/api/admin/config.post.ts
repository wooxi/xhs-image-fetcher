import { readFileSync, writeFileSync, existsSync } from 'fs'
import { resolve } from 'path'

const envKeyMapping: Record<string, string> = {
  lskyUrl: 'LSKY_PRO_URL',
  lskyToken: 'LSKY_PRO_TOKEN',
  dbHost: 'DB_HOST',
  dbPort: 'DB_PORT',
  dbUser: 'DB_USER',
  dbPassword: 'DB_PASSWORD',
  dbDatabase: 'DB_DATABASE',
  cdpHost: 'CDP_HOST',
  cdpPort: 'CDP_PORT',
}

export default defineEventHandler(async (event) => {
  if (getMethod(event) !== 'POST') {
    return { success: false, error: '仅支持 POST 请求' }
  }

  try {
    const body = await readBody(event)
    const envPath = resolve(process.cwd(), '../.env')

    if (!existsSync(envPath)) {
      return { success: false, error: '.env 文件不存在' }
    }

    const content = readFileSync(envPath, 'utf-8')
    const lines = content.split('\n')
    const updatedKeys = new Set<string>()

    // 更新已有的 key 或追加新 key
    const newLines = lines.map(line => {
      const trimmed = line.trim()
      if (!trimmed || trimmed.startsWith('#')) return line

      const eqIndex = trimmed.indexOf('=')
      if (eqIndex <= 0) return line

      const key = trimmed.substring(0, eqIndex).trim()
      for (const [field, envKey] of Object.entries(envKeyMapping)) {
        if (envKey === key && body[field] !== undefined) {
          updatedKeys.add(envKey)
          return `${envKey}=${String(body[field])}`
        }
      }
      return line
    })

    // 追加 .env 中不存在的 key
    for (const [field, envKey] of Object.entries(envKeyMapping)) {
      if (!updatedKeys.has(envKey) && body[field] !== undefined) {
        newLines.push(`${envKey}=${String(body[field])}`)
      }
    }

    writeFileSync(envPath, newLines.join('\n'), 'utf-8')

    return { success: true, message: '配置已保存' }
  } catch (error: any) {
    return { success: false, error: error.message || '保存失败' }
  }
})
