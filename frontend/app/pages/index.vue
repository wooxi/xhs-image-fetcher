<template>
  <div class="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
    <!-- 防盗链：设置 meta referrer -->
    <Head>
      <meta name="referrer" content="no-referrer" />
    </Head>

    <!-- 顶部搜索栏 -->
    <header class="sticky top-0 bg-white/95 backdrop-blur-sm shadow-sm z-50 border-b border-gray-100">
      <div class="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 bg-xhs-red rounded-lg flex items-center justify-center">
            <svg class="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
            </svg>
          </div>
          <h1 class="text-xl font-bold text-gray-900 tracking-tight">摄影灵感库</h1>
        </div>
        <div class="flex items-center gap-4">
          <div class="relative">
            <input
              v-model="searchKeyword"
              type="text"
              placeholder="搜索关键词..."
              class="pl-10 pr-4 py-2.5 w-64 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-xhs-red/30 focus:border-xhs-red transition-all"
              @keyup.enter="searchPosts"
            />
            <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
            </svg>
          </div>
          <button
            @click="searchPosts"
            class="px-5 py-2.5 bg-xhs-red text-white rounded-xl hover:bg-red-600 transition-all shadow-sm hover:shadow-md flex items-center gap-2"
          >
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
            </svg>
            搜索
          </button>
          <!-- 设置入口 -->
          <button
            @click="$router.push('/settings')"
            class="flex items-center gap-2 px-4 py-2.5 text-gray-600 hover:text-xhs-red hover:bg-gray-50 rounded-xl transition-all"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
            </svg>
            <span class="hidden sm:inline font-medium">设置</span>
          </button>
        </div>
      </div>
    </header>

    <!-- 瀑布流内容 -->
    <main class="max-w-7xl mx-auto px-4 py-6">
      <!-- 加载状态 - 骨架屏 -->
      <div v-if="pending" class="columns-1 sm:columns-1 md:columns-2 lg:columns-3 xl:columns-4 gap-4 space-y-4">
        <div v-for="i in 12" :key="i" class="bg-white rounded-xl shadow-sm overflow-hidden break-inside-avoid">
          <!-- 骨架图片 -->
          <div class="w-full h-48 bg-gradient-to-r from-gray-100 via-gray-200 to-gray-100 animate-pulse rounded-xl"></div>
          <!-- 骨架文本 -->
          <div class="p-4 space-y-3">
            <div class="h-4 bg-gray-100 rounded animate-pulse w-3/4"></div>
            <div class="h-3 bg-gray-100 rounded animate-pulse w-1/2"></div>
            <div class="flex justify-between">
              <div class="h-3 bg-gray-100 rounded animate-pulse w-1/4"></div>
              <div class="h-3 bg-gray-100 rounded animate-pulse w-1/3"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 错误状态 -->
      <div v-else-if="error" class="text-center py-20 text-gray-500">
        加载失败，请刷新页面重试
      </div>

      <!-- 内容展示 -->
      <div v-else class="columns-1 sm:columns-1 md:columns-2 lg:columns-3 xl:columns-4 gap-4 space-y-4">
        <div
          v-for="post in posts"
          :key="post.id"
          class="masonry-card bg-white rounded-xl shadow-sm overflow-hidden hover:shadow-lg transition-all duration-300 cursor-pointer group break-inside-avoid"
          @click="openPostModal(post)"
        >
          <!-- 主图 -->
          <div class="relative overflow-hidden">
            <img
              v-if="post.images && post.images.length > 0"
              :src="post.images[0]"
              :alt="post.title"
              class="w-full h-auto object-cover transform group-hover:scale-105 transition-transform duration-500"
              loading="lazy"
            />
            <!-- 多图指示器 - 更精美 -->
            <div
              v-if="post.images && post.images.length > 1"
              class="absolute top-3 right-3 bg-white/90 backdrop-blur-sm text-gray-800 px-2.5 py-1 rounded-full text-xs font-medium shadow-sm flex items-center gap-1"
            >
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/>
              </svg>
              {{ post.images.length }}
            </div>
            <!-- 无图占位 - 更精美 -->
            <div
              v-else
              class="w-full h-48 bg-gradient-to-br from-gray-100 to-gray-200 flex items-center justify-center"
            >
              <svg class="w-12 h-12 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"/>
              </svg>
            </div>
          </div>

          <!-- 卡片信息 - 更精美 -->
          <div class="p-4">
            <!-- 标题 -->
            <h3 class="text-sm font-semibold text-gray-800 line-clamp-2 leading-snug mb-3 group-hover:text-xhs-red transition-colors">
              {{ post.title }}
            </h3>

            <!-- 作者信息 -->
            <div class="flex items-center gap-2 mb-3">
              <div class="w-5 h-5 bg-gray-200 rounded-full flex items-center justify-center">
                <svg class="w-3 h-3 text-gray-400" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z"/>
                </svg>
              </div>
              <span class="text-xs text-gray-500">{{ post.author_name }}</span>
            </div>

            <!-- 互动数据 -->
            <div class="flex items-center justify-between text-xs text-gray-400">
              <div class="flex items-center gap-3">
                <!-- 点赞 -->
                <span class="flex items-center gap-1 hover:text-red-500 transition-colors">
                  <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
                  </svg>
                  {{ formatNumber(post.likes) }}
                </span>
                <!-- 收藏 -->
                <span class="flex items-center gap-1 hover:text-yellow-500 transition-colors">
                  <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M17 3H7c-1.1 0-2 .9-2 2v16l7-3 7 3V5c0-1.1-.9-2-2-2z"/>
                  </svg>
                  {{ formatNumber(post.collects) }}
                </span>
              </div>
              <!-- 评论 -->
              <span class="flex items-center gap-1">
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M21 6h-2v9H6v2c0 .55.45 1 1 1h11l4 4V7c0-.55-.45-1-1-1zm-4 6V3c0-.55-.45-1-1-1H3c-.55 0-1 .45-1 1v14l4-4h10c.55 0 1-.45 1-1z"/>
                </svg>
                {{ formatNumber(post.comments) }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div v-if="!pending && !error && total > pageSize" class="mt-8 flex justify-center gap-4">
        <button 
          @click="prevPage"
          :disabled="page <= 1"
          class="px-4 py-2 bg-white border rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 transition"
        >
          上一页
        </button>
        <span class="px-4 py-2 text-gray-600">
          第 {{ page }} 页 / 共 {{ Math.ceil(total / pageSize) }} 页
        </span>
        <button 
          @click="nextPage"
          :disabled="page >= Math.ceil(total / pageSize)"
          class="px-4 py-2 bg-white border rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50 transition"
        >
          下一页
        </button>
      </div>

      <!-- 无数据提示 -->
      <div v-if="!pending && !error && posts.length === 0" class="text-center py-20 text-gray-500">
        暂无数据
      </div>
    </main>

    <!-- 帖子详情模态框 - 全屏图片模式 -->
    <div 
      v-if="selectedPost"
      class="fixed inset-0 bg-black z-[9999] flex items-center justify-center"
      @click.self="closePostModal"
    >
      <!-- 悬浮关闭按钮 - 固定在右上角安全位置 -->
      <button 
        @click="closePostModal"
        class="fixed top-4 right-4 z-[10000] bg-white/90 hover:bg-white w-12 h-12 rounded-full flex items-center justify-center shadow-lg text-gray-600 hover:text-gray-800 transition-all"
        aria-label="关闭"
      >
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
      
      <!-- 详情切换按钮 - 固定在左下角 -->
      <button 
        @click="showDetails = !showDetails"
        class="fixed bottom-4 left-4 z-[10000] bg-white/90 hover:bg-white w-12 h-12 rounded-full flex items-center justify-center shadow-lg text-gray-600 hover:text-gray-800 transition-all"
        aria-label="显示详情"
      >
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
        </svg>
      </button>
      
      <!-- 图片容器 - 全屏 -->
      <div 
        class="absolute inset-0 flex items-center justify-center"
        @touchstart="handleTouchStart"
        @touchmove="handleTouchMove"
        @touchend="handleTouchEnd"
      >
        <!-- 当前图片 -->
        <img 
          v-if="selectedPost.images && selectedPost.images.length > 0"
          :src="currentImage"
          :alt="selectedPost.title"
          class="w-full h-full object-contain transition-transform duration-200"
          :style="{ transform: `translateX(${touchOffset}px)` }"
        />
        <span v-else class="text-gray-400 text-xl">暂无图片</span>
      
        <!-- 图片切换按钮 - 仅桌面端显示 -->
        <button 
          v-if="selectedPost.images && selectedPost.images.length > 1"
          @click="prevImage"
          :disabled="currentImageIndex === 0"
          class="hidden sm:flex absolute left-2 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white w-10 h-10 rounded-full items-center justify-center shadow-md disabled:opacity-30"
        >
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
          </svg>
        </button>
        <button 
          v-if="selectedPost.images && selectedPost.images.length > 1"
          @click="nextImage"
          :disabled="currentImageIndex >= selectedPost.images.length - 1"
          class="hidden sm:flex absolute right-2 top-1/2 -translate-y-1/2 bg-white/80 hover:bg-white w-10 h-10 rounded-full items-center justify-center shadow-md disabled:opacity-30"
        >
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
          </svg>
        </button>
      
        <!-- 图片索引指示 - 顶部 -->
        <div 
          v-if="selectedPost.images && selectedPost.images.length > 1"
          class="fixed top-4 left-1/2 -translate-x-1/2 bg-black/60 text-white px-3 py-1 rounded-full text-sm z-[10001]"
        >
          {{ currentImageIndex + 1 }} / {{ selectedPost.images.length }}
        </div>
      
        <!-- 手机端滑动提示 -->
        <div 
          v-if="selectedPost.images && selectedPost.images.length > 1 && showSwipeHint"
          class="fixed bottom-4 left-1/2 -translate-x-1/2 bg-black/40 text-white px-3 py-1 rounded-full text-xs animate-pulse z-[10001]"
        >
          ← 左右滑动切换 →
        </div>
      </div>
    
      <!-- 图片缩略图列表 - 底部悬浮 -->
      <div 
        v-if="selectedPost.images && selectedPost.images.length > 1"
        class="fixed bottom-16 left-1/2 -translate-x-1/2 flex gap-2 px-4 py-2 bg-black/50 rounded-lg z-[10001] max-w-[90vw] overflow-x-auto"
      >
        <img 
          v-for="(img, idx) in selectedPost.images"
          :key="idx"
          :src="img"
          :alt="`图片 ${idx + 1}`"
          class="w-12 h-12 object-cover rounded cursor-pointer border-2 transition-all"
          :class="idx === currentImageIndex ? 'border-xhs-red' : 'border-transparent hover:border-white/50'"
          @click="currentImageIndex = idx"
        />
      </div>
    
      <!-- 帖子详情 - 右侧悬浮面板，点击显示 -->
      <div 
        v-if="showDetails"
        class="fixed right-0 top-0 bottom-0 w-80 bg-white/95 shadow-xl z-[10002] overflow-y-auto"
      >
        <div class="p-4">
          <!-- 标题 -->
          <h2 class="text-lg font-bold text-gray-800 mb-4">
            {{ selectedPost.title }}
          </h2>
        
          <!-- 作者和互动数据 -->
          <div class="flex items-center justify-between text-sm text-gray-600 mb-4">
            <span class="flex items-center gap-2">
              <svg class="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z"/>
              </svg>
              {{ selectedPost.author_name }}
            </span>
          </div>
        
          <!-- 互动数据 -->
          <div class="flex items-center gap-4 text-sm mb-4">
            <span class="flex items-center gap-1">
              <svg class="w-4 h-4 text-red-500" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/>
              </svg>
              {{ formatNumber(selectedPost.likes) }}
            </span>
            <span class="flex items-center gap-1">
              <svg class="w-4 h-4 text-yellow-500" viewBox="0 0 24 24" fill="currentColor">
                <path d="M17 3H7c-1.1 0-2 .9-2 2v16l7-3 7 3V5c0-1.1-.9-2-2-2z"/>
              </svg>
              {{ formatNumber(selectedPost.collects) }}
            </span>
            <span class="flex items-center gap-1">
              <svg class="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                <path d="M21 6h-2v9H6v2c0 .55.45 1 1 1h11l4 4V7c0-.55-.45-1-1-1zm-4 6V3c0-.55-.45-1-1-1H3c-.55 0-1 .45-1 1v14l4-4h10c.55 0 1-.45 1-1z"/>
              </svg>
              {{ formatNumber(selectedPost.comments) }}
            </span>
          </div>
        
          <!-- 内容摘要 -->
          <p 
            v-if="selectedPost.content"
            class="text-gray-700 text-sm leading-relaxed mb-4"
          >
            {{ selectedPost.content }}
          </p>
        
          <!-- 查看原文按钮 -->
          <a 
            :href="selectedPost.url" 
            target="blank"
            class="inline-block px-4 py-2 bg-xhs-red text-white rounded-lg hover:bg-red-600 transition text-sm"
          >
            查看小红书原文 ↗
          </a>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
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

const searchKeyword = ref('')
const page = ref(1)
const pageSize = ref(20)

// 模态框状态
const selectedPost = ref<Post | null>(null)
const currentImageIndex = ref(0)

// 记住每个帖子上次浏览的图片索引
const lastImageIndex = ref<Record<number, number>>({})

// 详情显示状态
const showDetails = ref(false)

// 触摸滑动状态
const touchStartX = ref(0)
const touchOffset = ref(0)
const showSwipeHint = ref(true)
const SWIPE_THRESHOLD = 50 // 滑动阈值(px)

// 计算当前显示的图片
const currentImage = computed(() => {
  if (selectedPost.value && selectedPost.value.images && selectedPost.value.images.length > 0) {
    return selectedPost.value.images[currentImageIndex.value]
  }
  return ''
})

// 使用 useFetch 获取数据（SSR）
const { data, pending, error, refresh } = await useFetch('/api/posts', {
  query: {
    page,
    pageSize,
    keyword: searchKeyword
  },
  watch: [page]
})

const posts = computed(() => data.value?.posts || [])
const total = computed(() => data.value?.total || 0)

// 格式化数字
const formatNumber = (num: number): string => {
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + 'w'
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'k'
  }
  return num.toString()
}

