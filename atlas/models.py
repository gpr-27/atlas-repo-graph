"""In-memory types for Atlas (architecture §4)."""
import json
from dataclasses import asdict, dataclass, field

NODE_KINDS = ("endpoint", "field", "http_call", "field_ref")
EDGE_KINDS = ("EXPOSES", "CALLS", "CONSUMES")
CONFIDENCES = ("exact", "inferred")
STATES = ("pass", "fail", "not_run", "unknown")
HTTP_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")


@dataclass(frozen=True)
class Node:
    repo: str
    kind: str
    name: str
    file: str          # relative to repo root, posix separators
    line: int
    meta: dict = field(default_factory=dict, compare=False, hash=False)

    @property
    def meta_json(self) -> str:
        return json.dumps(self.meta, sort_keys=True)

    @property
    def key(self) -> str:            # stable identity used before DB ids exist; matches the DB UNIQUE constraint
        return f"{self.repo}|{self.kind}|{self.name}|{self.file}|{self.line}|{self.meta_json}"


@dataclass(frozen=True)
class Evidence:
    file: str
    line: int
    snippet: str
    extractor: str
    reason: str = ""


@dataclass(frozen=True)
class Edge:
    src_key: str
    dst_key: str
    kind: str
    confidence: str
    evidence: Evidence


@dataclass
class ExtractResult:
    nodes: list[Node] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)   # "file: reason"


@dataclass
class RepoInfo:
    name: str
    path: str
    commit_sha: str | None
    test_cmd: str | None


@dataclass
class ImpactRow:
    repo: str
    file: str
    line: int
    snippet: str
    confidence: str
    via: str            # endpoint name for exact, "name match" for inferred
    edge_id: int


@dataclass
class ImpactResult:
    symbol: str
    producers: list[dict]      # {"repo","endpoint","file","line"}
    consumers: list[ImpactRow]


@dataclass
class VerifyRow:
    repo: str
    evidence: str       # "file:line" of the strongest ref
    confidence: str     # best confidence among this repo's refs
    contract: str       # "pass" | "fail" | "n/a"
    tests: str          # "pass" | "fail" | "not_run" | "unknown"
    state: str          # final, one of STATES
    reason: str
    test_output: str = ""   # last 30 lines, only when tests ran


def as_dict(obj) -> dict:
    """dataclasses.asdict, exposed for callers that need plain dicts."""
    return asdict(obj)
