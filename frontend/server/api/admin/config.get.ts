import { readFileSync, existsSync } from 'fs'
import { resolve } from 'path'

export default defineEventHandler(async () => {
  try {
    const envPath = resolve(process.cwd(), '../.env')

    if (!existsSync(envPath)) {
      return { success: false, error: '.env 文件不存在' }
    }

    const content = readFileSync(envPath, 'utf-8')
    const config: Record<string, string> = {}

    content.split('\n').forEach(line => {
      const trimmed = line.trim()
      if (trimmed && !trimmed.startsWith('#')) {
        const eqIndex = trimmed.indexOf('=')
        if (eqIndex > 0) {
          const key = trimmed.substring(0, eqIndex).trim()
          const value = trimmed.substring(eqIndex + 1).trim()
          config[key] = value
        }
      }
    })

    return {
      success: true,
      config: {
        lskyProUrl: config.LSKY_PRO_URL || '',
        lskyProToken: config.LSKY_PRO_TOKEN || '',
        dbHost: config.DB_HOST || '',
        dbPort: config.DB_PORT || '',
        dbUser: config.DB_USER || '',
        dbPassword: config.DB_PASSWORD || '',
        dbDatabase: config.DB_DATABASE || '',
        cdpHost: config.CDP_HOST || '',
        cdpPort: config.CDP_PORT || '',
        searchLimit: config.SEARCH_LIMIT || '',
        peakHours: config.PEAK_HOURS || '',
      }
    }
  } catch (error: any) {
    return {
      success: false,
      error: error.message || '读取配置失败'
    }
  }
})
