<template>
  <div>
    <!-- Top bar: solid ink, no gradients, clear hierarchy -->
    <header class="bg-[#1C1917] text-stone-100">
      <div class="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-5 py-4">
        <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-[#FAF7F1] font-display text-xl font-semibold text-[#1C1917]" aria-hidden="true">M</div>
        <div class="mr-auto">
          <p class="text-xs font-medium uppercase tracking-[0.14em] text-stone-400">Meridian Industrial · Internal</p>
          <h1 class="font-display text-xl font-semibold leading-tight">RAG Retrieval Console</h1>
        </div>
        <div class="flex items-center gap-2 text-sm">
          <span class="inline-flex items-center gap-2 rounded-full border border-stone-700 px-3 py-1.5">
            <span class="h-2 w-2 rounded-full" :class="health?.status === 'ok' ? 'bg-emerald-400' : 'bg-red-400'" aria-hidden="true" />
            {{ health ? `${health.chunks_indexed} chunks · ${health.llm}` : 'connecting…' }}
          </span>
          <UButton color="amber" variant="solid" size="md" class="!min-h-[44px]" @click="runEval" :loading="evalLoading">Run eval</UButton>
        </div>
      </div>
    </header>

    <main class="mx-auto grid max-w-6xl gap-5 px-5 py-6 lg:grid-cols-[1fr_380px]">
      <!-- Chat column -->
      <section aria-label="Chat" class="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-[0_1px_2px_rgba(28,25,23,0.06)]">
        <div class="border-b border-stone-200 px-5 py-4">
          <h2 class="font-display text-lg font-semibold">Ask the corpus</h2>
          <p class="mt-0.5 text-sm text-stone-500">Grounded answers with citations. Try the multi-hop supplier question.</p>
          <div class="mt-3 flex flex-wrap gap-2">
            <button v-for="s in samples" :key="s" @click="ask(s)"
              class="min-h-[44px] rounded-full border border-stone-300 bg-[#FAF7F1] px-4 text-sm font-medium hover:border-[#1F3D2B] hover:text-[#1F3D2B]">
              {{ s }}
            </button>
          </div>
        </div>

        <div ref="scrollBox" class="max-h-[46vh] space-y-4 overflow-y-auto px-5 py-4" role="log" aria-live="polite">
          <div v-if="!messages.length" class="rounded-xl border border-dashed border-stone-300 bg-[#FAF7F1] p-5 text-sm text-stone-600">
            <p class="font-medium text-stone-800">Start with one of these senior-level probes:</p>
            <ul class="mt-2 list-disc space-y-1 pl-5">
              <li><strong>Multi-hop:</strong> Which supplier provides the component used in Product X?</li>
              <li><strong>Exact code (BM25):</strong> What does SAF-114 require?</li>
              <li><strong>Table:</strong> Which units failed and what revision were they?</li>
            </ul>
          </div>
          <article v-for="(m, i) in messages" :key="i" :class="m.role === 'user' ? 'ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-[#1F3D2B] px-4 py-3 text-[15px] text-white' : 'max-w-[95%] rounded-2xl rounded-bl-sm border border-stone-200 bg-white px-4 py-3 shadow-sm'">
            <p v-if="m.role === 'user'" class="whitespace-pre-wrap">{{ m.text }}</p>
            <div v-else>
              <div class="mb-1 flex flex-wrap items-center gap-2 text-xs text-stone-500">
                <span class="rounded-full bg-stone-100 px-2 py-0.5 font-medium">{{ m.model || 'rag' }}</span>
                <span v-if="m.ms">· {{ m.ms }} ms</span>
                <span v-if="m.cached" class="rounded-full bg-emerald-100 px-2 py-0.5 font-semibold text-emerald-900">instant · cached</span>
                <a v-if="m.verification?.trace_url" :href="m.verification.trace_url" target="_blank" rel="noopener"
                   class="rounded-full bg-stone-900 px-2 py-0.5 font-medium text-white underline decoration-white/40 underline-offset-2">verified trace ↗</a>
                <span v-else-if="m.verification" class="rounded-full bg-stone-100 px-2 py-0.5">gate {{ m.verification.eval_gate || '—' }}</span>
                <span v-if="m.pii?.length" class="rounded-full bg-amber-100 px-2 py-0.5 text-amber-900">PII redacted: {{ m.pii.join(', ') }}</span>
              </div>
              <p class="whitespace-pre-wrap text-[15px] leading-relaxed">{{ m.text }}</p>
              <div v-if="m.citations?.length" class="mt-2 flex flex-wrap gap-1.5">
                <span v-for="c in m.citations" :key="c.chunk_id" class="cursor-pointer rounded-md border border-stone-200 bg-[#FAF7F1] px-2 py-1 font-mono text-xs hover:border-[#1F3D2B]"
                  @click="selected = m.contexts?.find(x => x.chunk_id === c.chunk_id) || selected" :title="c.chunk_id">[{{ c.doc_id }}]</span>
              </div>
              <div v-if="!m.streaming && m.model !== 'error'" class="mt-2 flex items-center gap-1.5 text-xs text-stone-500">
                <span class="mr-1">Was this useful?</span>
                <button @click="vote(m, 'up')" :aria-pressed="m.voted === 'up'" aria-label="Thumbs up"
                  class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg border px-2"
                  :class="m.voted === 'up' ? 'border-[#1F3D2B] bg-[#1F3D2B] text-white' : 'border-stone-200 hover:border-[#1F3D2B]'">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M7 11v9H4a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1h3Zm2-7 6 6v2h5a2 2 0 0 1 2 2.4l-1.2 6A2 2 0 0 1 18.8 22H9V4Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>
                </button>
                <button @click="vote(m, 'down')" :aria-pressed="m.voted === 'down'" aria-label="Thumbs down"
                  class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg border px-2"
                  :class="m.voted === 'down' ? 'border-red-800 bg-red-800 text-white' : 'border-stone-200 hover:border-red-800'">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M17 13V4h3a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1h-3Zm-2 7-6-6v-2H4a2 2 0 0 1-2-2.4l1.2-6A2 2 0 0 1 5.2 2H15v18Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>
                </button>
                <span v-if="m.usage" class="ml-auto tabular-nums">{{ m.usage.prompt_tokens + m.usage.completion_tokens }} tok</span>
              </div>
            </div>
          </article>
          <p v-if="loading" class="text-sm text-stone-500">Retrieving → reranking → answering…</p>
        </div>

        <form @submit.prevent="ask()" class="flex gap-2 border-t border-stone-200 bg-[#FAF7F1] p-4">
          <label for="q" class="sr-only">Ask a question</label>
          <UInput id="q" v-model="draft" placeholder="Ask about suppliers, SAF-114, field failures…" size="lg" class="flex-1" :disabled="loading" />
          <UButton type="submit" color="primary" size="lg" class="min-h-[44px] min-w-[44px] bg-[#1F3D2B]" :loading="loading" aria-label="Send">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 12h13m-6-6 6 6-6 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </UButton>
        </form>
        <div class="flex flex-wrap items-center gap-3 border-t border-stone-100 px-5 py-2.5 text-sm text-stone-600">
          <label class="inline-flex min-h-[44px] items-center gap-2"><UToggle v-model="useAgent" /> Agentic (ReAct)</label>
          <label class="inline-flex min-h-[44px] items-center gap-2"><UToggle v-model="useGraph" /> GraphRAG</label>
        </div>
      </section>

      <!-- Inspector column -->
      <aside class="space-y-5" aria-label="Inspector">
        <section class="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm">
          <h2 class="font-display text-base font-semibold">Retrieval trace</h2>
          <p class="text-xs text-stone-500">Plan → retrieve → rerank. Open a step to see branch scores.</p>
          <ol v-if="lastTrace.length" class="mt-2 space-y-1.5">
            <li v-for="(t, i) in lastTrace" :key="i" class="rounded-lg border border-stone-200 bg-[#FAF7F1] px-3 py-2 text-[13px]">
              <p class="font-semibold capitalize">{{ t.step }}</p>
              <p class="text-stone-600">{{ t.detail }}</p>
            </li>
          </ol>
          <p v-else class="mt-2 text-sm text-stone-400">Ask a question to see the pipeline think.</p>
          <div v-if="graphTriples.length" class="mt-3">
            <h3 class="text-sm font-semibold">Knowledge graph hops</h3>
            <ul class="mt-1 space-y-1 font-mono text-xs">
              <li v-for="(g, i) in graphTriples" :key="i" class="rounded bg-stone-100 px-2 py-1">{{ g.s }} —{{ g.r }}→ {{ g.o }}</li>
            </ul>
          </div>
        </section>

        <section class="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm">
          <h2 class="font-display text-base font-semibold">Source context</h2>
          <div v-if="selected" class="mt-2 rounded-lg border border-[#1F3D2B]/30 bg-[#FAF7F1] p-3 text-sm">
            <p class="font-mono text-xs text-stone-500">{{ selected.chunk_id }} · rerank {{ selected.rerank_score }}</p>
            <p class="mt-1 whitespace-pre-wrap">{{ selected.text?.slice(0, 900) }}</p>
          </div>
          <p v-else class="mt-2 text-sm text-stone-400">Click a citation chip to inspect the exact chunk sent to the model.</p>
        </section>

        <section class="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm">
          <div class="flex items-center justify-between">
            <h2 class="font-display text-base font-semibold">Eval gate</h2>
            <span v-if="evalRes" class="rounded-full px-2.5 py-1 text-xs font-semibold" :class="evalRes.summary.gate === 'PASS' ? 'bg-emerald-100 text-emerald-900' : 'bg-amber-100 text-amber-900'">{{ evalRes.summary.gate }}</span>
          </div>
          <dl v-if="evalRes" class="mt-2 grid grid-cols-3 gap-2 text-center">
            <div v-for="(v, k) in evalMetrics" :key="k" class="rounded-lg bg-[#FAF7F1] px-1 py-2">
              <dt class="text-[11px] uppercase tracking-wide text-stone-500">{{ k }}</dt>
              <dd class="font-display text-lg font-semibold">{{ v }}</dd>
            </div>
          </dl>
          <p v-else class="mt-2 text-sm text-stone-400">Runs the 5-question golden set: context precision/recall, faithfulness, NDCG.</p>
        </section>

        <section class="rounded-2xl border border-stone-200 bg-white p-4 shadow-sm">
          <h2 class="font-display text-base font-semibold">Pipeline verification</h2>
          <div v-if="verify" class="mt-2 space-y-1.5 text-sm">
            <p class="flex items-center justify-between">
              <span class="text-stone-500">Langfuse tracing</span>
              <span class="font-semibold" :class="verify.tracing === 'langfuse' ? 'text-emerald-800' : 'text-stone-500'">
                {{ verify.tracing === 'langfuse' ? 'Connected' : 'Off — local gate' }}
              </span>
            </p>
            <p class="flex items-center justify-between">
              <span class="text-stone-500">Last eval gate</span>
              <span class="font-semibold">{{ verify.gate || '—' }} <span v-if="verify.faith" class="font-normal text-stone-500">(faith {{ verify.faith }})</span></span>
            </p>
            <p class="flex items-center justify-between">
              <span class="text-stone-500">User feedback</span>
              <span class="font-semibold">{{ verify.up }} up · {{ verify.down }} down</span>
            </p>
            <p v-if="verify.tracing !== 'langfuse'" class="rounded-lg bg-[#FAF7F1] p-2 text-xs text-stone-500">
              Every answer carries per-stage spans + faithfulness scores the moment
              <span class="font-mono">LANGFUSE_*</span> keys are set — no code change needed.
            </p>
          </div>
          <p v-else class="mt-2 text-sm text-stone-400">Loading verification status…</p>
        </section>
      </aside>
    </main>

    <footer class="mx-auto max-w-6xl px-5 pb-8 text-xs text-stone-500">
      <p>Solid colors, real citations, keyboard accessible. No gradients, no emoji icons — per ui-ux-pro-max review.</p>
    </footer>
  </div>
</template>

<script setup lang="ts">
const config = useRuntimeConfig()
const api = (config.public.apiBase as string) || '/api'
const draft = ref('')
const loading = ref(false)
const evalLoading = ref(false)
const useAgent = ref(true)
const useGraph = ref(true)
const messages = ref<any[]>([])
const lastTrace = ref<any[]>([])
const graphTriples = ref<any[]>([])
const selected = ref<any>(null)
const health = ref<any>(null)
const evalRes = ref<any>(null)
const verify = ref<any>(null)
const evalMetrics = computed(() => {
  if (!evalRes.value?.summary) return {}
  return Object.fromEntries(Object.entries(evalRes.value.summary).filter(([k]) => k !== 'gate'))
})
const scrollBox = ref<HTMLElement | null>(null)
const samples = [
  'Which supplier provides the component used in Product X?',
  'What does SAF-114 require?',
  'Which units failed and what revision were they?'
]

async function loadHealth() {
  try { health.value = await $fetch(`${api}/health`) } catch { /* api offline */ }
}
async function ask(preset?: string) {
  const q = (preset ?? draft.value).trim()
  if (!q || loading.value) return
  messages.value.push({ role: 'user', text: q })
  draft.value = ''
  loading.value = true
  const t0 = performance.now()
  const sid = sessionId()
  // progressive render via SSE; falls back to plain POST if streams fail
  const msg: any = { role: 'assistant', text: '', streaming: true, query: q }
  messages.value.push(msg)
  const params = new URLSearchParams({ query: q, top_k: '10', use_agent: String(useAgent.value), use_graph: String(useGraph.value), session_id: sid })
  try {
    const resp = await fetch(`${api}/query/stream?${params}`)
    if (!resp.ok || !resp.body) throw new Error(`stream ${resp.status}`)
    const reader = resp.body.getReader()
    const dec = new TextDecoder()
    let buf = ''
    const trace: any[] = []
    let done: any = null
    let errored = false
    for (;;) {
      const { done: eof, value } = await reader.read()
      if (eof) break
      buf += dec.decode(value, { stream: true })
      let idx: number
      while ((idx = buf.indexOf('\n\n')) >= 0) {
        const raw = buf.slice(0, idx); buf = buf.slice(idx + 2)
        const m = raw.match(/event: (\w+)\ndata: ([\s\S]*)/)
        if (!m) continue
        const payload = JSON.parse(m[2])
        if (m[1] === 'token') { msg.text += payload.text; nextTick(scroll) }
        else if (m[1] === 'trace') trace.push(payload)
        else if (m[1] === 'done') done = payload
        else if (m[1] === 'error') { errored = true; msg.text = payload.detail || 'Generation failed.'; msg.model = 'error' }
      }
    }
    if (!errored) {
      if (done?.truncated) msg.text += `\n\n[Warning: generation cut short — ${done?.error || 'partial answer'}.]`
      Object.assign(msg, { streaming: false, citations: done?.citations, contexts: done?.contexts, model: done?.model, pii: done?.pii_redactions, usage: done?.usage, verification: done?.verification, cached: done?.cached, ms: Math.round(performance.now() - t0) })
    } else {
      Object.assign(msg, { streaming: false, ms: Math.round(performance.now() - t0) })
    }
    lastTrace.value = trace
    graphTriples.value = done?.graph_triples || []
    selected.value = done?.contexts?.[0] || null
  } catch (e: any) {
    try {
      const r: any = await $fetch(`${api}/query`, {
        method: 'POST', body: { query: q, top_k: 10, use_agent: useAgent.value, use_graph: useGraph.value, session_id: sid }
      })
      Object.assign(msg, { streaming: false, text: r.answer, citations: r.citations, contexts: r.contexts, model: r.model, pii: r.pii_redactions, usage: r.usage, verification: r.verification, cached: r.cached, ms: Math.round(performance.now() - t0) })
      lastTrace.value = r.trace || []
      graphTriples.value = r.graph_triples || []
      selected.value = r.contexts?.[0] || null
    } catch {
      Object.assign(msg, { streaming: false, text: `API unreachable at ${api}. Start it with: uvicorn backend.app.main:app --port 8000`, model: 'error' })
    }
  } finally {
    loading.value = false
    nextTick(scroll)
  }
}
function scroll() { scrollBox.value?.scrollTo({ top: 99999, behavior: 'smooth' }) }
function sessionId() {
  let s = localStorage.getItem('rag-session')
  if (!s) { s = Math.random().toString(36).slice(2) + Date.now().toString(36); localStorage.setItem('rag-session', s) }
  return s
}
async function vote(m: any, v: 'up' | 'down') {
  m.voted = v
  try { await $fetch(`${api}/feedback`, { method: 'POST', body: { session_id: sessionId(), query: m.query || '', vote: v } }); loadVerify() } catch { /* offline-safe */ }
}
async function runEval() {
  evalLoading.value = true
  try { evalRes.value = await $fetch(`${api}/eval`, { method: 'POST' }); loadVerify() }
  catch { evalRes.value = null }
  finally { evalLoading.value = false }
}
async function loadVerify() {
  try {
    const [h, hist, fb] = await Promise.all([
      $fetch(`${api}/health`).catch(() => ({})),
      $fetch(`${api}/eval/history?limit=1`).catch(() => ({ runs: [] })),
      $fetch(`${api}/feedback/stats`).catch(() => ({ up: 0, down: 0 }))
    ]) as any[]
    const last = hist?.runs?.[hist.runs.length - 1]?.summary || {}
    verify.value = { tracing: (h as any)?.tracing || 'off', gate: last.gate, faith: last.faith, up: (fb as any)?.up || 0, down: (fb as any)?.down || 0 }
  } catch { /* api offline */ }
}
onMounted(() => { loadHealth(); loadVerify() })
</script>
