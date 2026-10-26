# 07 — Demo and submission

## The 2-minute demo (script)

Record the terminal at a large font (≥ 18 pt), dark theme, window ≈ 110×30. Narrate calmly. No installation on camera.

| Time | On screen | Say |
|---|---|---|
| 0:00–0:15 | Title card: "Atlas — know what breaks across your repos, with proof" | "Coding agents and grep see one repo. Real systems span many. A change that looks safe breaks a consumer somewhere else." |
| 0:15–0:35 | `tree -L 1 examples` then `atlas scan backend billing web analytics` | "Four small repos: a backend, and three things that read its `customer_id` field. One command builds the map." |
| 0:35–0:55 | `atlas impact customer_id` | "Every consumer, with file and line, and whether the link is exact or just a name match. Nothing here is guessed by a model: it's from the code." |
| 0:55–1:15 | `./apply_rename.sh` then `atlas scan …` | "The backend renames the field. The web team updated. Billing and analytics didn't." |
| 1:15–1:45 | `atlas verify customer_id --renamed-to account_id --run-tests` | "Billing: contract broken, its tests fail. Web: updated, tests pass. Analytics: name-only match, no tests — so Atlas says *unknown*, not green. A truthful unknown beats a false check." |
| 1:45–2:10 | Agent window: prompt "rename customer_id → account_id; use atlas impact first, then atlas verify" and the tool calls appearing | "And agents can ask Atlas directly over MCP, before they edit." |
| 2:10–2:20 | README on screen: install line + repo URL | "Open source, MIT, Python, one SQLite file. Try it on your own repos." |

## Recording checklist
- [ ] `bash examples/reset.sh` run; `git status` clean in `examples/`.
- [ ] Terminal font ≥ 18 pt; prompt shortened (`PS1='$ '`).
- [ ] Rehearse once off-camera; time it (target 1:45–2:15).
- [ ] Record with QuickTime (⌘⇧5) or OBS at 1080p; mic on.
- [ ] Agent segment recorded separately if needed; only show real tool calls.
- [ ] Export MP4 ≤ 3 min; check audio; save as `atlas-demo.mp4` outside the repo.
- [ ] Take 3 screenshots: impact output, verify table, agent tool call (for the X post and README).

## X post (draft — edit to match what actually shipped)

> I built **Atlas** for #OpenFire: an open-source tool that maps how your repos depend on each other and tells you what a change will break — with file:line evidence on every link, and honest pass / fail / not_run / unknown states (no fake green checks).
>
> Works from the CLI and as an MCP server, so coding agents can ask "who uses this field?" before they edit.
>
> Python, one SQLite file, MIT. Repo: <URL>
> [video]
>
> @prasad_pilla @tryAlanAI

Build-in-public update (post mid-way, only after Task 8 is green):
> Progress on Atlas: scan + cross-repo linking + verify with four honest states are working on the example workspace. Next: MCP server and docs. [screenshot]

## Submission checklist (done by 21:30 IST on 27 Oct)
- [ ] Public GitHub repo; README renders; LICENSE = MIT; CI green.
- [ ] `git log` has no `Co-Authored-By` lines.
- [ ] Working link: the repo URL (the tool is a CLI; the README's demo section is the "working link" target). If a hosted demo is required, add a GitHub Pages page embedding the video and the verify table.
- [ ] X post with the video, repo link, and tags published; copy the post URL.
- [ ] Submit the X post URL, repo URL and working link in the hackathon form.
- [ ] Reply to your own post with the three screenshots.
