# LeadPilot

An agentic lead-generation pipeline that finds local SMBs, scrapes their contact emails, scores them, and sends personalised outreach — built on **LangGraph**, the **A2A (Agent-to-Agent) Protocol**, and **MCP (Model Context Protocol)**.

LeadPilot is both a course project demonstrating multi-protocol agent design and a real freelancing tool used to surface clients.

---

## Architecture

```
                         ┌────────────────────────────────┐
                         │           main.py              │
                         │  niche + countries from user   │
                         └───────────────┬────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────── LangGraph ────────────────────────────────────┐
│                                                                                   │
│   START ─► query_generator ─► lead_finder ─► enrich ─► score ─► router            │
│                ▲                                                  │                │
│                │                                                  ▼                │
│                └────── query_optimizer ◄──── (≤3 loops) ─── outreach ── END        │
│                                                                                   │
└──────────────┬────────────────────────────────────────────────────────────────────┘
               │ every node packages args into an A2A Task and calls:
               ▼
       ┌───────────────────┐         ┌──────────────────────────────────────┐
       │  A2ADispatcher    │ ──────► │ QueryGeneratorAgent (LLM)            │
       │  (in-process,     │         │ LeadDiscoveryAgent  (Apify Places)   │
       │  wire-compatible  │         │ EnrichmentAgent     (Playwright+MX)  │
       │  with HTTP A2A)   │         │ ScoringAgent        (100-pt + LLM)   │
       └───────────────────┘         │ OutreachAgent       ───┐             │
                                     └────────────────────────┼─────────────┘
                                                              │
                                                              ▼
                                              ┌────────────────────────────┐
                                              │ MCP Gmail server (HTTP)    │
                                              │  tool: send_email(...)     │
                                              └──────────┬─────────────────┘
                                                         │ (fallback if down)
                                                         ▼
                                              ┌────────────────────────────┐
                                              │ SMTP via utils/smtp.py     │
                                              └────────────────────────────┘
```

---

## How A2A is built into LeadPilot

The `a2a/` package implements the Google A2A open spec primitives — Tasks, Messages with typed Parts, Artifacts, AgentCards, AgentSkills — so every cross-agent call goes through a standard envelope rather than a direct Python call.

**Type layer — [a2a/types.py](a2a/types.py)**

```python
Task { id, agent_name, Message { role, parts: [DataPart{data}] } }
        │
        ▼
TaskResult { task_id, status, artifacts: [Artifact{ name, data }] }
```

`AgentCard` is each agent's capability declaration (`name`, `description`, `version`, `skills`). In a production A2A deployment these are served at `/.well-known/agent.json`; here they are listed in-process at startup.

**Dispatch layer — [a2a/dispatcher.py](a2a/dispatcher.py)**

`A2ADispatcher` is the router. Today it's in-process (`endpoint="in-process"`), tomorrow you swap the body for an HTTP POST to each agent's endpoint and the same Task/Artifact envelope works end-to-end.

```python
result = dispatcher.send(Task(
    id=uuid4(),
    agent_name="EnrichmentAgent",
    message=Message(role="user", parts=[DataPart(data={"raw_leads": [...]})]),
))
enriched = result.first("enriched_leads")
```

**Agent layer — [agents/](agents/)**

Each agent subclasses `A2AAgent` and implements two things:

- `agent_card` — declares capabilities
- `process(task) -> TaskResult` — does the work

| Agent | Skill ID | Output Artifact |
|-------|----------|-----------------|
| `QueryGeneratorAgent` | `generate-queries` | `queries` |
| `LeadDiscoveryAgent` | `fetch-places` | `raw_leads` |
| `EnrichmentAgent` | `scrape-emails` | `enriched_leads` |
| `ScoringAgent` | `score-leads` | `scored_leads`, `scoring_summary` |
| `OutreachAgent` | `send-outreach` | `emails` |

LangGraph nodes in [nodes.py](nodes.py) are intentionally thin — they only build the Task envelope and call `_dispatcher.send(...)`. All business logic lives behind the A2A boundary, so the same agents could be lifted out into separate processes without touching the graph.

---

## How MCP is built into LeadPilot

The `OutreachAgent` does **not** talk to Gmail directly. It calls a **Model Context Protocol** server that exposes a `send_email` tool, using the official `mcp` Python SDK over streamable HTTP.

**Why MCP here:** decouple the agent's business logic from the transport/auth layer to Gmail. The same agent can drive any MCP-compatible mailer, or a non-Gmail provider, without code changes.

**Client — [agents/outreach_agent.py](agents/outreach_agent.py)**

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client(f"{MCP_GMAIL_URL}/mcp") as (r, w, _):
    async with ClientSession(r, w) as session:
        await session.initialize()
        await session.call_tool(
            "send_email",
            {"to": to, "subject": subject, "body": html_body, "mimeType": "text/html"},
        )
