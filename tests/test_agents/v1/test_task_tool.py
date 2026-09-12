"""Danh sách việc theo hạn chót (UC-01).

Hai thứ được chốt ở đây: công cụ không đọc được việc của người khác, và việc
chưa có hạn chót không bị bộ lọc thời gian nuốt mất im lặng.
"""

import json
import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.agents.tools.task_tool import (
    draft_task,
    list_tasks,
    reset_task_scope,
    set_task_scope,
    suggest_tasks,
)
from src.db import engine
from src.models.connection import Connection
from src.models.task import Task
from src.models.task_evidence import TaskEvidence

_TZ = timezone(timedelta(hours=7))


@pytest.fixture(autouse=True)
def _clean_scope():
    reset_task_scope()
    yield
    reset_task_scope()


@pytest.fixture
def owner():
    """Một user riêng mỗi test, xoá sạch sau khi chạy."""
    user_id = f"test-{uuid.uuid4()}"
    yield user_id
    with Session(engine) as db:
        # Phải xoá evidence TRƯỚC task: sqlite tái dùng id sau khi xoá, nên
        # evidence mồ côi sẽ bám vào task của test sau và làm nó thấy nguồn
        # không phải của mình.
        task_ids = db.execute(select(Task.id).where(Task.user_id == user_id)).scalars().all()
        if task_ids:
            db.execute(delete(TaskEvidence).where(TaskEvidence.task_id.in_(task_ids)))
        db.execute(delete(Task).where(Task.user_id == user_id))
        db.execute(delete(Connection).where(Connection.user_id == user_id))
        db.commit()


def _add_tasks(user_id: str, *rows: Task) -> None:
    with Session(engine) as db:
        for row in rows:
            row.user_id = user_id
            db.add(row)
        db.commit()


def test_tu_choi_khi_chua_biet_la_viec_cua_ai():
    ket_qua = list_tasks.invoke({})
    assert "Chưa xác định được đây là việc của ai" in ket_qua


def test_draft_task_tu_choi_khi_chua_biet_user():
    result = draft_task.invoke({"title": "Nộp báo cáo"})

    assert "Chưa xác định được đây là việc của ai" in result


def test_suggest_tasks_chuan_hoa_nhung_khong_ghi_db(owner):
    set_task_scope(owner)

    result = json.loads(
        suggest_tasks.invoke(
            {
                "suggestions": [
                    {
                        "title": " Nộp báo cáo ",
                        "detail": "Gửi PDF",
                        "due_at": "2026-08-14T09:00:00+07:00",
                        "source": "Gmail",
                    },
                    {"title": "nộp báo cáo", "source": "Jira"},
                    {"title": "", "source": "Discord"},
                ]
            }
        )
    )

    assert result["status"] == "suggested"
    assert result["suggestions"] == [
        {
            "title": "Nộp báo cáo",
            "detail": "Gửi PDF",
            "due_at": "2026-08-14T09:00:00+07:00",
            "source": "Gmail",
        }
    ]
    with Session(engine) as db:
        assert db.scalar(select(Task).where(Task.user_id == owner)) is None


def test_suggest_tasks_chi_tra_assignee_khi_nguon_noi_ro(owner):
    set_task_scope(owner)

    result = json.loads(suggest_tasks.invoke({"suggestions": [{"title": "Gửi báo cáo", "assignee": "An"}]}))

    assert result["suggestions"][0]["assignee"] == "An"


def test_draft_task_tao_proposed_dung_user_va_han_gio(owner):
    set_task_scope(owner)

    result = json.loads(
        draft_task.invoke(
            {
                "title": "Nộp báo cáo",
                "detail": "Gửi bản PDF cho mentor",
                "due_at": "2026-08-14T09:00:00+07:00",
            }
        )
    )

    assert result["status"] == "draft_created"
    assert result["task_status"] == "proposed"
    assert result["calendar_write_ready"] is False
    assert any("/tasks" in step for step in result["next_steps"])
    with Session(engine) as db:
        row = db.get(Task, result["task_id"])
        assert row is not None
        assert row.user_id == owner
        assert row.title == "Nộp báo cáo"
        assert row.detail == "Gửi bản PDF cho mentor"
        assert row.status == "proposed"
        assert row.source_count == 0
        assert row.due_at is not None


