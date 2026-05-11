export default defineEventHandler(async (event) => {
  return {
    success: false,
    error: '关键词已锁定，不允许删除'
  }
})
