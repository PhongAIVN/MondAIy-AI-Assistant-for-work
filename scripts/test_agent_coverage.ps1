param(
    [int]$MinCoverage = 80
)

$ErrorActionPreference = "Stop"

python -m pytest tests/test_agents/v1/pipeline `
    --cov=src.agents.pipeline `
    --cov-branch `
    --cov-report=term-missing `
    --cov-report=html:htmlcov `
    --cov-fail-under=$MinCoverage

if ($LASTEXITCODE -ne 0) {
    throw "Agent pipeline coverage is below $MinCoverage% or tests failed."
}
