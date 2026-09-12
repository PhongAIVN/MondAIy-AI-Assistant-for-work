"""Planner xác định (ADR-018 QĐ-1) — không gọi LLM, không I/O ngoài DB.

`estimate.py` ước lượng thời lượng, `score.py` xếp hạng ưu tiên. `schedule.py`
(xếp vào khối rảnh Calendar) nằm ngoài phạm vi lượt này.
"""
