"""OpenAPI 3.x extractor (architecture §5.2)."""
import re
from pathlib import Path

import yaml

from atlas.extract import iter_files, path_pattern
from atlas.models import Edge, Evidence, ExtractResult, HTTP_METHODS, Node

OPENAPI_NAMES = (
    "openapi.yaml", "openapi.yml", "openapi.json", "swagger.yaml", "swagger.json",
)


def find_openapi_files(repo_root: Path) -> list[Path]:
    return [p for p in iter_files(repo_root, (".yaml", ".yml", ".json")) if p.name in OPENAPI_NAMES]


def _find(lines: list[str], key: str, start_line: int = 1) -> int | None:
    """1-based line of the first `key:` mapping entry at or after start_line."""
    pattern = re.compile(r"^\s*['\"]?" + re.escape(key) + r"['\"]?\s*:")
    for index, raw in enumerate(lines[start_line - 1:], start=start_line):
        if pattern.match(raw):
            return index
    return None


def _resolve_schema(schema, doc: dict) -> tuple[dict, str | None]:
    """Resolve one `$ref` level into components.schemas; return (schema, ref name)."""
    if not isinstance(schema, dict):
        return {}, None
    ref = schema.get("$ref")
    if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
        name = ref.rsplit("/", 1)[-1]
        schemas = (doc.get("components") or {}).get("schemas") or {}
        target = schemas.get(name)
        if isinstance(target, dict):
            return target, name
    return schema, None


def _response_properties(operation: dict, doc: dict) -> tuple[list[str], str | None]:
    """Property names of the first 2xx application/json response schema."""
    responses = operation.get("responses")
    if not isinstance(responses, dict):
        return [], None
    for status, response in responses.items():
        if not str(status).startswith("2") or not isinstance(response, dict):
            continue
        content = response.get("content")
        media = content.get("application/json") if isinstance(content, dict) else None
        schema = media.get("schema") if isinstance(media, dict) else None
        resolved, schema_name = _resolve_schema(schema, doc)
        if resolved.get("type") == "array":
            items, item_name = _resolve_schema(resolved.get("items"), doc)
            return _properties(items), item_name or schema_name
        return _properties(resolved), schema_name
    return [], None


def _properties(schema: dict) -> list[str]:
    props = schema.get("properties") if isinstance(schema, dict) else None
    return list(props.keys()) if isinstance(props, dict) else []


def _property_line(lines: list[str], prop: str, schema_name: str | None, fallback: int) -> int:
    anchor = 1
    if schema_name:
        found = _find(lines, schema_name)
        if found:
            anchor = found
    props_line = _find(lines, "properties", anchor)
    if props_line:
        found = _find(lines, prop, props_line)
        if found:
            return found
    return fallback


def extract_openapi(repo_name: str, repo_root: Path) -> ExtractResult:
    result = ExtractResult()
    for path in find_openapi_files(repo_root):
        rel = path.relative_to(repo_root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
            doc = yaml.safe_load(text)
        except (yaml.YAMLError, UnicodeDecodeError, OSError) as exc:
            reason = f"{type(exc).__name__}: {exc}".replace("\n", " ")
            result.skipped.append(f"{rel}: {reason}")
            continue
        if not isinstance(doc, dict) or not isinstance(doc.get("paths"), dict):
            continue
        lines = text.splitlines()
        for raw_path, item in doc["paths"].items():
            if not isinstance(item, dict):
                continue
            path_line = _find(lines, str(raw_path)) or 1
            for method in HTTP_METHODS:
                operation = item.get(method.lower())
                if not isinstance(operation, dict):
                    continue
                name = f"{method} {raw_path}"
                endpoint = Node(
                    repo_name, "endpoint", name, rel, path_line,
                    {"method": method, "path": raw_path, "pattern": path_pattern(raw_path)},
                )
                result.nodes.append(endpoint)
                props, schema_name = _response_properties(operation, doc)
                for prop in props:
                    line = _property_line(lines, prop, schema_name, path_line)
                    snippet = lines[line - 1].strip() if 0 < line <= len(lines) else ""
                    field = Node(repo_name, "field", prop, rel, line, {"endpoint": name})
                    result.nodes.append(field)
                    result.edges.append(
                        Edge(
                            endpoint.key, field.key, "EXPOSES", "exact",
                            Evidence(rel, line, snippet, "openapi", "response schema property"),
                        )
                    )
    return result