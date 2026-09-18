# Q3 Field Report — Scanner Fleet (multimodal sample)

## Summary
Fleet uptime 99.1% across 412 deployed Product X units. Three thermal incidents
traced to pre-rev-C XK-7 controllers operating above 40C.

## Failure table (must survive chunking as a unit)

| Unit | Component | Temp (C) | Firmware | Outcome |
|------|-----------|----------|----------|---------|
| X-101 | XK-7 rev B | 44 | Helios 4.0 | Jitter, auto-recovered |
| X-207 | XK-7 rev B | 47 | Helios 4.0 | Shutdown, replaced with rev C |
| X-309 | XK-7 rev C | 46 | Helios 4.2 | Nominal — no fault |

Reading the table: only rev B units failed; rev C at 46C with Helios 4.2 stayed nominal.
This row-level fact tests table-aware parsing and parent-child chunking
(table kept whole as one child, never split mid-row).

## Chart note (multimodal stub)
Figure F-3 (not embedded as pixels in this markdown): jitter vs temperature,
inflection at 40C for rev B, flat for rev C. The pipeline's multimodal module
stores figure captions adjacent to the referencing paragraph so text queries
like "at what temperature does jitter start?" retrieve the caption chunk.
Jitter onset: 40C on rev B.
