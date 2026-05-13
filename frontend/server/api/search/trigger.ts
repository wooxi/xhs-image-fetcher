import { getPool } from '../../utils/db'
import { spawn } from 'child_process'

export default defineEventHandler(async (event) => {
  const body = await readBody(event)
  const keyword = body.keyword?.trim()

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

  const limit = Math.min(Math.max(Number(body.limit ?? 10), 1), 50)

  try {
    const pool = getPool()
    await pool.execute(
      'UPDATE keywords SET last_search_time = NOW() WHERE keyword = ?',
      [keyword]
    )

    const scriptPath = '/xhs-project/backend/main.py'
    const pythonPath = '/xhs-project/backend/venv/bin/python'
    const child = spawn(pythonPath, [scriptPath, 'search', keyword, '--limit', String(limit)], {
      cwd: '/xhs-project/backend',
      env: process.env,
      detached: true,
      stdio: 'ignore'
    })
    child.unref()

    return {
      success: true,
      keyword,
      limit,
      message: '搜索任务已启动',
      note: '搜索将在后台运行，结果会自动入库'
    }
  } catch (error: any) {
    return {
      success: false,
      error: error.message || '触发搜索失败'
    }
  }
})
