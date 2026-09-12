"""Composition root phải thực sự nạp API/model của kho thông tin chương trình."""

from src.main import app
from src.models.program_information import (
    ProgramInformationItem,
    ProgramInformationRequest,
    ProgramInformationVersion,
)


def _registered_paths() -> set[str]:
    """FastAPI 0.116+ giữ router include ở wrapper thay vì flatten app.routes."""
    paths: set[str] = set()
    for route in app.routes:
        if path := getattr(route, "path", None):
            paths.add(path)
            continue
        original_router = getattr(route, "original_router", None)
        include_context = getattr(route, "include_context", None)
        if original_router is None or include_context is None:
            continue
        prefix = include_context.prefix
        paths.update(f"{prefix}{child.path}" for child in original_router.routes)
    return paths


def test_program_information_routes_are_registered() -> None:
    paths = _registered_paths()

    assert "/api/v1/program-information" in paths
    assert "/api/v1/program-information/human-requests" in paths
    assert "/api/v1/admin/program-information" in paths
    assert "/api/v1/admin/program-information/human-requests" in paths


def test_program_information_tables_are_registered() -> None:
    assert ProgramInformationItem.__table__.metadata is ProgramInformationVersion.__table__.metadata
    assert ProgramInformationRequest.__table__.metadata is ProgramInformationItem.__table__.metadata
    table_names = ProgramInformationItem.__table__.metadata.tables

    assert "program_information_items" in table_names
    assert "program_information_versions" in table_names
    assert "program_information_requests" in table_names
