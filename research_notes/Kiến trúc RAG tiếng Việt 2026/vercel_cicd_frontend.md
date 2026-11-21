# Next.js + FastAPI monorepo on Vercel Hobby, with GitHub Actions CI/CD (state as of 2026-11-22)

Scope: a portfolio Vietnamese RAG chat app. FastAPI runs on the Vercel Python runtime, does retrieval against Supabase pgvector, calls an external OpenAI-compatible LLM (self-hosted on Kaggle behind a tunnel, sometimes offline) and streams the answer to a Next.js chat UI. Ingestion and eval are Python, in the same repo. Free tiers only.

Freshness: most Vercel pages were fetched with `last_updated` between 2026-06 and 2026-11-14. Renames and deprecations to watch for in older blog posts and LLM answers:
- **Edge Config is now "Global Config".**
- **Cron Jobs are "legacy"**, replaced by "Schedules" (beta).
- **`experimentalServices` was replaced by `services`.**
- **AI SDK is at v7.**
- **AI Elements will be deprecated at the end of November 2026** and is moving into shadcn/ui.

---

## 1. Vercel Python runtime in 2026: versions, zero-config FastAPI, limits, streaming, cold starts, regions, uv

### Takeaway
Python on Vercel is GA. FastAPI deploys with zero config: Vercel finds `app` in `app.py`, `index.py`, `server.py`, `main.py`, `wsgi.py` or `asgi.py` (at the root or under `src/` or `app/`), or uses `tool.vercel.entrypoint`. It supports Python 3.12 (default), 3.13 and 3.14, and installs from pyproject.toml/uv.lock. The Python bundle limit is 500 MB, and streaming works. On Hobby every function gets a fixed 2 GB / 1 vCPU, runs in a single region, and is capped at 300 s.

