# 08 — Risk register

| ID | Risk | Prob. | Impact | Early warning | Prevention | Mitigation / fallback |
|---|---|---|---|---|---|---|
| R-01 | Consumer extractor misses or over-matches field refs on real code | High | Medium | Unit tests pass but `impact` on a real repo shows noise or nothing | Keep rules narrow (string-literal keys; attr only for known fields) | Label everything not backed by a CALLS edge as `inferred`; `unknown` state absorbs it honestly |
| R-02 | f-string/URL normalization fails for a URL style (e.g. `urljoin`, `.format`) | High | Low | `url_to_path` returns None for a real call | Skipped list with reason; `search` still finds the call by text | Add the pattern as a 5-line case; document "supported URL forms" |
| R-03 | Running a repo's tests takes too long or hangs | Medium | Medium | demo step 5 slow | `--timeout` default 120 s; `--run-tests` opt-in | `unknown` with "timed out"; demo without `--run-tests` still shows fail/not_run/unknown |
| R-04 | `mcp` 2.x API differs from the plan (e.g. structured output shape) | Low | High | `test_mcp_tools_roundtrip` fails | Already verified `MCPServer`, `dict[str, Any]` return, `structured_content` on 2.3.0 | Pin `mcp==2.3.0`; read `/v2/migration/` page; worst case pin `mcp<2` and use `FastMCP` |
| R-05 | Agent does not pick up the MCP server config | Medium | Medium | tools don't appear in the agent | `scripts/mcp_check.py` proves the server; use absolute path to `atlas` | Demo the agent running `atlas impact --json` in a shell instead; MCP still shown via `mcp_check.py` |
| R-06 | Cheaper coding model drifts from the contracts (renames, adds deps, skips tests) | High | High | diff touches files outside the task; `pyproject` gains deps | Master prompt rules; one task at a time; review each diff | Revert the task, re-run with the task card pasted verbatim |
| R-07 | Time overrun | Medium | High | Task 8 not done by hour 7 | Time plan with cumulative hours; stretch items last | Cut `search`/`explain-edge` from MCP, skip stretch, keep Tasks 10–12 |
| R-08 | Prior art makes Atlas look like a clone | Medium | Medium | — | Credit codebase-memory-mcp, repowise, repo-graph, CODEGRAPH_MCP, GitNexus in README; state the differences (evidence trail, four states, tiny codebase) | Lead the video with the four-state table, which none of them shows |
| R-09 | Example line numbers in docs drift from files | High | Low | e2e test asserts states only, not lines | Write the README table **from** `demo.sh` output at the end | Regenerate the table before recording |
| R-10 | `examples/` scripts not executable or `sed -i` differs on Linux | Medium | Low | CI on Linux fails | `chmod +x`; use `sed -i.bak` + `rm *.bak` (works on BSD and GNU) | Replace with a 6-line Python script |
| R-11 | Hackathon "working link" interpreted as a hosted app | Medium | Medium | form field requires a URL other than GitHub | Prepare a GitHub Pages page (video + table + install) in 20 min | Use the repo README URL |
| R-12 | License confusion from reference repos (repowise AGPL, GitNexus noncommercial) | Low | High | — | **Never copy code** from those two; designs only | Remove any offending code immediately |
