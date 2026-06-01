# CLAUDE.md — RetailMind

## Project

RetailMind is an internal AI assistant for retail companies with two capabilities: Document Q&A (retrieval-augmented generation over uploaded PDFs) and Analytics Q&A (natural language → SQL over a Postgres retail database). A router decides which capability handles each question.

## Folder layout

```
RetailMind/
├── backend/          # Python API server, agents, provider abstraction, RAG pipeline
├── frontend/         # Web UI (framework TBD)
├── data/
│   └── sample_docs/  # Sample PDFs for local development and testing
├── docs/             # Architecture docs, decisions log, progress notes
├── scripts/          # SQL migrations and utility scripts
└── CLAUDE.md
```

## Key decisions

All architectural and schema decisions are recorded with plain-language explanations in [docs/02_decisions_log.md](docs/02_decisions_log.md). Read it before making changes that touch the database schema or agent routing logic.

## Working principles

**Explain decisions, don't over-engineer.** This is a portfolio project. The developer must be able to explain and defend every decision in an interview without consulting notes. Before adding a pattern, abstraction, or dependency, ask: is this the simplest thing that works, and can the reasoning be stated in one sentence?

Every non-obvious decision — a schema choice, a library pick, a routing strategy — belongs in the decisions log with a plain-language "Why".

No backwards-compatibility shims, no speculative abstractions for future requirements, no features beyond the current task.

## Model abstraction

**Dev:** all LLM calls use a local Ollama instance (no API key required, no cost).

**Prod:** all LLM calls go through a provider abstraction layer in `backend/` that swaps in a hosted model (e.g. Anthropic, OpenAI) via environment configuration.

The abstraction boundary must be a single interface that both local and hosted adapters implement. No LLM calls should be made directly outside that abstraction.

## Analytics agent rule

The analytics agent connects to Postgres as the `analytics_reader` role. This role has `SELECT` on the `retail` schema only. It has no access to the `app` schema.

This is the hard security boundary: generated SQL — including SQL produced by prompt injection — physically cannot read `app.chat_messages` or `app.documents`. Do not widen the grants on `analytics_reader` without updating the decisions log.

## Vocabulary

Use these terms consistently in code, comments, and documentation:

| Use | Avoid |
|-----|-------|
| `document` | `rag`, `pdf_agent` |
| `analytics` | `sql_agent`, `text2sql` |
| `query_type` values: `document`, `analytics`, `unknown` | `rag`, `sql` |
