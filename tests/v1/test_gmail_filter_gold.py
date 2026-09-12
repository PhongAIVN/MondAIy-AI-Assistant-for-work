import json
from pathlib import Path

from src.services.filter_classify import FilterConfig, filter_and_classify


def test_gmail_filter_gold_cases():
    path = Path(__file__).parents[2] / "eval" / "golden_dataset" / "fetch_norm_filter" / "filter_cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    config = FilterConfig(
        user_email="student@example.edu",
        approved_labels=frozenset({"INBOX"}),
        program_domains=frozenset({"vlearn.edu.vn"}),
    )
    result = filter_and_classify([case["message"] for case in cases], config)
    by_id = {item["id"]: item for item in result["items"]}
    rejected = {item["id"]: item["reason"] for item in result["rejected"]}

    for case in cases:
        expected = case["expected"]
        message_id = case["message"]["id"]
        if expected["status"] == "accepted":
            assert message_id in by_id, case["id"]
            for key in ("importance", "brief_section"):
                if key in expected:
                    assert by_id[message_id][key] == expected[key], case["id"]
        else:
            assert message_id in rejected, case["id"]
            if expected.get("reason") == "label_not_approved":
                assert rejected[message_id] == "label_not_approved"
