.PHONY: run worker test test-agent-coverage test-quality evaluation-evidence lint format typecheck check clean

# Trỏ thẳng python trong .venv, không dùng "python"/"uvicorn" trơn theo PATH —
# PATH đổi theo terminal (vd. trỏ nhầm sang Python global) từng gây chạy 2
# process backend cùng lúc, giành port 8000.
run:
	.venv/Scripts/python.exe -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# POST /runs chỉ enqueue (status=queued) — process này mới thật sự chạy pipeline
# 9 node (claim_next_run + execute_run trong src/worker.py). Không chạy song
# song với `make run` thì mọi Sync treo mãi ở "queued", không báo lỗi gì.
worker:
	.venv/Scripts/python.exe -m src.worker

test:
	pytest tests/ -v

test-agent-coverage:
	pytest tests/test_agents/v1/pipeline --cov=src.agents.pipeline --cov-branch --cov-report=term-missing --cov-report=html:htmlcov --cov-fail-under=80

test-quality:
	powershell -ExecutionPolicy Bypass -File scripts/test_quality.ps1

evaluation-evidence:
	powershell -ExecutionPolicy Bypass -File scripts/generate_evaluation_evidence.ps1

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

typecheck:
	mypy src/

check: lint format test

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
