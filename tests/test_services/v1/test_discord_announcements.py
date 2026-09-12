import uuid
from datetime import UTC, datetime, timedelta

from src.db import SessionLocal, engine
from src.models.evidence import SourceItem, SourceScope
from src.services.discord_announcements import (
    MIN_SCORE,
    classify_announcement,
    is_announcement_scope,
    list_announcements,
)


def _add_item(db, scope, *, content, offset, suffix, roles=None, author="btc", attachments=0):
    """Thêm một tin vào kho bằng chứng để test lọc thông báo."""
    occurred_at = datetime.now(UTC) + timedelta(minutes=offset)
    db.add(
        SourceItem(
            provider="discord",
            external_id=f"ann-{suffix}-{offset}",
            scope_id=scope.id,
            author_external_id=author,
            author_name=author,
            author_roles=roles,
            content=content,
            item_type=0,
            attachment_count=attachments,
            deep_link=f"https://discord.com/channels/g/{scope.external_id}/{offset}",
            content_hash=f"hash-{suffix}-{offset}",
            source_updated_at=occurred_at,
            observed_at=occurred_at,
            run_id="test",
        )
    )


def test_kenh_thong_bao_nhan_dien_theo_the_loai_va_ten():
    assert is_announcement_scope(SourceScope(provider="discord", external_id="1", kind=5))
    assert is_announcement_scope(SourceScope(provider="discord", external_id="2", kind=0, name="📢-thông-báo"))
    assert not is_announcement_scope(SourceScope(provider="discord", external_id="3", kind=0, name="hoi-dap-chung"))


def test_tin_nhac_ca_kenh_la_thong_bao_du_o_kenh_thuong():
    score, reasons = classify_announcement(
        content="@everyone Buổi lab tối nay dời sang 20h nhé cả nhà",
        author_roles=None,
    )
    assert score >= MIN_SCORE
    assert any("@everyone" in reason for reason in reasons)


def test_chat_thuong_cua_mentor_khong_thanh_thong_bao():
    """Mentor nhắc tới deadline trong lúc chat không phải một thông báo chính thức."""
    score, _ = classify_announcement(
        content="mình nghĩ deadline này hơi gấp, nhóm bạn thấy sao",
        author_roles=["Mentor"],
    )
    assert score < MIN_SCORE


def test_tin_khong_con_chu_nao_thi_khong_vao_danh_sach():
    """Bot trong kênh thông báo hay đăng embed nên content rỗng hoặc chỉ có mention.

    Gặp thật trên dữ liệu đã cào: lọt vào danh sách thì agent đưa cho học viên
    một dòng trống. Có file đính kèm thì vẫn giữ vì còn cái link để mở.
    """
    assert classify_announcement(content="", author_roles=None, in_announcement_channel=True) == (0, ())
    assert classify_announcement(content="<@744497566581915730>", author_roles=None, in_announcement_channel=True) == (
        0,
        (),
    )

    score, _ = classify_announcement(content="", author_roles=None, attachment_count=1, in_announcement_channel=True)
    assert score >= MIN_SCORE


def test_tin_ngan_khong_co_tin_hieu_manh_bi_loai():
    score, reasons = classify_announcement(content="ok mọi người nhé", author_roles=["BTC"])
    assert (score, reasons) == (0, ())


def test_liet_ke_thong_bao_chi_trong_pham_vi_duoc_cap():
    suffix = uuid.uuid4().hex
    with SessionLocal() as db:
        allowed = SourceScope(provider="discord", external_id=f"ann-allowed-{suffix}", name="thông-báo", kind=5)
        forbidden = SourceScope(
            provider="discord", external_id=f"ann-forbidden-{suffix}", name="thông-báo-nội-bộ", kind=5
        )
        db.add_all([allowed, forbidden])
        db.flush()
        _add_item(
            db,
            allowed,
            content="Hạn nộp bài Gate 2 dời sang 23h59 ngày 20/08, mọi người lưu ý",
            offset=1,
            suffix=f"in-{suffix}",
        )
        _add_item(
            db,
            forbidden,
            content="@everyone Kênh nội bộ: chốt điểm nhóm T004 trước thứ Sáu",
            offset=2,
            suffix=f"out-{suffix}",
        )
        db.commit()
        allowed_id, forbidden_id = allowed.id, forbidden.id

    found = list_announcements(engine, scope_ids=[allowed_id])
    contents = [item.content for item in found]
    assert any("Gate 2" in c for c in contents)
    assert not any("nội bộ" in c for c in contents)

    # Phạm vi rỗng là tập quyền rỗng, không phải "không giới hạn".
    assert list_announcements(engine, scope_ids=[]) == []

    forbidden_only = list_announcements(engine, scope_ids=[forbidden_id])
    assert all("Gate 2" not in item.content for item in forbidden_only)


def test_thao_luan_thuong_trong_kenh_chung_khong_lot_vao_danh_sach():
    suffix = uuid.uuid4().hex
    with SessionLocal() as db:
        chat = SourceScope(provider="discord", external_id=f"ann-chat-{suffix}", name="hoi-dap", kind=0)
        db.add(chat)
        db.flush()
        _add_item(
            db,
            chat,
            content="cho em hỏi deadline nộp bài là hôm nào ạ, em tìm mãi không thấy",
            offset=1,
            suffix=f"chat-{suffix}",
            roles=["Học viên"],
            author="hocvien",
        )
        db.commit()
        chat_id = chat.id

    assert list_announcements(engine, scope_ids=[chat_id]) == []


def test_loc_theo_tu_khoa_khong_dau_va_theo_cua_so_thoi_gian():
    suffix = uuid.uuid4().hex
    with SessionLocal() as db:
        scope = SourceScope(provider="discord", external_id=f"ann-win-{suffix}", name="thong-bao", kind=5)
        db.add(scope)
        db.flush()
        _add_item(
            db,
            scope,
            content="Lịch học tuần này đổi sang thứ Bảy, phòng lab tầng 3",
            offset=-2000,
            suffix=f"cu-{suffix}",
        )
        _add_item(
            db,
            scope,
            content="Hạn nộp báo cáo Gate 3 là 25/08, nộp qua form đã gửi",
            offset=-1,
            suffix=f"moi-{suffix}",
        )
        db.commit()
        scope_id = scope.id

    # "han nop" không dấu phải khớp được "Hạn nộp".
    khop = list_announcements(engine, scope_ids=[scope_id], query="han nop")
    assert len(khop) == 1
    assert "Gate 3" in khop[0].content

    gan_day = list_announcements(engine, scope_ids=[scope_id], since=datetime.now(UTC) - timedelta(hours=1))
    assert [item.content for item in gan_day] == [khop[0].content]
