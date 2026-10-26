# 06 — Testing strategy and release gates

## Test pyramid

| Level | What | Where | Needs network/model? |
|---|---|---|---|
| Unit | extractors, linker, `decide_state`, `url_to_path`, `path_pattern`, render | `tests/test_openapi.py`, `test_pyroutes.py`, `test_pyconsumers.py`, `test_link.py`, `test_verify.py`, `test_render.py` | No |
| Integration | scan → DB → query/verify on fixture repos | `tests/test_scan.py`, `test_query.py`, `test_verify.py` | No |
| Contract | MCP tools list + structured output | `tests/test_mcp.py`, `scripts/mcp_check.py` | No (local subprocess) |
| End-to-end | the demo workspace: scan, impact, rename, rescan, verify with tests | `tests/test_e2e.py`, `examples/demo.sh` | No |
| Manual smoke | an agent calling `atlas_impact`/`atlas_verify` over MCP; clean install | checklist below | No |

Commands:
```bash
python -m pytest -q                 # everything, ~10 s
python -m pytest -q -k "not e2e"    # fast loop
bash examples/demo.sh               # prints the demo table
python scripts/mcp_check.py examples/atlas.db
```

## Required test cases (traceability)

| ID | Requirement | Test | Expected |
|---|---|---|---|
| T-01 | FR-002 | `test_extract_endpoints_and_fields` | 2 endpoints, 6 EXPOSES, array items resolved |
| T-02 | FR-002/NFR-003 | `test_bad_yaml_is_skipped` | no raise, skipped entry |
| T-03 | FR-003 | `test_routes_and_fields` | 5 endpoints incl. two methods for `route`, non-literal return skipped |
| T-04 | NFR-003 | `test_syntax_error_file_is_skipped` | scan continues |
| T-05 | FR-004 | `test_url_to_path`, `test_http_calls_and_field_refs` | normalization and refs as specified |
| T-06 | FR-005 | `test_consumes_exact_when_same_file_calls_endpoint` / `..._inferred_without_call` | confidence rules |
| T-07 | FR-005 | `test_same_field_name_in_two_endpoints_is_exact_only_toward_called_one` | Review Focus #3 |
| T-08 | FR-005 | `test_orphan_call_gets_no_edge_and_no_error` | Review Focus #2 |
| T-09 | FR-001 | `test_scan_is_idempotent` | identical summaries |
| T-10 | FR-006 | `test_impact_lists_producers_and_consumers` | exact + inferred rows with evidence |
| T-11 | FR-007 | `test_decide_state` (8 cases) | NFR-006 invariant |
| T-12 | FR-008 | `test_run_test_cmd_pass_fail_timeout` | Review Focus #5 |
| T-13 | FR-007 | `test_verify_after_rename` | billing fail, web pass, analytics unknown |
| T-14 | FR-007 | `test_verify_nobody_references` | empty, exit 0 (Review Focus #4) |
| T-15 | FR-012 | `test_mcp_tools_roundtrip` | 5 tools, structured content |
| T-16 | FR-014 | `test_e2e` | states and exit code 2 |
| T-17 | NFR-008 | clean-install check (manual, Task 11) | demo table from fresh clone |

## Failure-path tests to keep
- Missing DB → exit 1 with a clear message.
- `explain-edge` with unknown id → exit 1.
- Test command that times out → `unknown`, other rows unaffected.
- Repo path that doesn't exist → `scan` exits 1 naming the path; nothing written.

## Release gates (all must pass before submission)

| Gate | Evidence that proves it |
|---|---|
| **G1 Environment** | `python -m pytest -q` passes in a fresh venv; `atlas --help` works; `python scripts/mcp_check.py` prints status JSON. |
| **G2 Core workflow** | `bash examples/demo.sh` prints the table with `billing fail / web pass / analytics unknown`, exit code 2 on verify. |
| **G3 Critical tests** | ≥ 25 tests, all green, none skipped except MCP if `mcp` missing. Paste the pytest summary line into the PR/commit. |
| **G4 Safety and honesty** | `grep -n "pass" atlas/verify.py` shows `pass` only reachable via `decide_state`; `test_decide_state` covers inferred → unknown; no `print` in `mcp_server.py`; no network calls outside `explain.py`. |
| **G5 Clean install** | Fresh clone in `/tmp`, `pipx install .` or `uv tool install .`, `atlas --help`, `bash examples/demo.sh` succeed. |
| **G6 Docs accurate** | Every command in README was run and its output matches; the states table matches `decide_state`; prior art section present. |
| **G7 Demo recorded** | Video 1–3 min, shows real terminal output and one real agent call over MCP; file saved and uploaded. |
| **G8 Submission ready** | Public repo URL opens in a private window; LICENSE present; X post drafted with video and tags; link to repo in the post. Done ≥ 30 min before 22:00 IST. |

If a gate fails: fix it before moving on. Do not record the demo on a failing gate. If G5 fails because of packaging, fall back to documenting `pip install -e .` from a clone and note it in the README.