def test_draft_task_khong_ghi_khi_due_at_khong_hop_le(owner):
    set_task_scope(owner)

    result = draft_task.invoke({"title": "Nộp báo cáo", "due_at": "khi nào rảnh"})

    assert "Chưa tạo bản nháp" in result
    with Session(engine) as db:
        assert db.scalar(select(Task).where(Task.user_id == owner)) is None


def test_draft_task_bao_calendar_ready_khi_co_write_scope(owner):
    with Session(engine) as db:
        db.add(
            Connection(
                user_id=owner,
                provider="google",
                status="connected_ready",
                scopes="openid https://www.googleapis.com/auth/calendar.events",
            )
        )
        db.commit()
    set_task_scope(owner)

    result = json.loads(draft_task.invoke({"title": "Workshop", "due_at": "2026-08-14T09:00:00+07:00"}))

    assert result["calendar_write_ready"] is True
    assert any("Đồng bộ lịch" in step for step in result["next_steps"])


def test_khong_doc_duoc_viec_cua_nguoi_khac(owner):
    """Ranh giới quyền: đặt phạm vi user A thì không thấy việc của user B."""
    nguoi_khac = f"test-{uuid.uuid4()}"
    _add_tasks(nguoi_khac, Task(cluster_key="k1", title="Việc của người khác", detail=""))

    set_task_scope(owner)
    ket_qua = list_tasks.invoke({})

    assert "Việc của người khác" not in ket_qua

    with Session(engine) as db:
        db.execute(delete(Task).where(Task.user_id == nguoi_khac))
        db.commit()


def test_liet_ke_sap_theo_han(owner):
    _add_tasks(
        owner,
        Task(
            cluster_key="k-muon",
            title="Nộp báo cáo cuối",
            detail="",
            due_at=datetime(2026, 8, 20, 17, 0, tzinfo=_TZ),
        ),
        Task(
            cluster_key="k-som",
            title="Gửi bản nháp",
            detail="",
            due_at=datetime(2026, 8, 9, 9, 0, tzinfo=_TZ),
        ),
    )

    set_task_scope(owner)
    ket_qua = list_tasks.invoke({})

    assert ket_qua.index("Gửi bản nháp") < ket_qua.index("Nộp báo cáo cuối")
    assert "09/08/2026 09:00" in ket_qua


def test_viec_chua_co_han_khong_bi_nuot_im_lang(owner):
    """Bộ lọc thời gian loại việc chưa có hạn, nhưng phải đếm và nói ra."""
    _add_tasks(
        owner,
        Task(
            cluster_key="k-co-han",
            title="Việc có hạn",
            detail="",
            due_at=datetime(2026, 8, 9, 9, 0, tzinfo=_TZ),
        ),
        Task(cluster_key="k-chua-han", title="Việc chưa có hạn", detail=""),
    )

    set_task_scope(owner)
    ket_qua = list_tasks.invoke({"due_after": "03/08/2026", "due_before": "10/08/2026"})

    assert "Việc có hạn" in ket_qua
    assert "Việc chưa có hạn" not in ket_qua
    assert "1 việc chưa có hạn chót" in ket_qua


def test_khong_loc_thoi_gian_thi_hien_ca_viec_chua_co_han(owner):
    _add_tasks(owner, Task(cluster_key="k1", title="Việc chưa có hạn", detail=""))

    set_task_scope(owner)
    ket_qua = list_tasks.invoke({})

    assert "Việc chưa có hạn" in ket_qua


def test_hoi_tuan_qua_doc_duoc_viec_da_lam_theo_completed_at(owner):
    now = datetime.now(UTC)
    _add_tasks(
        owner,
        Task(
            cluster_key="k-done",
            title="Đã hoàn thành tuần này",
            detail="",
            status="completed",
            completed_at=now - timedelta(days=2),
        ),
        Task(
            cluster_key="k-open",
            title="Việc chưa làm",
            detail="",
            status="confirmed",
        ),
    )

    set_task_scope(owner)
    ket_qua = list_tasks.invoke(
        {
            "status": "completed",
            "due_after": (now - timedelta(days=7)).isoformat(),
            "due_before": now.isoformat(),
        }
    )

    assert "Đã hoàn thành tuần này" in ket_qua
    assert "Việc chưa làm" not in ket_qua
    assert "chưa có hạn chót" in ket_qua


def test_han_mo_ho_thi_noi_ro_la_mo_ho(owner):
    """BR-05: nguồn ghi không rõ thì phải hiện ra, không im lặng coi như chắc."""
    _add_tasks(
        owner,
        Task(
            cluster_key="k1",
            title="Họp review",
            detail="",
            due_at=datetime(2026, 8, 9, 9, 0, tzinfo=_TZ),
            ambiguous=True,
        ),
    )

    set_task_scope(owner)
    assert "chưa rõ ràng" in list_tasks.invoke({})


