# Third-Party Notices

This project is Apache-2.0 (see `LICENSE`). The following third-party materials
are bundled or used, each under its own terms. Nothing below is relicensed.

## Bundled assets (shipped in this repo)

| Asset | Source | License |
|---|---|---|
| `brag-output/composition/assets/music/*.mp3` | ende.app — Sascha Ende, "Happy Beats / Business Moves" | **CC BY 4.0, attribution waived by the author** (commercial use allowed; do not upload to Content ID / Spotify as your own). Credit included in video share copy as courtesy. |
| `brag-output/composition/assets/sfx/**` | [Kenney](https://kenney.nl/) | **CC0** (public domain, no attribution required) |
| `brag-output/composition/assets/fonts/Fraunces-*.ttf` | Google Fonts (Fraunces by Undercase Type) | **SIL Open Font License 1.1** |
| `brag-output/composition/assets/fonts/Inter-*.woff2` | Google Fonts (Inter by Rasmus Andersson) | **SIL Open Font License 1.1** |

## Corpora (fetched by scripts, never committed)

| Corpus | Fetch | Terms |
|---|---|---|
| 20 Newsgroups subset (`fetch_scale_corpus.py`) | sklearn | Research/benchmark use (no formal license; cite Joachims 1997) |
| BEIR SciFact (`fetch_beir.py`) | Thakur et al., NeurIPS 2021 | Research use; cite the BEIR paper |

## Models (downloaded at runtime, never redistributed)

| Model | Terms |
|---|---|
| sentence-transformers `all-MiniLM-L6-v2` | Apache-2.0 |
| FlashRank `ms-marco-TinyBERT-L-2-v2` | Apache-2.0 |
| Ollama `qwen3:1.7b` | Apache-2.0 |
| Ollama `gemma4:26b` (optional) | **Gemma Terms of Use** (not open-source; use-only, no redistribution) |

## Video output
`brag-output/brag.mp4` mixes Apache-2.0 code output with CC BY 4.0 music
(attribution waived) and CC0 SFX — safe to post commercially. Do not register
the video's audio with Content ID (per ende.app terms).
