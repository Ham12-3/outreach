# Outreach Operations Agent

An AI agent that runs a sales/outreach **lead pipeline** end to end. You give it a
goal in plain English — *"Find product managers at US AI startups, store them,
score them, draft a first-touch message for each, and queue them"* — and the
agent **plans the steps and executes them**, asking for your confirmation before
it writes anything to the database.

Built for the **Google Cloud Rapid Agent Hackathon — MongoDB partner track**.

- **Brain:** Gemini 3 (`gemini-3.1-pro-preview`) via the Gemini Enterprise Agent
  Platform / Vertex AI.
- **Framework:** Google **Agent Development Kit (ADK)** for Python.
- **Superpower:** the **MongoDB MCP server**, connected to the agent as an ADK
  toolset. This is the core of the project — the agent reads and writes leads in
  MongoDB Atlas entirely through MCP tools.

---

## What it does

1. **Find / accept leads** — loads ~20 realistic sample leads from a seed file so
   the demo runs fully offline (no external lead source needed).
2. **Store leads in MongoDB** — via the MongoDB MCP server (`insert-many`).
3. **Score & segment** — a simple, explainable 0–100 rubric → Hot / Warm / Cold,
   with a reason for every point.
4. **Draft outreach** — a short, plain-English message per lead (opener + bridge
   + call to action, under 60 words).
5. **Track status** — each lead moves `new → scored → drafted → queued →
   contacted → replied`, persisted to MongoDB as the agent works.
6. **Keep you in control** — before **any** database write, the agent summarises
   exactly what it will do and waits for your `y/n` confirmation.

---

## Architecture (in words)

```
            You (plain-English goals, y/n confirmations)
                                │
                                ▼
                    ┌───────────────────────┐
                    │   CLI chat loop        │   main.py
                    │   (ADK Runner)         │
                    └───────────┬───────────┘
                                │ events (text, tool calls, results)
                                ▼
                    ┌───────────────────────┐
                    │   LlmAgent (Gemini 3)  │   outreach_agent/agent.py
                    │   plans + executes     │
                    └───────────┬───────────┘
              before_tool_callback│  (human-in-the-loop write gate)
                                ▼
        ┌───────────────────────┴───────────────────────┐
        │                                                │
        ▼                                                ▼
┌───────────────────┐                      ┌──────────────────────────┐
│ Custom tools      │                      │ MongoDB MCP toolset       │
│ (pure Python)     │                      │ (the partner superpower)  │
│ • load_seed_leads │                      │  npx mongodb-mcp-server   │
│ • score_lead      │                      │  via StdioConnectionParams│
│ • draft_message   │                      │  find / insert-many /     │
└───────────────────┘                      │  update-many / ...        │
                                           └─────────────┬────────────┘
                                                         ▼
                                              ┌─────────────────────┐
                                              │ MongoDB Atlas        │
                                              │ db: outreach         │
                                              │ collection: leads    │
                                              └─────────────────────┘
```

**How a request flows:** You type a goal. The Gemini 3 agent plans the steps and
starts calling tools. The *business logic* (loading leads, scoring, drafting)
runs as plain Python **function tools** so it's deterministic and auditable. All
*storage* goes through the **MongoDB MCP server**, which ADK launches on demand
via `npx` and exposes to the agent as tools (`find`, `insert-many`,
`update-many`, …). Every tool call passes through a `before_tool_callback`: read
tools run straight through, but any **write** tool is paused — the agent prints a
plain-English summary and waits for your confirmation before the data is changed.

### Why this design

- **MCP is central, not bolted on.** The agent has no hand-written MongoDB code —
  it talks to the database purely through the MongoDB MCP server's tools. Swapping
  clusters is just a connection-string change.
- **Explainable where it matters.** Scoring and drafting are plain Python so a
  judge can read exactly how a lead got its score and message.
- **Safe by default.** Nothing is written without an explicit human `y/n`.

---

## Project layout

```
outreach/
├── main.py                     # CLI chat interface (ADK Runner)
├── requirements.txt
├── Dockerfile                  # for Cloud Run (Python + Node for npx)
├── .env.example                # copy to .env and fill in
├── LICENSE                     # MIT
├── README.md
├── SETUP.md                    # exact local + Cloud Run steps
├── data/
│   └── seed_leads.json         # ~20 realistic sample leads (offline source)
├── outreach_agent/
│   ├── __init__.py             # exposes root_agent for `adk run`/`adk web`
│   ├── agent.py                # LlmAgent + MongoDB MCP toolset wiring
│   ├── prompts.py              # the agent's system instruction
│   ├── config.py               # env / settings loader
│   ├── scoring.py              # the lead-scoring rubric
│   ├── drafting.py             # the message-drafting logic
│   ├── tools.py                # custom function tools (ADK)
│   └── confirmation.py         # human-in-the-loop write gate
└── tests/
    └── test_logic.py           # offline tests for scoring/drafting/seed/gate
```

---

## Quick start

See **[SETUP.md](SETUP.md)** for the full, exact steps. In short:

```bash
# 1. install
python -m venv .venv && .venv/Scripts/activate    # Windows
pip install -r requirements.txt

# 2. configure
cp .env.example .env        # then fill in MDB_MCP_CONNECTION_STRING + GCP project

# 3. authenticate to Vertex AI (one time)
gcloud auth application-default login

# 4. run the agent
python main.py
```

Then try:

> Find product managers at US AI startups, store them, score them, draft a
> message for each, and queue them.

You'll watch the agent plan, call the MongoDB MCP tools, and pause for your
confirmation before each write.

---

## The scoring rubric (simple & explainable)

| Signal       | Max points | How it's earned                                  |
|--------------|-----------:|--------------------------------------------------|
| Title fit    | 40         | Title contains *product* / *growth*              |
| Seniority    | 25         | Exec/founder 25 · Head/Director 20 · Senior 14 · Manager 10 · Junior 5 |
| Industry fit | 20         | Company is in AI / ML / generative / agents / robotics |
| Region fit   | 15         | Lead is in the US                                |

**Segments:** Hot ≥ 70 · Warm 45–69 · Cold < 45. Every score comes with a
`reasons` list explaining each point awarded.

## The message format

Three fixed parts, plain English, under 60 words:

- **Opener** — greets by first name, references their role + company.
- **Bridge** — one sentence linking why we're reaching out to what they do
  (lightly tuned by segment).
- **CTA** — one low-friction ask.

---

## Testing

```bash
pytest        # 9 offline tests: scoring, drafting, seed loading, the write gate
```

These run without MongoDB or Gemini, so you can verify the core logic instantly.

---

## Tech & credits

- [Google Agent Development Kit (ADK)](https://google.github.io/adk-docs/)
- [Gemini 3 on Vertex AI](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/3-1-pro)
- [MongoDB MCP Server](https://github.com/mongodb-js/mongodb-mcp-server) — the
  partner integration at the heart of this project.

Licensed under the [MIT License](LICENSE).
