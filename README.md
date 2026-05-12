# Claude Bootstrap

> **Opinionated Claude Code setup → autonomous AI engineering platform.**

62 skills, TDD enforcement via Stop hooks, agent teams, persistent memory (Mnemos), intent tracking (iCPG), and a local AI command center (Maggy). Works with **Claude Code**, **Kimi CLI**, and **OpenAI Codex CLI**.

## Quick Start

```bash
git clone https://github.com/alinaqi/claude-bootstrap.git
cd claude-bootstrap && ./install.sh

# In any project directory
claude
> /initialize-project
```

Claude will validate tools, ask about your stack, create the repo structure, copy skills/rules/hooks, and spawn an agent team.

## What It Sets Up

| Layer | What | Why |
|-------|------|-----|
| **Skills** | 62 skills loaded via `@include` in CLAUDE.md | Language, framework, security, AI patterns |
| **Rules** | Conditional rules (activate by file path) | Quality gates, TDD workflow, security — only when relevant |
| **Hooks** | Stop hooks for TDD loops | Tests run after every Claude response, failures feed back automatically |
| **Agents** | Team Lead + Quality + Security + Review + Merger + Feature | Coordinated pipeline: spec → test → implement → review → PR |
| **Memory** | Mnemos (typed graph on disk) | Survives compaction, crashes, restarts |
| **Intent** | iCPG (code property graph) | Tracks *why* code exists, detects drift |

## Skills (62)

**Core** — TDD, memory, intent tracking, code review, agent teams, security, commit hygiene, cross-agent delegation, Polyphony orchestration

**Languages** — Python, TypeScript, Node.js, React, React Native, Android (Java/Kotlin), Flutter

**Databases** — Supabase, Firebase, Cloudflare D1, DynamoDB, Aurora, Cosmos DB

**AI** — Agentic development, LLM patterns, AI models reference

**UI** — Web (Tailwind), mobile, visual testing, Playwright, PWA

**Integrations** — Stripe, Reddit, Shopify, WooCommerce, Medusa, Klaviyo, Teams, PostHog

See [full skills catalog](./docs/claude-bootstrap-reference.md#skills-catalog-62-skills) for details.

## Cross-Tool Compatibility

| Feature | Claude Code | Kimi CLI | Codex CLI |
|---------|-------------|----------|-----------|
| Skills | `.claude/skills/` | `.kimi/skills/` | `.codex/skills/` |
| Instructions | `CLAUDE.md` | (uses skills) | `AGENTS.md` |

`install.sh` auto-detects installed tools. `/sync-agents` syncs config across tools on demand.

## Maggy — AI Command Center

Maggy is the optional local dashboard bundled with Claude Bootstrap. Point it at your codebases and issue tracker:

- **Chat** — multi-model routing with semantic blast scoring across Claude/Codex/Kimi/Local
- **Tasks** — AI-prioritized inbox from GitHub Issues or Asana
- **Execute** — one-click TDD pipeline with iCPG context
- **Competitors** — auto-discovered competitors + daily AI briefing
- **Insights** — CLI session analysis, health signals
- **P2P Mesh** — cross-machine session sync

```bash
cd maggy && pip install -e .
maggy serve   # dashboard at localhost:8080
```

See [maggy/README.md](./maggy/README.md) for setup and routing details.

## Core Concepts

**TDD via Stop Hooks** — tests run after every Claude response. Failures feed back automatically. No plugins needed. [Details →](./docs/claude-bootstrap-reference.md#tdd-loops-via-stop-hooks)

**Mnemos Memory** — typed graph on disk (goals, constraints, results, context). Survives compaction, crashes, multi-agent failures. 4-dimension fatigue model writes checkpoints *before* things go wrong. [Details →](./docs/claude-bootstrap-reference.md#mnemos--task-scoped-memory)

**iCPG Intent Tracking** — links every code change to a ReasonNode with intent, postconditions, and invariants. 6-dimension drift detection. [Details →](./docs/claude-bootstrap-reference.md#icpg--intent-augmented-code-property-graph)

**Agent Teams** — 6 agents with enforced pipeline (spec → test → implement → review → security → PR). Only Feature agents can edit code. [Details →](./docs/claude-bootstrap-reference.md#agent-teams)

## Usage

```bash
# New project
mkdir my-app && cd my-app
claude
> /initialize-project

# Existing project
cd my-existing-app
claude
> /initialize-project    # auto-detects existing code

# Update skills globally
cd "$(cat ~/.claude/.bootstrap-dir)"
git pull && ./install.sh
```

## Docs

- [Full reference](./docs/claude-bootstrap-reference.md) — TDD hooks, Mnemos, iCPG, agent teams, skills catalog, evolution
- [Maggy reference](./maggy/docs/maggy-reference.md) — CLI commands, REPL, routing, dashboard, architecture
- [Architecture v5](./maggy/docs/architecture-v5.md) — Full system architecture
- [Polyphony spec](./maggy/docs/polyphony-spec.md) — Container orchestration
- [Changelog](./CHANGELOG.md) — Version history

## License

MIT — See [LICENSE](LICENSE)

---

**Need help scaling AI in your org?** [Claude Code & MCP experts](https://leanai.ventures/aiops/claude)
