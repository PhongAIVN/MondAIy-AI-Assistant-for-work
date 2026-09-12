# Filter Flow — Golden Dataset Test Report

**Execution date:** 2026-08-15  
**Dataset:** `eval/golden_dataset/fetch_norm_filter`  
**Implementation under test:** `src.services.filter_classify.filter_and_classify`  
**Test:** `tests/v1/test_gmail_filter_gold.py`

## Additional V1 mail-filter evaluation

The repository also contains a broader 100-case Gmail benchmark documented in
[`test-results/mail-filter-v1-dataset-report.md`](../../../../test-results/mail-filter-v1-dataset-report.md).
It exercises the same deterministic filter path through
`filter_and_classify`, including the pipeline filter node and Gmail search
integration.

| V1 benchmark metric | Result |
|---|---:|
| Golden cases | 100 |
| Expected KEEP | 57 |
| Expected DROP | 43 |
| True positives | 57 |
| False positives | 0 |
| False negatives | 0 |
| True negatives | 43 |
| Precision / Recall / F1 | **1.0000 / 1.0000 / 1.0000** |
| Test result | **1 passed** |

The V1 result is not contradictory to the 9/10 result below: these are two
different benchmark inputs. The 100-case V1 workbook passes completely, while
the smaller `filter_cases.json` contract still exposes the separate
`GML-F-021` regression.

The V1 report also records the RADAR action-item triage check: all 744 stripped
messages are routed to the LLM judge rather than being auto-dropped, so no
possible action item is silently discarded from the anonymized corpus.

## Result

**Filter golden test: 9/10 cases correct — NOT GREEN.**

| Metric | Result |
|---|---:|
| Executable filter cases | 10 |
| Expected accepted | 3 |
| Actual accepted | 4 |
| Expected rejected | 7 |
| Actual rejected | 6 |
| Correct cases | 9 |
| Failed cases | 1 |
| Exact case accuracy | 90% |

The complete `fetch_norm_filter` inventory contains **36 cases**: 18 Gmail and
18 Discord. Its manifest has no missing fixture or expected files. The current
filter-specific executable test uses the separate 10-case file
`filter_cases.json`; the remaining 36-case manifest covers fetch, normalize,
permission, duplicate/version and partial/error scenarios in addition to
filter relevance.

## Case-by-case result

| Case | Expected | Actual | Result | Actual reason |
|---|---|---|---|---|
| GML-F-019 | rejected | rejected | PASS | `negative_state` |
| GML-F-020 | rejected | rejected | PASS | `negative_state` |
| GML-F-021 | rejected | **accepted** | **FAIL** | — |
| GML-F-022 | rejected | rejected | PASS | `negative_state` |
| GML-F-023 | rejected | rejected | PASS | `stale_thread` |
| GML-F-024 | rejected | rejected | PASS | `low_importance` |
| GML-F-025 | accepted | accepted | PASS | — |
| GML-F-026 | accepted | accepted | PASS | — |
| GML-F-027 | accepted | accepted | PASS | — |
| GML-F-028 | rejected | rejected | PASS | `label_not_approved` |

## Failed case

### GML-F-021 — personal shopping receipt outside program scope

Input characteristics:

- Sender: `receipt@store.example`
- Subject: `Your order receipt`
- Body contains transactional terms: purchase/order/total
- Recipient is the configured user
- Label is `INBOX`

Expected behavior: reject with `low_relevance`.  
Observed behavior: accepted by the filter.

This is a relevance-classification gap: the current filter recognizes the
message as addressed to the user, but does not apply a strong enough
transactional/non-program negative rule to override that signal.

## Commands and evidence

| Check | Command / purpose | Evidence |
|---|---|---|
| Filter golden pytest | `.venv\Scripts\python.exe -m pytest tests/v1/test_gmail_filter_gold.py -vv` | [13-filter-golden-dataset.log](./13-filter-golden-dataset.log) |
| Per-case classification | Directly ran `filter_and_classify` over all 10 entries in `filter_cases.json` | [14-filter-golden-classification.log](./14-filter-golden-classification.log) |
| Dataset inventory | Counted manifest entries and checked fixture/expected paths | [15-filter-golden-inventory.log](./15-filter-golden-inventory.log) |
| Broader V1 benchmark | 100-case Gmail workbook, metrics and RADAR triage results | [mail-filter-v1-dataset-report.md](../../../../test-results/mail-filter-v1-dataset-report.md) |

## Conclusion

The filter flow is **90% correct on the current executable golden subset**.
The gate remains conditional until GML-F-021 is fixed or the expected behavior
is formally revised. After any change, rerun the same pytest command and require
all 10 cases to pass.
