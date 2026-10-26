"""Python consumer extractor (architecture §5.4)."""
import ast
import re
import urllib.parse
from pathlib import Path
from typing import Optional

from atlas.extract import iter_files, parse_file
from atlas.models import Evidence, ExtractResult, Node

# Libraries whose attribute-access calls are HTTP verbs, not field getters
_HTTP_ROOTS = {"requests", "httpx", "client", "session"}
_HTTP_ATTRS = {"get", "post", "put", "patch", "delete"}


def _root_id(node: ast.expr) -> str | None:
    """Return the leftmost Name id of an attribute chain, or None."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return _root_id(node.value)
    return None


def _normalize_path(path: str) -> str:
    """Strip scheme+host, remove trailing slash (except root), collapse //."""
    if "://" in path:
        path = urllib.parse.urlsplit(path).path
    path = re.sub(r"//+", "/", path)
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return path or "/"


def _raw_path(node: ast.expr) -> str | None:
    """Return raw (un-normalized) path string, None if unresolvable."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                parts.append("{}")
            else:
                return None
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _raw_path(node.left)
        right = _raw_path(node.right)
        if left is None and right is None:
            return None
        return (left or "{}") + (right or "{}")
    return None


def url_to_path(node: ast.expr) -> str | None:
    """Extract and normalize a URL/path from an AST expression; return None if unresolvable."""
    raw = _raw_path(node)
    if raw is None:
        return None
    # strip scheme+host
    if "://" in raw:
        raw = urllib.parse.urlsplit(raw).path
    # strip leading base-URL placeholder
    if raw.startswith("{}"):
        raw = raw[2:]
    if not raw:
        return None
    return _normalize_path(raw)


class _ConsumerVisitor(ast.NodeVisitor):
    def __init__(self, repo_name: str, rel: str, source_lines: list[str], known_fields: set[str]):
        self.repo_name = repo_name
        self.rel = rel
        self.lines = source_lines
        self.known_fields = known_fields
        self.nodes: list[Node] = []
        self._func_stack: list[str] = []

    def _snippet(self, lineno: int) -> str:
        if 0 < lineno <= len(self.lines):
            return self.lines[lineno - 1].strip()[:200]
        return ""

    def _cur_func(self) -> str:
        return self._func_stack[-1] if self._func_stack else ""

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._func_stack.append(node.name)
        self.generic_visit(node)
        self._func_stack.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Call(self, node: ast.Call):
        self._check_http_call(node)
        self._check_get_ref(node)
        self.generic_visit(node)

    def _method_from_attr(self, attr: str) -> str:
        return attr.upper()

    def _check_http_call(self, node: ast.Call):
        method: str | None = None
        library: str | None = None

        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            root = _root_id(node.func.value)
            if attr in _HTTP_ATTRS and root in _HTTP_ROOTS:
                method = attr.upper()
                library = root
            elif attr == "urlopen":
                method = "GET"
                library = "urllib"
        elif isinstance(node.func, ast.Name) and node.func.id == "urlopen":
            method = "GET"
            library = "urllib"

        if method is None:
            return

        # find the URL argument
        url_node: ast.expr | None = None
        if node.args:
            url_node = node.args[0]
        else:
            for kw in node.keywords:
                if kw.arg == "url":
                    url_node = kw.value
                    break
        if url_node is None:
            return

        path = url_to_path(url_node)
        if path is None:
            return

        name = f"{method} {path}"
        n = Node(
            self.repo_name, "http_call", name, self.rel, node.lineno,
            {"method": method, "path": path, "library": library},
        )
        self.nodes.append(n)

    def _check_get_ref(self, node: ast.Call):
        """x.get("field") → field_ref with access='get'."""
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "get":
            return
        # exclude HTTP library .get calls
        root = _root_id(node.func.value)
        if root in _HTTP_ROOTS:
            return
        if not node.args:
            return
        first = node.args[0]
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            return
        name = first.value
        # spec §5.4: .get() gated only by HTTP-lib check above, not by known_fields
        n = Node(
            self.repo_name, "field_ref", name, self.rel, node.lineno,
            {"access": "get", "function": self._cur_func()},
        )
        self.nodes.append(n)

    def visit_Subscript(self, node: ast.Subscript):
        # x["field"]
        if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
            name = node.slice.value
            n = Node(
                self.repo_name, "field_ref", name, self.rel, node.lineno,
                {"access": "subscript", "function": self._cur_func()},
            )
            self.nodes.append(n)
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        # x.field where field is in known_fields
        attr = node.attr
        if attr in self.known_fields:
            root = _root_id(node.value)
            if root not in _HTTP_ROOTS:
                n = Node(
                    self.repo_name, "field_ref", attr, self.rel, node.lineno,
                    {"access": "attr", "function": self._cur_func()},
                )
                self.nodes.append(n)
        self.generic_visit(node)


def extract_py_consumers(
    repo_name: str, repo_root: Path, known_fields: set[str]
) -> ExtractResult:
    result = ExtractResult()
    for path in iter_files(repo_root, (".py",)):
        rel = path.relative_to(repo_root).as_posix()
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            result.skipped.append(f"{rel}: {type(exc).__name__}: {exc}")
            continue
        tree = parse_file(path)
        if tree is None:
            result.skipped.append(f"{rel}: SyntaxError")
            continue
        visitor = _ConsumerVisitor(repo_name, rel, lines, known_fields)
        visitor.visit(tree)
        result.nodes.extend(visitor.nodes)
    return result
