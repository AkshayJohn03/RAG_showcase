// Nuxt 3 + Nuxt UI — senior RAG dashboard
export default defineNuxtConfig({
  compatibilityDate: '2024-08-01',
  devtools: { enabled: false },
  modules: ['@nuxt/ui'],
  runtimeConfig: {
    // Same-origin '/api' by default (Nitro proxies to the backend, so the
    // dashboard works on any host). Override only for split hosting.
    public: { apiBase: process.env.NUXT_PUBLIC_API_BASE || '/api' }
  },
  app: {
    head: {
      title: 'Meridian RAG — Retrieval Console',
      meta: [
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'description', content: 'Production-grade RAG console: hybrid retrieval, rerank inspection, eval.' }
      ]
    }
  },
  nitro: {
    routeRules: {
      '/api/**': { proxy: { to: 'http://localhost:8000/**' } }
    }
  }
})