def test_jira_task_cua_nguoi_khac_khong_thanh_viec_ca_nhan(owner):
    """Jira issue c?ng user d? li?u nh?ng assignee kh?c kh?ng ???c nh?c/approve."""
    with Session(engine) as db:
        db.add(Connection(
            user_id=owner,
            provider="jira",
            provider_user_id="account-me",
            status="connected_ready",
        ))
        db.commit()

    _add_tasks(
        owner,
        Task(
            cluster_key="jira-own",
            title="Vi?c Jira c?a t?i",
            detail="",
            assignee="account-me",
            assignee_ambiguous=False,
        ),
        Task(
            cluster_key="jira-other",
            title="Vi?c Jira c?a ng??i kh?c",
            detail="",
            assignee="account-other",
            assignee_ambiguous=False,
        ),
    )
    with Session(engine) as db:
        tasks = db.scalars(select(Task).where(Task.user_id == owner)).all()
        db.add_all([
            TaskEvidence(task_id=tasks[0].id, provider="jira", evidence_quote="mine", deep_link="jira://mine"),
            TaskEvidence(task_id=tasks[1].id, provider="jira", evidence_quote="other", deep_link="jira://other"),
        ])
        db.commit()

    set_task_scope(owner)
    result = list_tasks.invoke({})

    assert "Vi?c Jira c?a t?i" in result
    assert "Vi?c Jira c?a ng??i kh?c" not in result


def test_liet_ke_task_noi_ro_provider_va_link_bang_chung(owner):
    """Task tổng hợp phải cho agent biết đã đọc Gmail/Jira nào, không chỉ đếm."""
    _add_tasks(owner, Task(cluster_key="k-source", title="Hoàn thiện báo cáo", detail=""))
    with Session(engine) as db:
        task = db.execute(select(Task).where(Task.user_id == owner, Task.cluster_key == "k-source")).scalar_one()
        db.add_all(
            [
                TaskEvidence(
                    task_id=task.id,
                    provider="google",
                    evidence_quote="Gửi báo cáo trước thứ Sáu",
                    deep_link="https://mail.google.com/mail/u/0/#all/m1",
                ),
                TaskEvidence(
                    task_id=task.id,
                    provider="jira",
                    evidence_quote="Issue đang mở",
                    deep_link="https://example.atlassian.net/browse/PROJ-1",
                ),
            ]
        )
        db.commit()

    set_task_scope(owner)
    result = list_tasks.invoke({})

    # Việc được HAI nguồn cùng xác nhận nay xếp riêng lên đầu thay vì nằm lẫn
    # trong danh sách phẳng — nó đáng tin nhất và cũng là thứ người dùng khó tự
    # đối chiếu nhất.
    assert "Nhiều nguồn cùng xác nhận" in result
    assert "xác nhận bởi Gmail, Jira" in result
    assert "https://mail.google.com/mail/u/0/#all/m1" in result
    assert "https://example.atlassian.net/browse/PROJ-1" in result


def test_liet_ke_task_nhom_theo_tung_nguon(owner):
    """Danh sách phẳng có ghi "nguồn Gmail" cuối mỗi dòng, nhưng mô hình đọc
    xong vẫn kể một mạch nên người dùng không thấy việc nào từ đâu."""
    _add_tasks(
        owner,
        Task(cluster_key="k-mail", title="Sửa báo cáo", detail=""),
        Task(cluster_key="k-jira", title="Cập nhật TAPB-131", detail=""),
    )
    with Session(engine) as db:
        mail_task = db.execute(
            select(Task).where(Task.user_id == owner, Task.cluster_key == "k-mail")
        ).scalar_one()
        jira_task = db.execute(
            select(Task).where(Task.user_id == owner, Task.cluster_key == "k-jira")
        ).scalar_one()
        db.add_all(
            [
                TaskEvidence(
                    task_id=mail_task.id,
                    provider="google",
                    evidence_quote="Sửa báo cáo",
                    deep_link="https://mail.google.com/mail/u/0/#all/m9",
                ),
                TaskEvidence(
                    task_id=jira_task.id,
                    provider="jira",
                    evidence_quote="Issue đang mở",
                    deep_link="https://example.atlassian.net/browse/PROJ-9",
                ),
            ]
        )
        db.commit()

    set_task_scope(owner)
    result = list_tasks.invoke({})

    assert "Gmail (1 việc):" in result
    assert "Jira (1 việc):" in result
    # Mỗi việc phải nằm dưới đúng cụm của nó.
    assert result.index("Gmail (1 việc):") < result.index("Sửa báo cáo")
    assert result.index("Jira (1 việc):") < result.index("Cập nhật TAPB-131")


