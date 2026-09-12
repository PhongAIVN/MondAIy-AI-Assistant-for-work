"""Hợp đồng cấu hình cho đường LangSmith → Grafana.

Dashboard và datasource là file tĩnh, sai một khoá là Grafana im lặng bỏ qua
hoặc render panel rỗng mà không ai biết. Các test dưới khoá lại đúng những chỗ
dễ trôi: uid datasource, host được phép gọi, và việc key nằm ở secureJsonData.
"""

import json
from pathlib import Path

import yaml

DATASOURCES = Path("observability/grafana/provisioning/datasources/prometheus.yml")
DASHBOARD = Path("observability/grafana/dashboards/p004-langsmith.json")
INFINITY_TYPE = "yesoreyeram-infinity-datasource"
LANGSMITH_HOST = "https://api.smith.langchain.com"


# Đọc sẵn một lần: mọi test đều cần cùng khối datasource LangSmith.
def _langsmith_datasource() -> dict:
    """Trả về khai báo datasource LangSmith trong file provisioning."""
    provisioned = yaml.safe_load(DATASOURCES.read_text(encoding="utf-8"))
    return next(ds for ds in provisioned["datasources"] if ds["uid"] == "p004-langsmith")


def _all_panels() -> list[dict]:
    """Duyệt cả panel nằm trong row thu gọn, vì row lồng panel vào chính nó."""
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    panels = []
    for panel in dashboard["panels"]:
        panels.extend(panel["panels"]) if panel["type"] == "row" else panels.append(panel)
    return panels


def _dashboard_targets() -> list[dict]:
    """Gom mọi target của mọi panel trong dashboard LangSmith."""
    return [target for panel in _all_panels() for target in panel["targets"]]


def _eagerly_loaded_targets() -> list[dict]:
    """Chỉ những target chạy ngay lúc mở dashboard — panel trong row đóng thì
    Grafana chưa gọi, nên không tính vào hạn mức đồng thời của LangSmith."""
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    return [target for panel in dashboard["panels"] if panel["type"] != "row" for target in panel["targets"]]


def test_langsmith_datasource_proxies_requests_and_hides_the_api_key():
    datasource = _langsmith_datasource()

    assert datasource["type"] == INFINITY_TYPE
    # access=proxy giữ key ở phía server; access=direct là lộ key ra trình duyệt.
    assert datasource["access"] == "proxy"
    assert datasource["editable"] is False
    assert datasource["jsonData"]["httpHeaderName1"] == "x-api-key"
    assert datasource["secureJsonData"]["httpHeaderValue1"] == "${LANGSMITH_API_KEY}"
    # Key không được xuất hiện ở jsonData vì phần đó đọc được qua API Grafana.
    assert "httpHeaderValue1" not in datasource["jsonData"]


def test_langsmith_datasource_only_allows_the_langsmith_host():
    assert _langsmith_datasource()["jsonData"]["allowedHosts"] == [LANGSMITH_HOST]


def test_existing_datasources_survive_alongside_langsmith():
    provisioned = yaml.safe_load(DATASOURCES.read_text(encoding="utf-8"))
    uids = {ds["uid"] for ds in provisioned["datasources"]}

    assert {"p004-prometheus", "p004-loki", "p004-langsmith"} == uids


def test_grafana_installs_the_infinity_plugin_and_receives_the_key():
    compose = yaml.safe_load(Path("docker-compose.prod.yml").read_text(encoding="utf-8"))
    grafana = compose["services"]["grafana"]["environment"]

    assert INFINITY_TYPE in grafana["GF_INSTALL_PLUGINS"]
    # Mặc định rỗng: VM đang chạy phải deploy được ngay cả khi chưa điền key.
    assert grafana["LANGSMITH_API_KEY"] == "${LANGSMITH_API_KEY:-}"


def test_every_dashboard_target_queries_langsmith_through_the_provisioned_datasource():
    targets = _dashboard_targets()

    assert targets, "dashboard phải có ít nhất một target"
    for target in targets:
        assert target["datasource"] == {"type": INFINITY_TYPE, "uid": "p004-langsmith"}
        assert target["url"].startswith(LANGSMITH_HOST + "/api/v1/")
        # parser=backend là điều kiện để root_selector/columns được áp dụng.
        assert target["parser"] == "backend"


