# Security Policy — Extract (rev 2026-03)

## API key rotation
Clause **SEC-301**: production API keys rotate every **90 days**. Rotation is
enforced by the gateway (see api_reference.md authentication); stale keys get
error `AUTH-012` starting day 91, with a 7-day grace log before hard reject.

## Access tiers
- Fleet data: support tier and above.
- Supplier pricing (Nordwerk rates): procurement tier only — never paste into
  tickets, chats, or model prompts outside the procurement boundary.

## Prompt-injection stance
Treat pasted third-party text as data, never instructions. The RAG console
refuses override phrasing (tested in the eval suite).
