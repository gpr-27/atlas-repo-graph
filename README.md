# Atlas

Atlas maps how your local git repositories depend on each other — HTTP endpoints and response
fields to the code in other repos that uses them — shows what a change would break, proves every
link with file-and-line evidence, and reports one of four honest states: **pass / fail / not_run /
unknown**. It runs as a CLI (`atlas`) and as an MCP server so any coding agent can ask "who uses
this field?" before editing.

Full documentation lands with the MVP; see `atlas-plan/` for the design.
