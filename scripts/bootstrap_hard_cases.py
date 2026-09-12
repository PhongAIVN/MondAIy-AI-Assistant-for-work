"""Sinh thêm case chat đời thường (kiểu hard_cases.json) bằng LLM, có kiểm soát
nhãn ngay lúc sinh — không phải sinh xong rồi tự phân loại lại (tránh cộng dồn
lỗi 2 lớp: lỗi sinh câu + lỗi tự phân loại câu vừa sinh).

Lý do cần: "ml/model for extension/data/README.md" mục "Hướng 4" ghi lại
kết quả ML classifier chỉ 70.8% trên hard_cases.json (24 câu) dù đạt 94.5% CV
trên 220 câu chính — classifier overfit vào văn phong "sạch" của 220 câu do kỹ
sư tự soạn, cần thêm data văn phong chat thật để nó generalize được. Đã thử
kéo raw text công khai (5CD-AI/Vietnamese-Multi-turn-Chat-Alpaca,
fsnaix/vietnamese-corpus-large) nhưng cả hai sai văn phong (hội thoại
người-hỏi-AI và văn viết trang trọng, không phải chat nhóm việc đời thường) —
xem ghi chú nghiên cứu trong hội thoại lúc implement. Nên đổi hướng: LLM sinh
trực tiếp theo đúng văn phong đã biết rõ đặc điểm qua hard_cases.json.

Output: "ml/model for extension/data/bootstrap_cases.json" — TÁCH RIÊNG
khỏi hard_cases.json (không trộn) vì provenance khác nhau (hard_cases.json là
câu thật từ Zalo + case tự soạn bổ sung; file này là câu LLM sinh theo văn
phong đó, không phải câu thật) — giữ đúng tinh thần "case đã ổn định thì không
sửa ngầm" của README, không âm thầm đổi nguồn gốc của hard_cases.json.

Chạy: PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/bootstrap_hard_cases.py
Tốn LLM call thật (không phải LLM_PROVIDERS test), không chạy trong CI.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.llm import get_llm  # noqa: E402

_OUTPUT_PATH = Path(__file__).resolve().parents[1] / "eval" / "golden_dataset" / "task_extraction" / "bootstrap_cases.json"

_SYSTEM_PROMPT = """Bạn tạo dữ liệu eval cho một bộ phân loại "đây có phải một
việc cần làm thật sự không" (task/to-do), áp dụng cho tin nhắn trích từ NHÓM
CHAT CÔNG VIỆC/HỌC TẬP tiếng Việt đời thường (Zalo, Messenger) — KHÔNG phải
câu văn viết trang trọng, KHÔNG phải hội thoại hỏi-đáp với AI assistant.

Mỗi câu PHẢI mang đặc điểm chat thật: câu ngắn, ngữ pháp không chuẩn mực,
thiếu chủ ngữ, có tiểu từ đệm cuối câu (nhé/ạ/nha/đó/á...), có thể có
@mention, có thể lẫn thì quá khứ (đã/rồi/xong) dù đang là yêu cầu, đa dạng
động từ (không chỉ dùng các động từ phổ biến như gửi/nộp/báo cáo).

is_task=true: có ai đó THẬT SỰ CẦN THỰC HIỆN một hành động cụ thể, việc đó
CHƯA xảy ra — kể cả khi nhờ vả gián tiếp, không chỉ đích danh ("ai đó",
"bạn nào rảnh"), giao việc kiểu "để X lo", hoặc câu hỏi nhưng thực chất là nhờ
vả ("mọi người xem giúp được không nhỉ").

is_task=false: chào hỏi, cảm ơn, tường thuật việc ĐÃ xong, nhận xét/than
phiền không kèm hành động cụ thể, câu hỏi phiếm, thông báo (nghỉ lễ, lịch
học), phản hồi cụt ("gửi ạ", "ok"), hoặc câu có động từ hành động nhưng ở
NGỮ CẢNH đã làm rồi/không phải yêu cầu.

Sinh câu ĐA DẠNG, không lặp mẫu câu, không dùng nguyên văn ví dụ trong hướng
dẫn này."""


class _BootstrapCase(BaseModel):
    text: str = Field(description="Một dòng chat tiếng Việt, đúng văn phong đã mô tả")
    is_task: bool


class _BootstrapBatch(BaseModel):
    cases: list[_BootstrapCase]


async def _generate_batch(n_positive: int, n_negative: int) -> list[_BootstrapCase]:
    structured_llm = get_llm(lane="work_response").with_structured_output(_BootstrapBatch)
    prompt = (
        f"Sinh {n_positive} câu is_task=true và {n_negative} câu is_task=false "
        f"(tổng {n_positive + n_negative} câu), xen kẽ ngẫu nhiên, không theo thứ tự "
        "cố định positive-rồi-negative."
    )
    result: _BootstrapBatch = await structured_llm.ainvoke(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
    )
    return result.cases


async def main() -> None:
    # 3 batch nhỏ thay vì 1 batch lớn — giảm rủi ro model lặp mẫu câu khi phải
    # sinh quá nhiều trong một lượt, và tránh mất hết nếu một lượt lỗi giữa chừng.
    batches = await asyncio.gather(*(_generate_batch(10, 10) for _ in range(3)))
    all_cases = [case for batch in batches for case in batch]

    existing_texts = set()
    output: list[dict] = []
    if _OUTPUT_PATH.exists():
        output = json.loads(_OUTPUT_PATH.read_text(encoding="utf-8"))
        existing_texts = {c["input"]["text"] for c in output}

    next_id = len(output) + 1
    added = 0
    for case in all_cases:
        text = case.text.strip()
        if not text or text in existing_texts:
            continue
        existing_texts.add(text)
        output.append(
            {
                "id": f"TASK-BOOT-{next_id:03d}",
                "description": f"LLM-generated, expected_is_task={case.is_task}",
                "input": {"text": text},
                "expected": {"is_task": case.is_task},
            }
        )
        next_id += 1
        added += 1

    _OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    positive = sum(1 for c in output if c["expected"]["is_task"])
    print(f"Thêm {added} case mới. Tổng {len(output)} case ({positive} positive / {len(output) - positive} negative).")
    print(f"Đã ghi: {_OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
