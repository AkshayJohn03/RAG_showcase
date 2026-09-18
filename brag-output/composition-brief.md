# Hyperframes Composition Brief: Senior RAG Showcase

## Objective
Create a short launch-style brag video for the Senior RAG Showcase console.

## Output
- Composition directory: `brag-output/composition/`
- Rendered video: `brag-output/brag.mp4`
- Format: landscape — 1920x1080
- Duration: 21 seconds

## Source Material
- Project root: `D:\aria\rag-senior-showcase`
- Primary files read: `frontend/pages/index.vue`, `frontend/app.vue`, `README.md`,
  `backend/app/api/routes.py`, `data/eval/ablation.json`
- Product name: Senior RAG Showcase (RAG Retrieval Console)
- Tagline / strongest claim: "Measured, not claimed." / "survived six hostile reviews"
- Key UI moment to recreate: the chat console — ink header, paper column,
  moss user bubble, trace steps, citation chips, amber PASS badge
- Copy that must appear verbatim:
  - "Most RAG demos are API wrappers."
  - "This one survived SIX HOSTILE REVIEWS."
  - "Which supplier provides the component used in Product X?"
  - "dense-only recall 0.41" → "hybrid 0.91"
  - "PASS · 16 questions · 1,874 docs"
  - "Measured, not claimed."

## Creative Direction
- Tone preset: polished
- Creative direction: quiet confident engineering demo
- Interpretation: restrained pacing with longer holds; serif display type; energy
  from numbers landing, not motion chaos.
- Angle: the anti-demo demo — evidence as the flex. Hostile reviews, ablation
  numbers, millisecond traces, stated plainly.
- Hook: "Most RAG demos are API wrappers." then "This one survived SIX HOSTILE REVIEWS."
- Outro / punchline: "Measured, not claimed." + "Senior RAG Showcase"
- Avoid:
  - Generic SaaS language
  - Abstract filler visuals
  - Unrelated visual redesign

## Visual Identity
- Background: #FAF7F1 (warm paper; ink #1C1917 cards for the numbers scene)
- Text: #1C1917 (paper scenes) / #FAF7F1 (ink scene)
- Accent: #1F3D2B (moss green, trace + bubbles)
- Secondary: #B45309 (clay/amber, badges)
- Display font: Fraunces (shipped locally if downloadable, else Georgia serif fallback)
- Body font: Inter (shipped locally if downloadable, else system sans fallback)
- Visual references from the project: chat console layout, trace step list,
  citation chips, eval gate badge

## Storyboard
Use the storyboard in `brag-output/brag-plan.md` as the creative contract.

Scene summary:
1. Hook — 3s — two serif lines arrive sequentially on paper
2. Reveal — 4s — console chrome assembles (header, bubble with the supplier question)
3. Trace run — 5s — 4 trace steps arrive sequentially and hold; answer streams with chips; "p50 33 ms" chip lands
4. Numbers — 5s — ink card; "dense-only recall 0.41" morphs to "hybrid 0.91"; PASS badge flips (beat-locked ~17.0s)
5. Outro — 4s — "Measured, not claimed." settled hold

## Audio
- Audio role: warm bed
- Audio arc: bed in under hook, steady through demos, gentle fade under outro line and out
- Music: happy-beats-business-moves-vol-1-by-ende-dot-app.mp3 (bundled, 120 BPM, cue preset present)
- Music treatment: full bed at moderate volume; fade out over final 2s
- Music cue guidance: bundled preset `assets/music/cues/...vol-1....music-cues.json`; strong cues near 16-18s for the PASS flip (target ~17.0s within ±0.15s); beat grid ~0.5s for trace-step arrivals (text reads: snap arrivals to every other beat or faster with full-set hold)
- Audio-reactive treatment: subtle — trace-step glow presence breathes with the bed if extraction works; skip with note if not
- Audio-coupled moments:
  - hook line two arrival — key/click
  - console chrome assembly — UI clicks
  - trace steps arriving one by one — soft ticks
  - number morph + PASS flip — single decisive ticks
- SFX selection guidance: interface/ui clicks for arrivals, keyboard ticks for typed lines, one light impact for the PASS payoff; restraint under outro
- SFX analysis guidance: skill `assets/sfx/sfx-analysis.md` (+json); prefer low high-frequency-risk files for repeated moments
- Exact SFX choice: Hyperframes should choose filenames, timestamps, density, and volume based on the implemented animation.
- Audio files: copy the chosen music and any Hyperframes-selected SFX into `brag-output/composition/assets/`

## Hyperframes Instructions
Load the composition-building Hyperframes domain skills — `hyperframes-core` (composition contract + `data-*` timing), `hyperframes-animation` (motion), `hyperframes-creative` (design spec, beats, audio-reactive), `hyperframes-keyframes` (seek-safe keyframes), and `hyperframes-cli` (lint/check/render). /brag is its own workflow: do not enter the `hyperframes` entry-point intent interview and do not route into its generic promo / launch-video workflow. Prefer native Hyperframes conventions over anything in `/brag`.

Requirements:
- Show at least one real UI, copy, or visual element from the source project.
- Keep all text readable in the final render.
- Keep the video within 15-25 seconds.
- Include the planned music/SFX layer unless audio was explicitly disabled or documented as intentionally silent.
- Treat `/brag` audio notes as guidance, not a fixed cue sheet. Choose SFX after the visual animation exists.
- Treat music cue metadata as optional timing hints. Hyperframes decides exact animation timing and should ignore cues that hurt readability, scene pacing, or the product story.
- Major reveals may move toward nearby strong cues within about 0.15s. Smaller entrances may align to nearby beat points within about 0.10s. Use only 1-3 strong cue locks in a 15-25s video unless the edit clearly benefits from more.
- Use SFX to support motion and interaction: card sounds for card-like reveals, short announcement cues for major payoffs, key/click sounds for text or user actions, and restraint when the edit is already busy.
- Honor planned music treatment such as fade-outs, ducking, beat-aligned reveals, or letting a final SFX ring over the music, using the best Hyperframes-supported implementation.
- When music is present and the treatment is not `none`, consider Hyperframes audio-reactive workflow: extract audio data and use RMS/frequency bands for subtle, brand-specific motion. Good targets are glow, depth, background warmth, card presence, title emphasis, or other existing visual elements. Avoid waveform/equalizer visuals, musical-note graphics, generic particle systems, strobing, or heavy pulsing.
- Use local assets for audio and any required runtime/media dependencies when possible.
- Run `hyperframes check` before render — it is brag's single gate.
