# Brag Plan: Senior RAG Showcase

## What is this app?
A production-grade RAG console — chat over an enterprise corpus with grounded,
cited answers, a live retrieval-trace inspector, and an eval gate dashboard.
Its distinction: every claim is measured (ablation tables, BEIR benchmark) and
it survived six rounds of hostile code review.

## The angle
The anti-demo demo. Instead of "AI magic", the video sells *evidence*: hostile
reviews, ablation numbers, millisecond traces. For a hiring audience, the joke
is that thoroughness is the flex — "we publish our failures next to our wins."

## Hook (first 2-3 seconds)
"Most RAG demos are API wrappers." — beat — "This one survived six hostile reviews."
Big serif type on paper. The word "six" lands like a stat.

## Key moments (the middle)
- A question being typed into the console, trace steps lighting up one by one
  (plan → hybrid → graph → rerank), answer streaming with citation chips.
- The ablation punchline: "dense-only recall 0.41" morphing to "hybrid 0.91".
- The eval gate flipping to PASS over 1,874 docs.

## Outro / punchline
"Measured, not claimed." — then the console name. Quiet confidence, no hype.

## User flow worth showing
Type a question → watch the retrieval trace light up → grounded answer with
citations lands → eval gate reads PASS. (Entry → key action → result, all real
product beats from `frontend/pages/index.vue` + `backend/app/api/routes.py`.)

## Tone
- Preset: polished
- Creative direction: quiet confident engineering demo
- Interpretation: restrained pacing, longer holds, serif display type, warm bed;
  energy comes from the numbers landing, not from motion chaos.

## Format: landscape — 1920x1080
## Duration: 21.5 seconds

## v2 enrichment (post-review)
Typing simulation for the question, animated knowledge-graph strip
(Product X → XK-7 → Nordwerk), BEIR caption under the numbers, scene exit
fades, transition whooshes, RMS-driven glow (20 keys sampled from the track's
audio data — the first attempt swapped opacity/time axes and never glowed;
caught on snapshot review, fixed before render).

## Visual identity (from the project)
- Background: #FAF7F1 (warm paper)
- Accent: #1F3D2B (moss green, primary actions + trace)
- Text: #1C1917 (ink)
- Secondary accent: #B45309 (clay/amber, badges)
- Display font: Fraunces (serif, headings)
- Body font: Inter (UI text)
- Strongest visual element: the chat console — ink header bar, paper chat column,
  moss-green user bubbles, citation chips, amber eval badge.

## Share copy (draft)
We built a RAG system, then let hostile reviewers attack it six times — and
published every failure next to every win. Dense-only recall 0.41; hybrid 0.91.
Measured, not claimed.

## Audio direction
- Role: warm bed
- Music: happy-beats-business-moves vol-1 (bundled, cue preset available)
- Music treatment: full bed, gentle fade under the outro line, out at end
- Music cue guidance: bundled preset in skill cues dir; 1-3 strong cues for the
  hook landing (~2.5s), the ablation number morph (~13s), and the PASS flip (~17s)
- Audio-reactive treatment: subtle — trace-step glow presence breathes with the bed
- SFX posture: sparse, motion-matched — key ticks for typing, soft clicks for
  trace steps and chips, one payoff tick for the PASS flip
- Audio-coupled moments: hook typing, question typing, trace steps arriving one
  by one, ablation number morph, PASS badge flip
- Restraint rule: no SFX under the outro line; music never masks readable text

## Storyboard

### Scene 1 — Hook — 3s
Paper background. "Most RAG demos are API wrappers." holds, then "This one
survived SIX HOSTILE REVIEWS." with "SIX" emphasized. Serif, ink on paper.
Sequential/interaction: two lines arrive one by one (second slams in).
Audio intent: bed starts; soft tick on the second line.
Audio-coupled idea: typed/key arrival on line two.
Music: warm bed in.
Transition mood: clean → Scene 2

### Scene 2 — Reveal — 4s
Console recreation: ink header bar ("RAG Retrieval Console"), paper chat column,
a moss user bubble with "Which supplier provides the component used in Product X?".
Sequential/interaction: header slides in, bubble pops, no answer yet (tease).
Audio intent: UI clicks as chrome assembles.
Audio-coupled idea: click per element arrival.
Music: bed continues.
Transition mood: clean → Scene 3

### Scene 3 — Trace run — 5s
Same console: trace steps light up one by one — plan → hybrid → graph → rerank —
then the answer streams with citation chips; "p50 33 ms" chip lands last.
Sequential/interaction: yes — 4 trace steps arrive sequentially, then chips.
Each trace line holds; full set stays readable (no fast beat-snapping on text).
Audio intent: rising confidence; tick per trace step, soft chime on the ms chip.
Audio-coupled idea: sequential card arrival + simulated streaming text.
Music: bed continues.
Transition mood: clean → Scene 4

### Scene 4 — Numbers — 5s
Dark ink card. "dense-only recall 0.41" morphs/flips to "hybrid 0.91".
Then the eval badge flips to "PASS · 16 questions · 1,874 docs".
Sequential/interaction: number morph first (hold), badge flip second (hold).
Audio intent: payoff moment; single decisive tick on the morph, warmer tick on PASS.
Audio-coupled idea: counter morph + badge flip.
Music: bed continues, slight lift if cue supports it.
Transition mood: soft → Scene 5

### Scene 5 — Outro — 4s
Paper again. "Measured, not claimed." holds. Small line: "Senior RAG Showcase".
Sequential/interaction: none — one settled hold.
Audio intent: resolve; music fades under the line and out.
Audio-coupled idea: none.
Music: fade out.

**Music mood for this video:** upbeat
**Audio summary:** Warm corporate bed throughout with sparse UI ticks tracking arrivals and two payoff ticks (number morph, PASS flip), fading under the quiet outro.
