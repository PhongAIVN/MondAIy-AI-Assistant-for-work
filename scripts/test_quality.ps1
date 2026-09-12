param(
    [int]$MinCoverage = 70
)

$ErrorActionPreference = "Stop"
$resultDir = Join-Path (Get-Location) "test-results"
New-Item -ItemType Directory -Force -Path $resultDir | Out-Null

$pytestLog = Join-Path $resultDir "pytest.log"
$junitFile = Join-Path $resultDir "pytest.xml"
$coverageXml = Join-Path $resultDir "coverage.xml"
$failureLog = Join-Path $resultDir "failures.log"
$summaryFile = Join-Path $resultDir "summary.json"

$testPaths = @("tests")

Write-Host "Running pytest quality suite..."
# Pytest/coverage can emit harmless ResourceWarning messages on stderr when
# SQLite test connections are garbage-collected. Do not let PowerShell treat
# native stderr as a runner failure; pytest's exit code remains authoritative.
$previousErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& python -m pytest @testPaths `
    --cov=src `
    --cov-branch `
    --cov-report=term-missing `
    --cov-report=html:htmlcov `
    --cov-report=xml:$coverageXml `
    --cov-fail-under=$MinCoverage `
    --junitxml=$junitFile 2>&1 | Tee-Object -FilePath $pytestLog
$testExit = $LASTEXITCODE
$ErrorActionPreference = $previousErrorAction

& powershell -ExecutionPolicy Bypass -File scripts/generate_evaluation_evidence.ps1

$failureLines = Select-String -Path $pytestLog -Pattern '^\s*FAILED |^\s*ERROR |short test summary' -SimpleMatch:$false
if ($failureLines) {
    # Keep the complete pytest output so the traceback and captured logs are
    # available, not only the short summary line.
    Copy-Item -LiteralPath $pytestLog -Destination $failureLog -Force
} else {
    "No pytest failures." | Set-Content -Path $failureLog -Encoding utf8
}

$junit = [xml](Get-Content -Raw $junitFile)
$suite = $junit.testsuites.testsuite
$summary = [ordered]@{
    generated_at = (Get-Date).ToUniversalTime().ToString("o")
    exit_code = $testExit
    tests = [int]$suite.tests
    passed = [int]$suite.tests - [int]$suite.failures - [int]$suite.errors - [int]$suite.skipped
    failed = [int]$suite.failures
    errors = [int]$suite.errors
    skipped = [int]$suite.skipped
    junit = $junitFile
    pytest_log = $pytestLog
    failure_log = $failureLog
    coverage_xml = $coverageXml
    coverage_html = (Join-Path (Get-Location) "htmlcov/index.html")
}
$summary | ConvertTo-Json | Set-Content -Path $summaryFile -Encoding utf8

Write-Host "Summary: $($summary.tests) tests | $($summary.passed) passed | $($summary.failed) failed | $($summary.errors) errors | $($summary.skipped) skipped"
Write-Host "Coverage report: $($summary.coverage_html)"
Write-Host "Failure log: $failureLog"

if ($testExit -ne 0) {
    exit $testExit
}
