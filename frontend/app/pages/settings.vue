<template>
  <div class="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
    <Head>
      <meta name="referrer" content="no-referrer" />
    </Head>

    <!-- 顶部导航 -->
    <header class="sticky top-0 bg-white/95 backdrop-blur-sm shadow-sm z-50 border-b border-gray-100">
      <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <button
            @click="$router.push('/')"
            class="flex items-center gap-1.5 text-gray-500 hover:text-xhs-red hover:bg-gray-50 px-2.5 py-2 rounded-lg transition-all"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"/>
            </svg>
            <span class="text-sm font-medium">返回</span>
          </button>
          <h1 class="text-lg font-bold text-gray-800">系统设置</h1>
        </div>

        <!-- Tab 切换 -->
        <div class="flex gap-1 bg-gray-100 rounded-lg p-1">
          <button
            @click="activeTab = 'keywords'"
            :class="activeTab === 'keywords' ? 'bg-white shadow-sm text-xhs-red' : 'text-gray-500 hover:text-gray-700'"
            class="px-4 py-1.5 rounded-md transition-all text-sm font-medium"
          >
            关键词管理
          </button>
          <button
            @click="activeTab = 'logs'; refreshLogs()"
            :class="activeTab === 'logs' ? 'bg-white shadow-sm text-xhs-red' : 'text-gray-500 hover:text-gray-700'"
            class="px-4 py-1.5 rounded-md transition-all text-sm font-medium flex items-center gap-1"
          >
            执行日志
            <span v-if="logs.length > 0" class="inline-flex items-center justify-center w-4 h-4 text-[10px] rounded-full bg-xhs-red/10 text-xhs-red">{{ logs.length }}</span>
          </button>
        </div>

        <!-- 调度器状态 -->
        <div class="flex items-center gap-2">
          <div class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-green-50 text-green-700" title="调度器由 start.sh 管理，自动启动并始终运行">
            <div class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
            运行中
          </div>
          <button
            v-show="activeTab === 'keywords'"
            @click="showAddModal = true"
            class="px-3 py-1.5 bg-xhs-red text-white rounded-lg hover:bg-red-600 transition-all text-xs font-medium flex items-center gap-1"
          >
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
            </svg>
            添加
          </button>
        </div>
      </div>
    </header>

    <!-- 内容区域 -->
    <main class="max-w-7xl mx-auto px-4 py-5">
      <!-- 关键词 Tab -->
      <div v-show="activeTab === 'keywords'">
        <!-- 加载状态 -->
        <div v-if="pending" class="flex justify-center py-20">
          <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-xhs-red"></div>
        </div>

        <!-- 错误状态 -->
        <div v-else-if="error" class="text-center py-20 text-gray-400">
          加载失败，请刷新页面重试
        </div>

        <!-- 空状态 -->
        <div v-else-if="keywords.length === 0" class="text-center py-20">
          <svg class="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
          </svg>
          <p class="text-gray-400 mb-4">暂无配置的搜索词</p>
          <button @click="showAddModal = true" class="px-4 py-2 bg-xhs-red text-white rounded-lg hover:bg-red-600 transition text-sm">
            添加第一个关键词
          </button>
        </div>

        <!-- 关键词列表 -->
        <div v-else class="grid gap-3 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
          <div
            v-for="kw in keywords"
            :key="kw.id"
            class="bg-white rounded-xl shadow-sm border border-gray-100 p-4 hover:shadow-md transition-all group"
          >
            <!-- 关键词头部 -->
            <div class="flex items-start justify-between mb-3">
              <div class="flex items-center gap-2.5 min-w-0 flex-1">
                <div class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0" :class="kw.auto_search ? 'bg-green-100' : 'bg-gray-100'">
                  <svg class="w-4 h-4" :class="kw.auto_search ? 'text-green-600' : 'text-gray-400'" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                  </svg>
                </div>
                <div class="min-w-0">
                  <h3 class="text-sm font-semibold text-gray-900 truncate">{{ kw.keyword }}</h3>
                  <div class="flex items-center gap-1.5 mt-0.5">
                    <span v-if="kw.auto_search" class="inline-flex items-center gap-1 text-[11px] text-green-600 bg-green-50 px-1.5 py-0.5 rounded-full">
                      <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                      </svg>
                      每 {{ formatInterval(kw.search_interval) }}
                    </span>
                    <span v-else class="text-[11px] text-gray-400">手动</span>
                    <span v-if="kw.priority && kw.priority !== 'normal'" class="text-[11px] px-1.5 py-0.5 rounded-full" :class="{ 'bg-yellow-50 text-yellow-600': kw.priority === 'high', 'bg-gray-50 text-gray-500': kw.priority === 'low' }">
                      {{ kw.priority === 'high' ? '高优先' : '低优先' }}
                    </span>
                    <span v-if="kw.retry_count > 0" class="text-[11px] text-red-500 bg-red-50 px-1.5 py-0.5 rounded-full">
                      失败 {{ kw.retry_count }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- 操作菜单 -->
              <div class="relative flex-shrink-0">
                <button
                  @click="openActionMenu(kw)"
                  class="p-1.5 rounded-lg hover:bg-gray-100 transition-all opacity-0 group-hover:opacity-100"
                >
                  <svg class="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"/>
                  </svg>
                </button>

                <!-- 下拉菜单 -->
                <div v-if="actionMenuOpen[kw.id]" class="absolute right-0 mt-1 w-36 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-10">
                  <button
                    @click="toggleAutoSearch(kw)"
                    class="w-full text-left px-3 py-2 text-sm hover:bg-gray-50 flex items-center gap-2"
                    :class="kw.auto_search ? 'text-green-600' : 'text-gray-600'"
                  >
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    {{ kw.auto_search ? '关闭自动' : '开启自动' }}
                  </button>
                  <button
                    @click="triggerSearch(kw)"
                    :disabled="searchingKeywords.includes(kw.keyword)"
                    class="w-full text-left px-3 py-2 text-sm text-xhs-red hover:bg-red-50 flex items-center gap-2 disabled:opacity-50"
                  >
                    <svg class="w-4 h-4" :class="searchingKeywords.includes(kw.keyword) ? 'animate-spin' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                    </svg>
                    {{ searchingKeywords.includes(kw.keyword) ? '搜索中...' : '立即搜索' }}
                  </button>
                </div>
              </div>
            </div>

            <!-- 时间信息 -->
            <div v-if="kw.last_search_time || kw.next_search_time" class="flex items-center gap-3 text-[11px] text-gray-400 bg-gray-50 rounded-lg px-2.5 py-1.5">
              <span v-if="kw.last_search_time">上次: {{ formatTime(kw.last_search_time) }}</span>
              <span v-if="kw.next_search_time">下次: {{ formatTime(kw.next_search_time) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 日志 Tab -->
      <div v-show="activeTab === 'logs'">
        <!-- 实时搜索任务面板 -->
        <div v-if="runningTasks.length > 0" class="mb-5 space-y-3">
          <div class="flex items-center gap-2 px-3 py-2 bg-blue-50 rounded-lg text-blue-700 text-sm font-medium">
            <div class="animate-spin rounded-full h-4 w-4 border-2 border-blue-500 border-t-transparent"></div>
            正在执行搜索任务 ({{ runningTasks.length }})
          </div>

          <div v-for="task in runningTasks" :key="task.id" class="bg-white rounded-xl shadow-sm border border-blue-100 overflow-hidden">
            <div class="px-4 py-2.5 bg-gradient-to-r from-blue-50 to-gray-50 flex items-center justify-between border-b border-blue-100">
              <div class="flex items-center gap-2">
                <span class="px-2.5 py-0.5 bg-xhs-red text-white rounded text-xs font-medium">{{ task.keyword }}</span>
                <span class="text-xs text-gray-400">目标 {{ task.limit }} 条</span>
              </div>
              <span class="text-xs text-gray-400">{{ formatTaskTime(task.startTime) }}</span>
            </div>

            <!-- 进度条 -->
            <div class="h-1.5 bg-gray-100">
              <div class="h-full bg-blue-500 transition-all duration-300 rounded-r" :style="{ width: `${Math.min(100, (task.postsInserted / Math.max(task.limit, 1)) * 100)}%` }"></div>
            </div>

            <!-- 统计数据 -->
            <div class="grid grid-cols-4 gap-2 px-4 py-2 bg-gray-50 text-center">
              <div><span class="text-sm font-bold text-gray-700">{{ task.postsFound }}</span><span class="text-[11px] text-gray-400 block">发现</span></div>
              <div><span class="text-sm font-bold text-green-600">{{ task.postsInserted }}</span><span class="text-[11px] text-gray-400 block">入库</span></div>
              <div><span class="text-sm font-bold text-blue-600">{{ task.imagesUploaded }}</span><span class="text-[11px] text-gray-400 block">上传</span></div>
              <div><span class="text-sm font-bold text-red-500">{{ task.imagesFailed }}</span><span class="text-[11px] text-gray-400 block">失败</span></div>
            </div>

            <!-- 实时日志 -->
            <div class="px-4 py-2 max-h-48 overflow-y-auto bg-gray-900 text-gray-100 font-mono text-xs">
              <div v-for="(log, i) in task.logs.slice(-30)" :key="i" class="py-0.5" :class="{ 'text-green-400': log.type === 'success', 'text-red-400': log.type === 'error' }">
                <span class="text-gray-500">[{{ log.time }}]</span> {{ log.message }}
              </div>
            </div>
          </div>
        </div>

        <!-- 日志过滤 -->
        <div class="mb-4 flex items-center gap-3">
          <div class="relative flex-1 max-w-xs">
            <input
              v-model="logFilter"
              type="text"
              placeholder="过滤关键词..."
              class="w-full pl-9 pr-3 py-2 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-xhs-red/30 focus:border-xhs-red"
            />
            <svg class="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
            </svg>
          </div>
          <button @click="refreshLogs()" class="px-3 py-2 text-sm text-xhs-red hover:bg-red-50 rounded-lg transition-all">
            刷新
          </button>
        </div>

        <!-- 加载/错误/空状态 -->
        <div v-if="logsPending" class="flex justify-center py-20">
          <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-xhs-red"></div>
        </div>

        <div v-else-if="logsError" class="text-center py-20 text-gray-400">
          加载失败，请刷新重试
        </div>

        <div v-else-if="filteredLogs.length === 0" class="text-center py-16 text-gray-400">
          <svg class="w-12 h-12 mx-auto mb-3 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/>
          </svg>
          <p class="text-sm">暂无搜索日志</p>
        </div>

        <!-- 日志列表 -->
        <div v-else class="space-y-3">
          <div
            v-for="log in filteredLogs"
            :key="log.id"
            class="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden hover:shadow-md transition-all"
          >
            <div class="px-4 py-3">
              <!-- 头部 -->
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <span class="px-2.5 py-0.5 bg-xhs-red/10 text-xhs-red rounded-md text-xs font-semibold">{{ log.keyword }}</span>
                  <span v-if="log.error_message" class="px-2 py-0.5 bg-red-100 text-red-600 rounded-md text-[11px] flex items-center gap-0.5">
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01"/></svg>
                    失败
                  </span>
                  <span v-else class="px-2 py-0.5 bg-green-100 text-green-600 rounded-md text-[11px] flex items-center gap-0.5">
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4"/></svg>
                    成功
                  </span>
                </div>
                <span class="text-[11px] text-gray-400">{{ formatLogTime(log.created_at) }}</span>
              </div>

              <!-- 统计 -->
              <div class="flex items-center gap-4 mt-3">
                <div class="text-center"><span class="text-base font-bold text-gray-700">{{ log.posts_found }}</span><span class="text-[10px] text-gray-400 block">发现</span></div>
                <div class="text-center"><span class="text-base font-bold text-green-600">{{ log.posts_inserted }}</span><span class="text-[10px] text-gray-400 block">入库</span></div>
                <div class="text-center"><span class="text-base font-bold text-blue-600">{{ log.images_uploaded }}</span><span class="text-[10px] text-gray-400 block">上传</span></div>
                <div class="text-center"><span class="text-base font-bold text-orange-600">{{ log.duration_seconds }}s</span><span class="text-[10px] text-gray-400 block">耗时</span></div>
                <span v-if="log.posts_skipped" class="text-[11px] text-gray-400">跳过 {{ log.posts_skipped }}</span>
              </div>

              <!-- 错误信息 -->
              <div v-if="log.error_message" class="mt-2 p-2 bg-red-50 rounded text-red-600 text-xs">{{ log.error_message }}</div>

              <!-- 展开详情 -->
              <button
                @click="toggleLogDetail(log.id)"
                class="mt-2 text-xs text-xhs-red hover:text-red-600 flex items-center gap-1"
              >
                <svg class="w-3.5 h-3.5 transition-transform" :class="expandedLogs[log.id] ? 'rotate-90' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                </svg>
                {{ expandedLogs[log.id] ? '收起' : '详情' }}
              </button>

              <!-- 内联详情日志 -->
              <div v-if="expandedLogs[log.id] && log.execution_id" class="mt-2 border border-gray-100 rounded-lg overflow-hidden">
                <div v-if="logDetailCache[log.execution_id]?.loading" class="flex justify-center py-4">
                  <div class="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-xhs-red"></div>
                </div>
                <div v-else-if="logDetailCache[log.execution_id]?.logs?.length > 0" class="max-h-60 overflow-y-auto bg-gray-900 text-gray-100 font-mono text-xs px-3 py-2">
                  <div v-for="(dl, i) in logDetailCache[log.execution_id].logs" :key="i" class="py-0.5" :class="{ 'text-green-400': dl.log_type === 'success', 'text-red-400': dl.log_type === 'error', 'text-blue-300': dl.log_type === 'info' }">
                    <span class="text-gray-500">[{{ formatLogDetailTime(dl.created_at) }}]</span> {{ dl.message }}
                  </div>
                </div>
                <div v-else class="text-center py-4 text-gray-400 text-xs">暂无详细日志</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- 添加关键词模态框 -->
    <div
      v-if="showAddModal"
      class="fixed inset-0 bg-black/50 z-[100] flex items-center justify-center"
      @click.self="showAddModal = false"
    >
      <div class="bg-white rounded-xl shadow-xl w-full max-w-sm p-5">
        <h2 class="text-base font-bold text-gray-800 mb-4">添加搜索关键词</h2>

        <div class="space-y-3">
          <div>
            <label class="block text-sm text-gray-500 mb-1">关键词</label>
            <input
              v-model="newKeyword"
              type="text"
              placeholder="输入搜索关键词..."
              class="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-xhs-red/30 focus:border-xhs-red"
            />
          </div>

          <div class="flex items-center justify-between">
            <div>
              <div class="text-sm text-gray-700">启用自动搜索</div>
              <p class="text-[11px] text-gray-400">按设定间隔自动搜索</p>
            </div>
            <button
              @click="newAutoSearch = !newAutoSearch"
              :class="newAutoSearch ? 'bg-xhs-red' : 'bg-gray-300'"
              class="w-10 h-5 rounded-full transition relative"
            >
              <div
                :class="newAutoSearch ? 'right-0.5' : 'left-0.5'"
                class="w-3.5 h-3.5 bg-white rounded-full absolute top-0.5 transition-all"
              ></div>
            </button>
          </div>

          <div v-if="newAutoSearch">
            <label class="block text-sm text-gray-500 mb-1">搜索间隔</label>
            <div class="flex gap-1.5 flex-wrap">
              <button v-for="opt in intervalOptions" :key="opt.value" @click="newInterval = opt.value" class="px-2.5 py-1 text-xs rounded-lg border transition-all" :class="newInterval === opt.value ? 'bg-xhs-red text-white border-xhs-red' : 'bg-gray-50 text-gray-500 border-gray-200 hover:border-gray-300'">
                {{ opt.label }}
              </button>
            </div>
          </div>
        </div>

        <div class="flex justify-end gap-2 mt-4">
          <button @click="showAddModal = false" class="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700 transition">取消</button>
          <button @click="addKeyword" :disabled="!newKeyword.trim() || adding" class="px-3 py-1.5 bg-xhs-red text-white rounded-lg text-sm hover:bg-red-600 transition disabled:opacity-50">
            {{ adding ? '添加中...' : '添加' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 提示消息 -->
    <div
      v-if="toast.show"
      class="fixed top-4 left-1/2 -translate-x-1/2 z-[200] px-4 py-2 rounded-lg shadow-lg transition-all text-sm"
      :class="toast.type === 'success' ? 'bg-green-500 text-white' : 'bg-red-500 text-white'"
    >
      {{ toast.message }}
    </div>
  </div>
</template>

<script setup lang="ts">
interface Keyword {
  id: number
  keyword: string
  status: string
  auto_search: boolean
  search_interval: number
  last_search_time: string | null
  priority: string
  retry_count: number
  last_error: string | null
  next_search_time: string | null
  created_at: string
  updated_at: string
}

const router = useRouter()

const activeTab = ref<'keywords' | 'logs'>('keywords')

const { data, pending, error, refresh } = await useFetch('/api/keywords')
const keywords = computed(() => data.value?.keywords || [])

const { data: logsData, pending: logsPending, error: logsError, refresh: refreshLogs } = await useFetch('/api/logs', { lazy: true })
const logs = computed(() => logsData.value?.logs || [])

// 日志过滤
const logFilter = ref('')
const filteredLogs = computed(() => {
  if (!logFilter.value) return logs.value
  const kw = logFilter.value.toLowerCase()
  return logs.value.filter((l: any) => l.keyword?.toLowerCase().includes(kw))
})

// 展开日志详情
const expandedLogs = ref<Record<number, boolean>>({})
const logDetailCache = ref<Record<string, { loading: boolean; logs: any[] }>>({})

const toggleLogDetail = async (logId: number) => {
  expandedLogs.value[logId] = !expandedLogs.value[logId]
  const log = logs.value.find((l: any) => l.id === logId)
  if (!log || !log.execution_id) return

  const eid = log.execution_id
  if (logDetailCache.value[eid]) return

  logDetailCache.value[eid] = { loading: true, logs: [] }
  try {
    const res = await $fetch(`/api/logs/detail?execution_id=${eid}`)
    if (res.success) {
      logDetailCache.value[eid] = { loading: false, logs: res.logs || [] }
    }
  } catch {
    logDetailCache.value[eid] = { loading: false, logs: [] }
  }
}

// Toast
const toast = ref({ show: false, message: '', type: 'success' as 'success' | 'error' })

const showToast = (message: string, type: 'success' | 'error' = 'success') => {
  toast.value = { show: true, message, type }
  setTimeout(() => {
    toast.value.show = false
  }, 3000)
}

// 添加关键词
const showAddModal = ref(false)
const newKeyword = ref('')
const newAutoSearch = ref(false)
const newInterval = ref(1)
const adding = ref(false)

const intervalOptions = [
  { label: '6分钟', value: 0.1 },
  { label: '15分钟', value: 0.25 },
  { label: '30分钟', value: 0.5 },
  { label: '1小时', value: 1 },
  { label: '2小时', value: 2 },
  { label: '6小时', value: 6 },
  { label: '12小时', value: 12 },
  { label: '24小时', value: 24 },
]

const addKeyword = async () => {
  if (!newKeyword.value.trim()) return
  adding.value = true
  try {
    const res = await $fetch('/api/keywords', {
      method: 'POST',
      body: {
        keyword: newKeyword.value.trim(),
        auto_search: newAutoSearch.value,
        search_interval: newInterval.value
      }
    })
    if (res.success) {
      showToast('添加成功', 'success')
      showAddModal.value = false
      newKeyword.value = ''
      newAutoSearch.value = false
      newInterval.value = 1
      refresh()
    } else {
      showToast(res.error || '添加失败', 'error')
    }
  } catch (e: any) {
    showToast(e.message || '添加失败', 'error')
  }
  adding.value = false
}

// 切换自动搜索
const toggleAutoSearch = async (kw: Keyword) => {
  actionMenuOpen.value[kw.id] = false
  try {
    const res = await $fetch('/api/keywords', {
      method: 'PATCH',
      body: {
        keyword: kw.keyword,
        auto_search: !kw.auto_search,
        search_interval: kw.search_interval
      }
    })
    if (res.success) {
      showToast(kw.auto_search ? '已关闭自动搜索' : '已开启自动搜索', 'success')
      refresh()
    } else {
      showToast(res.error || '操作失败', 'error')
    }
  } catch (e: any) {
    showToast(e.message || '操作失败', 'error')
  }
}

// 手动触发搜索
const searchingKeywords = ref<string[]>([])

const triggerSearch = async (kw: Keyword) => {
  if (searchingKeywords.value.includes(kw.keyword)) return
  actionMenuOpen.value[kw.id] = false

  searchingKeywords.value.push(kw.keyword)
  try {
    const res = await $fetch('/api/search/realtime?action=start&keyword=' + encodeURIComponent(kw.keyword) + '&limit=2&upload=true')
    if (res.success) {
      showToast('搜索任务已启动', 'success')
      startTaskPolling()
      activeTab.value = 'logs'
      setTimeout(() => refresh(), 3000)
    } else {
      showToast(res.error || '触发失败', 'error')
    }
  } catch (e: any) {
    showToast(e.message || '触发失败', 'error')
  }
  setTimeout(() => {
    searchingKeywords.value = searchingKeywords.value.filter(k => k !== kw.keyword)
  }, 10000)
}

// 操作菜单
const actionMenuOpen = ref<Record<number, boolean>>({})

const openActionMenu = (kw: Keyword) => {
  actionMenuOpen.value = {}
  actionMenuOpen.value[kw.id] = !actionMenuOpen.value[kw.id]
}

const closeActionMenus = () => {
  actionMenuOpen.value = {}
}

// 格式化搜索间隔
const formatInterval = (hours: number) => {
  if (hours < 1) {
    const minutes = Math.round(hours * 60)
    return `${minutes} 分钟`
  } else if (hours === 1) {
    return '1 小时'
  } else {
    return `${hours} 小时`
  }
}

const formatTime = (time: string | null) => {
  if (!time) return ''
  const d = new Date(time)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  return `${Math.floor(diff / 86400000)} 天前`
}

const formatLogTime = (time: string) => {
  if (!time) return ''
  const d = new Date(time)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const dateStr = `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  return `${dateStr}`
}

const formatLogDetailTime = (time: string) => {
  if (!time) return ''
  const d = new Date(time)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
}

// 日志详情模态框
const logDetail = ref({
  show: false,
  loading: false,
  execution_id: '',
  summary: null as any,
  logs: [] as Array<{ id: number; execution_id: string; keyword: string; log_type: string; message: string; created_at: string }>
})

const showLogDetail = async (log: any) => {
  logDetail.value = {
    show: true,
    loading: true,
    execution_id: log.execution_id || '',
    summary: null,
    logs: []
  }
  if (!log.execution_id) {
    logDetail.value.execution_id = `legacy_${log.id}`
    logDetail.value.summary = {
      keyword: log.keyword,
      posts_found: log.posts_found,
      posts_inserted: log.posts_inserted,
      posts_skipped: log.posts_skipped,
      images_uploaded: log.images_uploaded,
      images_failed: log.images_failed,
      duration_seconds: log.duration_seconds,
      error_message: log.error_message
    }
    logDetail.value.loading = false
    return
  }
  try {
    const res = await $fetch(`/api/logs/detail?execution_id=${log.execution_id}`)
    if (res.success) {
      logDetail.value.summary = res.summary
      logDetail.value.logs = res.logs || []
    } else {
      showToast(res.error || '获取详情失败', 'error')
      logDetail.value.show = false
    }
  } catch (e: any) {
    showToast(e.message || '获取详情失败', 'error')
    logDetail.value.show = false
  }
  logDetail.value.loading = false
}

// 实时任务
interface SearchTask {
  id: string
  keyword: string
  limit: number
  status: 'running' | 'completed' | 'failed'
  logs: Array<{ time: string; message: string; type: 'info' | 'success' | 'error' }>
  startTime: Date
  endTime?: Date
  postsFound: number
  postsInserted: number
  imagesUploaded: number
  imagesFailed: number
}

const runningTasks = ref<SearchTask[]>([])
let taskPollTimer: NodeJS.Timeout | null = null

const pollTaskStatus = async () => {
  try {
    const res = await $fetch('/api/search/realtime?action=status')
    if (res.success && res.tasks) {
      runningTasks.value = res.tasks
    } else {
      runningTasks.value = []
    }
  } catch {
    runningTasks.value = []
  }
}

const startTaskPolling = () => {
  if (taskPollTimer) return
  pollTaskStatus()
  taskPollTimer = setInterval(pollTaskStatus, 2000)
}

const stopTaskPolling = () => {
  if (taskPollTimer) {
    clearInterval(taskPollTimer)
    taskPollTimer = null
  }
}

const formatTaskTime = (time: Date | string) => {
  const d = new Date(time)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
}

watch(activeTab, (newTab) => {
  if (newTab === 'logs') {
    startTaskPolling()
  } else {
    stopTaskPolling()
  }
})

onUnmounted(() => {
  stopTaskPolling()
})

onMounted(() => {
  document.addEventListener('click', closeActionMenus)
})
onUnmounted(() => {
  document.removeEventListener('click', closeActionMenus)
})
</script>

<style scoped>
button, a, input, select {
  cursor: pointer;
}
</style>