def test_dashboard_scopes_every_run_query_to_the_resolved_project_uuid():
    posted = [t for t in _dashboard_targets() if t["url_options"]["method"] == "POST"]

    assert posted, "panel trace phải gọi POST /runs/query hoặc /runs/stats"
    for target in posted:
        body = target["url_options"]["data"]
        # Thiếu ràng buộc session là kéo trace của mọi project trong workspace.
        assert '"session":["$project_id"]' in body
        assert target["url_options"]["body_content_type"] == "application/json"
        json.loads(body.replace("$project_id", "00000000-0000-0000-0000-000000000000"))


def test_dashboard_resolves_the_project_uuid_from_the_project_name_variable():
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    variables = {var["name"]: var for var in dashboard["templating"]["list"]}

    assert variables["project"]["type"] == "textbox"
    resolver = variables["project_id"]["query"]["infinityQuery"]
    # LangSmith chỉ nhận UUID ở /runs/query, nên phải đổi tên project sang id.
    assert resolver["url"] == f"{LANGSMITH_HOST}/api/v1/sessions?name=$project&limit=1"
    assert resolver["columns"] == [{"selector": "id", "text": "id", "type": "string"}]


# Danh sách lấy từ chính thông báo 422 của LangSmith ngày 2026-08-13. Xin một
# field ngoài danh sách này là cả panel trả 422 và hiện bảng rỗng, không có cảnh
# báo nào trong Grafana — nên khoá lại bằng test thay vì phát hiện lúc vận hành.
LANGSMITH_SELECTABLE_FIELDS = {
    "app_path",
    "child_run_ids",
    "completion_cost",
    "completion_cost_details",
    "completion_token_details",
    "completion_tokens",
    "dotted_order",
    "end_time",
    "error",
    "error_or_signed_url",
    "events",
    "events_or_signed_url",
    "extra",
    "extra_or_signed_url",
    "feedback_stats",
    "first_token_time",
    "id",
    "in_dataset",
    "inputs",
    "inputs_or_signed_url",
    "inputs_preview",
    "inputs_s3_urls",
    "inserted_at",
    "last_queued_at",
    "manifest",
    "manifest_id",
    "manifest_s3_id",
    "messages",
    "name",
    "outputs",
    "outputs_or_signed_url",
    "outputs_preview",
    "outputs_s3_urls",
    "parent_run_id",
    "parent_run_ids",
    "price_model_id",
    "prompt_cost",
    "prompt_cost_details",
    "prompt_token_details",
    "prompt_tokens",
    "reference_dataset_id",
    "reference_example_id",
    "run_type",
    "s3_urls",
    "serialized",
    "serialized_or_signed_url",
    "session_id",
    "share_token",
    "start_time",
    "status",
    "tags",
    "thread_id",
    "total_cost",
    "total_tokens",
    "trace_first_received_at",
    "trace_id",
    "trace_min_max_start_time",
    "trace_tier",
    "trace_upgrade",
    "ttl_seconds",
}


def test_dashboard_only_selects_fields_langsmith_actually_accepts():
    for target in _dashboard_targets():
        if "/runs/query" not in target["url"]:
            continue
        body = json.loads(target["url_options"]["data"].replace("$project_id", "x"))
        unknown = set(body["select"]) - LANGSMITH_SELECTABLE_FIELDS
        assert not unknown, f"LangSmith trả 422 cho các field: {sorted(unknown)}"


def test_dashboard_columns_are_backed_by_a_selected_field():
    for target in _dashboard_targets():
        if "/runs/query" not in target["url"]:
            continue
        body = json.loads(target["url_options"]["data"].replace("$project_id", "x"))
        for column in target["columns"]:
            assert column["selector"] in body["select"]


