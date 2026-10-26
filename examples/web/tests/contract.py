"""Load the backend's example response from its OpenAPI contract (keeps consumer tests honest)."""
import io, json, pathlib, yaml


def example_user() -> dict:
    spec = pathlib.Path(__file__).resolve().parents[2] / "backend" / "openapi.yaml"
    return yaml.safe_load(spec.read_text())["components"]["schemas"]["User"]["example"]


def fake_urlopen(url: str):
    """Stands in for urllib's urlopen: returns a file-like object with the contract example."""
    return io.BytesIO(json.dumps(example_user()).encode())
