# Adding a language extractor to Atlas

An extractor is a pure function that reads files in a repo and returns nodes and edges. It never touches the database, never calls a model, and never raises on bad input.

## Signature

```python
from pathlib import Path
from atlas.models import ExtractResult

def extract_mylang(repo_name: str, repo_root: Path) -> ExtractResult:
    result = ExtractResult()
    # ... read files, append nodes/edges/skipped ...
    return result
```

For consumer extractors that need to know producer field names:
```python
def extract_mylang_consumers(repo_name: str, repo_root: Path, known_fields: set[str]) -> ExtractResult:
    ...
```

## Node kinds

| Kind | When to produce | Required meta keys |
|---|---|---|
| `endpoint` | A route handler or OpenAPI path+method | `method`, `path`, `pattern` |
| `field` | A response property the endpoint exposes | `endpoint` (the endpoint name) |
| `http_call` | An outbound HTTP call | `method`, `path`, `library` |
| `field_ref` | A reference to a field by name | `access` (`subscript`/`get`/`attr`), `function` |

`pattern` must be `"^" + re.sub(r"\{[^}]+\}", "[^/]+", path) + "$"` (see `path_pattern` in `atlas/extract/__init__.py`).

## Evidence

Every `EXPOSES` edge must carry:
```python
Evidence(file=rel, line=lineno, snippet=source_line_stripped[:200],
         extractor="mylang", reason="...")
```

`CALLS` and `CONSUMES` edges are produced by `atlas/link.py` automatically — you only need to produce `endpoint`, `field`, `http_call`, `field_ref` nodes.

## Error handling

```python
try:
    tree = parse_file(path)
except (SyntaxError, UnicodeDecodeError, OSError) as exc:
    result.skipped.append(f"{rel}: {exc}")
    continue
```

Never `raise`. The scan continues even if one file is unparsable.

## Wire it into scan.py

In `atlas/scan.py`, import your extractor and call it in the first pass (producers) or second pass (consumers), exactly like `extract_openapi` and `extract_py_routes`.

## Tests

Create `tests/fixtures/mylang_repo/` with a minimal file and `tests/test_mylang.py` following the pattern in `tests/test_openapi.py` or `tests/test_pyroutes.py`. Assert:
- Correct node kinds and counts
- Edge kinds are `EXPOSES`
- Bad input is skipped, not raised
