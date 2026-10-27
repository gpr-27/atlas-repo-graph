# Contributing to Atlas

Atlas is intentionally small. Please keep it that way.

## Setup

```bash
git clone https://github.com/gpr-27/atlas-repo-graph
cd atlas-repo-graph
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest -q          # must be all green
bash examples/demo.sh        # must print the verify table
```

## Rules

1. **No new runtime dependencies** without a written reason. Runtime: `pyyaml`, `mcp`. Dev: `pytest`.
2. **No model in the decision path.** `decide_state`, linker, extractors, query — all deterministic.
3. **Extractors never raise.** Catch `SyntaxError`, `UnicodeDecodeError`, `yaml.YAMLError`, `OSError`; append `"file: reason"` to `skipped`.
4. **`mcp_server.py` never prints to stdout.** That corrupts the protocol channel.
5. **`state == "pass"` only when tests actually ran and passed and confidence is exact** (NFR-006).
6. **Tests first.** Write the failing test, implement, confirm green.
7. **One module per concern.** Keep modules under ~250 lines.

## Adding a language extractor

See [`docs/adding-an-extractor.md`](docs/adding-an-extractor.md).

## Running tests

```bash
python -m pytest -q                   # full suite (~10 s)
python -m pytest -q -k "not e2e"      # fast loop
bash examples/demo.sh                  # end-to-end check
python scripts/mcp_check.py ./atlas.db # MCP contract check
```

## Commit style

Conventional commits: `feat:`, `fix:`, `docs:`, `chore:`, `test:`. No `Co-Authored-By` lines.
