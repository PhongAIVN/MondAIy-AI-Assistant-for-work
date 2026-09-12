import importlib.util
import json
from pathlib import Path


def _load(name):
    """Nạp script trong scripts/discord/ như một module để test gọi thẳng hàm."""
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parents[3] / "scripts" / "discord" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


export_dce = _load("export_dce")
sync = _load("sync")


def _manifest(root: Path, run_id: str, rows: list[dict]) -> None:
    """Ghi một _manifest.json giả cho một run đã chuẩn hóa."""
    out = root / "normalized" / run_id
    out.mkdir(parents=True)
    (out / "_manifest.json").write_text(json.dumps({"run_id": run_id, "channels": rows}), encoding="utf-8")


def test_con_tro_gop_qua_moi_run_nen_kenh_im_lang_khong_bi_cao_lai(tmp_path, monkeypatch):
    """Kênh không có tin mới ở run cuối vẫn phải giữ con trỏ của run trước.

    Đây là hồi quy: bản cũ chỉ đọc manifest gần nhất, mà run tăng dần ghi
    last_message_id = null cho kênh im lặng, nên kênh đó bị cào lại từ đầu.
    """
    monkeypatch.setattr(export_dce, "RAW_ROOT", tmp_path / "raw")
    _manifest(
        tmp_path,
        "20260801T000000Z",
        [
            {"channel_id": "A", "last_message_id": "a1"},
            {"channel_id": "B", "last_message_id": "b1"},
        ],
    )
    _manifest(
        tmp_path,
        "20260808T000000Z",
        [
            {"channel_id": "A", "last_message_id": "a2"},
            {"channel_id": "B", "last_message_id": None},
        ],
    )

    assert export_dce.resume_cursors() == {"A": "a2", "B": "b1"}


def test_manifest_hong_khong_chan_ca_lan_cao(tmp_path, monkeypatch):
    monkeypatch.setattr(export_dce, "RAW_ROOT", tmp_path / "raw")
    _manifest(tmp_path, "20260801T000000Z", [{"channel_id": "A", "last_message_id": "a1"}])
    hong = tmp_path / "normalized" / "20260802T000000Z"
    hong.mkdir(parents=True)
    (hong / "_manifest.json").write_text("{ vỡ", encoding="utf-8")

    assert export_dce.resume_cursors() == {"A": "a1"}


def test_chua_co_run_nao_thi_khong_co_con_tro(tmp_path, monkeypatch):
    monkeypatch.setattr(export_dce, "RAW_ROOT", tmp_path / "raw")
    assert export_dce.resume_cursors() == {}


def test_sync_mac_dinh_cao_tang_dan_va_dung_thu_tu_bon_buoc():
    export = sync.export_step("R1", Path("channels.json"), full=False, media=False)
    assert "--incremental" in export
    assert export[export.index("--run-id") + 1] == "R1"

    steps = sync.downstream_steps("R1", embed=False)
    ten_buoc = [Path(step[1]).name for step in steps]
    assert ten_buoc == ["dce_to_raw.py", "chunker.py", "load_to_db.py"]
    assert sync.downstream_steps("R1", embed=True)[-1][1].endswith("embed_chunks.py")


def test_sync_full_thi_bo_tang_dan():
    assert "--incremental" not in sync.export_step("R1", Path("c.json"), full=True, media=False)


def test_sync_dung_ngay_khi_mot_buoc_hong():
    """Chạy tiếp sau lỗi sẽ nạp DB từ thư mục chunk chưa sinh xong."""
    da_chay = []

    def runner(cmd):
        da_chay.append(Path(cmd[1]).name)
        return 1 if len(da_chay) == 2 else 0

    ma = sync.run_steps(sync.downstream_steps("R1", embed=False), runner=runner)
    assert ma == 1
    assert da_chay == ["dce_to_raw.py", "chunker.py"]


def test_khong_co_file_raw_nghia_la_khong_co_tin_moi(tmp_path, monkeypatch):
    monkeypatch.setattr(sync, "DATA", tmp_path)
    assert sync.has_raw_files("R1") is False

    raw = tmp_path / "raw" / "R1"
    raw.mkdir(parents=True)
    (raw / "_run.json").write_text("{}", encoding="utf-8")
    # Chỉ có metadata của lần chạy thì vẫn là không có tin mới.
    assert sync.has_raw_files("R1") is False

    (raw / "kenh_123.json").write_text("{}", encoding="utf-8")
    assert sync.has_raw_files("R1") is True
