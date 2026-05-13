<template>
  <div class="h-screen flex bg-gray-50">
    <Head>
      <meta name="referrer" content="no-referrer" />
    </Head>

    <!-- 左侧菜单 -->
    <aside class="w-56 bg-white border-r border-gray-200 flex flex-col flex-shrink-0">
      <div class="px-5 py-4 border-b border-gray-100">
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 bg-xhs-red rounded-lg flex items-center justify-center">
            <svg class="w-4.5 h-4.5 text-white" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
          </div>
          <div>
            <span class="text-sm font-bold text-gray-800">管理后台</span>
            <p class="text-[10px] text-gray-400">XHS Admin</p>
          </div>
        </div>
      </div>

      <nav class="flex-1 py-3 px-2.5 space-y-0.5 overflow-y-auto">
        <button
          v-for="item in menuItems"
          :key="item.key"
          @click="activeMenu = item.key"
          class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all"
          :class="activeMenu === item.key ? 'bg-xhs-red/5 text-xhs-red font-semibold' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-800'"
        >
          <component :is="item.icon" class="w-4.5 h-4.5 flex-shrink-0" />
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <div class="p-3 border-t border-gray-100">
        <button @click="$router.push('/')" class="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-gray-500 hover:bg-gray-50 hover:text-gray-700 transition-all">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 19l-7-7m0 0l7-7m-7 7h18"/>
          </svg>
          返回前台
        </button>
      </div>
    </aside>

    <!-- 右侧内容 -->
    <main class="flex-1 flex flex-col min-w-0">
      <header class="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between flex-shrink-0">
        <h1 class="text-lg font-bold text-gray-800">{{ currentMenuLabel }}</h1>
        <div class="flex items-center gap-3">
          <div class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium" :class="schedulerRunning ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'">
            <div class="w-2 h-2 rounded-full" :class="schedulerRunning ? 'bg-green-500 animate-pulse' : 'bg-red-500'"></div>
            {{ schedulerRunning ? '调度器运行中' : '调度器已停止' }}
          </div>
          <button v-if="!schedulerRunning" @click="startScheduler" class="px-3 py-1.5 bg-green-600 text-white rounded-lg text-xs hover:bg-green-700 transition">启动</button>
          <button v-else @click="stopScheduler" class="px-3 py-1.5 bg-red-600 text-white rounded-lg text-xs hover:bg-red-700 transition">停止</button>
        </div>
      </header>

      <div class="flex-1 overflow-y-auto p-6">
        <!-- 概览 -->
        <div v-if="activeMenu === 'dashboard'" class="space-y-6">
          <div class="grid grid-cols-5 gap-4">
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <div class="flex items-center justify-between mb-3">
                <span class="text-xs text-gray-400 font-medium">帖子总数</span>
                <div class="w-8 h-8 rounded-lg bg-blue-50 flex items-center justify-center">
                  <svg class="w-4 h-4 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/></svg>
                </div>
              </div>
              <p class="text-2xl font-bold text-gray-800">{{ formatNumber(stats.totalPosts) }}</p>
              <p class="text-xs text-gray-400 mt-1">今日新增 {{ formatNumber(stats.todayPosts) }}</p>
            </div>
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <div class="flex items-center justify-between mb-3">
                <span class="text-xs text-gray-400 font-medium">图片总数</span>
                <div class="w-8 h-8 rounded-lg bg-purple-50 flex items-center justify-center">
                  <svg class="w-4 h-4 text-purple-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
                </div>
              </div>
              <p class="text-2xl font-bold text-gray-800">{{ formatNumber(stats.totalImages) }}</p>
              <p class="text-xs text-gray-400 mt-1">已上传图床</p>
            </div>
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <div class="flex items-center justify-between mb-3">
                <span class="text-xs text-gray-400 font-medium">关键词数</span>
                <div class="w-8 h-8 rounded-lg bg-green-50 flex items-center justify-center">
                  <svg class="w-4 h-4 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"/></svg>
                </div>
              </div>
              <p class="text-2xl font-bold text-gray-800">{{ stats.totalKeywords }}</p>
              <p class="text-xs text-gray-400 mt-1">自动 {{ stats.autoKeywords }}</p>
            </div>
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <div class="flex items-center justify-between mb-3">
                <span class="text-xs text-gray-400 font-medium">今日搜索</span>
                <div class="w-8 h-8 rounded-lg bg-yellow-50 flex items-center justify-center">
                  <svg class="w-4 h-4 text-yellow-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
                </div>
              </div>
              <p class="text-2xl font-bold text-gray-800">{{ stats.recentLogs }}</p>
              <p class="text-xs text-gray-400 mt-1">最近 24 小时</p>
            </div>
            <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <div class="flex items-center justify-between mb-3">
                <span class="text-xs text-gray-400 font-medium">热门关键词</span>
                <div class="w-8 h-8 rounded-lg bg-red-50 flex items-center justify-center">
                  <svg class="w-4 h-4 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>
                </div>
              </div>
              <div class="flex flex-wrap gap-1.5 mt-2">
                <span v-for="kw in stats.topKeywords" :key="kw.keyword" class="text-[11px] px-2 py-0.5 bg-gray-100 rounded-full text-gray-600">{{ kw.keyword }} ({{ kw.count }})</span>
              </div>
            </div>
          </div>

          <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            <h3 class="text-sm font-semibold text-gray-800 mb-4">关键词数据量</h3>
            <div class="space-y-2.5">
              <div v-for="kw in keywordStats" :key="kw.keyword" class="flex items-center gap-3">
                <span class="text-xs text-gray-600 w-24 truncate">{{ kw.keyword }}</span>
                <div class="flex-1 h-5 bg-gray-100 rounded-full overflow-hidden">
                  <div class="h-full bg-gradient-to-r from-xhs-red/60 to-xhs-red rounded-full transition-all" :style="{ width: `${kw.percent}%` }"></div>
                </div>
                <span class="text-xs text-gray-500 w-12 text-right">{{ kw.count }}</span>
              </div>
              <p v-if="keywordStats.length === 0" class="text-xs text-gray-400 text-center py-4">暂无数据</p>
            </div>
          </div>
        </div>

        <!-- 实时搜索任务 -->
        <div v-if="activeMenu === 'dashboard' && runningTasks.length > 0" class="mt-6">
          <h3 class="text-sm font-semibold text-gray-800 mb-3">正在进行的搜索</h3>
          <div class="space-y-3">
            <div v-for="task in runningTasks" :key="task.id" class="bg-white rounded-xl shadow-sm border border-blue-100 overflow-hidden">
              <div class="px-4 py-2.5 bg-gradient-to-r from-blue-50 to-gray-50 flex items-center justify-between border-b border-blue-100">
                <div class="flex items-center gap-2">
                  <div class="animate-spin rounded-full h-4 w-4 border-2 border-blue-500 border-t-transparent"></div>
                  <span class="px-2.5 py-0.5 bg-xhs-red text-white rounded text-xs font-medium">{{ task.keyword }}</span>
                  <span class="text-xs text-gray-400">目标 {{ task.limit }} 条</span>
                </div>
                <span class="text-xs text-gray-400">{{ formatTaskTime(task.startTime) }}</span>
              </div>
              <div class="h-1.5 bg-gray-100">
                <div class="h-full bg-blue-500 transition-all duration-300 rounded-r" :style="{ width: `${Math.min(100, (task.postsInserted / Math.max(task.limit, 1)) * 100)}%` }"></div>
              </div>
              <div class="grid grid-cols-4 gap-2 px-4 py-2 bg-gray-50 text-center">
                <div><span class="text-sm font-bold text-gray-700">{{ task.postsFound }}</span><span class="text-[11px] text-gray-400 block">发现</span></div>
                <div><span class="text-sm font-bold text-green-600">{{ task.postsInserted }}</span><span class="text-[11px] text-gray-400 block">入库</span></div>
                <div><span class="text-sm font-bold text-blue-600">{{ task.imagesUploaded }}</span><span class="text-[11px] text-gray-400 block">上传</span></div>
                <div><span class="text-sm font-bold text-red-500">{{ task.imagesFailed }}</span><span class="text-[11px] text-gray-400 block">失败</span></div>
              </div>
              <div class="px-4 py-2 max-h-48 overflow-y-auto bg-gray-900 text-gray-100 font-mono text-xs">
                <div v-for="(log, i) in task.logs.slice(-30)" :key="i" class="py-0.5" :class="{ 'text-green-400': log.type === 'success', 'text-red-400': log.type === 'error' }">
                  <span class="text-gray-500">[{{ log.time }}]</span> {{ log.message }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 关键词管理 -->
        <div v-if="activeMenu === 'keywords'" class="space-y-5">
          <div class="flex items-center justify-between">
            <p class="text-sm text-gray-500">管理搜索关键词、自动搜索间隔和优先级</p>
            <button @click="openAddModal" class="px-4 py-2 bg-xhs-red text-white rounded-lg hover:bg-red-600 text-sm font-medium flex items-center gap-1.5 transition-all">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
              添加关键词
            </button>
          </div>

          <div v-if="keywordsPending" class="flex justify-center py-20">
            <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-xhs-red"></div>
          </div>
          <div v-else-if="keywords.length === 0" class="text-center py-20 text-gray-400">
            <svg class="w-16 h-16 mx-auto text-gray-300 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>
            <p class="mb-4">暂无搜索关键词</p>
            <button @click="openAddModal" class="px-4 py-2 bg-xhs-red text-white rounded-lg text-sm">添加第一个关键词</button>
          </div>
          <div v-else class="space-y-2">
            <div class="grid grid-cols-12 gap-4 px-4 py-2 text-xs text-gray-400 font-medium">
              <div class="col-span-2">关键词</div>
              <div class="col-span-2">状态</div>
              <div class="col-span-2">搜索间隔</div>
              <div class="col-span-1">优先级</div>
              <div class="col-span-2">上次搜索</div>
              <div class="col-span-1">重试</div>
              <div class="col-span-2 text-right">操作</div>
            </div>
            <div v-for="kw in keywords" :key="kw.id" class="grid grid-cols-12 gap-4 bg-white rounded-xl shadow-sm border border-gray-100 px-4 py-3 items-center hover:shadow-md transition-all">
              <div class="col-span-2 font-medium text-sm text-gray-800">{{ kw.keyword }}</div>
              <div class="col-span-2">
                <button @click="toggleAutoSearch(kw)" class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium transition-all cursor-pointer" :class="kw.auto_search ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'">
                  <div class="w-1.5 h-1.5 rounded-full" :class="kw.auto_search ? 'bg-green-500 animate-pulse' : 'bg-gray-400'"></div>
                  {{ kw.auto_search ? '自动' : '手动' }}
                </button>
              </div>
              <div class="col-span-2 text-xs text-gray-500">{{ formatInterval(kw.search_interval) }}</div>
              <div class="col-span-1">
                <span class="text-[11px] px-1.5 py-0.5 rounded-full" :class="{ 'bg-yellow-50 text-yellow-600': kw.priority === 'high', 'bg-green-50 text-green-600': kw.priority === 'normal', 'bg-gray-50 text-gray-500': kw.priority === 'low' }">
                  {{ kw.priority === 'high' ? '高' : kw.priority === 'low' ? '低' : '中' }}
                </span>
              </div>
              <div class="col-span-2 text-xs text-gray-400">{{ formatTime(kw.last_search_time) }}</div>
              <div class="col-span-1">
                <span v-if="kw.retry_count > 0" class="text-xs text-red-500 font-medium">{{ kw.retry_count }}</span>
                <span v-else class="text-xs text-gray-300">-</span>
              </div>
              <div class="col-span-2 flex items-center justify-end gap-1.5">
                <button @click="triggerSearch(kw)" :disabled="searchingKeywords.includes(kw.keyword)" class="px-2.5 py-1 text-xs text-xhs-red hover:bg-red-50 rounded-lg transition-all disabled:opacity-50">
                  {{ searchingKeywords.includes(kw.keyword) ? '搜索中...' : '立即搜索' }}
                </button>
                <button @click="openEditModal(kw)" class="px-2.5 py-1 text-xs text-gray-500 hover:bg-gray-50 rounded-lg transition-all">编辑</button>
                <button @click="confirmDelete(kw)" class="px-2.5 py-1 text-xs text-red-500 hover:bg-red-50 rounded-lg transition-all">删除</button>
              </div>
            </div>
          </div>
        </div>

        <!-- 日志 -->
        <div v-if="activeMenu === 'logs'" class="space-y-4">
          <div class="flex items-center gap-3">
            <div class="relative flex-1 max-w-xs">
              <input v-model="logFilter" type="text" placeholder="过滤关键词..." class="w-full pl-9 pr-3 py-2 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-xhs-red/30 focus:border-xhs-red" />
              <svg class="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
            </div>
            <button @click="refreshLogs()" class="px-3 py-2 text-sm text-xhs-red hover:bg-red-50 rounded-lg transition-all">刷新</button>
          </div>
          <div v-if="logsPending" class="flex justify-center py-20">
            <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-xhs-red"></div>
          </div>
          <div v-else-if="filteredLogs.length === 0" class="text-center py-16 text-gray-400"><p class="text-sm">暂无搜索日志</p></div>
          <div v-else class="space-y-2">
            <div v-for="log in filteredLogs" :key="log.id" class="bg-white rounded-xl shadow-sm border border-gray-100 px-4 py-3 hover:shadow-md transition-all">
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                  <span class="px-2.5 py-0.5 bg-xhs-red/10 text-xhs-red rounded-md text-xs font-semibold">{{ log.keyword }}</span>
                  <span v-if="log.error_message" class="px-2 py-0.5 bg-red-100 text-red-600 rounded-md text-[11px]">失败</span>
                  <span v-else class="px-2 py-0.5 bg-green-100 text-green-600 rounded-md text-[11px]">成功</span>
                </div>
                <span class="text-[11px] text-gray-400">{{ formatLogTime(log.created_at) }}</span>
              </div>
              <div class="flex items-center gap-4 mt-2">
                <span class="text-xs text-gray-500">发现 <strong class="text-gray-700">{{ log.posts_found }}</strong></span>
                <span class="text-xs text-green-600">入库 <strong>{{ log.posts_inserted }}</strong></span>
                <span class="text-xs text-blue-600">上传 <strong>{{ log.images_uploaded }}</strong></span>
                <span class="text-xs text-gray-400">耗时 <strong>{{ log.duration_seconds }}s</strong></span>
                <span v-if="log.posts_skipped" class="text-xs text-gray-400">跳过 {{ log.posts_skipped }}</span>
              </div>
              <div v-if="log.error_message" class="mt-2 text-xs text-red-500 bg-red-50 rounded px-2 py-1">{{ log.error_message }}</div>
              <button @click="toggleLogDetail(log.id, log.execution_id)" class="mt-1.5 text-xs text-xhs-red hover:text-red-600 flex items-center gap-1">
                <svg class="w-3.5 h-3.5 transition-transform" :class="expandedLogs[log.id] ? 'rotate-90' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                {{ expandedLogs[log.id] ? '收起' : '详情' }}
              </button>
              <div v-if="expandedLogs[log.id]" class="mt-2 border border-gray-100 rounded-lg overflow-hidden max-h-60 overflow-y-auto bg-gray-900 text-gray-100 font-mono text-xs px-3 py-2">
                <div v-if="logDetailCache[log.execution_id]?.loading" class="flex justify-center py-4">
                  <div class="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-xhs-red"></div>
                </div>
                <div v-else-if="logDetailCache[log.execution_id]?.logs?.length > 0">
                  <div v-for="(dl, i) in logDetailCache[log.execution_id].logs" :key="i" class="py-0.5" :class="{ 'text-green-400': dl.log_type === 'success', 'text-red-400': dl.log_type === 'error', 'text-blue-300': dl.log_type === 'info' }">
                    <span class="text-gray-500">[{{ formatLogDetailTime(dl.created_at) }}]</span> {{ dl.message }}
                  </div>
                </div>
                <div v-else class="text-center py-4 text-gray-400 text-xs">暂无详细日志</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 帖子管理 -->
        <div v-if="activeMenu === 'posts'" class="space-y-4">
          <div class="flex items-center gap-3">
            <div class="relative flex-1 max-w-xs">
              <input v-model="postSearch" type="text" placeholder="搜索帖子..." class="w-full pl-9 pr-3 py-2 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-xhs-red/30 focus:border-xhs-red" @keyup.enter="postPage = 1" />
              <svg class="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
            </div>
            <select v-model="postPageSize" class="px-3 py-2 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none" @change="postPage = 1">
              <option :value="10">10 条/页</option>
              <option :value="20">20 条/页</option>
              <option :value="50">50 条/页</option>
            </select>
          </div>
          <div v-if="postsPending" class="flex justify-center py-20">
            <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-xhs-red"></div>
          </div>
          <div v-else-if="adminPosts.length === 0" class="text-center py-20 text-gray-400"><p>暂无帖子数据</p></div>
          <div v-else>
            <table class="w-full bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
              <thead class="bg-gray-50 text-xs text-gray-400 font-medium">
                <tr>
                  <th class="text-left px-4 py-3">帖子</th>
                  <th class="text-left px-4 py-3">作者</th>
                  <th class="text-left px-4 py-3">关键词</th>
                  <th class="text-left px-4 py-3">互动</th>
                  <th class="text-left px-4 py-3">入库时间</th>
                  <th class="text-right px-4 py-3">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="post in adminPosts" :key="post.id" class="border-t border-gray-100 hover:bg-gray-50">
                  <td class="px-4 py-3">
                    <div class="flex items-center gap-2.5">
                      <img v-if="post.images && post.images.length" :src="post.images[0]" class="w-10 h-10 rounded-lg object-cover flex-shrink-0" loading="lazy" />
                      <div class="min-w-0">
                        <p class="text-sm text-gray-800 truncate max-w-[200px]">{{ post.title || '无标题' }}</p>
                        <p class="text-[11px] text-gray-400 truncate max-w-[200px]">{{ post.content?.slice(0, 30) }}</p>
                      </div>
                    </div>
                  </td>
                  <td class="px-4 py-3 text-xs text-gray-500">{{ post.author_name || '-' }}</td>
                  <td class="px-4 py-3"><span class="text-[11px] px-2 py-0.5 bg-gray-100 rounded-full text-gray-600">{{ post.keyword || '-' }}</span></td>
                  <td class="px-4 py-3 text-xs">
                    <span class="text-red-400">{{ formatNumber(post.likes) }}</span>
                    <span class="text-yellow-400 ml-2">{{ formatNumber(post.collects) }}</span>
                    <span class="text-gray-400 ml-2">{{ formatNumber(post.comments) }}</span>
                  </td>
                  <td class="px-4 py-3 text-xs text-gray-400">{{ post.created_at ? new Date(post.created_at).toLocaleString('zh-CN', { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '-' }}</td>
                  <td class="px-4 py-3 text-right">
                    <button @click="adminDeletePost(post)" class="text-xs text-red-500 hover:text-red-600 px-2 py-1 rounded-lg hover:bg-red-50 transition-all">删除</button>
                  </td>
                </tr>
              </tbody>
            </table>
            <div class="mt-4 flex items-center justify-between">
              <span class="text-xs text-gray-400">共 {{ postTotal }} 条，{{ postTotalPages }} 页</span>
              <div class="flex items-center gap-2">
                <button @click="postPage--; if(postPage<1)postPage=1" :disabled="postPage <= 1" class="px-3 py-1.5 text-xs bg-white border rounded-lg disabled:opacity-50 hover:bg-gray-50">上一页</button>
                <span class="px-3 py-1.5 text-xs text-gray-500">第 {{ postPage }} 页</span>
                <button @click="postPage++; if(postPage>postTotalPages)postPage=postTotalPages" :disabled="postPage >= postTotalPages" class="px-3 py-1.5 text-xs bg-white border rounded-lg disabled:opacity-50 hover:bg-gray-50">下一页</button>
              </div>
            </div>
          </div>
        </div>

        <!-- 调度器 -->
        <div v-if="activeMenu === 'scheduler'" class="space-y-5">
          <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h3 class="text-sm font-semibold text-gray-800 mb-4">调度器状态</h3>
            <div class="grid grid-cols-3 gap-6">
              <div>
                <p class="text-xs text-gray-400 mb-1">运行状态</p>
                <div class="flex items-center gap-2">
                  <div class="w-3 h-3 rounded-full" :class="schedulerRunning ? 'bg-green-500 animate-pulse' : 'bg-gray-400'"></div>
                  <span class="text-sm font-medium" :class="schedulerRunning ? 'text-green-700' : 'text-gray-500'">{{ schedulerRunning ? '运行中' : '已停止' }}</span>
                </div>
              </div>
              <div>
                <p class="text-xs text-gray-400 mb-1">当前时间</p>
                <p class="text-sm font-medium text-gray-800">{{ currentTime }}</p>
              </div>
              <div>
                <p class="text-xs text-gray-400 mb-1">高峰时段</p>
                <p class="text-sm text-gray-500">{{ schedulerConfig.peakHours || '12:00-14:00, 18:00-22:00' }}</p>
              </div>
            </div>
          </div>

          <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h3 class="text-sm font-semibold text-gray-800 mb-4">调度器配置</h3>
            <p class="text-xs text-gray-400 mb-4">调度器配置通过后端 Python 代码管理，修改后需重启调度器生效</p>
            <div class="grid grid-cols-2 gap-6 max-w-lg">
              <div>
                <label class="block text-xs text-gray-500 mb-1.5">高峰时段延迟倍数</label>
                <p class="text-sm text-gray-700 bg-gray-50 px-3 py-2 rounded-lg">{{ schedulerConfig.peakDelayMultiplier }}x</p>
                <p class="text-[11px] text-gray-400 mt-1">高峰时段等待时间 = 基础 × 此倍数</p>
              </div>
              <div>
                <label class="block text-xs text-gray-500 mb-1.5">最大重试次数</label>
                <p class="text-sm text-gray-700 bg-gray-50 px-3 py-2 rounded-lg">{{ schedulerConfig.maxRetries }}</p>
                <p class="text-[11px] text-gray-400 mt-1">超过此次数后任务将被降级</p>
              </div>
            </div>
          </div>
        </div>

        <!-- 系统配置 -->
        <div v-if="activeMenu === 'settings'" class="space-y-5">
          <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h3 class="text-sm font-semibold text-gray-800 mb-4">图床配置 (Lsky Pro)</h3>
            <div class="space-y-4 max-w-md">
              <div>
                <label class="block text-xs text-gray-500 mb-1.5">图床 API 地址</label>
                <input v-model="configForm.lskyUrl" type="text" placeholder="http://192.168.100.3:5021" class="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-xhs-red/30 focus:border-xhs-red" />
              </div>
              <div>
                <label class="block text-xs text-gray-500 mb-1.5">图床 Token</label>
                <input v-model="configForm.lskyToken" type="password" placeholder="输入 Token" class="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-xhs-red/30 focus:border-xhs-red" />
                <p class="text-[11px] text-gray-400 mt-1">用于上传图片到图床，可在图床后台获取</p>
              </div>
            </div>
          </div>

          <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h3 class="text-sm font-semibold text-gray-800 mb-4">数据库配置</h3>
            <div class="space-y-4 max-w-md">
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-xs text-gray-500 mb-1.5">数据库主机</label>
                  <input v-model="configForm.dbHost" type="text" class="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-xhs-red/30 focus:border-xhs-red" />
                </div>
                <div>
                  <label class="block text-xs text-gray-500 mb-1.5">端口</label>
                  <input v-model="configForm.dbPort" type="number" class="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-xhs-red/30 focus:border-xhs-red" />
                </div>
                <div>
                  <label class="block text-xs text-gray-500 mb-1.5">用户名</label>
                  <input v-model="configForm.dbUser" type="text" class="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-xhs-red/30 focus:border-xhs-red" />
                </div>
                <div>
                  <label class="block text-xs text-gray-500 mb-1.5">密码</label>
                  <input v-model="configForm.dbPassword" type="password" class="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-xhs-red/30 focus:border-xhs-red" />
                </div>
                <div>
                  <label class="block text-xs text-gray-500 mb-1.5">数据库名</label>
                  <input v-model="configForm.dbDatabase" type="text" class="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-xhs-red/30 focus:border-xhs-red" />
                </div>
              </div>
            </div>
          </div>

          <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
            <h3 class="text-sm font-semibold text-gray-800 mb-4">CDP 浏览器配置</h3>
            <div class="space-y-4 max-w-md">
              <div class="grid grid-cols-2 gap-4">
                <div>
                  <label class="block text-xs text-gray-500 mb-1.5">CDP 主机</label>
                  <input v-model="configForm.cdpHost" type="text" class="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-xhs-red/30 focus:border-xhs-red" />
                </div>
                <div>
                  <label class="block text-xs text-gray-500 mb-1.5">CDP 端口</label>
                  <input v-model="configForm.cdpPort" type="number" class="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-xhs-red/30 focus:border-xhs-red" />
                </div>
              </div>
            </div>
          </div>

          <div class="flex justify-end gap-3">
            <button @click="loadConfig" class="px-5 py-2.5 bg-white border border-gray-200 rounded-lg text-sm text-gray-600 hover:bg-gray-50 transition-all">重新读取</button>
            <button @click="saveConfig" :disabled="savingConfig" class="px-5 py-2.5 bg-xhs-red text-white rounded-lg text-sm hover:bg-red-600 transition-all disabled:opacity-50">
              {{ savingConfig ? '保存中...' : '保存配置' }}
            </button>
          </div>
          <p class="text-xs text-gray-400 text-center">配置会同时写入 .env 文件，重启服务后生效</p>
        </div>
      </div>
    </main>

    <!-- 添加/编辑关键词模态框 -->
    <div v-if="showAddModal" class="fixed inset-0 bg-black/50 z-[100] flex items-center justify-center" @click.self="closeModal">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-sm p-5">
        <h2 class="text-base font-bold text-gray-800 mb-4">{{ isEditing ? '编辑关键词' : '添加搜索关键词' }}</h2>
        <div class="space-y-3">
          <div>
            <label class="block text-sm text-gray-500 mb-1">关键词</label>
            <input v-model="editKeyword" type="text" placeholder="输入搜索关键词..." class="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-xhs-red/30 focus:border-xhs-red" />
          </div>
          <div>
            <label class="block text-sm text-gray-500 mb-1">优先级</label>
            <div class="flex gap-2">
              <button v-for="p in [{ label: '高', value: 'high' }, { label: '中', value: 'normal' }, { label: '低', value: 'low' }]" :key="p.value" @click="editPriority = p.value" class="flex-1 px-3 py-1.5 text-xs rounded-lg border transition-all" :class="editPriority === p.value ? 'bg-xhs-red text-white border-xhs-red' : 'bg-gray-50 text-gray-500 border-gray-200 hover:border-gray-300'">{{ p.label }}</button>
            </div>
          </div>
          <div class="flex items-center justify-between">
            <div>
              <div class="text-sm text-gray-700">启用自动搜索</div>
              <p class="text-[11px] text-gray-400">按设定间隔自动搜索</p>
            </div>
            <button @click="editAutoSearch = !editAutoSearch" :class="editAutoSearch ? 'bg-xhs-red' : 'bg-gray-300'" class="w-10 h-5 rounded-full transition relative">
              <div :class="editAutoSearch ? 'right-0.5' : 'left-0.5'" class="w-3.5 h-3.5 bg-white rounded-full absolute top-0.5 transition-all"></div>
            </button>
          </div>
          <div v-if="editAutoSearch">
            <label class="block text-sm text-gray-500 mb-1">搜索间隔</label>
            <div class="flex gap-1.5 flex-wrap">
              <button v-for="opt in intervalOptions" :key="opt.value" @click="editInterval = opt.value" class="px-2.5 py-1 text-xs rounded-lg border transition-all" :class="editInterval === opt.value ? 'bg-xhs-red text-white border-xhs-red' : 'bg-gray-50 text-gray-500 border-gray-200 hover:border-gray-300'">{{ opt.label }}</button>
            </div>
          </div>
        </div>
        <div class="flex justify-end gap-2 mt-4">
          <button @click="closeModal" class="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700 transition">取消</button>
          <button @click="saveKeyword" :disabled="!editKeyword.trim() || saving" class="px-3 py-1.5 bg-xhs-red text-white rounded-lg text-sm hover:bg-red-600 transition disabled:opacity-50">
            {{ saving ? '保存中...' : (isEditing ? '保存' : '添加') }}
          </button>
        </div>
      </div>
    </div>

    <!-- 删除确认 -->
    <div v-if="deleteTarget" class="fixed inset-0 bg-black/50 z-[100] flex items-center justify-center" @click.self="deleteTarget = null">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-sm p-5 text-center">
        <svg class="w-12 h-12 mx-auto text-red-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.542 0 2.282-1.284 1.636-2.286l-6.8-10.284c-.774-1.036-2.698-1.036-3.472 0l-6.8 10.284c-.646 1.002.094 2.286 1.636 2.286z"/></svg>
        <h2 class="text-base font-bold text-gray-800 mb-1">确认删除</h2>
        <p class="text-sm text-gray-500 mb-1">要删除关键词 "<strong class="text-gray-700">{{ deleteTarget.keyword }}</strong>" 吗？</p>
        <p class="text-xs text-red-500 mb-4">关联的搜索日志和执行日志也会被一并删除</p>
        <div class="flex justify-center gap-3">
          <button @click="deleteTarget = null" class="px-4 py-1.5 text-sm text-gray-500 hover:text-gray-700 bg-gray-100 rounded-lg transition">取消</button>
          <button @click="deleteKeyword" :disabled="deleting" class="px-4 py-1.5 bg-red-500 text-white rounded-lg text-sm hover:bg-red-600 transition disabled:opacity-50">{{ deleting ? '删除中...' : '确认删除' }}</button>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <div v-if="toast.show" class="fixed top-4 left-1/2 -translate-x-1/2 z-[200] px-4 py-2 rounded-lg shadow-lg text-sm" :class="toast.type === 'success' ? 'bg-green-500 text-white' : 'bg-red-500 text-white'">{{ toast.message }}</div>
  </div>
</template>

<script setup lang="ts">
import { LayoutDashboard, Tags, FileText, ImageIcon, Settings2, Timer } from 'lucide-vue-next'

const menuItems = [
  { key: 'dashboard', label: '概览', icon: LayoutDashboard },
  { key: 'keywords', label: '关键词', icon: Tags },
  { key: 'logs', label: '日志', icon: FileText },
  { key: 'posts', label: '帖子', icon: ImageIcon },
  { key: 'scheduler', label: '调度器', icon: Timer },
  { key: 'settings', label: '配置', icon: Settings2 },
]

const activeMenu = ref('dashboard')
const currentMenuLabel = computed(() => menuItems.find(m => m.key === activeMenu.value)?.label || '')

// ============ 调度器状态 ============
const schedulerRunning = ref(true)

const checkSchedulerStatus = async () => {
  try {
    const res = await $fetch('/api/scheduler/status')
    schedulerRunning.value = res.running ?? true
  } catch {
    schedulerRunning.value = false
  }
}

const startScheduler = async () => {
  try {
    const res = await $fetch('/api/scheduler/start', { method: 'POST' })
    if (res.success) { showToast('调度器已启动', 'success'); schedulerRunning.value = true }
    else { showToast(res.error || '启动失败', 'error') }
  } catch (e: any) { showToast(e.message || '启动失败', 'error') }
}

const stopScheduler = async () => {
  try {
    const res = await $fetch('/api/scheduler/stop', { method: 'POST' })
    if (res.success) { showToast('调度器已停止', 'success'); schedulerRunning.value = false }
    else { showToast(res.error || '停止失败', 'error') }
  } catch (e: any) { showToast(e.message || '停止失败', 'error') }
}

// ============ 统计 ============
interface AdminStats {
  totalPosts: number;
  totalImages: number;
  totalKeywords: number;
  autoKeywords: number;
  todayPosts: number;
  recentLogs: number;
  topKeywords: any[];
}

const stats = ref<AdminStats>({ totalPosts: 0, totalImages: 0, totalKeywords: 0, autoKeywords: 0, todayPosts: 0, recentLogs: 0, topKeywords: [] })

const fetchStats = async () => {
  try {
    const res = await $fetch('/api/admin/stats')
    if (res.success) stats.value = res.stats
  } catch {}
}

watch(activeMenu, (v) => { if (v === 'dashboard') fetchStats() })

const keywordStats = computed(() => {
  const max = Math.max(...stats.value.topKeywords.map(k => k.count), 1)
  return stats.value.topKeywords.map(k => ({ ...k, percent: (k.count / max) * 100 }))
})

// ============ 实时搜索任务 ============
interface SearchTask {
  id: string;
  keyword: string;
  limit: number;
  status: string;
  logs: Array<{ time: string; message: string; type: 'info' | 'success' | 'error' }>;
  startTime: string;
  postsFound: number;
  postsInserted: number;
  imagesUploaded: number;
  imagesFailed: number;
}

const runningTasks = ref<SearchTask[]>([])
let taskPollTimer: ReturnType<typeof setInterval> | null = null

const pollTasks = async () => {
  try {
    const res = await $fetch('/api/search/realtime?action=status')
    if (res.success && res.tasks) runningTasks.value = res.tasks
    else runningTasks.value = []
  } catch { runningTasks.value = [] }
}

onMounted(() => {
  pollTasks()
  taskPollTimer = setInterval(pollTasks, 2000)
  fetchStats()
  checkSchedulerStatus()
  currentTime.value = new Date().toLocaleString('zh-CN')
  setInterval(() => { currentTime.value = new Date().toLocaleString('zh-CN') }, 1000)
  loadConfig()
})

onUnmounted(() => {
  if (taskPollTimer) clearInterval(taskPollTimer)
})

const formatTaskTime = (time: string | Date) => {
  const d = new Date(time)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
}

// ============ 关键词 ============
interface Keyword {
  id: number;
  keyword: string;
  status: string;
  auto_search: boolean;
  search_interval: number;
  last_search_time: string | null;
  priority: string;
  retry_count: number;
  last_error: string | null;
  next_search_time: string | null;
  created_at: string;
  updated_at: string;
}

const { data: kwData, pending: keywordsPending, refresh: refreshKw } = await useFetch('/api/keywords')
const keywords = computed(() => kwData.value?.keywords || [])

const showAddModal = ref(false)
const isEditing = ref(false)
const editingId = ref<number | null>(null)
const editKeyword = ref('')
const editAutoSearch = ref(false)
const editInterval = ref(1)
const editPriority = ref('normal')
const saving = ref(false)

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

const openAddModal = () => {
  isEditing.value = false
  editingId.value = null
  editKeyword.value = ''
  editAutoSearch.value = false
  editInterval.value = 1
  editPriority.value = 'normal'
  showAddModal.value = true
}

const openEditModal = (kw: Keyword) => {
  isEditing.value = true
  editingId.value = kw.id
  editKeyword.value = kw.keyword
  editAutoSearch.value = kw.auto_search
  editInterval.value = kw.search_interval
  editPriority.value = kw.priority || 'normal'
  showAddModal.value = true
}

const closeModal = () => { showAddModal.value = false; isEditing.value = false }

const saveKeyword = async () => {
  if (!editKeyword.value.trim()) return
  saving.value = true
  try {
    if (isEditing.value) {
      const res = await $fetch('/api/keywords', {
        method: 'PATCH',
        body: { keyword: editKeyword.value.trim(), auto_search: editAutoSearch.value, search_interval: editInterval.value }
      })
      if (res.success) { showToast('已更新', 'success'); closeModal(); refreshKw() }
      else { showToast(res.error || '更新失败', 'error') }
    } else {
      const res = await $fetch('/api/keywords', {
        method: 'POST',
        body: { keyword: editKeyword.value.trim(), auto_search: editAutoSearch.value, search_interval: editInterval.value }
      })
      if (res.success) { showToast('添加成功', 'success'); closeModal(); refreshKw() }
      else { showToast(res.error || '添加失败', 'error') }
    }
  } catch (e: any) { showToast(e.message || '操作失败', 'error') }
  saving.value = false
}

const deleteTarget = ref<Keyword | null>(null)
const deleting = ref(false)
const confirmDelete = (kw: Keyword) => { deleteTarget.value = kw }

const deleteKeyword = async () => {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    const res = await $fetch('/api/keywords', { method: 'DELETE', body: { keyword: deleteTarget.value.keyword } })
    if (res.success) { showToast('已删除', 'success'); deleteTarget.value = null; refreshKw() }
    else { showToast(res.error || '删除失败', 'error') }
  } catch (e: any) { showToast(e.message || '删除失败', 'error') }
  deleting.value = false
}

const toggleAutoSearch = async (kw: Keyword) => {
  try {
    const res = await $fetch('/api/keywords', {
      method: 'PATCH',
      body: { keyword: kw.keyword, auto_search: !kw.auto_search, search_interval: kw.search_interval }
    })
    if (res.success) { showToast(kw.auto_search ? '已关闭自动搜索' : '已开启自动搜索', 'success'); refreshKw() }
    else { showToast(res.error || '操作失败', 'error') }
  } catch (e: any) { showToast(e.message || '操作失败', 'error') }
}

const searchingKeywords = ref<string[]>([])
const triggerSearch = async (kw: Keyword) => {
  if (searchingKeywords.value.includes(kw.keyword)) return
  searchingKeywords.value.push(kw.keyword)
  try {
    const res = await $fetch('/api/search/realtime?action=start&keyword=' + encodeURIComponent(kw.keyword) + '&limit=2&upload=true')
    if (res.success) { showToast('搜索任务已启动', 'success'); pollTasks() }
    else { showToast(res.error || '触发失败', 'error') }
  } catch (e: any) { showToast(e.message || '触发失败', 'error') }
  setTimeout(() => { searchingKeywords.value = searchingKeywords.value.filter(k => k !== kw.keyword) }, 10000)
}

// ============ 日志 ============
const { data: logsData, pending: logsPending, refresh: refreshLogs } = await useFetch('/api/logs', { lazy: true })
const logs = computed(() => logsData.value?.logs || [])
const logFilter = ref('')
const filteredLogs = computed(() => {
  if (!logFilter.value) return logs.value
  const kw = logFilter.value.toLowerCase()
  return logs.value.filter((l: any) => l.keyword?.toLowerCase().includes(kw))
})
const expandedLogs = ref<Record<number, boolean>>({})
const logDetailCache = ref<Record<string, { loading: boolean; logs: any[] }>>({})

const toggleLogDetail = async (logId: number, executionId?: string) => {
  expandedLogs.value[logId] = !expandedLogs.value[logId]
  if (!executionId) return
  if (logDetailCache.value[executionId]) return
  logDetailCache.value[executionId] = { loading: true, logs: [] }
  try {
    const res = await $fetch(`/api/logs/detail?execution_id=${executionId}`)
    if (res.success) logDetailCache.value[executionId] = { loading: false, logs: res.logs || [] }
  } catch { logDetailCache.value[executionId] = { loading: false, logs: [] } }
}

// ============ 帖子 ============
const postPage = ref(1)
const postPageSize = ref(20)
const postSearch = ref('')

const { data: postData, pending: postsPending } = await useFetch('/api/posts', {
  query: { page: postPage, pageSize: postPageSize, keyword: postSearch },
  watch: [postPage, postPageSize, postSearch]
})
const adminPosts = computed(() => postData.value?.posts || [])
const postTotal = computed(() => postData.value?.total || 0)
const postTotalPages = computed(() => Math.ceil(postTotal.value / postPageSize.value))

const adminDeletePost = async (post: any) => {
  try {
    const res = await $fetch('/api/posts/delete', { method: 'POST', body: { id: post.id } })
    if (res.success) { showToast('帖子已删除', 'success'); refreshKw() }
    else { showToast(res.error || '删除失败', 'error') }
  } catch (e: any) { showToast(e.message || '删除失败', 'error') }
}

// ============ 系统配置 ============
const currentTime = ref('')
const schedulerConfig = ref({
  peakDelayMultiplier: 2.5,
  maxRetries: 3,
  peakHours: '12:00-14:00, 18:00-22:00'
})

const configForm = ref({
  lskyUrl: '',
  lskyToken: '',
  dbHost: '',
  dbPort: '',
  dbUser: '',
  dbPassword: '',
  dbDatabase: '',
  cdpHost: '',
  cdpPort: ''
})

const savingConfig = ref(false)

const loadConfig = async () => {
  try {
    const res = await $fetch('/api/admin/config')
    if (res.success) {
      configForm.value = {
        lskyUrl: res.config.lskyProUrl || '',
        lskyToken: res.config.lskyProToken || '',
        dbHost: res.config.dbHost || '',
        dbPort: res.config.dbPort || '',
        dbUser: res.config.dbUser || '',
        dbPassword: res.config.dbPassword || '',
        dbDatabase: res.config.dbDatabase || '',
        cdpHost: res.config.cdpHost || '',
        cdpPort: res.config.cdpPort || ''
      }
    }
  } catch {}
}

const saveConfig = async () => {
  savingConfig.value = true
  try {
    const res = await $fetch('/api/admin/config', {
      method: 'POST',
      body: configForm.value
    })
    if (res.success) { showToast('配置已保存到 .env 文件', 'success'); loadConfig() }
    else { showToast(res.error || '保存失败', 'error') }
  } catch (e: any) { showToast(e.message || '保存失败', 'error') }
  savingConfig.value = false
}

// ============ 工具 ============
const toast = ref({ show: false, message: '', type: 'success' as 'success' | 'error' })
const showToast = (message: string, type: 'success' | 'error' = 'success') => {
  toast.value = { show: true, message, type }
  setTimeout(() => { toast.value.show = false }, 3000)
}

const formatNumber = (num: number): string => {
  if (num >= 10000) return (num / 10000).toFixed(1) + 'w'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'k'
  return num.toString()
}

const formatInterval = (hours: number) => {
  if (hours < 1) return `${Math.round(hours * 60)} 分钟`
  if (hours === 1) return '1 小时'
  return `${hours} 小时`
}

const formatTime = (time: string | null) => {
  if (!time) return ''
  const d = new Date(time)
  const diff = new Date().getTime() - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  return `${Math.floor(diff / 86400000)} 天前`
}

const formatLogTime = (time: string) => {
  if (!time) return ''
  const d = new Date(time)
  const diff = new Date().getTime() - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
}

const formatLogDetailTime = (time: string) => {
  if (!time) return ''
  const d = new Date(time)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
}
</script>