def test_liet_ke_task_khong_con_bang_chung_thi_noi_thang(owner):
    """Task do người dùng tự tạo, hoặc nguồn đã bị gỡ kết nối — gán bừa vào một
    nền tảng là bịa."""
    _add_tasks(owner, Task(cluster_key="k-orphan", title="Việc tự thêm", detail=""))

    set_task_scope(owner)
    result = list_tasks.invoke({})

    assert "Chưa rõ nguồn" in result


def test_loc_theo_trang_thai(owner):
    _add_tasks(
        owner,
        Task(cluster_key="k1", title="Việc chờ duyệt", detail="", status="proposed"),
        Task(cluster_key="k2", title="Việc đã bỏ", detail="", status="dismissed"),
    )

    set_task_scope(owner)
    ket_qua = list_tasks.invoke({"status": "proposed"})

    assert "Việc chờ duyệt" in ket_qua
    assert "Việc đã bỏ" not in ket_qua

    assert "Việc đã bỏ" in list_tasks.invoke({"status": "all"})


def test_trang_thai_khong_co_that_thi_tu_choi(owner):
    set_task_scope(owner)
    ket_qua = list_tasks.invoke({"status": "dang_lam"})

    assert "không có thật" in ket_qua


def test_moc_hong_thi_tu_choi_chu_khong_bo_bo_loc(owner):
    set_task_scope(owner)
    ket_qua = list_tasks.invoke({"due_before": "cuối tuần này"})

    assert "Không hiểu được mốc thời gian" in ket_qua


def test_khoang_nguoc_thi_tu_choi(owner):
    set_task_scope(owner)
    ket_qua = list_tasks.invoke({"due_after": "10/08/2026", "due_before": "03/08/2026"})

    assert "ngược" in ket_qua


def test_chua_co_viec_nao(owner):
    set_task_scope(owner)
    assert "Chưa có việc nào" in list_tasks.invoke({})


def test_user_id_khong_nam_trong_chu_ky_cong_cu():
    # Bảng tasks phân theo user_id. Để model tự truyền user_id nghĩa là nó đọc
    # được việc của người khác chỉ bằng cách đoán một chuỗi.
    assert set(list_tasks.args) == {"status", "due_before", "due_after"}
    assert set(draft_task.args) == {"title", "detail", "due_at", "all_day"}


def test_liet_ke_task_gan_nhan_do_gap_dau_moi_dong(owner):
    """Hạn chót vẫn in trong ngoặc, nhưng người đọc (và mô hình tóm tắt lại)
    phải quét cả dòng mới biết việc nào gấp. Nhãn ở đầu dòng cho phép nhìn cột
    trái là thấy ngay thứ tự cần làm."""
    now = datetime.now(UTC)
    _add_tasks(
        owner,
        Task(cluster_key="k-late", title="Việc quá hạn", detail="", due_at=now - timedelta(days=2)),
        Task(cluster_key="k-today", title="Việc hôm nay", detail="", due_at=now),
        Task(cluster_key="k-none", title="Việc chưa có hạn", detail=""),
    )

    set_task_scope(owner)
    result = list_tasks.invoke({})

    assert "[QUÁ HẠN] Việc quá hạn" in result
    assert "[hôm nay] Việc hôm nay" in result
    assert "[chưa có hạn] Việc chưa có hạn" in result


def test_liet_ke_task_viec_chua_co_han_xuong_cuoi(owner):
    """Postgres xếp NULL sau cùng với ASC, SQLite lại đưa lên đầu — không nói rõ
    thì hai môi trường cho ra hai thứ tự, và việc chưa có hạn che mất việc gấp."""
    now = datetime.now(UTC)
    _add_tasks(
        owner,
        Task(cluster_key="k-no-due", title="Chua co han", detail=""),
        Task(cluster_key="k-urgent", title="Gap lam", detail="", due_at=now - timedelta(days=1)),
    )

    set_task_scope(owner)
    result = list_tasks.invoke({})

    assert result.index("Gap lam") < result.index("Chua co han")