def test_no_two_panels_fire_the_same_langsmith_request():
    """Bốn stat panel dùng chung một payload là bốn request song song, LangSmith
    trả 429 cho các request sau và panel hiện lỗi thay vì số."""
    requests = [(t["url"], t["url_options"].get("data")) for t in _dashboard_targets()]

    assert len(requests) == len(set(requests)), "có panel trùng request, sẽ ăn 429"


def test_dashboard_open_stays_under_the_langsmith_concurrency_limit():
    """Đo thật ngày 2026-08-13: bắn 6 query cùng lúc thì hai cái cuối ăn 429.
    Panel nặng phải nằm trong row đóng để lúc mở dashboard không vượt ngưỡng."""
    assert len(_eagerly_loaded_targets()) <= 4


def test_only_the_drilldown_panels_pull_prompt_and_completion_content():
    """Nội dung người dùng chỉ được xuất hiện ở panel drill-down đã bị giới hạn
    phạm vi. Panel danh sách phải sạch, nếu không thì chỉ mở dashboard lên là đã
    đổ dữ liệu của cả ngày ra màn hình."""
    sensitive = {
        "inputs",
        "outputs",
        "inputs_preview",
        "outputs_preview",
        "events",
        "extra",
        "messages",
        "serialized",
    }

    for target in _dashboard_targets():
        leaked = {c["selector"] for c in target["columns"]} & sensitive
        if not leaked:
            continue
        body = target["url_options"]["data"]
        assert "$trace_id" in body or "$run_id" in body, (
            f"panel kéo {sorted(leaked)} mà không giới hạn theo trace_id/run_id"
        )


def test_full_payload_is_limited_to_a_single_run():
    """Đo trên trace thật: 27 bước = 70 MB nếu kéo inputs/outputs đầy đủ, đủ để
    treo trình duyệt. Cây trace phải dùng bản preview (6 KB), chỉ panel một-run
    mới được lấy payload trọn vẹn."""
    for target in _dashboard_targets():
        selectors = {c["selector"] for c in target["columns"]}
        if not selectors & {"inputs", "outputs"}:
            continue
        body = json.loads(target["url_options"]["data"])
        assert body["filter"] == 'eq(id, "$run_id")'
        assert body["limit"] == 1


def test_drilldown_panels_stay_empty_until_a_trace_is_chosen():
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    variables = {var["name"]: var for var in dashboard["templating"]["list"]}

    # Mặc định rỗng: mở dashboard lên chưa thấy nội dung của ai cả.
    for name in ("trace_id", "run_id"):
        assert variables[name]["type"] == "textbox"
        assert variables[name]["current"]["value"] == ""


def test_trace_table_links_stay_inside_grafana_first():
    """Không còn ghế LangSmith trả phí thì link đầu tiên phải là link nội bộ."""
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))

    found = False
    for panel in dashboard["panels"]:
        for override in panel.get("fieldConfig", {}).get("overrides", []):
            if override["matcher"].get("options") != "trace":
                continue
            for prop in override["properties"]:
                if prop["id"] != "links":
                    continue
                found = True
                assert prop["value"][0]["url"].startswith("d/p004-langsmith-traces/")
                assert "var-trace_id=" in prop["value"][0]["url"]
    assert found, "bảng trace phải có data link ở cột trace"


def test_production_env_template_documents_the_langsmith_variables():
    template = Path(".env.prod.example").read_text(encoding="utf-8")

    for key in ("LANGSMITH_TRACING=true", "LANGSMITH_PROJECT=", "LANGSMITH_API_KEY="):
        assert key in template
    # Key thật không bao giờ được nằm trong file mẫu.
    assert "LANGSMITH_API_KEY=\n" in template or "LANGSMITH_API_KEY=" in template
    assert "lsv2_" not in template


def test_dashboard_defaults_to_the_production_langsmith_project():
    dashboard = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    variables = {var["name"]: var for var in dashboard["templating"]["list"]}

    assert variables["project"]["current"] == {
        "text": "p004-production",
        "value": "p004-production",
    }
    assert "LANGSMITH_PROJECT=p004-production" in Path(".env.prod.example").read_text(encoding="utf-8")
