> **P-004 dùng [`docs/ADR/`](../ADR) làm nơi ghi quyết định.** Thư mục này đến từ
> repository-harness và **để trống có chủ ý** — đừng mở một nhà thứ hai cho decision.
> Mẫu `templates/decision.md` vẫn dùng được, nhưng file kết quả đặt trong `ADR/`.

# Decisions

Decision records preserve lasting product, architecture, data ownership,
security, compatibility, and validation choices that future work must inherit.

Use `docs/templates/decision.md`. Task-local implementation choices remain in
the active execution plan and do not require a separate decision.

An installed consumer begins with no fabricated decisions. Add local decision
documents here as real choices are accepted, then index them in this file.
