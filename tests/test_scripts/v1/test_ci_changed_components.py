import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[3] / "scripts" / "ci_changed_components.py"
_SPEC = importlib.util.spec_from_file_location("ci_changed_components", _PATH)
ci_changed_components = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ci_changed_components)


def test_backend_only_changes_skip_frontend_checks():
    assert ci_changed_components.classify_paths(["src/api/routes.py", "tests/test_api/test_routes.py"]) == (True, False)


def test_frontend_only_changes_skip_backend_checks():
    assert ci_changed_components.classify_paths(["client/web-app/src/App.tsx"]) == (False, True)


def test_workflow_or_dependency_change_runs_both_stacks():
    assert ci_changed_components.classify_paths([".github/workflows/checks.yml"]) == (True, True)
    assert ci_changed_components.classify_paths(["requirements.txt"]) == (True, True)


def test_observability_and_quality_config_run_backend_checks():
    assert ci_changed_components.classify_paths(["observability/grafana/dashboards/p004.json"]) == (True, False)
    assert ci_changed_components.classify_paths(["pytest.ini"]) == (True, True)
    assert ci_changed_components.requires_full_backend(["pytest.ini"])
    assert not ci_changed_components.requires_full_backend(["src/api/routes.py"])


def test_unknown_or_docs_only_change_does_not_skip_secret_scan_but_skips_stacks():
    assert ci_changed_components.classify_paths(["docs/DEPLOY.md"]) == (False, False)


def test_unavailable_base_defaults_to_full_ci(monkeypatch):
    monkeypatch.setattr(ci_changed_components, "changed_paths", lambda base, head: None)
    assert ci_changed_components.changed_paths("missing", "head") is None