// 搜索
const searchPosts = () => {
  page.value = 1
  refresh()
}

// 分页
const prevPage = () => {
  if (page.value > 1) {
    page.value--
  }
}

const nextPage = () => {
  const maxPage = Math.ceil(total.value / pageSize.value)
  if (page.value < maxPage) {
    page.value++
  }
}

// 模态框操作
const openPostModal = (post: Post) => {
  selectedPost.value = post
  // 使用存储的索引或默认 0
  currentImageIndex.value = lastImageIndex.value[post.id] || 0
}

const closePostModal = () => {
  // 保存当前浏览位置
  if (selectedPost.value) {
    lastImageIndex.value[selectedPost.value.id] = currentImageIndex.value
  }
  selectedPost.value = null
  showDetails.value = false // 关闭时隐藏详情
}

const prevImage = () => {
  if (currentImageIndex.value > 0) {
    currentImageIndex.value--
  }
}

const nextImage = () => {
  if (selectedPost.value && selectedPost.value.images && currentImageIndex.value < selectedPost.value.images.length - 1) {
    currentImageIndex.value++
  }
}

// 触摸滑动处理
const handleTouchStart = (e: TouchEvent) => {
  touchStartX.value = e.touches[0].clientX
  touchOffset.value = 0
}

const handleTouchMove = (e: TouchEvent) => {
  const currentX = e.touches[0].clientX
  const diff = currentX - touchStartX.value
  // 限制滑动范围，防止过度偏移
  touchOffset.value = Math.max(-100, Math.min(100, diff))
}

const handleTouchEnd = () => {
  // 滑动超过阈值则切换图片
  if (touchOffset.value > SWIPE_THRESHOLD) {
    // 右滑 -> 上一张
    prevImage()
    showSwipeHint.value = false
  } else if (touchOffset.value < -SWIPE_THRESHOLD) {
    // 左滑 -> 下一张
    nextImage()
    showSwipeHint.value = false
  }
  // 重置偏移
  touchOffset.value = 0
}

// ESC 关闭模态框
const handleEsc = (e: KeyboardEvent) => {
  if (e.key === 'Escape' && selectedPost.value) {
    closePostModal()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleEsc)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleEsc)
})

</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>