### Cited Findings
- **Python versions:** 3.12 (default), 3.13 and 3.14. Set the version via `pyproject.toml` (`requires-python`), `.python-version` or `Pipfile.lock`. If the requested version is missing or unsupported, Vercel falls back to the default. — [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python)
- **Dependencies:** `pyproject.toml` (with or without `uv.lock`), `requirements.txt`, or `Pipfile` plus `Pipfile.lock`. Vercel picks the framework preset (FastAPI, Flask, Django) when the dependency appears in one of these files. — [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python)
- **Changelog titles on the runtime page** (dates not captured): "Python on Vercel is now generally available", "Python package manager uv is now available for builds with zero configuration", "Python 3.13 and 3.14 are now available", "Python function bundles now include precompiled bytecode", "Python support added to in-function concurrency beta". — [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python)
- **Entrypoint detection:** Vercel looks for `app.py`, `index.py`, `server.py`, `main.py`, `wsgi.py` or `asgi.py`, the same names inside `src/` or `app/`, or the `module:variable` given in `[tool.vercel] entrypoint = "my_package.api:app"`. The file must define a top-level `app` (FastAPI or Flask) or `application` (Django/WSGI). The older `[project.scripts] app = "module:variable"` still works, but new projects should use `tool.vercel.entrypoint`. — [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python)
- **Build hook:** `[tool.vercel.scripts] build = "python build.py"` runs after dependencies are installed. A Build Command set in `vercel.json` or the dashboard takes precedence. — [Vercel FastAPI docs](https://vercel.com/docs/frameworks/backend/fastapi)
- **Lifespan:** FastAPI lifespan events are supported. Shutdown cleanup gets at most **500 ms** after SIGTERM, and logs printed during shutdown do not show up in the dashboard. — [Vercel FastAPI docs](https://vercel.com/docs/frameworks/backend/fastapi)
- **One function per app:** a FastAPI app becomes a single Vercel Function on Fluid compute. `maxDuration` is configured in `vercel.json` under `functions`, keyed by the resolved entrypoint file (e.g. `"app/main.py": {"maxDuration": 60}`). — [Vercel FastAPI docs](https://vercel.com/docs/frameworks/backend/fastapi)
- **Streaming:** the Python runtime supports streaming responses. Vercel's example returns `StreamingResponse(event_stream(), media_type="text/plain")` from an async generator. Vercel notes that streaming pairs well with Fluid compute, because an instance can serve other requests while it waits between chunks. — [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python); [Ship a FastAPI app on Vercel](https://vercel.com/kb/guide/ship-a-fastapi-app-on-vercel)
- **Bundle size:** **250 MB** uncompressed in general, **500 MB for Python**. "Large functions" (beta, Fluid plus Active CPU) allow up to **5 GB**, and new projects are eligible by default via `VERCEL_SUPPORT_LARGE_FUNCTIONS`. Python gets no tree-shaking, so every reachable file is bundled. Use `excludeFiles` in `vercel.json`. Setting `VERCEL_ANALYZE_BUILD_OUTPUT=1` prints per-function sizes and the largest files. — [Vercel Functions limits](https://vercel.com/docs/functions/limitations); [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python)
- **Max duration with Fluid compute:** Hobby is **300 s default and 300 s maximum**. Pro/Enterprise get 300 s default, 800 s max, and 1800 s in beta. The limit includes the time spent streaming the response. A timeout returns 504 `FUNCTION_INVOCATION_TIMEOUT`. — [Vercel Functions limits](https://vercel.com/docs/functions/limitations)
- **Memory:** Hobby is **2 GB / 1 vCPU as both default and maximum**. Pro/Ent can go up to 4 GB / 2 vCPU. — [Vercel Functions limits](https://vercel.com/docs/functions/limitations)
- **Body sizes:** requests up to **4.5 MB** by default. The 20 MiB beta needs the 4 GB memory tier, which Hobby cannot select. Responses are capped at **4.5 MB, except streamed responses**. — [Vercel Functions limits](https://vercel.com/docs/functions/limitations)
- **Regions:** one region by default (`iad1`), changeable. Only Pro/Enterprise can run multiple regions. — [Vercel Functions limits](https://vercel.com/docs/functions/limitations)
- **File descriptors:** **1,024**, shared across concurrent executions on an instance, so pool and close DB/HTTP connections. — [Vercel Functions limits](https://vercel.com/docs/functions/limitations)
- **Cold starts:** Vercel precompiles `.pyc` bytecode into the bundle "when space allows" to cut init time. Fluid compute runs several requests per instance, which Vercel says reduces cold starts. Neither page gives a cold-start latency figure. — [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python); [Ship a FastAPI app on Vercel](https://vercel.com/kb/guide/ship-a-fastapi-app-on-vercel)
- **Routing Middleware in Python:** set via `"proxy": {"entrypoint": "proxy:proxy"}` in `vercel.json`. It runs separately, with only the `vercel.proxy` dependency group installed. — [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python)
- **Relative paths:** `open()` resolves against the project base, not the file's directory. — [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python)
- **Legacy layout:** file-based Python functions in an `/api` directory are still supported. — [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python)
- **Local dev:** `vercel dev` runs the app locally (CLI ≥ 48.1.8). — [Vercel FastAPI docs](https://vercel.com/docs/frameworks/backend/fastapi)
- **Hobby monthly allotment:** 1,000,000 function invocations, **4 h Active CPU**, **360 GB-hrs provisioned memory**, 100 GB Fast Data Transfer, 10 GB Fast Origin Transfer. — [Vercel fair use guidelines](https://vercel.com/docs/limits/fair-use-guidelines)
- **Active CPU vs memory time:** time spent waiting on I/O (AI model calls, DB queries) does not count toward Active CPU. Provisioned memory time counts for as long as the instance runs. — [Vercel Functions limits](https://vercel.com/docs/functions/limitations)

### Inferences
- **The memory allotment is the binding Hobby budget for streaming chat, not CPU.** Memory is fixed at 2 GB, so 360 GB-hrs ≈ 180 instance-hours per month. One 30 s streamed answer costs about 0.017 GB-hr, so roughly 21k answers per month if Fluid compute never shares an instance; sharing raises that. Waiting on the Kaggle LLM is I/O, so the 4 h Active CPU allotment should last.
- **Set `maxDuration` explicitly, around 60–120 s.** A hung tunnel should not burn the full 300 s, and the answer generator should apply its own timeout to the LLM call (e.g. httpx `timeout=(5, 60)`).
- **Pin `requires-python = ">=3.12,<3.13"`** and add a `.python-version` of `3.12`, so CI and Vercel use the same interpreter.
- **Choose the region near users and DB.** For Vietnamese users with Supabase in `ap-southeast-1` (Singapore), set the function region to Singapore (`sin1`). I did not re-verify that `sin1` is on the current region list in this session, but it is a long-standing Vercel region ID.
- **"No torch" fits easily.** fastapi, httpx, a psycopg/asyncpg driver and openai/pydantic are tens of MB, far below 500 MB. Anything heavier (torch, sentence-transformers, PDF parsers) belongs in the ingestion project, never in the API's dependencies.
- **Query-time embedding is the hidden coupling.** If query embedding also comes from the Kaggle endpoint, retrieval dies whenever Kaggle is offline, and the "retrieval-only degraded mode" goes with it. Options:
  - a hosted embedding API;
  - an ONNX-runtime embedder small enough for 500 MB (unverified here: cold-start cost on 1 vCPU, and quality of multilingual small models for Vietnamese);
  - Postgres full-text search as a fallback.

### Gaps
- No official cold-start latency numbers for Python on Vercel in 2026.
- I did not fetch the current region list for Hobby. Hobby can change its single default region, but I did not confirm that `sin1` is selectable.
- Whether the "in-function concurrency" beta for Python is on by default for FastAPI (relevant to memory-time sharing) was not confirmed.

---

## 2. Next.js + FastAPI in one Vercel project: Services vs the `/api` directory vs two projects; repo layout

### Takeaway
In 2026 the official way is **Vercel Services** (beta, all plans, Hobby included). One `vercel.json` declares a Next.js service and a FastAPI service. Top-level rewrites send `/api/*` to FastAPI and everything else to Next.js, on one domain with no CORS. Each service builds separately but they share a deployment, and a private-backend variant uses service bindings. Two separate Vercel projects remain possible but add CORS or cross-domain proxying, and the 120 s proxy timeout applies to external rewrites.

### Cited Findings
- **Services availability:** "Services are available in Beta on all plans". They "deploy multiple backends and frontends within a single Vercel project … a Next.js frontend and a FastAPI backend in the same repository deploy together with shared routing, environment variables, and a unique domain, replacing the need to split monorepos into separate Vercel projects." — [Vercel Services](https://vercel.com/docs/services)
- **Official quick-start config:**
  ```json
  {
    "services": {
      "my_frontend": { "root": "frontend/" },
      "my_backend": { "root": "backend/", "entrypoint": "main:app" }
    },
    "rewrites": [
      { "source": "/api/(.*)", "destination": { "service": "my_backend" } },
      { "source": "/(.*)", "destination": { "service": "my_frontend" } }
    ]
  }
  ```
  Services are internal unless a top-level rewrite exposes them. Firewall, Deployment Protection and redirects are configured once, at the top level. — [Vercel Services](https://vercel.com/docs/services)
- **Services mode moves build keys into each service:** `functions`, `installCommand`, `buildCommand`, `devCommand`, `ignoreCommand`, `outputDirectory` and `framework` are invalid at the top level and go into the service. Public routing stays at the top. — [Vercel Services](https://vercel.com/docs/services)
- **Local dev:** `vercel dev` (or `vercel dev --local` without logging in) runs all services and injects the binding env vars. — [Vercel Services](https://vercel.com/docs/services)
- **Bindings:** one service calls another privately through a binding, and Vercel injects the target URL as an env var. The `experimentalServices` model is the older one. Projects can also be configured with `vercel.toml` or `vercel.ts`. — [Vercel Services](https://vercel.com/docs/services)
- **Services pricing:** each service is billed like a Vercel Function (Active CPU, provisioned memory, invocations). Service-to-service calls are "Service Requests", and Hobby includes the first 1,000,000. Function limits apply to every service. — [Services pricing](https://vercel.com/docs/services/pricing)
- **Vercel's own "Python backend with Next.js" guide:**
  - Layout: `frontend/` (Next.js) and `backend/` (FastAPI `app/main.py`, `pyproject.toml`, `uv.lock`, migrations), with the root `vercel.json` declaring the `backend` service (framework `fastapi`, entrypoint `app.main:app`) and the `frontend` service.
  - Privacy: the frontend reaches the backend via a binding exposed as `BACKEND_URL`. The backend has no public route, and the browser calls a Next.js Route Handler at `/api/backend/*` that forwards allowlisted requests, so no CORS is needed.
  - Previews: each Preview contains both services from the same version. All previews share one DB by default.
  - Migrations: they run in the Python build hook (`[tool.vercel.scripts] build = "python -m scripts.deploy_setup"`) before the new deployment serves traffic, so they must stay compatible with older deployments.
  - No tracing is set up by default.

  — [Python backend on Vercel guide](https://vercel.com/kb/guide/python-backend-on-vercel)
- **FastAPI page on frontends:** use Services to deploy FastAPI with a frontend in one project. — [Vercel FastAPI docs](https://vercel.com/docs/frameworks/backend/fastapi)
- **Hobby project limits:** 200 projects, 25 projects per Git repository, 100 deployments created per day, 1 concurrent build, 45 min build time per deployment, 100 builds per hour (each Vercel Function counts as a build), 5 deploy hooks per project and 60 hook triggers per hour, 100 MB static/CLI source upload, Proxied Request Timeout 120 s. — [Vercel limits](https://vercel.com/docs/limits)
- **Hobby and GitHub organizations:** "Vercel does not support connecting a project on your Hobby team to Git repositories owned by Git organizations." — [Vercel limits](https://vercel.com/docs/limits)
- **The older official example `vercel/ai/examples/next-fastapi`:**
  - Structure: `api/` (FastAPI, `api.index:app`), `app/` (Next.js), and `requirements.txt` at the root.
  - Dev: `concurrently "next dev" "uvicorn api.index:app --reload"`, with Next `^16.4.6`.
  - Packaging: it depends on workspace AI SDK packages and must be run from a clone of the `vercel/ai` repo. Its README does not mention Vercel deployment.

  — [next-fastapi example](https://github.com/vercel/ai/tree/main/examples/next-fastapi); [package.json](https://raw.githubusercontent.com/vercel/ai/main/examples/next-fastapi/package.json)

### Inferences
**Recommended layout (lazy, two Python projects so the Vercel bundle stays clean):**
```
repo/
├─ vercel.json                 # services + rewrites (below)
├─ frontend/                   # Next.js 16, pnpm, AI SDK v7, shadcn AI Elements
├─ backend/                    # Vercel service: FastAPI only, runtime deps only
│  ├─ pyproject.toml           # requires-python 3.12, fastapi, httpx, psycopg[binary] or asyncpg, openai (optional)
│  ├─ uv.lock
│  └─ app/{main.py, rag/, settings.py}
├─ pipelines/                  # NOT deployed: ingestion + eval (heavy deps OK here)
│  ├─ pyproject.toml           # depends on backend via path dep, e.g. rag-core = {path="../backend"}
│  ├─ ingest/  eval/  datasets/golden.jsonl
├─ supabase/migrations/        # SQL migrations (pgvector, tables, RPCs)
└─ .github/workflows/          # ci.yml, e2e.yml, db-deploy.yml, keepalive.yml, eval.yml
```

**`vercel.json` sketch.** It follows the documented quick start. The per-service `functions`/`maxDuration` key placement is from the "moved into the service" rule; the exact schema is unverified, see Gaps.
```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "services": {
    "web": { "root": "frontend/" },
    "api": { "root": "backend/", "entrypoint": "app.main:app" }
  },
  "rewrites": [
    { "source": "/api/(.*)", "destination": { "service": "api" } },
    { "source": "/(.*)", "destination": { "service": "web" } }
  ]
}
```

**Public `/api/*` vs private backend plus Next proxy.** The public rewrite is simplest: the browser streams directly from FastAPI, and only one function is alive per chat. The private-binding pattern from Vercel's guide doubles function memory-time during a stream, because the Next.js Route Handler stays open while it proxies. Its upside is that BotID `checkBotId()` (a JS server API) can gate the request. For a public demo, expose `/api/*` publicly, enforce rate limits in the WAF and FastAPI, and skip the proxy.

**Hobby repo ownership.** On Hobby, keep the repo under a personal GitHub account if you want Vercel's Git integration (automatic preview per PR). If the repo must live in a GitHub org, deploy from GitHub Actions with the Vercel CLI instead (section 5).

**Two Vercel projects** is the fallback if Services beta misbehaves. Next.js rewrites to the external FastAPI URL work, but the 120 s Proxied Request Timeout applies and previews of the two projects are not paired.

### Gaps
- I did not fetch the Service configuration reference (`/docs/services/config-reference`). Still unconfirmed:
  - the exact per-service keys (`functions`, `maxDuration`, `excludeFiles`, region);
  - whether `crons` and `regions` stay top-level in services mode;
  - whether FastAPI sees the `/api` prefix in the path. The Services routing doc covers "how to control the path your code sees", but I did not read it. Safest: declare FastAPI routes with the `/api` prefix and test both.
- I did not verify whether `vercel build` / `vercel deploy --prebuilt` (the GitHub Actions path) fully supports Services projects.
- Whether a uv path dependency outside the service `root` gets bundled is unverified, which is why the layout keeps shared retrieval code inside `backend/`.

---

## 3. Chat UI and streaming: AI SDK useChat with a Python backend, UI libraries, citations, markdown, "model offline" status

### Takeaway
Use AI SDK (v7, released late June 2026) `useChat` on the frontend. Have FastAPI emit the **UI Message Stream protocol**: SSE carrying JSON parts, with the header `x-vercel-ai-ui-message-stream: v1` and a closing `data: [DONE]`. It can be hand-rolled in about 25 lines (no new dependency), produced by Pydantic AI's `VercelAIAdapter`, or produced by the new AI SDK for Python (`ai`, beta). Use `source-url`/`source-document` parts for citations and a custom `data-*` part for status. For components: AI Elements is being deprecated at the end of Nov 2026 in favour of the copy-in AI Elements patterns inside shadcn/ui; assistant-ui is the alternative.

### Cited Findings
- **The protocol:**
  - Transport: SSE. Custom backends must set `x-vercel-ai-ui-message-stream: v1`. `useChat` uses this protocol by default.
  - Message parts: `start` (`messageId`), `finish`, `abort`.
  - Text parts: `text-start`, `text-delta` (`delta`), `text-end`, each with an `id`.
  - Reasoning parts: `reasoning-start`, `reasoning-delta`, `reasoning-end`.
  - Citations: `source-url` and `source-document`.
  - Files: `file` (`url`, `mediaType`).
  - Custom data: `data-*` (custom suffix, e.g. `data-weather`).
  - Errors: `error` (`errorText`).
  - Tools: `tool-input-start`, `tool-input-delta`, `tool-input-available`, `tool-output-available`, approval parts.
  - Steps: `start-step`, `finish-step`, `reset-step`.
  - Termination: the stream ends with a literal `data: [DONE]`.
  - A simpler Text Stream protocol (plain text, via `TextStreamChatTransport`) exists but carries no structured data.

  — [AI SDK stream protocols](https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol)
- **AI SDK 7 release:** published around June 25–27, 2026. It is agent-focused (WorkflowAgent, harness adapters, tool search, stream retries, WebSocket chat) and ships a codemod plus a v6→v7 migration guide. Sources disagree on beta vs GA: Langfuse's changelog says GA, while one summary said beta. — [Vercel blog: AI SDK 7](https://vercel.com/blog/ai-sdk-7); [Langfuse changelog](https://langfuse.com/changelog/2026-06-26-vercel-ai-sdk-7); [Developers Digest](https://www.developersdigest.tech/blog/vercel-ai-sdk-whats-new-2026); [v7 migration guide](https://ai-sdk.dev/docs/migration-guides/migration-guide-7-0.md)
- **AI SDK for Python:**
  - Package: `ai`, installed with `uv add ai`. It is beta ("APIs may change before general availability") and needs Python ≥ 3.12.
  - FastAPI pattern: a Pydantic `ChatRequest(messages: list[ai.ui.ai_sdk.UIMessage])` plus `ai.ui.ai_sdk.to_messages(...)`, returning `StreamingResponse(ai.ui.ai_sdk.to_sse(events()), headers=ai.ui.ai_sdk.UI_MESSAGE_STREAM_HEADERS)`.
  - Models: IDs such as `anthropic/...` route through AI Gateway by default, and the guide does not cover custom OpenAI-compatible base URLs.

  — [Build AI agents in Python with the AI SDK](https://vercel.com/kb/guide/python-and-ai-sdk)
- **Pydantic AI:**
  - Entry point: `VercelAIAdapter.dispatch_request(request, agent=agent)` handles a FastAPI/Starlette request directly.
  - Versions: it targets AI SDK **v5 by default**, and `sdk_version=6` unlocks v6 features. The page does not mention v7.
  - Citations: tool metadata can emit `SourceUrlChunk`/`SourceDocumentChunk`/`DataChunk`, and custom events reach the client as `data-{name}`.

  — [Pydantic AI: Vercel AI integration](https://pydantic.dev/docs/ai/integrations/ui/vercel-ai/)
- **Vercel templates:** Vercel publishes an "AI SDK Python Streaming" template that uses the data stream protocol with useChat. — [Vercel template: ai-sdk-python-streaming](https://vercel.com/templates/next.js/ai-sdk-python-streaming) (from search results; not opened)
- **AI Elements:**
  - What it is: "A component library and custom registry built on top of shadcn/ui". Components include Conversation, Message, Sources, Inline Citation, Prompt Input, Reasoning, Chain of Thought, Shimmer, Suggestion and Code Block.
  - Status: the site says "**AI Elements is moving to shadcn/ui. This project will be deprecated at the end of November 2026.**"

  — [AI Elements](https://elements.ai-sdk.dev/)
- **AI Elements in shadcn/ui:** it is a set of shadcn/ui component compositions that you copy into the project, with no package to install. It was announced in shadcn's October 2026 changelog, and a migration prompt exists for existing code. The Loader component was deprecated in favour of the shadcn `Spinner`. — [shadcn/ui AI Elements](https://ui.shadcn.com/docs/ai-elements); [shadcn changelog 2026-10](https://ui.shadcn.com/docs/changelog/2026-10-ai-elements); [ai-elements releases](https://github.com/vercel/ai-elements/releases)
- **InfoQ's view:** shadcn's chat primitives (Aug 2026) do not force existing AI Elements users to rewrite anything. — [InfoQ](https://infoq.com/news/2026/08/shadcn-conversational-primitives)
- **assistant-ui:** "Components, runtimes, and primitives for building AI chat interfaces in React, Vue, React Native, and the terminal". Runtimes include Vercel AI SDK, LangGraph, LangChain, AG-UI, A2A and "Your own server". Setup is `npx assistant-ui@latest setup`. — [assistant-ui docs](https://www.assistant-ui.com/docs)

### Inferences
**Recommendation:** Next.js 16 + `@ai-sdk/react` v7 `useChat` (default `DefaultChatTransport`, `api: '/api/chat'`) + shadcn/ui with the **shadcn-hosted AI Elements** patterns. Use Conversation, Message, Sources/Inline Citation and Prompt Input, and start on the shadcn version rather than the soon-deprecated `elements.ai-sdk.dev` registry. Use assistant-ui instead only if you want a more opinionated thread UI.

**Python emitter:** hand-roll it. It adds no dependency, stays version-agnostic, and is easy to unit-test. Before relying on them, verify the exact field names of `source-url`, `source-document` and `data-*` against the v7 protocol page (`sourceId`, `url`, `title`, `data`, `transient` follow the v5/v6 shape).
```python
import json, uuid
from fastapi.responses import StreamingResponse

def sse(part: dict) -> str:
    return f"data: {json.dumps(part, ensure_ascii=False)}\n\n"

async def ui_stream(question: str):
    yield sse({"type": "start", "messageId": uuid.uuid4().hex})
    docs = await retrieve(question)                      # pgvector
    for d in docs:
        yield sse({"type": "source-url", "sourceId": d.id, "url": d.url, "title": d.title})
    yield sse({"type": "text-start", "id": "t"})
    try:
        async for delta in llm_stream(question, docs):   # OpenAI-compatible, stream=True
            yield sse({"type": "text-delta", "id": "t", "delta": delta})
    except LLMUnavailable:
        yield sse({"type": "data-status", "data": {"llm": "offline"}})
    yield sse({"type": "text-end", "id": "t"})
    yield sse({"type": "finish"})
    yield "data: [DONE]\n\n"

# in the route:
return StreamingResponse(ui_stream(q), media_type="text/event-stream",
    headers={"x-vercel-ai-ui-message-stream": "v1", "Cache-Control": "no-cache"})
```
- **Unit test:** parse each `data:` line as JSON and assert the part order (start, then sources, then text, then finish, then [DONE]).
- **Offline handling:** if the LLM is offline, still stream the retrieved sources plus a short Vietnamese message ("Mô hình đang ngoại tuyến – dưới đây là các đoạn liên quan"), which gives a retrieval-only degraded answer. Send `error` parts only for real failures.
- **Health badge:** a `GET /api/health` FastAPI route pings `{LLM_BASE_URL}/models` with a 2–3 s timeout and returns `{llm: "online"|"offline", db: "ok"}`. The UI polls it (e.g. every 30 s, or on focus) and shows a badge, and can disable or annotate the send button.
- **Citations:** number the sources in the prompt (`[1]`, `[2]`), render the `source-url` parts as an AI Elements Sources list, and turn the `[n]` markers into Inline Citation hovercards.
- **Markdown:** AI Elements' Message/Response uses a streaming-friendly markdown renderer. I did not verify the name (Streamdown); otherwise use `react-markdown` with `remark-gfm`.
- **Vietnamese fonts:** use `next/font/google` with `subsets: ['latin', 'vietnamese']`, e.g. Be Vietnam Pro or Inter, both of which have Vietnamese subsets on Google Fonts. Set `<html lang="vi">`. For DB full-text search, normalise Unicode to NFC on ingest and query, since Vietnamese text often mixes NFC and NFD forms. These are standard practice, not verified in this session.

### Gaps
- I did not open the v7 stream-protocol page directly. The page fetched at ai-sdk.dev/docs had no version label. Exact JSON field names for `source-url`/`source-document`/`data-*` in v7 should be verified, and so should whether v7 changed the header value from `v1`.
- Whether Pydantic AI's adapter emits v7-compatible streams is unknown (only v5/v6 documented).
- The Streamdown renderer name and the AI Elements install command for the shadcn version were not confirmed.

---

## 4. Making the LLM base URL changeable without redeploy (tunnel URL changes)

### Takeaway
Store the current tunnel URL in a **Supabase `app_config` row**. Have the Kaggle notebook write it at startup, and have FastAPI read it with a short in-process TTL cache. This costs nothing, needs no redeploy, and works even though the URL changes every session. Vercel Global Config (formerly Edge Config) also works, but the Hobby quota is tight (1 store, 100 writes and 100k reads per month, up to 10 s propagation). Env var plus redeploy is slowest, and it uses deployments and build time.

### Cited Findings
- **Global Config on Hobby:**
  - Rename: it is the renamed Edge Config.
  - Hobby quota: **1 store** in total and per project, **1 MB** max store size, **100,000 reads** and **100 writes** included per month.
  - Behaviour: writes take **up to 10 seconds** to propagate globally, and Vercel advises against using it for frequently updated data.
  - SDK: reads count once per `getAll()`.

  — [Global Config limits](https://vercel.com/docs/global-config/global-config-limits)
- **Env vars require a redeploy:** framework-prefixed system env vars are build-time only. There are 1,000 env vars per environment and a 64 KB total per deployment. — [Vercel limits](https://vercel.com/docs/limits)
- **Deploy hooks:** 5 per project, 60 triggers per hour per project. Hobby allows 100 deployments per day and 1 concurrent build. — [Vercel limits](https://vercel.com/docs/limits)

### Inferences
**Option comparison:**

| Option | Change latency | Free-tier cost | Complexity | Notes |
|---|---|---|---|---|
| **Supabase `app_config` table** (recommended) | Instant, bounded by the cache TTL (e.g. 30–60 s) | None; it is the DB you already have | Low: one table, a few lines of code | Kaggle can **self-register**: on startup it upserts `llm_base_url` with a dedicated write-only key or RPC. Also store `llm_api_key_version` and `updated_at` so health can show "last seen". RLS: anon gets no access, the backend reads via service role or direct DB. |
| Vercel Global Config | ≤ 10 s | 100 writes and 100k reads per month on Hobby | Low–medium; needs a token to write via the REST API | Fine for a few URL changes per day. Every chat request costs one read unless cached. The Python read SDK is unverified, so you may need raw HTTP. |
| Env var + deploy hook | 1–3 min (a full build) | Uses 1 of 100 deployments per day and blocks the single build slot | Low | Redeploys the frontend too. The hook URL is a secret, and Kaggle would call it. Simplest to reason about, slowest in practice. |
| Stable tunnel hostname | None needed | A domain is needed for a named Cloudflare Tunnel (inference) | Medium | Removes the problem at its root. Out of scope for verification here. |

- Whatever the source, also keep `LLM_BASE_URL` as an env-var fallback, plus `LLM_API_KEY` as a Sensitive env var. Rotating the key does require a redeploy, but that is rare.

### Gaps
- Whether Global Config has an official Python SDK (vs REST only) was not verified.
- Cloudflare quick-tunnel vs named-tunnel behaviour and requirements were not researched here; another researcher may have covered them.

---

## 5. GitHub Actions CI/CD: checks, deploy strategy, branch protection, path filters, Supabase migrations, eval gate, keep-alive, Dependabot, secrets

### Takeaway
On Hobby with a personal-account repo:
- **Deploys:** let Vercel's Git integration build a preview per PR and production on `main`.
- **CI:** GitHub Actions runs lint, types and tests for both languages, plus a retrieval-only eval. One aggregate "ci-ok" job is the required check under branch protection.
- **Migrations:** applied with `supabase db push` from Actions on `main`.

Switch to Actions-driven deploys (`vercel pull/build/deploy --prebuilt`, with Git auto-deploy disabled) if the repo is org-owned or you need deploys gated on CI. Keep Supabase awake with a daily Vercel cron and/or a 3-day GitHub schedule.

### Cited Findings
- **Vercel CLI deploys from Actions:**
  - Secrets: `VERCEL_TOKEN`, `VERCEL_ORG_ID` and `VERCEL_PROJECT_ID` (the last two come from `.vercel/project.json` after `vercel link`).
  - Preview steps: `vercel pull --yes --environment=preview --token=…`, then `vercel build --token=…`, then `vercel deploy --prebuilt --token=…`.
  - Production steps: the same with `--environment=production`, `vercel build --prod` and `vercel deploy --prebuilt --prod`.
  - Avoiding double deploys: set `"git": { "deploymentEnabled": false }` in `vercel.json`.
  - Monorepo example: a Turborepo/pnpm job gates the deploy jobs via `needs: build-and-test`. Multiple projects are handled with separate secrets such as `VERCEL_PROJECT_ID_APP`.

  — [Vercel: GitHub Actions guide](https://vercel.com/kb/guide/how-can-i-use-github-actions-with-vercel)
- **Hobby limits relevant to CI:** 100 deployments per day, 100 builds per hour, 1 concurrent build, and no Git integration with org-owned repos. A changelog title notes that "Skipped monorepo deployments no longer count against limits". — [Vercel limits](https://vercel.com/docs/limits)
- **Deployment Protection on Hobby:**
  - Standard Protection (all plans) protects everything except production domains, and Vercel Authentication is available.
  - Password Protection is not available on Hobby.
  - Same-domain requests do not need a bypass. Protection Bypass for Automation exists for CI; its Hobby availability was not explicitly stated on the fetched page.

  — [Deployment Protection](https://vercel.com/docs/deployment-protection)
- **Running preview checks:** Vercel's GitHub Actions guide uses `VERCEL_AUTOMATION_BYPASS_SECRET` for E2E against protected previews, and the Python backend guide recommends `vercel curl` for protected checks. — [Vercel: GitHub Actions guide](https://vercel.com/kb/guide/how-can-i-use-github-actions-with-vercel); [Python backend guide](https://vercel.com/kb/guide/python-backend-on-vercel)
- **Supabase migrations in CI:**
  - Deploy workflow: `supabase/setup-cli@v1` (`version: latest`), then `supabase link --project-ref $SUPABASE_PROJECT_ID`, then `supabase db push --yes --remote`. Env vars: `SUPABASE_ACCESS_TOKEN`, `SUPABASE_DB_PASSWORD` and `SUPABASE_PROJECT_ID`.
  - PR CI workflow: `supabase db start`, then `supabase db diff --strict-coverage` (pg-delta engine only), then regenerate types and diff them.
  - Token scope: the token needs read access to Project Settings, API Keys and API Key Secrets.

  — [Supabase: managing environments](https://supabase.com/docs/guides/deployment/managing-environments)
- **Migrations and old deployments:** with a shared DB, migrations run before the new deployment serves traffic and must stay compatible with older deployments. — [Python backend guide](https://vercel.com/kb/guide/python-backend-on-vercel)
- **uv in GitHub Actions:** use `astral-sh/setup-uv` (the docs pin it by SHA, `# v9.0.0`) with `enable-cache: true`. Pin the uv version, run `uv python install`, which respects `.python-version`, run `uv sync --locked --all-extras --dev` (`--locked` fails on a stale lockfile), then `uv run pytest`. — [uv: GitHub Actions integration](https://docs.astral.sh/uv/guides/integration/github/)
- **Dependabot and uv:** version updates for uv have been GA since 2025-03-13, and security updates since 2025-12-16. Known pitfalls:
  - `versioning-strategy` is unsupported, so lower bounds get rewritten.
  - Lockfile-only updates are unreliable.
  - Mitigations: add `uv lock --check` in CI and a `cooldown`. Renovate also supports uv.

  — [GitHub changelog (uv GA)](https://github.blog/changelog/2025-03-13-dependabot-version-updates-now-support-uv-in-general-availability/); [GitHub changelog (security updates)](https://github.blog/changelog/2025-12-16-dependabot-security-updates-now-support-uv/); [Classmethod: Dependabot uv pitfall](https://dev.classmethod.jp/en/articles/dependabot-uv-versioning-pitfall/); [uv: Dependabot](https://docs.astral.sh/uv/guides/integration/dependabot/)
- **Push protection:** user-level push protection is on by default on GitHub.com and blocks pushing secrets to public repos. Repo-level push protection requires GitHub Secret Protection and is off by default. — [GitHub: about push protection](https://docs.github.com/en/code-security/secret-scanning/introduction/about-push-protection)
- **Supabase pausing:** Free projects with "low activity over a 7-day period" are paused. "A few user requests to the database each day over the previous week" is typically enough to avoid it. A warning email goes out about one week before. A paused project can be restored for **up to 1 year**. Only paid plans are guaranteed not to pause. — [Supabase: project pausing](https://supabase.com/docs/guides/platform/free-plan-pausing); [Supabase FAQ](https://supabase.com/kb/faqs/platform/free-project-pausing)
- **Community keep-alive pattern:** a scheduled GitHub Action pings the DB, e.g. twice a week or every 3 days. This is anecdotal; Supabase has not endorsed it. — [DEV: GitHub Actions keep-alive](https://dev.to/jps27cse/how-to-prevent-your-supabase-project-database-from-being-paused-using-github-actions-3hel); [travisvn/supabase-pause-prevention](https://github.com/travisvn/supabase-pause-prevention)
- **Vercel cron jobs on Hobby:** they still work and are labelled "legacy", to be migrated to Schedules. Hobby allows up to 100 per project, **once per day**, with **±59 min** precision; more frequent expressions fail the deploy. They run only on production deployments, and Vercel sends `Authorization: Bearer $CRON_SECRET`. — [Cron usage and pricing](https://vercel.com/docs/cron-jobs/usage-and-pricing); [Ship a FastAPI app](https://vercel.com/kb/guide/ship-a-fastapi-app-on-vercel)
- **Vercel Schedules (beta) on Hobby:** at most every 15 minutes with a fixed 15-minute jitter, up to 100 static schedules per deployment, and 5,000 runs plus 500 dynamic schedules per billing period. Over the limit, runs are skipped until the next period. — [Schedules limits](https://vercel.com/docs/schedules/limits)
- **Secrets visibility:** Development values are Config variables that `vercel env pull` can read. Preview and Production Secrets cannot be pulled. — [Python backend guide](https://vercel.com/kb/guide/python-backend-on-vercel)

### Inferences
**Workflow design (minimal set):**

1. **`ci.yml`** (on `pull_request` and `push: main`, with `concurrency: ci-${{ github.ref }}` and `cancel-in-progress: true`):
   - `changes`: path filter (e.g. `dorny/paths-filter`) that outputs `web`, `api`, `db` and `pipelines`.
   - `web` (if web): `pnpm/action-setup`, then `actions/setup-node` with `cache: pnpm`, then `pnpm i --frozen-lockfile`, `pnpm lint` (ESLint), `pnpm typecheck` (`tsc --noEmit`), `pnpm test` (Vitest) and `pnpm build`.
   - `api` (if api or pipelines): `astral-sh/setup-uv` with `enable-cache` and `working-directory: backend`, then `uv lock --check`, `uv sync --locked`, `uv run ruff check`, `uv run ruff format --check`, `uv run pyright` (or mypy), and `uv run pytest`. The tests include a protocol test of the SSE emitter and a mocked LLM via `respx`/httpx.
   - `db` (if db or api): `supabase/setup-cli@v1`, then `supabase db start`. This should apply local migrations; verify whether `supabase db reset` is needed. Then the pgvector smoke test.
   - `eval-retrieval` (if api, db or pipelines): seed the local Supabase with a small fixture corpus and **precomputed embeddings committed to the repo**, plus a golden set of question → expected chunk IDs, also with precomputed query vectors. Compute recall@k, MRR and nDCG, and fail below a threshold. This makes the eval deterministic and independent of Kaggle.
   - `ci-ok`: `needs: [all above]`, `if: always()`, and fails if any needed job failed. Make **only `ci-ok`** the required status check. With path filters, individually-required jobs can be skipped and leave PRs stuck "pending" or wrongly green; standard GitHub behaviour, not re-verified here.
2. **Branch protection or ruleset on `main`:** require a PR, require `ci-ok` to pass, block force-push, require linear history (optional). Production deploys then only ever see CI-green code, even though Vercel's Git integration deploys independently of Actions.
3. **`e2e.yml`** (on `deployment_status` with `state == success`, which Vercel's GitHub integration emits): run Playwright against `github.event.deployment_status.target_url`, sending the `x-vercel-protection-bypass` header from `VERCEL_AUTOMATION_BYPASS_SECRET` when previews are protected. Assert that the page renders, `/api/health` returns JSON, and a chat returns a stream. Allow `llm: offline` and check for sources only.
4. **`db-deploy.yml`** (on `push: main` with `paths: supabase/migrations/**`): `supabase link` then `supabase db push`. Use additive or expand-contract migrations only, because previews and production share one free DB, and Supabase Free allows 2 active projects, so no separate staging DB unless you spend the second slot.
5. **`eval-full.yml`** (`workflow_dispatch` plus a weekly `schedule`): call `/api/health` or the LLM `/models` first. If offline, run retrieval-only metrics, write a job summary saying "generation skipped: LLM offline", and exit 0. If online, also run generation metrics such as faithfulness, answer relevance and citation correctness, and upload the report as an artifact. Never block PR merges on an LLM that may be offline.
6. **Keep-alive:** the simplest, GitHub-independent option is a **Vercel daily cron** to `/api/cron/keepalive`. It checks `CRON_SECRET` and runs `select 1` plus a cheap pgvector query, which also warms the function. Optionally add **`keepalive.yml`** (`cron: '0 3 */3 * *'`) that queries Supabase via psql or REST, so the DB is still pinged if the Vercel project is broken. Caveat: GitHub disables scheduled workflows in public repos after 60 days without repo activity (standard GitHub behaviour; not re-verified here).
7. **Actions-driven deploys** (use if the repo is org-owned or you want "deploy only if CI passes"): add `"git": {"deploymentEnabled": false}` and a `deploy` job with `needs: ci-ok` running `vercel pull/build/deploy --prebuilt`. Post the preview URL as a PR comment. This must be validated for Services projects (see Gaps).
8. **Dependabot:** `.github/dependabot.yml` with ecosystems `npm` (`/frontend`; pnpm lockfiles are handled by the npm ecosystem), `uv` (`/backend` and `/pipelines`) and `github-actions` (`/`). Set a weekly schedule, grouping, and a cooldown. Keep `uv lock --check` in CI.
9. **Secret scanning:** a public repo gets push protection by default at the user level. Also add a `gitleaks` step in CI (inference: common practice), and never commit `.env*` or `.vercel/`.

**Env and secrets handling:**
- **Vercel project env vars**, set per environment (Development, Preview, Production):
  - `DATABASE_URL` (pooler, port 6543), `LLM_API_KEY`, `LLM_BASE_URL` (fallback), `CRON_SECRET`, `UPSTASH_REDIS_REST_URL`/`UPSTASH_REDIS_REST_TOKEN`, `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`/`LANGFUSE_HOST`.
  - Mark secrets as Sensitive.
  - Only non-secret values may use the `NEXT_PUBLIC_` prefix.
  - Preview should use a read-only DB role, or the same DB with RLS, if you worry about preview code mutating production data.
- **GitHub Actions secrets:**
  - `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` (only if using CLI deploys).
  - `SUPABASE_ACCESS_TOKEN`, `SUPABASE_DB_PASSWORD`, `SUPABASE_PROJECT_ID`.
  - `VERCEL_AUTOMATION_BYPASS_SECRET`.
  - Optional `LLM_BASE_URL`/`LLM_API_KEY` for the full eval.
  - Put production-mutating jobs (db push) in a GitHub Environment `production` so their secrets are scoped.
- **Local dev:** `vercel link`, then `vercel env pull .env.local --environment development`, then `vercel dev` (it runs both services).

### Gaps
- I did not confirm that `vercel build` / `--prebuilt` supports Services projects end-to-end.
- I did not confirm that Protection Bypass for Automation is available on Hobby; the fetched page did not state its plan availability.
- Not re-verified in this session: GitHub's 60-day scheduled-workflow auto-disable and the `deployment_status` event emission by Vercel. Both are long-standing behaviours.
- Supabase does not document an exact activity threshold, so keep-alive frequency is a heuristic.

---

## 6. Rate limiting and abuse protection for a public demo; API-key auth between Vercel and the tunnel

### Takeaway
Layer three free controls:
1. **One Vercel WAF rate-limit rule** on `/api/chat` (Hobby allows 1 rule, fixed window, keyed by IP or JA4, 1M allowed requests included).
2. An app-level per-IP and **global daily budget** in **Upstash Redis free** (500K commands/month).
3. Optionally **BotID Basic**, which is free but needs a JS server check.

Protect the Kaggle tunnel with a shared bearer key stored only in Vercel env vars.

### Cited Findings
- **WAF rate limiting** is available on all plans. Hobby gets: counting keys IP and JA4 Digest, the Fixed window algorithm, a 10 s – 10 min window, **1 rule per project** (within the total of **3 custom firewall rules**), and **1,000,000 allowed requests** included. Actions: 429 (default), Log, Deny or Challenge. Counters are tracked per region. — [WAF rate limiting](https://vercel.com/docs/vercel-firewall/vercel-waf/rate-limiting)
- **Firewall placement with Services:** firewall rules apply at the top-level public surface, across all services. — [Vercel Services](https://vercel.com/docs/services)
- **BotID** is available on all plans. Basic validation is free on all plans. Deep Analysis (Kasada) costs Pro $1 per 1,000 `checkBotId()` calls and is not on Hobby. Flow: a client challenge, then server-side `checkBotId()`. A changelog title says BotID is "now available for all frameworks". — [Vercel BotID](https://vercel.com/docs/botid)
- **Upstash Redis free:** 500K commands per month, 256 MB max data size (the plan card says 250 MB), 10 GB bandwidth, 1 database, 10,000 max commands per second. The pricing page does not mention `@upstash/ratelimit`. — [Upstash Redis pricing](https://upstash.com/pricing/redis)
- **Vercel's own guidance** adds no auth to example endpoints and warns that you must protect them before exposing them publicly. — [Python and AI SDK guide](https://vercel.com/kb/guide/python-and-ai-sdk)

### Inferences
- **Rule 1 (WAF):** `Request Path equals /api/chat` → Rate Limit, e.g. 10 requests per 60 s per IP, action 429. Use "Log" first to calibrate. It runs before the function, so blocked requests cost no function time.
- **Rule 2 (app):** a FastAPI dependency that keeps an Upstash counter per IP per day, e.g. 30 chats, plus a **global** daily cap, e.g. 500, to protect the single Kaggle GPU and the 360 GB-hr memory budget. One chat costs about 2–4 Redis commands, so 500K commands per month is ample. Use Upstash's REST API via httpx (a few lines) to avoid adding a dependency, or the Python ratelimit client (existence not verified here).
- **Input caps:** limit message length (e.g. 2,000 characters) and history (last N turns) in Pydantic validation. Reject requests with oversized bodies.
- **BotID with a Python backend:** `checkBotId()` is a JS server API, so it only fits if the chat request passes through a Next.js Route Handler (the private-binding pattern), which doubles function time. For a demo the WAF rule plus Upstash is enough. Add BotID only if abuse shows up.
- **Tunnel auth:**
  - Run the LLM server with an API key, e.g. the OpenAI-compatible servers' `--api-key`, or a reverse proxy in the notebook checking `Authorization: Bearer`.
  - Store the key in a Vercel Sensitive env var (`LLM_API_KEY`). Never ship it to the browser, and never accept a base URL from the client.
  - Optionally add an `X-Client` HMAC header. Rotate the key per Kaggle session if self-registration writes a new key version.
  - Validate the base URL read from Supabase against an allowlist pattern (e.g. `^https://[a-z0-9-]+\.trycloudflare\.com$`) to block SSRF via a tampered config row.
- **Deployment Protection:** keep Standard Protection on, so previews require Vercel login while the production domain stays public.

### Gaps
- I did not verify a current Upstash Python rate-limit SDK or the exact `@upstash/ratelimit` command cost per check.
- How BotID integrates with non-JS frameworks ("all frameworks") was not read in detail.

---

## 7. Observability for LLM apps on free tiers: Langfuse, Vercel logs, OpenTelemetry

### Takeaway
Use **Langfuse Cloud Hobby**: 50k units per month, 30-day data access, 2 users, no credit card, Python SDK v5 built on OpenTelemetry. Trace retrieval and generation spans, and call `flush()` before the streaming generator ends. Vercel's built-in Observability is automatic, but **runtime logs are kept only 1 hour on Hobby**, so don't rely on them for debugging after the fact.

### Cited Findings
- **Langfuse Hobby:** 50,000 billable units per month (traces, observations and scores all count), 1,000 requests per minute ingestion, 30 days of data access, 2 users, unlimited projects, no credit card. Self-hosting is free (open source). — [Langfuse pricing](https://langfuse.com/pricing)
- **Langfuse SDKs:** Python **v5** and JS/TS v6 require Langfuse server v4. They are based on OpenTelemetry. Python uses `get_client()` and `start_as_current_observation(...)`. In short-lived apps call `langfuse.flush()`; on JS call `sdk.shutdown()`. — [Langfuse Python SDK overview](https://langfuse.com/docs/observability/sdk/python/overview)
- **Langfuse and AI SDK 7:** Langfuse published a changelog entry for AI SDK 7 support. — [Langfuse changelog](https://langfuse.com/changelog/2026-06-26-vercel-ai-sdk-7)
- **Vercel log retention:** runtime logs are stored **1 hour on Hobby** (1 day on Pro, 3 days on Enterprise). Build logs are kept indefinitely. — [Vercel limits](https://vercel.com/docs/limits)
- **Vercel Observability** is automatic: invocations, errors, durations, and outgoing external API requests for the FastAPI function. Observability Plus (paid) adds retention and per-path latency. — [Ship a FastAPI app](https://vercel.com/kb/guide/ship-a-fastapi-app-on-vercel)
- **Tracing across services** is not configured by default. OpenTelemetry would have to be added to both runtimes. — [Python backend guide](https://vercel.com/kb/guide/python-backend-on-vercel)

### Inferences
- **Budget:** about 3–5 Langfuse units per chat (a trace, a retrieval span, a generation, an optional score) gives roughly 10–15k chats per month within the free tier. Sample if needed.
- **What to log per trace:**
  - query (optionally hashed), top-k chunk IDs and scores, latency per stage;
  - LLM online/offline, token counts (if the server returns usage), and the model name from the self-registered config;
  - the user's 👍/👎 as a Langfuse score from a small `/api/feedback` route.
- **Flushing on Vercel:** call `flush()` in a `finally:` at the end of the SSE generator. Shutdown hooks get only 500 ms and their logs are invisible.
- **Durable request logs:** with 1-hour runtime-log retention, add structured JSON logs to Langfuse metadata, or a small `chat_logs` table in Supabase (watch the 500 MB limit). Log drains are a paid-plan feature (not verified here).

### Gaps
- I did not verify whether Langfuse's Python `langfuse.openai` drop-in wrapper supports a custom `base_url` in SDK v5 (the overview did not cover it).
- I did not check whether Vercel log drains or OTel export are available on Hobby.

---

## 8. Supabase free tier limits (2026) and connecting from serverless Python

### Takeaway
Supabase Free gives:
- **2 active projects**, **500 MB DB**, 5 GB egress and 1 GB storage;
- no backups and 1-day log retention;
- **pausing after one week of low activity**, restorable for up to 1 year.

From Vercel Python, connect through the **shared Supavisor pooler in transaction mode, port 6543** (IPv4 on every plan). Use pool size 1 and disable prepared statements. The direct connection is IPv6-only unless you buy the IPv4 add-on (Pro). `supabase-py` (PostgREST over HTTPS) avoids pooling issues but is a heavier dependency set.

### Cited Findings
- **Free plan:** 2 active projects; 500 MB database per project (shared CPU, 500 MB RAM); 5 GB egress plus 5 GB cached egress; 1 GB file storage; 50 MB max upload; 50,000 MAU; 500,000 Edge Function invocations; unlimited API requests; no backups; 1-day API/DB log retention. "Free projects are paused after 1 week of inactivity". — [Supabase pricing](https://supabase.com/pricing)
- **Restoring:** a paused project can be restored for up to 1 year, with data and config intact. — [Supabase: project pausing](https://supabase.com/docs/guides/platform/free-plan-pausing)
- **Connection modes:**
  - **Direct**: port 5432, `db.[ref].supabase.co`, IPv6 (or IPv4 with the add-on). Use it for persistent servers, migrations and `pg_dump`.
  - **Shared pooler, session mode**: port 5432, user `postgres.[ref]`, host `aws-[INDEX]-[REGION].pooler.supabase.com`. IPv4 on every plan, supports prepared statements.
  - **Shared pooler, transaction mode**: **port 6543**. This is the one for serverless and edge functions. No prepared statements, no pipelining, and session state (SET, advisory locks, LISTEN/NOTIFY, temp tables) does not persist.
  - **Dedicated PgBouncer**: Pro and above.
  - Serverless advice: pool max 1 and prepare off. asyncpg needs `statement_cache_size=0`. The IPv4 add-on is Pro+ and not dual-stack.

  — [Supabase: connecting to Postgres](https://supabase.com/docs/guides/database/connecting-to-postgres)
- **CLI migrations from CI:** `supabase link` plus `supabase db push`. Note that `supabase link` requires an access token. — [Supabase: managing environments](https://supabase.com/docs/guides/deployment/managing-environments)

### Inferences
**Driver choice for a lightweight backend:**

| Option | Pros | Cons |
|---|---|---|
| **`psycopg[binary]` 3 (recommended)** | Small. Plain SQL `ORDER BY embedding <=> %s LIMIT k` or calling an RPC function. Works on port 6543. | Prepared statements must be disabled for transaction mode (`prepare_threshold=None` per psycopg docs; not verified here). Open one connection per request, or keep a module-level connection with reconnect-on-error. |
| `asyncpg` | Fast, async. | Must set `statement_cache_size=0` (documented). |
| `supabase-py` (PostgREST via `rpc('match_documents', …)`) | No pooler or IPv6 concerns, HTTPS only. | Pulls several sub-packages (auth, storage, realtime, postgrest). Every query must be a SQL function exposed via PostgREST, and needs a service-role key on the server. |

- **Vercel's guide pattern** keeps two URLs: `DATABASE_URL` (pooled, runtime) and `DATABASE_URL_UNPOOLED` (direct, for migrations, which CI runs via the Supabase CLI instead).
- **The 500 MB limit is the real RAG constraint:**
  - A 1024-dim float32 vector is about 4 KB, so 50k chunks ≈ 200 MB of vectors plus an HNSW index of similar order plus the text.
  - Use pgvector `halfvec` (2 bytes per dimension) or a smaller embedding dimension, keep only the needed text, and monitor DB size in CI or with a weekly job.
  - These are back-of-envelope estimates, not measured.
- **2 active projects** means one prod project plus one optional staging/CI project at most. CI can instead use `supabase db start` locally in the runner, which costs no cloud project.
- **Region:** pick `ap-southeast-1` (Singapore) for the Supabase project and colocate the Vercel function region there (see section 1).

### Gaps
- I did not verify the exact psycopg 3 settings Supabase recommends (the docs page links a KB article I did not open).
- Whether Vercel Functions have outbound IPv6 (which would make the direct connection usable) was not checked. Use the pooler regardless.
- No official 2026 changelog for Supabase free-tier changes was found. The pricing page has no dates.
