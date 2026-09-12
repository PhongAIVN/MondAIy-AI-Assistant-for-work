"""Đổi cột vector từ 2048 sang 1024 chiều cho Vietnamese_Embedding của FPT.

Revision ID: a1c4f7e29b30
Revises: f6b9d12e4a70
Create Date: 2026-08-28

Vì sao phải XOÁ embedding cũ chứ không chuyển đổi:

pgvector cố định số chiều ở DDL. Vector 2048 chiều không "cắt" được thành 1024 —
mỗi chiều là một trục do chính model sinh ra, cắt đi là ra một vector vô nghĩa
chứ không phải một vector kém chính xác hơn.

Và kể cả giữ được thì cũng không dùng được: trộn vector của hai model khác nhau
trong cùng một cột làm khoảng cách cosine mất ý nghĩa hoàn toàn — truy hồi sẽ
trả kết quả sai mà không báo lỗi.

Embedding đang có được sinh bằng `nvidia/nemotron-3-embed-1b:free` qua OpenRouter,
và đường đó hiện trả 402 vì hết credit. Nghĩa là chúng đã không dùng được từ
trước; migration này không làm mất khả năng nào đang hoạt động.

Sau khi chạy phải NHÚNG LẠI — không có vòng quét nền nào tự làm:
    chunks         — chạy tay `scripts/discord/embed_chunks.py <run_id>`
    user_memories  — `backfill_memory_embeddings`, tự chạy khi mở hội thoại

Migration này drop index vector của `chunks` và KHÔNG dựng lại: số chiều mới đổi
loại index (1024 chiều dùng HNSW trên `vector`, 2048 phải đi qua `halfvec`), và
dựng index trên cột toàn NULL là vô ích. `embed_chunks.py` dựng lại sau khi nhúng.

`downgrade` đưa cột về 2048 và cũng xoá embedding: không có đường quay lại dữ
liệu cũ, và giả vờ có là tệ hơn.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1c4f7e29b30"
down_revision: str | Sequence[str] | None = "f6b9d12e4a70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BANG = ("chunks", "user_memories")
# Index vector đã từng được dựng trên từng bảng. `scripts/discord/embed_chunks.py`
# dựng lại đúng loại cho số chiều mới sau khi nhúng xong — ở 1024 chiều là HNSW
# trên `vector` thay vì trên `halfvec` như hồi 2048.
_INDEX_VECTOR = {"chunks": ("ix_chunks_embedding", "ix_chunks_embedding_half")}


def _doi_chieu(so_chieu: int) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite trong test không có kiểu vector; cột là JSON nên không cần đổi.
        return
    inspector = sa.inspect(bind)
    co_san = set(inspector.get_table_names())
    for bang in _BANG:
        if bang not in co_san:
            continue
        cot = {c["name"] for c in inspector.get_columns(bang)}
        if "embedding" not in cot:
            continue
        # Phải drop index vector TRƯỚC. Đã đo trên Postgres thật: index KHÔNG
        # chặn ALTER TYPE — lệnh chạy xong bình thường — nhưng index SỐNG SÓT
        # với định nghĩa cũ. Production có
        # `ix_chunks_embedding_half` = hnsw((embedding::halfvec(2048))); sau
        # ALTER nó vẫn là halfvec(2048) trong khi cột đã là vector(1024), và
        # lệnh ghi tiếp theo nổ "expected 2048 dimensions, not 1024".
        #
        # Nghĩa là bỏ bước này thì migration BÁO THÀNH CÔNG rồi mới hỏng lúc
        # nhúng lại — kiểu hỏng khó lần nhất.
        for ten_index in _INDEX_VECTOR.get(bang, ()):
            op.execute(sa.text(f"DROP INDEX IF EXISTS {ten_index}"))
        # Xoá dữ liệu trước rồi mới đổi kiểu: ALTER TYPE trên cột còn vector
        # khác chiều bị từ chối, và USING không cứu được vì không có phép
        # chuyển đổi đúng nghĩa giữa hai không gian nhúng.
        op.execute(sa.text(f"UPDATE {bang} SET embedding = NULL WHERE embedding IS NOT NULL"))
        op.execute(sa.text(f"ALTER TABLE {bang} ALTER COLUMN embedding TYPE vector({so_chieu})"))
    if "user_memories" in co_san:
        # Nhãn model cũ phải mất theo vector, nếu không `backfill_memory_embeddings`
        # nhìn nhãn tưởng đã nhúng đúng model rồi và bỏ qua hàng đó vĩnh viễn.
        op.execute(sa.text("UPDATE user_memories SET embedding_model = NULL"))


def upgrade() -> None:
    _doi_chieu(1024)


def downgrade() -> None:
    _doi_chieu(2048)
