import importlib.util
import re

from pathlib import Path

import pytest

from fastapi.testclient import TestClient
from inline_snapshot import snapshot

from fastapi_router_versioning._compat import iter_routes_flat

DOCS_SRC = Path(__file__).parent.parent / "docs_src"
SNIPPETS = sorted(DOCS_SRC.rglob("*.py"))

# For each docs_src file: every version's schema, its paths, and whether each operation is
# deprecated. Only what the package decides, so it holds across the whole FastAPI matrix.
# Regenerate with `pytest tests/test_docs_src.py --inline-snapshot=fix` and read the diff.
SCHEMAS = snapshot(
    {
        "advanced/callback_hook": {
            "/v1_0/openapi.json": {"/v1_0/items": {"get": False}},
            "/v2_0/openapi.json": {"/v2_0/items": {"get": False}},
        },
        "advanced/callbacks": {"/v1_0/openapi.json": {"/v1_0/items": {"post": False}}},
        "advanced/custom_url_format": {
            "/v1/openapi.json": {"/v1/items": {"get": False}},
            "/v2/openapi.json": {"/v2/items": {"get": False}},
            "/latest/openapi.json": {"/latest/items": {"get": False}},
        },
        "advanced/deprecation_headers": {
            "/v1_0/openapi.json": {"/v1_0/legacy": {"get": False}},
            "/v2_0/openapi.json": {"/v2_0/legacy": {"get": True}},
            "/v3_0/openapi.json": {"/v3_0/current": {"get": False}},
        },
        "advanced/latest_alias": {
            "/v1_0/openapi.json": {"/v1_0/items": {"get": False}},
            "/v2_0/openapi.json": {"/v2_0/items": {"get": False}},
            "/latest/openapi.json": {"/latest/items": {"get": False}},
        },
        "advanced/multiple_routers": {
            "/v1_0/openapi.json": {"/v1_0/users": {"get": False}, "/v1_0/products": {"get": False}}
        },
        "advanced/openapi_hook": {
            "/v1_0/openapi.json": {"/v1_0/items": {"get": False}},
            "/v2_0/openapi.json": {"/v2_0/items": {"get": False}},
        },
        "advanced/reverse_proxy": {
            "/v1_0/openapi.json": {"/v1_0/items": {"get": False}},
            "/v2_0/openapi.json": {"/v2_0/items": {"get": False}},
        },
        "advanced/self_hosted_assets": {
            "/v1_0/openapi.json": {"/v1_0/items": {"get": False}},
            "/v2_0/openapi.json": {"/v2_0/items": {"get": False}},
        },
        "advanced/validation_error_status_code": {
            "/v1_0/openapi.json": {"/v1_0/items": {"get": False}, "/v1_0/items/{item_id}": {"get": False}},
            "/v2_0/openapi.json": {"/v2_0/items": {"get": False}, "/v2_0/items/{item_id}": {"get": False}},
        },
        "advanced/version_discovery": {
            "/v1_0/openapi.json": {"/v1_0/items": {"get": False}},
            "/v2_0/openapi.json": {"/v2_0/items": {"get": False}},
        },
        "advanced/webhooks": {
            "/v1_0/openapi.json": {"/v1_0/items": {"get": False}},
            "/v2_0/openapi.json": {"/v2_0/items": {"get": False}},
        },
        "lifecycle/legacy_route": {
            "/v1_0/openapi.json": {"/v1_0/legacy": {"get": False}},
            "/v2_0/openapi.json": {"/v2_0/legacy": {"get": True}},
            "/v3_0/openapi.json": {},
        },
        "migration/adopt": {"/v1_0/openapi.json": {"/v1_0/items": {"get": False}}},
        "migration/change_endpoint": {
            "/v1_0/openapi.json": {"/v1_0/items": {"get": False}},
            "/v2_0/openapi.json": {"/v2_0/items": {"get": False}},
        },
        "migration/retire_unversioned": {
            "/v1_0/openapi.json": {"/v1_0/items": {"get": False}},
            "/v2_0/openapi.json": {"/v2_0/items": {"get": False}},
            "/latest/openapi.json": {"/latest/items": {"get": False}},
        },
        "quickstart/calver": {"/2025-01-01/openapi.json": {"/2025-01-01/items": {"get": False}}},
        "quickstart/semver": {
            "/v1_0/openapi.json": {"/v1_0/items": {"get": False}},
            "/v2_0/openapi.json": {"/v2_0/items": {"get": False}},
        },
    }
)


def snippet_id(path: Path) -> str:
    return path.relative_to(DOCS_SRC).with_suffix("").as_posix()


@pytest.mark.parametrize("snippet", SNIPPETS, ids=snippet_id)
def test_docs_snippet_runs_and_serves_every_version_schema(snippet: Path) -> None:
    """The docs pages include these files, so a page can't show code that no longer runs.
    Importing the file versionizes its app; each version must then serve its own schema,
    with the routes and deprecations recorded in SCHEMAS."""
    spec = importlib.util.spec_from_file_location(f"docs_src_{snippet.stem}", snippet)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    client = TestClient(module.app)
    schema_paths = [
        route.path
        for route in iter_routes_flat(module.app.routes)
        if route.path.endswith("/openapi.json") and route.path != "/openapi.json"
    ]

    assert schema_paths
    schemas = {}
    for path in schema_paths:
        response = client.get(path)
        assert response.status_code == 200, path
        schemas[path] = {
            route: {method: operation.get("deprecated", False) for method, operation in operations.items()}
            for route, operations in response.json()["paths"].items()
        }

    assert schemas == SCHEMAS[snippet_id(snippet)]


def pages_text() -> str:
    return "\n".join(page.read_text(encoding="utf-8") for page in (DOCS_SRC.parent / "docs").rglob("*.md"))


def test_every_docs_src_file_is_included_by_a_page() -> None:
    """A file no page includes is an example nobody reads, and nobody notices when it rots."""
    pages = pages_text()

    files = [path.relative_to(DOCS_SRC.parent).as_posix() for path in SNIPPETS]

    assert [path for path in files if path not in pages] == []


def test_every_page_include_points_at_an_existing_docs_src_file() -> None:
    included = re.findall(r'--8<-- "(docs_src/[^":]+)', pages_text())

    assert included
    assert [path for path in included if not (DOCS_SRC.parent / path).is_file()] == []
