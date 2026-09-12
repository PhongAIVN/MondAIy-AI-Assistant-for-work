"""Deployment contract for the P0 capacity services."""

from pathlib import Path

import yaml


def test_production_compose_starts_healthy_redis_and_worker_after_backend():
    compose = yaml.safe_load(Path("docker-compose.prod.yml").read_text(encoding="utf-8"))
    services = compose["services"]

    assert services["redis"]["healthcheck"]["test"] == ["CMD", "redis-cli", "ping"]
    assert services["p004-backend"]["environment"]["REDIS_URL"] == "redis://redis:6379/0"
    assert services["worker"]["environment"]["REDIS_URL"] == "redis://redis:6379/0"
    assert services["worker"]["command"] == ["python", "-m", "src.worker"]
    assert services["worker"]["depends_on"]["redis"]["condition"] == "service_healthy"
    assert services["worker"]["depends_on"]["p004-backend"]["condition"] == "service_healthy"
    assert services["worker"]["healthcheck"]["disable"] is True


def test_deploy_workflow_explicitly_updates_capacity_services():
    workflow = Path(".github/workflows/deploy.yml").read_text(encoding="utf-8")

    assert "pull db redis minio loki promtail p004-backend worker" in workflow
    assert "up -d db redis minio loki promtail p004-backend worker" in workflow


def test_main_workflows_cancel_stale_runs():
    """CI huỷ run cũ trên nhánh, nhưng KHÔNG BAO GIỜ trên main.

    Trước đây `cancel-in-progress: true` áp cho mọi ref. Merge liên tiếp vào main
    khiến run trước bị huỷ, mà Deploy lại chờ `workflow_run.conclusion == success`
    — nên Deploy gần như không bao giờ chạy. Trên nhánh thì huỷ run cũ vẫn đúng và
    tiết kiệm runner; trên main thì mỗi run là cổng vào một lần deploy, không được
    huỷ. Vì vậy giá trị ở đây là một biểu thức, không phải hằng số boolean.
    """
    ci_workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))
    deploy_workflow = yaml.safe_load(Path(".github/workflows/deploy.yml").read_text(encoding="utf-8"))

    assert ci_workflow["concurrency"]["group"] == "ci-${{ github.ref }}"
    assert ci_workflow["concurrency"]["cancel-in-progress"] == (
        "${{ github.ref != 'refs/heads/main' }}"
    ), (
        "CI phải giữ nguyên run trên main. Đặt lại thành True là làm Deploy "
        "chết đói trở lại: run bị huỷ thì workflow_run không bao giờ success."
    )

    # Deploy dùng group cố định nên hai lần deploy không chồng nhau; ở đây huỷ
    # run cũ là đúng, vì chỉ bản mới nhất mới đáng lên production.
    assert deploy_workflow["concurrency"]["group"] == "deploy-production"
    assert deploy_workflow["concurrency"]["cancel-in-progress"] is True


def test_ci_runs_changed_components_once_and_deploy_waits_for_it():
    ci_workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))
    deploy_workflow = yaml.safe_load(Path(".github/workflows/deploy.yml").read_text(encoding="utf-8"))
    checks_workflow = yaml.safe_load(Path(".github/workflows/checks.yml").read_text(encoding="utf-8"))

    assert "changes" in ci_workflow["jobs"]
    assert ci_workflow["jobs"]["checks"]["needs"] == "changes"
    assert deploy_workflow[True]["workflow_run"]["workflows"] == ["CI"]
    assert "test" not in deploy_workflow["jobs"]
    assert checks_workflow[True]["workflow_call"]["inputs"]["run_backend"]["type"] == "boolean"
    assert "zricethezav/gitleaks:v8.30.1" in Path(".github/workflows/checks.yml").read_text(encoding="utf-8")


def test_runner_toolcache_warmer_pins_ci_runtime_versions():
    workflow = yaml.safe_load(Path(".github/workflows/warm-runner-toolcache.yml").read_text())
    steps = workflow["jobs"]["warm"]["steps"]

    assert "workflow_dispatch" in workflow[True]
    assert any(step.get("uses") == "actions/setup-python@v5" for step in steps)
    assert any(step.get("uses") == "actions/setup-node@v4" for step in steps)
