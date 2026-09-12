param(
    [string]$ResultsDir = "test-results",
    [string]$MetricsFile = "eval/evaluation_metrics.json",
    [string]$OutputFile = "eval/evaluation-evidence.md"
)

$ErrorActionPreference = "Stop"

function Get-MetricValue([object]$Object, [string]$Name, [string]$Default = "TBD") {
    if ($null -ne $Object -and $null -ne $Object.$Name -and "$($Object.$Name)" -ne "") {
        return "$($Object.$Name)"
    }
    return $Default
}

$junitPath = Join-Path (Get-Location) "$ResultsDir/pytest.xml"
$coveragePath = Join-Path (Get-Location) "$ResultsDir/coverage.xml"
$pytestLog = "$ResultsDir/pytest.log"
$coverageHtml = "htmlcov/index.html"

if (-not (Test-Path $junitPath)) {
    throw "Missing $junitPath. Run the pytest quality suite first."
}

$junit = [xml](Get-Content -Raw $junitPath)
$suite = $junit.testsuites.testsuite
$tests = [int]$suite.tests
$failures = [int]$suite.failures
$errors = [int]$suite.errors
$skipped = [int]$suite.skipped
$passed = $tests - $failures - $errors - $skipped

$coverage = "TBD"
if (Test-Path $coveragePath) {
    $coverageXml = [xml](Get-Content -Raw $coveragePath)
    $lineRate = [double]$coverageXml.coverage.'line-rate'
    $coverage = "{0:P1}" -f $lineRate
}

$metrics = $null
if (Test-Path $MetricsFile) {
    $metrics = Get-Content -Raw $MetricsFile | ConvertFrom-Json
}

$faithfulness = Get-MetricValue $metrics.rag "faithfulness"
$answerRelevance = Get-MetricValue $metrics.rag "answer_relevance"
$contextPrecision = Get-MetricValue $metrics.rag "context_precision"
$contextRecall = Get-MetricValue $metrics.rag "context_recall"
$participants = Get-MetricValue $metrics.user_feedback "participants"
$rating = Get-MetricValue $metrics.user_feedback "average_rating"
$feedback = Get-MetricValue $metrics.user_feedback "summary"

$performanceRows = "| TBD | TBD | TBD | TBD |"
if ($null -ne $metrics.performance -and $metrics.performance.Count -gt 0) {
    $performanceRows = ($metrics.performance | ForEach-Object {
        "| $($_.endpoint) | $($_.avg_response_time) | $($_.p95) | $($_.p99) |"
    }) -join "`n"
}

$outputDir = Split-Path -Parent $OutputFile
if ($outputDir) { New-Item -ItemType Directory -Force -Path $outputDir | Out-Null }

$content = @"
# Evaluation Evidence — mondAIy

Generated: $((Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"))

## 1. Test Results

- Số lượng test cases: $tests
- Pass/Fail: $passed/$($failures + $errors)
- Skipped: $skipped
- Code coverage: $coverage
- Pytest output: [$pytestLog]($pytestLog)
- Coverage report: [$coverageHtml]($coverageHtml)
- Failure log: [$ResultsDir/failures.log]($ResultsDir/failures.log)

## 2. RAG Quality Metrics

| Metric | Score | Benchmark |
|--------|-------|-----------|
| Faithfulness | $faithfulness | > 0.7 |
| Answer Relevance | $answerRelevance | > 0.7 |
| Context Precision | $contextPrecision | > 0.6 |
| Context Recall | $contextRecall | > 0.6 |

## 3. Performance Metrics

| Endpoint | Avg Response Time | P95 | P99 |
|----------|------------------|-----|-----|
$performanceRows

## 4. User Feedback

- Số người tham gia test: $participants
- Rating trung bình: $rating
- Phản hồi chính: $feedback

## Artifacts

- JUnit XML: [$ResultsDir/pytest.xml]($ResultsDir/pytest.xml)
- Coverage XML: [$ResultsDir/coverage.xml]($ResultsDir/coverage.xml)

> RAG, performance và user feedback chỉ được điền khi có số liệu trong
> MetricsFile; script không tự suy đoán các metric này.
"@

Set-Content -Path $OutputFile -Value $content -Encoding utf8
Write-Host "Evaluation evidence written to $OutputFile"
