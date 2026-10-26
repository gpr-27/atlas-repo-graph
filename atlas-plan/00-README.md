# Atlas — plan folder

Atlas is a small open-source tool that maps how several git repositories depend on each other
(API endpoints and response fields → the code in other repos that uses them), shows what a change
would break, proves every link with file/line evidence, and reports one of four honest states:
**pass / fail / not_run / unknown**. It runs as a CLI and as an MCP server so any coding agent
(Claude Code, Cursor, Codex, opencode, …) can ask it "who uses this field?" before editing.

Atlas is a standalone project. It is not tied to any vendor or agent.

Hackathon deadline: **27 Oct 2026, 22:00 IST** (building closes 20:00 IST).

## How to use this folder

| File | What it is | Read it when |
|---|---|---|
| `01-product-spec.md` | What Atlas is, who it's for, requirements (FR/NFR), acceptance criteria, non-goals | Before anything |
| `02-architecture.md` | Modules, data model, contracts, algorithms, diagrams | Before writing any code |
| `03-mcp-integration.md` | How any agent loads Atlas as an MCP server (verified with the Python MCP SDK 2.x) | Task 0 and Task 9 |
| `04-mvp-implementation-plan.md` | **The build plan.** Ordered tasks with files, signatures, tests, commands, acceptance | During the build — one task at a time |
| `05-full-roadmap.md` | Everything after the MVP, in priority order, with design notes | After the MVP ships |
| `06-testing-and-gates.md` | Test matrix, commands, and the 8 release gates with evidence | Before claiming anything is done |
| `07-demo-and-submission.md` | Demo script, recording checklist, X post, submission checklist | Last 4 hours |
| `08-risks.md` | Risk register with early warnings and fallbacks | When something goes wrong |
| `09-master-prompt-deepseek.md` | The prompt to paste into the coding model (DeepSeek Flash) | When starting the build |
| `10-reference-repos.md` | Existing projects to borrow ideas from (what to copy, what not to) | When a task says "see reference" |

## Facts verified on this machine (26 Oct 2026)

- Python 3.15.0, pip 26.2.1, uv 0.12.7, git 2.54.0 available. Plan targets **Python ≥ 3.11**.
- `mcp` PyPI version **2.3.0**. In mcp 2.x `FastMCP` was renamed: use `from mcp.server.mcpserver import MCPServer`.
  A stdio server + client round-trip was tested and works (`dict[str, Any]` return → `structured_content`).
- `pyyaml` 6.0.3, `pytest` 9.1.1.
- MCP clients register a server's tools as `<servername>_<toolname>` in most agents (e.g. `atlas_impact`).

## Ground rules for the whole project

1. **Facts come from code, never from a model.** Every edge carries evidence (repo, file, line, snippet, extractor, confidence).
2. **Never show a green check you didn't earn.** If a check didn't run, say `not_run`; if you can't tell, say `unknown`.
3. **MVP first, exactly as written in `04-…`.** Anything not in the MVP goes to `05-full-roadmap.md`.
4. **No model in the decision path.** Atlas works fully with no model. An optional open model may only turn results into prose.
5. **Prior art is credited** in the README (see `10-reference-repos.md`). Atlas's difference is the evidence trail + four-state report + cross-repo + agent-ready MCP, in a tiny, readable codebase.
