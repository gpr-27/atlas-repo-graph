"""Python route/decorator extractor (architecture §5.3)."""
import ast
from pathlib import Path

from atlas.extract import iter_files, parse_file, path_pattern
from atlas.models import Edge, Evidence, ExtractResult, Node

ROUTE_ATTRS = {"get", "post", "put", "patch", "delete", "route"}
_FUNCTION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


def _routes(function: ast.FunctionDef | ast.AsyncFunctionDef) -> list[tuple[str, str, int]]:
    """(method, path, decorator line) for every route decorator on this function."""
    found: list[tuple[str, str, int]] = []
    for decorator in function.decorator_list:
        if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
            continue
        attr = decorator.func.attr
        if attr not in ROUTE_ATTRS or not decorator.args:
            continue
        first = decorator.args[0]
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            continue
        if attr == "route":
            methods = ["GET"]
            for keyword in decorator.keywords:
                if keyword.arg == "methods" and isinstance(keyword.value, ast.List):
                    values = [
                        elt.value.upper()
                        for elt in keyword.value.elts
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                    ]
                    if values:
                        methods = values
            for method in methods:
                found.append((method, first.value, decorator.lineno))
        else:
            found.append((attr.upper(), first.value, decorator.lineno))
    return found


def _walk_body(function: ast.FunctionDef | ast.AsyncFunctionDef):
    """Yield nodes in the body, never descending into nested functions or classes."""
    stack = list(function.body)
    while stack:
        node = stack.pop(0)
        yield node
        if isinstance(node, (*_FUNCTION_NODES, ast.ClassDef, ast.Lambda)):
            continue
        stack.extend(ast.iter_child_nodes(node))


def _dict_keys(node: ast.AST) -> list[ast.Constant] | None:
    """Constant-string keys of a Dict node, or None if it has a non-constant key."""
    if not isinstance(node, ast.Dict):
        return None
    keys = []
    for key in node.keys:
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.append(key)
        else:
            return None
    return keys


def _return_keys(function: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[list[ast.Constant], bool]:
    """Return (constant keys returned by this function, whether a non-literal return was seen)."""
    keys: list[ast.Constant] = []
    non_literal = False
    for node in _walk_body(function):
        if not isinstance(node, ast.Return) or node.value is None:
            continue
        value = node.value
        dict_keys = _dict_keys(value)
        if dict_keys is not None:
            keys.extend(dict_keys)
            continue
        if isinstance(value, ast.Call):
            name = None
            if isinstance(value.func, ast.Name):
                name = value.func.id
            elif isinstance(value.func, ast.Attribute):
                name = value.func.attr
            if name in {"jsonify", "dict"}:
                if value.args and isinstance(value.args[0], ast.Dict):
                    inner = _dict_keys(value.args[0])
                    if inner is not None:
                        keys.extend(inner)
                        continue
                keyword_keys = [
                    ast.Constant(value=kw.arg, lineno=kw.value.lineno)
                    for kw in value.keywords
                    if kw.arg is not None
                ]
                if keyword_keys:
                    keys.extend(keyword_keys)
                    continue
        non_literal = True
    return keys, non_literal


def extract_py_routes(repo_name: str, repo_root: Path) -> ExtractResult:
    result = ExtractResult()
    for path in iter_files(repo_root, (".py",)):
        rel = path.relative_to(repo_root).as_posix()
        try:
            tree = parse_file(path)
            lines = path.read_text(encoding="utf-8").splitlines()
        except (SyntaxError, UnicodeDecodeError, OSError) as exc:
            reason = f"{type(exc).__name__}: {exc}".replace("\n", " ")
            result.skipped.append(f"{rel}: {reason}")
            continue
        for function in ast.walk(tree):
            if not isinstance(function, _FUNCTION_NODES):
                continue
            routes = _routes(function)
            if not routes:
                continue
            endpoints = []
            for method, route_path, line in routes:
                endpoint = Node(
                    repo_name, "endpoint", f"{method} {route_path}", rel, line,
                    {"method": method, "path": route_path, "pattern": path_pattern(route_path)},
                )
                result.nodes.append(endpoint)
                endpoints.append(endpoint)
            keys, non_literal = _return_keys(function)
            for key in keys:
                line = key.lineno
                snippet = lines[line - 1].strip() if 0 < line <= len(lines) else ""
                for endpoint in endpoints:
                    field = Node(
                        repo_name, "field", str(key.value), rel, line,
                        {"endpoint": endpoint.name},
                    )
                    result.nodes.append(field)
                    result.edges.append(
                        Edge(
                            endpoint.key, field.key, "EXPOSES", "exact",
                            Evidence(rel, line, snippet, "pyroutes", "dict literal in return"),
                        )
                    )
            if non_literal:
                result.skipped.append(f"{rel}:{routes[0][2]}: non-literal return")
    return result