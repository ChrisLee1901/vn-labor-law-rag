# AI SDK UI Message Stream - chunk shapes used by this project

Verified 2026-11-22 against:
- https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol (chunk shapes, header, `[DONE]`)
- https://ai-sdk.dev/docs/ai-sdk-ui/streaming-data (`data-*` parts, `id`, `transient`)
- https://ai-sdk.dev/docs/migration-guides/migration-guide-7-0 (v7: no wire-protocol change documented)

Emitter: `backend/app/stream.py`. Each chunk is one SSE line `data: <json>\n\n`; the stream ends with `data: [DONE]\n\n`.

Response headers: `x-vercel-ai-ui-message-stream: v1`, `content-type: text/event-stream`, `cache-control: no-cache`.

Order emitted by `/api/chat`: `start → data-status → source-url* → text-start → text-delta* → text-end → (data-citation-warning)? → data-trace → finish → [DONE]` (see `docs/api-contract.md`). On failure: `error` then `[DONE]`.

| Builder | JSON |
|---|---|
| `start(mid)` | `{"type":"start","messageId":mid}` |
| `text_start(id)` | `{"type":"text-start","id":id}` |
| `text_delta(id,d)` | `{"type":"text-delta","id":id,"delta":d}` |
| `text_end(id)` | `{"type":"text-end","id":id}` |
| `source_url(sid,url,title)` | `{"type":"source-url","sourceId":sid,"url":url,"title":title}` |
| `data_status(llm,mode)` | `{"type":"data-status","data":{"llm":"online\|offline","mode":"rag\|offline\|refused"}}` |
| `data_trace(id)` | `{"type":"data-trace","data":{"trace_id":id}}` |
| `data_citation_warning(inv,mis)` | `{"type":"data-citation-warning","data":{"invalid":[...],"mismatch":[...]}}` |
| `error(t)` | `{"type":"error","errorText":t}` |
| `finish()` | `{"type":"finish"}` |

Frontend: custom parts arrive in `useChat` as `message.parts` of type `data-status` / `data-trace` / `data-citation-warning`. `source-url` parts render as citations.

## Unverified / not used
- `title` on `source-url`: docs' wire example shows only `sourceId` + `url`; `title` is in the UIMessageChunk type but not shown on the docs page.
- `transient: true` on `data-*`: documented only as a `writer.write()` option (top-level, next to `type`/`data`), raw wire JSON not shown. We do not emit it.
- Optional `id` on `data-*` (reconciliation): documented, not used.
- `source-document` (`sourceId`, `mediaType`, `title`): documented, not used (no builder).
- v7 changelog is silent on the wire format; one secondary source says a stream ending without `finish` is treated as an error client-side, so always emit `finish`.
- Not tested against a live `useChat` yet (Phase-0 spike not run).
