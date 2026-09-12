import pytest

from src.services.document_read_quota import build_cache_key


def test_document_cache_invalidates_on_extractor_version_bump():
    common = {
        "user_id": "101",
        "file_id": "sheet-123",
        "revision": "sha256:same-content",
        "sheet_name": "*workbook*",
    }

    old = build_cache_key(**common, extractor_version="semantic-v1")
    current = build_cache_key(**common, extractor_version="semantic-v2")

    assert old != current
    assert current == build_cache_key(
        **common, extractor_version="semantic-v2"
    )


def test_document_cache_rejects_missing_extractor_version():
    with pytest.raises(ValueError, match="extractor_version"):
        build_cache_key(
            user_id="101",
            file_id="sheet-123",
            revision="sha256:content",
            extractor_version="",
        )
