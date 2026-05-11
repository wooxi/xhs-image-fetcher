// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

  modules: ['@nuxtjs/tailwindcss'],

  tailwindcss: {
    cssPath: '~/assets/css/tailwind.css',
    configPath: 'tailwind.config.js'
  },

  nitro: {
    runtimeConfig: {
      // 所有配置从环境变量读取，不硬编码默认值
      dbHost: process.env.DB_HOST,
      dbPort: process.env.DB_PORT,
      dbUser: process.env.DB_USER,
      dbPassword: process.env.DB_PASSWORD,
      dbDatabase: process.env.DB_DATABASE,
      lskyProUrl: process.env.LSKY_PRO_URL,
      lskyProToken: process.env.LSKY_PRO_TOKEN
    }
  },

  devServer: {
    port: 5020,
    host: '0.0.0.0'
  }
})