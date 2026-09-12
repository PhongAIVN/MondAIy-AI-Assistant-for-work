"""So sánh 3 hướng phân loại "có phải việc cần làm không" cho tab "Lấy dữ liệu":
rule-based thuần, LLM thuần, rule+LLM hybrid
— trên CÙNG một golden dataset ("eval/golden_dataset/task_extraction/").

Dùng thẳng is_task_like()/_is_task_like_llm()/_is_task_like_hybrid() thật
(không tự viết bản copy riêng) — script này so sánh đúng cái đang chạy
production, không phải một bản mô phỏng lệch dần theo thời gian.

Chạy một lần để ra quyết định, không phải code production, không chạy trong CI
(gọi LLM thật, tốn token + có độ trễ mạng). Cần LLM_PROVIDERS bao gồm đúng
provider có key thật (xem ghi chú trong .env.example và .env — get_llm() chỉ
tự thêm llm_provider vào provider_names khi nó khác "openai", nên
LLM_PROVIDER=openai một mình không đủ, phải set thêm LLM_PROVIDERS=openai).

Chạy: PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/eval_task_classifiers.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.page_extraction import (  # noqa: E402
    _is_task_like_hybrid,
    _is_task_like_llm,
    confidence_tier,
    is_task_like,
)

_CONCURRENCY = 8
_DATASET_DIR = Path(__file__).resolve().parents[1] / "eval" / "golden_dataset" / "task_extraction"


def _load_cases(name: str) -> list[tuple[str, bool]]:
    raw = json.loads((_DATASET_DIR / name).read_text(encoding="utf-8"))
    return [(c["input"]["text"], c["expected"]["is_task"]) for c in raw]


@dataclass
class Metrics:
    name: str
    tp: int = 0
    fp: int = 0
    tn: int = 0
    fn: int = 0
    llm_calls: int = 0
    seconds: float = 0.0

    @property
    def total(self) -> int:
        return self.tp + self.fp + self.tn + self.fn

    @property
    def accuracy(self) -> float:
        return (self.tp + self.tn) / self.total if self.total else 0.0

    @property
    def precision(self) -> float:
        denom = self.tp + self.fp
        return self.tp / denom if denom else 0.0

    @property
    def recall(self) -> float:
        denom = self.tp + self.fn
        return self.tp / denom if denom else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0


def _score(metrics: Metrics, predicted: bool, expected: bool) -> None:
    if predicted and expected:
        metrics.tp += 1
    elif predicted and not expected:
        metrics.fp += 1
    elif not predicted and expected:
        metrics.fn += 1
    else:
        metrics.tn += 1


async def _eval_rule(cases: list[tuple[str, bool]]) -> Metrics:
    m = Metrics(name="Hướng 1: Rule-based thuần")
    started = time.monotonic()
    for text, expected in cases:
        _score(m, is_task_like(text), expected)
    m.seconds = time.monotonic() - started
    return m


async def _eval_llm(cases: list[tuple[str, bool]]) -> Metrics:
    m = Metrics(name="Hướng 2: LLM thuần")
    semaphore = asyncio.Semaphore(_CONCURRENCY)

    async def _call(text: str) -> bool:
        async with semaphore:
            return await _is_task_like_llm(text)

    started = time.monotonic()
    predictions = await asyncio.gather(*(_call(text) for text, _ in cases))
    m.seconds = time.monotonic() - started
    m.llm_calls = len(cases)
    for (_, expected), predicted in zip(cases, predictions, strict=True):
        _score(m, predicted, expected)
    return m


async def _eval_hybrid(cases: list[tuple[str, bool]]) -> Metrics:
    m = Metrics(name="Hướng 3: Rule + LLM hybrid")
    semaphore = asyncio.Semaphore(_CONCURRENCY)
    started = time.monotonic()
    predictions = await asyncio.gather(*(_is_task_like_hybrid(text, semaphore) for text, _ in cases))
    m.seconds = time.monotonic() - started
    m.llm_calls = sum(1 for text, _ in cases if confidence_tier(text) == "ambiguous")
    for (_, expected), predicted in zip(cases, predictions, strict=True):
        _score(m, predicted, expected)
    return m


def _print_row(m: Metrics, total_cases: int) -> None:
    print(
        f"{m.name:<30} acc={m.accuracy:6.1%}  precision={m.precision:6.1%}  "
        f"recall={m.recall:6.1%}  f1={m.f1:6.1%}  llm_calls={m.llm_calls:>4}/{total_cases:<4}  "
        f"{m.seconds:5.1f}s"
    )


async def main() -> None:
    main_cases = _load_cases("task_extraction_cases.json")
    hard_cases = _load_cases("hard_cases.json")
    positive_count = sum(1 for _, expected in main_cases if expected)
    print(f"Golden dataset chính: {len(main_cases)} câu ({positive_count} positive / {len(main_cases) - positive_count} negative)")
    print(f"Hard cases (Zalo thật, nhãn chủ quan): {len(hard_cases)} câu\n")

    print("=== Golden dataset chính ===")
    rule_m, llm_m, hybrid_m = await asyncio.gather(
        _eval_rule(main_cases), _eval_llm(main_cases), _eval_hybrid(main_cases)
    )
    for m in (rule_m, llm_m, hybrid_m):
        _print_row(m, len(main_cases))

    print("\n=== Hard cases (Zalo thật — không gate CI, chỉ minh hoạ) ===")
    rule_h, llm_h, hybrid_h = await asyncio.gather(
        _eval_rule(hard_cases), _eval_llm(hard_cases), _eval_hybrid(hard_cases)
    )
    for m in (rule_h, llm_h, hybrid_h):
        _print_row(m, len(hard_cases))

    print("\n=== Chi tiết từng hard case ===")
    solo_semaphore = asyncio.Semaphore(1)
    for text, expected in hard_cases:
        rule_pred = is_task_like(text)
        llm_pred = await _is_task_like_llm(text)
        hybrid_pred = await _is_task_like_hybrid(text, solo_semaphore)
        print(
            f"  [{'OK' if rule_pred == expected else 'SAI'}] rule={rule_pred!s:<5} "
            f"[{'OK' if llm_pred == expected else 'SAI'}] llm={llm_pred!s:<5} "
            f"[{'OK' if hybrid_pred == expected else 'SAI'}] hybrid={hybrid_pred!s:<5} "
            f"expected={expected!s:<5} — {text}"
        )


if __name__ == "__main__":
    asyncio.run(main())

