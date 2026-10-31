"""Check build artifacts, or exercise an installed wheel outside its checkout.

No network, application credentials, or production database is used. This does
not validate business correctness, browser behavior, or operational security.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import tarfile
import tempfile
import zipfile
from service.evaluation.datasets import assert_public_artifacts


RUNTIME_FILES = {
    "service/__init__.py",
    "service/app.py",
    "service/cli.py",
    "service/domain/canonical.py",
    "service/domain/types.py",
    "service/models_v1.py",
    "service/commands.py",
    "service/repositories.py",
    "service/idempotency_v1.py",
    "service/auth.py",
    "service/workspace.py",
    "service/recovery.py",
    "service/domain/gates.py",
    "service/domain/evidence.py",
    "service/evaluation/runner.py",
    "service/evaluation/config.py",
    "service/evaluation/adapters.py",
    "service/evaluation/metrics.py",
    "service/evaluation/benchmark.py",
    "service/evaluation/datasets.py",
    "service/policies/schema.py",
    "service/policies/resolver.py",
    "service/policies/registry.py",
    "service/api/v1.py",
    "service/static/v1.html",
    "service/static/v1.js",
    "service/static/v1.css",
    "service/static/vendor/suit/SUIT-Variable.woff2",
    "service/static/vendor/suit/LICENSE.txt",
    "service/static/vendor/suit/PROVENANCE.json",
    "datasets/packs/fictional_harbor.json",
    "datasets/packs/fictional_orchard.json",
    "datasets/packs/fictional_lantern.json",
    "service/domain/state_machine.py",
    "service/api/__init__.py",
    "service/api/schemas_v1.py",
    "service/api/errors.py",
    "service/static/index.html",
    "service/static/vendor/tabler-1.7.3/tabler.min.css",
    "service/static/vendor/tabler-1.7.3/LICENSE.txt",
    "service/static/vendor/tabler-1.7.3/BOOTSTRAP-LICENSE.txt",
    "service/static/vendor/tabler-1.7.3/PROVENANCE.json",
    "reference/__init__.py",
    "reference/resolver.py",
    "reference/verify_answer.py",
    "datasets/synthetic_rules.json",
    "datasets/resolver_test_cases.json",
    "datasets/synthetic_impact_graph.json",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def check_paths(names: set[str]) -> None:
    try:
        assert_public_artifacts(names)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    for name in names:
        path = PurePosixPath(name)
        require(not path.is_absolute() and ".." not in path.parts,
                f"Unsafe archive member: {name}")
        require(not any(part in {".git", ".venv", "__pycache__"} for part in path.parts),
                f"Unexpected local state in distribution: {name}")
        require(not path.name.startswith(".env") and
                path.suffix.lower() not in {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3", ".pem", ".key"},
                f"Unexpected local state in distribution: {name}")


def check_archives(folder: Path) -> None:
    wheels = list(folder.glob("*.whl"))
    sources = list(folder.glob("*.tar.gz"))
    require(len(wheels) == len(sources) == 1,
            "Expected exactly one wheel and one sdist; use a clean build output directory.")
    with zipfile.ZipFile(wheels[0]) as archive:
        names = {item.filename for item in archive.infolist() if not item.is_dir()}
        check_paths(names)
        require(RUNTIME_FILES <= names,
                f"Wheel is missing runtime files: {sorted(RUNTIME_FILES - names)}")
        for license_file in ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md"):
            require(any(name.endswith(".dist-info/licenses/" + license_file) for name in names),
                    f"Wheel is missing {license_file}")
    with tarfile.open(sources[0], "r:gz") as archive:
        members = archive.getmembers()
        require(not any(item.issym() or item.islnk() for item in members),
                "Distribution must not contain symbolic or hard links.")
        raw_names = {item.name for item in members if item.isfile()}
        check_paths(raw_names)
        require(len({PurePosixPath(name).parts[0] for name in raw_names}) == 1,
                "Source distribution must have one root directory.")
        names = {"/".join(PurePosixPath(name).parts[1:]) for name in raw_names}
        required = RUNTIME_FILES | {
            "pyproject.toml", "requirements.txt", "README.md", "LICENSE", "NOTICE",
            "THIRD_PARTY_NOTICES.md", "scripts/check_distribution.py",
            "alembic.ini", "migrations/env.py", "migrations/script.py.mako",
            "migrations/versions/0001_v1.py",
            "alembic-postgres.ini", "compose.postgres-test.yaml", "scripts/pg_test_bootstrap.py",
            "migrations/postgres/env.py", "migrations/postgres/versions/0001_pg.py",
            "migrations/postgres/versions/0001_schema.sql",
        }
        require(required <= names,
                f"Source distribution is missing files: {sorted(required - names)}")
    print(f"Distribution contents checked: {wheels[0].name}, {sources[0].name}")


def check_installed() -> None:
    # Keep repository directories off sys.path: call this script from another cwd.
    import service
    import reference

    repository = Path(__file__).resolve().parents[1]
    runtime = Path(service.__file__).resolve().parents[1]
    require(runtime != repository, "Installed-wheel check imported the checkout instead.")
    require(Path(reference.__file__).resolve().parents[1] == runtime,
            "service and reference were loaded from different locations.")
    for name in RUNTIME_FILES:
        require((runtime / name).is_file(), f"Installed runtime asset is missing: {name}")
    from service.api.schemas_v1 import Decision, parse_body
    from service.domain.state_machine import apply_transition
    from service.models_v1 import BaseV1
    from service.models import Base

    require(parse_body(Decision, b'{"decision":"APPROVE","reason":"Synthetic review complete."}').decision == 'APPROVE'
            and callable(apply_transition), "Installed v1 foundation could not be imported.")
    require(BaseV1.metadata is not Base.metadata and bool(BaseV1.metadata.tables)
            and all(name.startswith("v1_") for name in BaseV1.metadata.tables),
            "Installed v1 schema must remain isolated from baseline metadata.")
    for name in ("synthetic_rules.json", "resolver_test_cases.json", "synthetic_impact_graph.json"):
        json.loads((runtime / "datasets" / name).read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(prefix="caseproof-wheel-check-") as temporary:
        os.environ["CASEPROOF_DEMO_MODE"] = "1"
        os.environ["CASEPROOF_DATABASE_URL"] = "sqlite:///" + str(Path(temporary) / "demo.sqlite3")
        from service.app import app, DATASET_HASH, EVALUATOR_HASH
        from service.db import create_tables
        from service.seed import seed_demo

        try:
            create_tables(app.state.db_engine)
            with app.state.session_factory() as session:
                credentials = seed_demo(session)
                session.commit()
            require(bool(credentials), "A fresh synthetic database was not seeded.")
            # Dispatch only local, unauthenticated endpoints using ASGI directly;
            # avoid introducing an HTTP test client as a runtime dependency.
            import asyncio

            async def request(path: str, application=app, headers=None) -> list[dict]:
                messages: list[dict] = []

                async def receive() -> dict:
                    return {"type": "http.request", "body": b"", "more_body": False}

                async def send(message: dict) -> None:
                    messages.append(message)

                scope = {
                    "type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
                    "http_version": "1.1", "method": "GET", "scheme": "http",
                    "path": path, "raw_path": path.encode(), "query_string": b"",
                    "root_path": "", "headers": headers or [], "client": ("127.0.0.1", 12345),
                    "server": ("127.0.0.1", 8000),
                }
                await application(scope, receive, send)
                return messages

            for path in ("/", "/api/health", "/static/vendor/tabler-1.7.3/tabler.min.css"):
                messages = asyncio.run(request(path))
                require(any(m["type"] == "http.response.start" and m["status"] == 200 for m in messages),
                        f"Installed application did not serve {path}")
                body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
                if path == "/":
                    require(b"CaseProof" in body, "Installed static HTML was not served.")
                elif path == "/api/health":
                    health = json.loads(body)
                    require(health.get("llm_connected") is False and
                            health.get("real_insurance_decisions") is False,
                            "Unexpected demo health claims.")
                else:
                    require(b"Tabler v1.7.3" in body, "Installed open-source UI stylesheet was not served.")
            require(len(DATASET_HASH) == len(EVALUATOR_HASH) == 64,
                    "Installed source/dataset hashing failed.")
            import hashlib
            from service.db import make_engine, session_factory
            from service.workspace import seed_workspace, create_workspace_app
            engine = make_engine('sqlite:///' + str(Path(temporary) / 'v1.sqlite3'))
            try:
                BaseV1.metadata.create_all(engine)
                factory = session_factory(engine)
                with factory.begin() as db:
                    seed_workspace(db)
                token = b'Bearer installed-demo-check'
                registry = {hashlib.sha256(token.removeprefix(b'Bearer ')).hexdigest():
                            {'tenant_id': 'fictional', 'actor_id': 'analyst'}}
                workspace = create_workspace_app(factory, registry)
                for path in ('/v1', '/static/v1.js', '/api/v1/workspace'):
                    messages = asyncio.run(request(path, workspace, [(b'authorization', token)]))
                    require(any(m['type'] == 'http.response.start' and m['status'] == 200 for m in messages),
                            f'Installed v1 workspace did not serve {path}')
                    if path == '/api/v1/workspace':
                        catalog = json.loads(b''.join(m.get('body', b'') for m in messages if m['type'] == 'http.response.body'))['data']
                        require(len(catalog['presets']) == 3 and catalog['capabilities']['external_model'] is False,
                                'Installed synthetic pack catalog is incomplete or advertises a real provider.')
                from service.commands import execute_command
                from service.domain.types import ActorContext, CommandContext
                actor = ActorContext('fictional', 'analyst', frozenset({'ANALYST'}))
                preset = catalog['presets'][0]
                created = execute_command(factory, actor, CommandContext('POST', '/api/v1/changes', 'NEW',
                    'installed_create_key', None, preset['create_body']))
                identity = created.data['change_id']
                evaluated = execute_command(factory, actor, CommandContext('POST',
                    '/api/v1/changes/{change_id}/evaluation-runs', identity, 'installed_evaluate_key', 1,
                    {'suite_version_id': preset['create_body']['suite_version_id'], 'case_inputs': preset['case_inputs']}))
                require(evaluated.data['run']['schema'] == 'evaluation_run_v2' and
                        evaluated.data['run']['gate_summary'] == 'PASS', 'Installed v2 execution did not pass.')
                messages = asyncio.run(request('/api/v1/changes/' + identity + '/evidence', workspace,
                                               [(b'authorization', token)]))
                evidence = json.loads(b''.join(m.get('body', b'') for m in messages if m['type'] == 'http.response.body'))['data']
                require(evidence['historical_integrity'] == 'VALID' and evidence['immutable_refs']['run_refs'],
                        'Installed evidence did not expose verified immutable execution references.')
            finally:
                engine.dispose()
        finally:
            app.state.db_engine.dispose()
    print(f"Installed-wheel assets, seed, HTML, and health checked: {importlib.metadata.version('caseproof-local-demo')}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", default="dist", type=Path)
    parser.add_argument("--installed", action="store_true")
    args = parser.parse_args()
    if args.installed:
        check_installed()
    else:
        check_archives(args.directory)


if __name__ == "__main__":
    main()