```

On startup `_MCPGmailClient` probes `${MCP_GMAIL_URL}/.well-known/agent.json`. If the server is unreachable, or any tool call fails, the agent **transparently falls back to SMTP** via [utils/smtp.py](utils/smtp.py). This makes the MCP integration opt-in for dev environments.

---

## The lead-quality pipeline

1. **Query generation** — LLM (structured output, schema-enforced) produces 5–15 varied Google Maps queries per niche/country.
2. **Discovery** — Apify Google Places actor returns business records (title, website, phone, rating, reviews).
3. **Enrichment** — Playwright visits each website + contact/about/legal/imprint subpages, decodes Cloudflare-obfuscated emails, HTML entities, JSON-LD, and `[at]/[dot]` notation. Emails are filtered by **DNS MX lookup** (dnspython, cached). When no email is found, **pattern fallbacks** (`info@`, `contact@`, `hello@`, …) are synthesised at the lead's own domain and MX-verified.
4. **Scoring** — 100-pt: email 35, reviews 20, rating 15, website 10, phone 5, LLM category relevance 15. Threshold ≥ 40 = qualified.
5. **Outreach** — niche-matched portfolio chosen via keyword map in [templates/selector.py](templates/selector.py), HTML email built in [templates/email.py](templates/email.py) with inline screenshots, sent via MCP Gmail (SMTP fallback).
6. **Loop** — if no leads qualify, `query_optimizer` regenerates queries and the graph loops up to 3 times.

---

## Setup

### Prerequisites

- Python 3.13+
- Node 18+ (for the Playwright email scraper)
- A Supabase project (for lead persistence)
- An Apify account + API key (Google Places actor)
- An OpenAI API key
- A Gmail account with an app password (SMTP fallback) — and optionally an MCP Gmail server

### Install

```bash
git clone https://github.com/UmarAurangzeb/Lead-Pilot.git
cd Lead-Pilot

# Python deps
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Node deps for extractEmails.js
npm install
```

### Environment variables

Create a `.env` in the project root:

```bash
# Core
OPENAI_API_KEY=sk-...
APIFY_API_KEY=apify_api_...
DATABASE_URL=postgresql://postgres:<pwd>@db.<ref>.supabase.co:5432/postgres

# Outreach (SMTP fallback used if MCP server is offline)
EMAIL_USER=you@gmail.com
EMAIL_PASSWORD=<gmail-app-password>
EMAIL_SMTP_HOST=smtp.gmail.com        # optional, default smtp.gmail.com
EMAIL_SMTP_PORT=587                   # optional, default 587

# MCP Gmail (optional; SMTP is used if absent/unreachable)
MCP_GMAIL_URL=http://localhost:3100

# Email pipeline tuning (optional, defaults shown)
SCRAPE_EMAILS=true                    # set false to skip Playwright scrape
EMAIL_MX_CHECK=true                   # DNS MX filter on scraped emails
EMAIL_PATTERN_FALLBACK=true           # synthesise info@/contact@ if scrape is empty
EMAIL_SCRAPE_TIMEOUT_SEC=3600

# Run mode
OUTREACH_DRY_RUN=true                 # true = build emails but don't send
```

### Initialise the database

```bash
python supabase/tables.py
```

---

## Running

```bash
source venv/bin/activate
python main.py
```

You'll be prompted for:

```
Target niche [cleaning services]: healthcare
Target countries (comma-separated) [UK, US]: UK, US, ES
```

Brackets and quotes around the country list are accepted (`[UK, US]`, `'UK','US'`, etc.). Use ISO-3166 alpha-2 codes (`ES`, not `SP`).

**First run** auto-captures portfolio screenshots into `assets/screenshots/`.

### Dry-run mode

Set `OUTREACH_DRY_RUN=true` to run the full pipeline (queries, discovery, scrape, score, build emails) without actually sending. The outreach log will show `dry-run:<title>:<email>:template=<portfolio>` per lead.

### MCP Gmail server (optional)

To send via MCP instead of SMTP, run a Gmail MCP server that exposes a `send_email` tool on `MCP_GMAIL_URL` (default `http://localhost:3100`). The server must answer `/.well-known/agent.json` and accept streamable-HTTP MCP connections at `/mcp`. If it's not running, LeadPilot falls back to SMTP automatically.

---

## Project layout

```
LeadPilot/
├── main.py                  # interactive entry point
├── graphs.py                # LangGraph wiring
├── nodes.py                 # LangGraph node wrappers (Task envelopes)
├── state.py                 # LangGraph LeadState TypedDict
├── helpers.py               # Apify fetch, query gen, email scrape orchestration
├── llm.py                   # OpenAI client
├── memory.py                # Supabase lead persistence
├── prompts.py               # System / user prompts
├── schema.py                # Pydantic structured-output schemas
├── extractEmails.js         # Playwright email scraper (subprocess)
│
├── a2a/                     # A2A protocol primitives
│   ├── types.py             #   Task, Message, Part, Artifact, AgentCard, AgentSkill
│   └── dispatcher.py        #   in-process Task router
│
├── agents/                  # A2A agents (one per stage)
│   ├── base.py              #   A2AAgent ABC
│   ├── query_agent.py
│   ├── discovery_agent.py
│   ├── enrichment_agent.py
│   ├── scoring_agent.py
│   └── outreach_agent.py    #   contains MCP Gmail client + SMTP fallback
│
├── templates/               # Niche → portfolio mapping + HTML email builder
├── utils/
│   ├── smtp.py              # SMTP send helper (fallback)
│   └── email_validation.py  # DNS MX lookup + pattern fallbacks
├── supabase/
│   ├── init.py              # psycopg2 connection
│   └── tables.py            # schema bootstrap
└── assets/screenshots/      # portfolio screenshots (auto-captured)
```

---

## Tech

LangGraph · A2A Protocol · MCP (streamable HTTP) · OpenAI structured outputs · Apify Google Places · Playwright · dnspython · psycopg2 / Supabase · Pydantic
