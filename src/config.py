from datetime import time
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "AI20K Agent"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"
    # Múi giờ dùng để nói chuyện với người dùng: công cụ thời gian của agent lấy
    # mốc "bây giờ" theo đây. Dữ liệu trong DB vẫn lưu kèm múi giờ như cũ, đây
    # chỉ là múi giờ hiển thị. Tên theo IANA, không dùng "GMT+7".
    app_timezone: str

    # ---- LangSmith outbound privacy ----
    # Redaction chỉ chạy trong Client gửi trace; prompt/DB vẫn giữ nguyên để
    # agent đọc được nguồn thật. Bật tracing mà thiếu salt thì startup phải lỗi.
    langsmith_pii_redaction_enabled: bool = True
    langsmith_pii_salt: SecretStr = SecretStr("")
    # Hai kill switch độc lập: trace vẫn giữ cấu trúc/metadata nhưng bỏ hẳn
    # payload input hoặc output khi cần ứng phó sự cố privacy.
    langsmith_hide_inputs: bool = False
    langsmith_hide_outputs: bool = False

    # Nhịp ngày mặc định cho planner xác định. Các mốc là giờ địa phương theo
    # app_timezone; schedule.py kiểm tra thứ tự nghiêm ngặt trước khi xếp việc.
    planner_workday_start: time = time(8, 0)
    planner_lunch_start: time = time(12, 0)
    planner_afternoon_start: time = time(13, 30)
    planner_dinner_start: time = time(18, 0)
    planner_evening_start: time = time(19, 30)
    planner_day_end: time = time(22, 0)

    # Lịch chương trình (ADR-008)
    # Khóa đang phục vụ. Tool lịch chương trình chỉ đọc đúng cohort này, nên đổi
    # khóa là đổi ở đây chứ không sửa truy vấn.
    program_cohort_slug: str
    # URL feed ICS do ban tổ chức phát. Chuỗi này chứa token cá nhân — để trống
    # trong repo và chỉ điền ở .env của máy chạy job nhập lịch.
    phoenix_ics_feed_url: str = ""
    # Vòng nhập lịch nền. Mặc định TẮT: bật là hệ thống tự gọi ra ngoài theo
    # nhịp, và feed chỉ có ở máy đã điền token. Chưa bật thì vẫn nhập tay bằng
    # scripts/import_program_calendar.py.
    program_calendar_auto_import_enabled: bool = False
    # Feed khai `REFRESH-INTERVAL:PT1H` nên quét dày hơn một giờ là gọi thừa.
    program_calendar_import_interval_minutes: int = Field(default=60, ge=5, le=1440)

    # LLM
    # TODO(OD-03): PRD ghi mọi lời gọi model đi qua OpenRouter nhưng quyết định
    # chưa chốt. Mặc định để OpenRouter vì đó là đường duy nhất đang có key thật,
    # còn openai_api_key trong .env mới là chỗ giữ tương thích ngược. Chốt OD-03
    # xong thì bỏ nhánh openai đi.
    openai_api_key: str = ""
    # Khử trùng task do agent tạo dùng OpenAI trực tiếp, tách khỏi đường
    # embedding OpenRouter/RAG đang chờ credit. Exact và fuzzy vẫn chạy khi
    # nhánh semantic tắt hoặc lỗi; fail-open để không làm mất việc.
    task_dedup_semantic_enabled: bool = True
    task_dedup_embedding_model: str = "text-embedding-3-small"
    task_dedup_fuzzy_threshold: float = Field(default=0.95, ge=0.72, le=1.0)
    task_dedup_semantic_threshold: float = Field(default=0.92, ge=0.0, le=1.0)
    task_dedup_embedding_timeout_seconds: float = Field(default=2.0, ge=0.5, le=10.0)
    task_dedup_due_proximity_hours: float = Field(default=6.0, gt=0.0, lt=24.0)
    task_dedup_candidate_limit: int = Field(default=50, ge=1, le=200)
    # Google Sheet semantic extraction sends only the bounded selected tab to a
    # dedicated small OpenAI model. It intentionally bypasses provider failover.
    google_sheet_extraction_model: str = "gpt-4o-mini"
    # ---- Memory intent extraction (LLM nhỏ thay regex — quyết định của Thái 22/08) ----
    # Model nhỏ chuyên trích fact từ lượt nói của user; regex chỉ còn là fallback
    # khi model lỗi/tắt cờ. Tắt cờ = hành vi regex thuần, không đổi schema.
    # Break task: model nhỏ lập kế hoạch hôm nay + prompt copy-paste từ danh
    # sách việc còn mở. Đường LLM riêng, không failover (xem task_breakdown.py).
    task_breakdown_model: str = "gpt-4o-mini"
    # Lịch chương trình tier A: feed ICS chỉ khai ở env (URL chứa access token,
    # không được commit). Rỗng = tính năng tắt hẳn. Xem tier_a_feed.py.
    tier_a_calendar_feed_url: str = ""
    memory_intent_model: str = "gpt-4o-mini"
    memory_intent_enabled: bool = True
    memory_intent_timeout_seconds: float = 6.0
    # Model vision/OCR dùng riêng cho ảnh. Giữ tách khỏi model chat để có thể
    # đổi model hoặc tắt tính năng mà không ảnh hưởng luồng hỏi đáp hiện tại.
    openai_vision_model: str = "gpt-5.6-luna"
    openai_vision_timeout_seconds: float = Field(default=60.0, ge=1.0, le=300.0)
    vision_max_image_bytes: int = Field(default=8_000_000, ge=100_000, le=20_000_000)
    model_name: str = "inclusionai/ling-3.0-tiny:free"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    # Nhiệt độ riêng cho lượt chọn công cụ. Lượt đó không viết văn, nó chỉ quyết
    # định gọi tool nào với tham số nào — sinh ngẫu nhiên ở đây nghĩa là cùng một
    # câu hỏi lúc tra nguồn lúc không, đúng triệu chứng đã phải vá bằng regex
    # trong nodes/core_nodes.py. Lượt viết câu trả lời vẫn dùng llm_temperature.
    llm_tool_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    # Trần thời gian cho một lời gọi model. Không đặt thì provider treo sẽ giữ
    # luôn cả lượt chat và chuỗi failover không bao giờ được chạy tới.
    llm_request_timeout_seconds: float = Field(default=30.0, ge=1.0, le=300.0)
    llm_provider: Literal["openrouter", "groq", "openai"] = "openrouter"
    # Chuỗi provider ưu tiên, phân cách bằng dấu phẩy. Provider tiếp theo chỉ
    # được thử khi provider trước trả lỗi transient/quota/auth.
    llm_providers: str = "openrouter,groq"
    # Gói free của OpenRouter dùng chung pool với người khác nên hay trả 429
    # giữa chừng. Thử lại vài lần đỡ gãy demo, nhưng đây chỉ là băng dán:
    # muốn hết hẳn thì phải cắm key provider riêng trên OpenRouter.
    llm_max_retries: int = Field(default=5, ge=0, le=10)
    # Capability-aware routing is gated so production can be rolled back to
    # the existing work path while candidate smoke tests are being completed.
    llm_routing_enabled: bool = False
    # Bật Responses API cho provider OpenAI. Bắt buộc với dòng gpt-5.6: các model
    # đó từ chối function tool trên /v1/chat/completions. Không ảnh hưởng
    # openrouter/groq vì hai provider đó không có endpoint này.
    llm_use_responses_api: bool = False
    small_talk_candidates: str = "openrouter:inclusionai/ling-3.0-tiny:free,groq:llama-3.1-8b-instant"
    work_tool_candidates: str = "openrouter:inclusionai/ling-3.0-tiny:free,groq:llama-3.1-8b-instant"
    work_response_candidates: str = "openrouter:inclusionai/ling-3.0-tiny:free,groq:llama-3.1-8b-instant"
    paid_fallback_enabled: bool = False
    llm_candidate_max_attempts: int = Field(default=1, ge=1, le=5)
    # USD trên một triệu token, đối chiếu bảng giá chính thức ngày 2026-08-27.
    # Cấu hình dạng map để model chưa khai giá không bị gán nhầm giá của model
    # khác; observability vẫn đếm token và phát metric pricing_unknown.
    llm_model_pricing_usd_per_million: dict[str, dict[str, float]] = Field(
        default_factory=lambda: {
            "inclusionai/ling-3.0-tiny:free": {"input": 0.0, "output": 0.0},
            "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            # developers.openai.com/api/docs/models — reasoning token của dòng
            # 5.6 nằm TRONG output_tokens nên tính theo giá output là đúng.
            "gpt-5.6-luna": {"input": 0.20, "output": 1.20},
            "gpt-5.6-terra": {"input": 2.00, "output": 12.00},
            "gpt-5.6-sol": {"input": 5.00, "output": 30.00},
        }
    )
    # true: bước extract/reduce của pipeline task-extraction (TAPB-121) dùng
    # mock thay vì gọi LLM thật — chỉ để test graph chạy hết 9 node, không phải
    # kết quả AI thật. Field này bị rớt khỏi config.py lúc merge nhánh
    # feat/backend-evidence-discord-union (họ viết lại file song song, không cố
    # ý xoá) — thêm lại vì extract_batch.py/reduce.py/runs.py vẫn gọi.
    mock_llm: bool = False

    # ---- XLM-R mail filter (optional, fail-closed) ----
    hf_mail_filter_enabled: bool = False
    hf_mail_filter_token: str = ""
    hf_mail_filter_model: str = "DungND1107/modaiy_vin"
    hf_mail_filter_endpoint: str = ""
    hf_mail_filter_timeout_seconds: float = Field(default=8.0, ge=1.0, le=30.0)
    hf_mail_filter_max_chars: int = Field(default=6000, ge=500, le=20000)
    hf_mail_filter_min_confidence: float = Field(default=0.80, ge=0.5, le=1.0)
    hf_mail_filter_keep_labels: str = "LABEL_1,keep,relevant,actionable,important,positive"
    hf_mail_filter_drop_labels: str = "LABEL_0,drop,irrelevant,spam,noise,negative"

    # ---- Ngân sách ngữ cảnh của vòng agent ----
    # Mỗi vòng think đọc lại toàn bộ observation đã có, nên không chặn thì prompt
    # phình theo số vòng và phần đầu bị model bỏ quên. Hai trần dưới đây cắt từ
    # cũ về mới: giữ observation mới nhất, cắt bớt phần vượt ngân sách ký tự.
    # Đếm bằng ký tự chứ không phải token vì repo chưa có tokenizer chung; với
    # tiếng Việt thì một token rơi vào khoảng 2-3 ký tự.
    agent_max_observations_in_context: int = Field(default=8, ge=1, le=50)
    agent_context_max_chars: int = Field(default=12_000, ge=500, le=200_000)

    # Buộc truy hồi trên toàn bộ kho, bỏ qua phạm vi theo user. /chat đã xác thực
    # và giải scope theo user (xem api/routes.py), nên cờ này chỉ dùng để demo nội
    # bộ: bật ở môi trường có người ngoài truy cập là để lộ dữ liệu của mọi người.
    # Mặc định tắt, phải tự bật.
    demo_unscoped_search: bool = False

    # OpenRouter — PRD ghi mọi lời gọi model đi qua đây. Nhúng gửi nội dung chunk
    # ra dịch vụ ngoài, nên phạm vi dữ liệu được nhúng phải khớp phạm vi đã đồng ý.
    openrouter_api_key: str = ""
    # Nhiều key phân cách bằng dấu phẩy. Dùng secret manager ở production; không
    # commit giá trị thật vào .env, log hoặc database.
    openrouter_api_keys: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    groq_api_key: str = ""
    groq_api_keys: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model_name: str = "llama-3.1-8b-instant"
    # Đổi model nhúng thì phải nhúng lại toàn bộ: pgvector khoá số chiều theo cột.
    # Script nhúng tự dò số chiều rồi chỉnh cột, không hardcode ở đây.
    embedding_model: str = "nvidia/nemotron-3-embed-1b:free"
    embedding_batch_size: int = Field(default=32, ge=1, le=256)
    # Trần thời gian cho một lời gọi nhúng. Trước đây để 60s cứng: một lượt chat
    # có thể đứng cả phút mà không ai biết vì sao. Nhúng chậm hơn ngần này thì
    # thà trả lời "không tra được lúc này" còn hơn bắt người dùng chờ.
    embedding_timeout_seconds: float = Field(default=8.0, ge=1.0, le=120.0)
    intent_similarity_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    intent_ambiguity_margin: float = Field(default=0.05, ge=0.0, le=1.0)

    # ---- Phân loại ý định bằng LLM (ADR-020 QĐ-1) ----
    # Đường embedding cũ gọi OpenRouter và trả 402 ở mọi lượt, nên tầng intent
    # chưa từng chạy trên production. Lượt chat đã dùng OpenAI sẵn, nên phân loại
    # bằng chính nhà cung cấp đó gỡ nút thắt mà không cần nạp credit ở đâu cả.
    # Bật mặc định: đường cũ đã chết, nên đây KHÔNG phải đánh đổi với thứ đang
    # chạy được — tắt cờ là quay về hạ cấp GENERAL_WORK, đúng hiện trạng.
    llm_intent_enabled: bool = True
    llm_intent_model: str = "gpt-4o-mini"
    llm_intent_timeout_seconds: float = Field(default=6.0, ge=1.0, le=60.0)
    # Câu dài gần như luôn là nội dung dán vào chứ không phải câu hỏi. Phân loại
    # nó vừa tốn vừa mở thêm bề mặt cho prompt injection.
    llm_intent_max_query_chars: int = Field(default=500, ge=50, le=10_000)

    # ---- Truy hồi memory dài hạn (ADR-006) ----
    # Bật nhánh vector khi truy hồi memory. Tắt thì hệ thống chạy nhánh từ khoá
    # như trước, không đổi schema và không mất dữ liệu — đây là đường rollback
    # của ADR-006. Nhánh vector còn tự tắt khi DB không phải PostgreSQL.
    memory_semantic_recall_enabled: bool = True
    # Số memory nhúng lại trong một lần chạy nền. Giữ nhỏ vì job này chạy sau
    # mỗi lượt chat, không phải một lần rồi thôi.
    memory_embedding_batch_limit: int = Field(default=16, ge=1, le=256)

    # ---- Học thích ứng P1 (ADR-017) ----
    # Cờ tổng của toàn bộ năng lực học. Mặc định TẮT theo ADR-017: consent từng
    # user chỉ có hiệu lực khi cờ này bật, nên deploy schema mới không đổi hành
    # vi của ai. Bật production phải qua pilot gate.
    adaptive_learning_enabled: bool = False
    # Worker review chat nền (fork học sau lượt trả lời) tách riêng để có thể
    # rollback độc lập với phần còn lại của learning loop.
    chat_learning_worker_enabled: bool = False

    # ---- Tavily (tìm kiếm web) ----
    # TODO(ADR): one-page-brief ghi "không làm tìm kiếm toàn mạng" trong sáu
    # tuần, và thêm nguồn dữ liệu là material change cần ADR. Mặc định tắt, chỉ
    # bật cho thử nghiệm nội bộ cho tới khi có ADR chốt.
    web_search_enabled: bool = False
    tavily_api_key: str = ""
    tavily_base_url: str = "https://api.tavily.com"
    tavily_max_results: int = Field(default=5, ge=1, le=20)
    tavily_search_depth: Literal["basic", "advanced"] = "basic"

    # ---- FPT Cloud marketplace ----
    # MỘT cổng, MỘT key, nhiều model: whisper cho STT và Vietnamese_Embedding
    # cho nhúng. Trước đây key này chỉ có tên `STT_API_KEY`; giữ tên đó rồi thêm
    # `FPT_EMBEDDING_API_KEY` là tạo hai tên cho cùng một secret — đúng loại lỗi
    # khiến "sửa rồi mà không ăn".
    fpt_api_key: str = ""
    fpt_base_url: str = "https://mkp-api.fptcloud.com"
    fpt_embedding_model: str = "Vietnamese_Embedding"
    # openrouter: model cũ, hiện trả 402 vì hết credit → RAG chết.
    # fpt: Vietnamese_Embedding, 1024 chiều, tối ưu cho tiếng Việt.
    embedding_provider: Literal["openrouter", "fpt"] = "openrouter"

    # ---- STT (FPT Cloud marketplace) ----
    # Chuyển audio buổi họp thành text. Endpoint tương thích kiểu OpenAI nhưng
    # chỉ nhận đúng hai trường form là model và file; các tham số khác bị bỏ qua.
    stt_model: str = "whisper-large-v3-turbo"
    # Ngôn ngữ ghim cho STT. Bỏ trống field này thì whisper-large-v3-turbo tự
    # dịch nội dung tiếng Việt sang tiếng Anh với đầu vào webm/opus (đo được:
    # cùng một audio, không gửi language ra "Hello everyone...", gửi language=vi
    # ra đúng tiếng Việt). Extension gửi webm/opus nên phải ghim "vi". Để rỗng
    # là chấp nhận auto-detect, chỉ dùng khi có chủ đích.
    stt_language: str = "vi"

    # Hạn mức ghi âm cuộc họp mỗi ngày cho tài khoản thường, tính bằng phút.
    # Quản trị viên không bị giới hạn. Đặt 0 nghĩa là khoá hẳn tính năng ghi âm
    # với người dùng thường chứ không phải cho dùng thoải mái.
    recording_quota_daily_minutes: int = 15
    # Vừa là độ dài một lát hạn mức, vừa là bước lưới để quy chuẩn offset của
    # chunk về đúng lát đó. Phải khớp `CHUNK_DURATION_MS` của extension
    # (client/extension/lib/recording.ts); lệch số này thì hạn mức đếm sai so
    # với thời gian họp thật.
    recording_chunk_duration_ms: int = 5_000

    # Database
    database_url: str = "sqlite:///./data/app.db"

    # Object storage — backend dùng endpoint nội bộ, còn URL presigned dùng
    # endpoint mà trình duyệt/client có thể truy cập được.
    minio_endpoint: str = "localhost:9000"
    minio_presign_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "app-objects"
    minio_secure: bool = False
    minio_presign_expiry_seconds: int = Field(default=900, ge=60, le=86400)

    # Vector Store
    chroma_persist_dir: str = "./data/chroma"

    # Public base URL của chính backend này (dùng để build redirect_uri gửi
    # cho Discord/Google/Telegram — phải là HTTPS công khai ở production, đăng
    # ký y hệt trên từng dev console).
    app_public_url: str = "http://localhost:8000"
    # URL giao diện người dùng. Bot Telegram dùng URL này để đưa người dùng
    # tới đúng màn hình kết nối thay vì mở nhầm domain API.
    web_app_public_url: str = ""
    # Deep-link callback duy nhất của app native. Không nhận wildcard để login
    # code không thể bị chuyển tiếp sang ứng dụng khác.
    mobile_app_redirect_uri: str = "mondaiy://auth/callback"
    # Bundle ID/Services ID đã đăng ký ở Apple Developer. Native iOS dùng nó
    # làm audience của identity token; để trống thì endpoint Apple bị tắt.
    apple_client_id: str = "com.mondaiy.product"
    apple_team_id: str = ""
    apple_key_id: str = ""
    apple_private_key: str = ""

    # Ký/verify state token OAuth (connections) VÀ ký JWT access/refresh token
    # (đăng ký/đăng nhập user thật — xem src/services/auth.py). Bắt buộc phải
    # set ở production, khác giá trị mẫu.
    app_secret_key: str = ""
    access_token_expire_minutes: int = Field(default=60 * 24, ge=1)
    refresh_token_expire_days: int = Field(default=30, ge=1)
    # Hạn của link đặt lại mật khẩu — ngắn hơn hẳn refresh token vì token này
    # đi qua email, kênh không đảm bảo an toàn bằng cookie/localStorage.
    password_reset_token_expire_minutes: int = Field(default=30, ge=1, le=1440)
    # Khoá TỪNG USER (không phải theo IP) khi bấm "quên mật khẩu" quá nhiều lần
    # trong 1 cửa sổ thời gian — chặn kẻ tấn công spam email đặt lại mật khẩu
    # tới nạn nhân dù đổi IP liên tục. limiter theo IP ở rate_limit.py không đủ
    # vì chỉ chặn 1 IP, không chặn theo mục tiêu.
    forgot_password_max_attempts: int = Field(default=5, ge=1)
    forgot_password_window_minutes: int = Field(default=60, ge=1)
    forgot_password_lockout_minutes: int = Field(default=30, ge=1)

    # ---- SMTP (email đặt lại mật khẩu) ----
    # Để trống smtp_host thì send_password_reset_email chỉ log link ra console
    # (dev/pilot chạy được ngay không cần secret). Set đủ host+user+password thì
    # gửi email thật.
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from_email: str = "no-reply@mondaiy.local"
    smtp_from_name: str = "AI Program Navigator"
    # ---- Production capacity guards ----
    # Mặc định localhost cho uvicorn chạy bằng .venv (không trong Docker, tên
    # DNS service `redis` không resolve được). Docker Compose ghi đè
    # REDIS_URL=redis://redis:6379/0 trong service backend/worker.
    redis_url: str = "redis://localhost:6379/0"
    # Số nguồn tối đa được chọn trong MỘT lần Sync. Trước đây là 3 và không
    # hiện ở đâu trên UI: người dùng tick nguồn thứ 4 vẫn được, chỉ tới lúc bấm
    # Sync mới ăn 422. FE nay đọc hạn mức này qua GET /runs/limits và chặn ngay
    # tại chỗ tick, nên nâng lên 10 là an toàn — trần cứng của schema vẫn là 20.
    max_sync_sources: int = Field(default=10, ge=1, le=20)
    max_sync_range_days: int = Field(default=31, ge=1, le=365)
    # Trần này đếm run đang chạy của TOÀN hệ thống, không phải theo user. Để 3
    # nghĩa là chỉ cần 3 người sync cùng lúc thì người thứ 4 ăn 429 "Hệ thống
    # đang bận" — với auto-sync chạy nền thì gần như chắc chắn đụng trần. Nó
    # cũng là số consumer loop mà run_worker() spawn, nên nâng lên là nâng cả
    # throughput thật; chi phí LLM vẫn bị max_total_llm_batches_per_run chặn.
    max_concurrent_runs: int = Field(default=10, ge=1, le=100)
    max_runs_per_user: int = Field(default=1, ge=1, le=10)
    max_total_llm_batches_per_run: int = Field(default=20, ge=1, le=200)
    # concurrency=1 nghĩa là extract_batch/reduce chạy TUẦN TỰ dù code đã
    # dùng asyncio.gather — mỗi run có nhiều batch/cluster (vd. Jira quét cả
    # project 31 ngày) cộng dồn độ trễ LLM, sync cảm giác rất lâu. 3 là biên
    # an toàn: vẫn có key-rotation khi 429 (xem llm-routing.md), và
    # max_total_llm_batches_per_run vẫn chặn worst-case phình vô hạn.
    max_llm_batches_per_run: int = Field(default=3, ge=1, le=10)
    run_claim_timeout_minutes: int = Field(default=30, ge=1, le=240)
    worker_poll_seconds: float = Field(default=1.0, ge=0.1, le=30.0)
    # POST /runs chỉ enqueue — quên chạy `make worker` song song `make run`
    # thì Sync treo mãi ở "queued", không báo lỗi gì (đúng sự cố TAPB đã gặp).
    # Mặc định BẬT để `make run` một mình đủ chạy hết pipeline cho dev/pilot.
    # docker-compose.yml đặt lại thành false cho service `backend` vì topology
    # production đã có container `worker` riêng (architecture.md §3) — bật cả
    # hai nơi cùng lúc không sai (claim_next_run dùng FOR UPDATE SKIP LOCKED,
    # an toàn chạy nhiều worker), chỉ là dư một loop không cần thiết.
    embed_worker: bool = True

    # ---- Attachment extraction (Gmail pdf/docx/xlsx/ảnh) ----
    # Công tắc tổng, mặc định TẮT — mở rộng phạm vi dữ liệu đọc từ Gmail (nội
    # dung file, không chỉ metadata), phải bật có chủ đích sau khi review chứ
    # không tự bật ngay khi deploy nhánh này. Cùng tinh thần auto_sync_enabled.
    attachment_extraction_enabled: bool = False
    # Trần kích thước file gốc trước khi tải về — chặn tải file quá nặng làm
    # chậm cả run vì 1 email.
    attachment_max_bytes: int = Field(default=8 * 1024 * 1024, ge=1, le=25 * 1024 * 1024)
    attachment_max_per_message: int = Field(default=3, ge=1, le=10)
    # Cắt text đã trích trước khi đưa vào evidence LLM — không đẩy nguyên file
    # lớn vào context, cũng giới hạn chi phí token.
    attachment_max_extracted_chars: int = Field(default=4000, ge=500, le=20000)
    attachment_extraction_timeout_seconds: int = Field(default=20, ge=1, le=120)
    # Tightening thêm so với mặc định Pillow (~89.5 triệu pixel) — vừa chặn
    # decompression bomb, vừa giữ ảnh gửi lên vision LLM không quá nặng.
    attachment_max_image_pixels: int = Field(default=20_000_000, ge=1_000_000, le=89_000_000)
    # Trích attachment có cấu trúc (theo trang/sheet/section) + grounding qua
    # LangExtract, thay vì nối text phẳng — mặc định TẮT, cùng lý do như
    # attachment_extraction_enabled (dependency mới + code path mới, bật thủ
    # công sau khi verify chạy thật qua OpenRouter).
    attachment_structured_extraction_enabled: bool = False
    # Trần token đầu ra cho 1 lần gọi LangExtract. Bắt buộc gửi tường minh:
    # không có nó, LangExtract bỏ trống max_tokens và OpenRouter tính hạn mức
    # theo TRẦN của model (gpt-4o-mini: 16384) rồi trả 402 "requires more
    # credits" dù việc trích thật chỉ cần vài trăm token. Lỗi đó bị
    # extract_structured_signals nuốt nên chỉ hiện ra dưới dạng
    # structured_extract = None, rất khó lần.
    attachment_structured_extraction_max_output_tokens: int = Field(default=2000, ge=256, le=16384)

    # ---- Danh sách tin cậy cho bộ lọc mail (filter_classify.py) ----
    # Chuỗi ngăn cách bằng dấu phẩy, giống cors_origins. Ba trường này vốn đã
    # có trong FilterConfig nhưng execute_run() truyền vào danh sách RỖNG cứng,
    # nên trên thực tế không sender nào từng được coi là tin cậy: mail hệ thống
    # của trường/công ty (no-reply@...) bị AUTOMATED_RE bắt là negative_state và
    # drop thẳng, không có đường nào miễn trừ.
    # trusted_senders: địa chỉ email đầy đủ. trusted_sender_domains: phần sau @.
    # program_domains: domain của chương trình/khoá đang theo học — mail chưa đọc
    # từ domain này luôn được giữ (must_not_miss).
    trusted_senders: str = ""
    trusted_sender_domains: str = ""
    program_domains: str = ""

    # ---- Đồng bộ kích hoạt từ chat (2026-08-21) ----
    # Người dùng không còn bấm Sync tay (nút đã ẩn): câu chat đầu tiên mỗi ngày
    # tự kéo một lần đồng bộ, và câu hỏi thẳng về công việc ép đồng bộ lại nếu
    # dữ liệu đã quá cũ. Xem src/services/chat_sync.py.
    chat_sync_enabled: bool = True
    # Ngưỡng "cũ" cho câu hỏi về việc. Yêu cầu gốc là "hỏi tôi có task gì thì
    # đồng bộ tự bật", nên con số này phải NGẮN — đặt 90 phút (bản đầu) khiến
    # người dùng vừa sync 43 phút trước hỏi lại vẫn nhận dữ liệu cũ và không có
    # dấu hiệu nào cho biết vì sao. 15 phút vẫn đủ chặn việc hỏi dồn dập biến
    # mỗi câu chat thành một lần chạy pipeline (mỗi lần đều gọi LLM).
    chat_sync_stale_minutes: int = Field(default=15, ge=5, le=1440)
    # Cửa sổ quét, ngắn hơn Sync tay vì phần cũ đã nằm trong DB từ các run trước.
    chat_sync_range_hours: int = Field(default=72, ge=1, le=720)
    # Sàn cửa sổ quét RIÊNG cho Jira. Issue tracker chuyển động chậm hơn hộp
    # thư nhiều: đo trên bảng thật, 72 giờ trả về 0 issue trong khi 30 ngày trả
    # về 139. Dùng chung một cửa sổ với mail thì Jira gần như luôn rỗng, còn
    # nới cửa sổ chung lên 30 ngày lại bắt quét lại cả tháng mail mỗi lần đồng
    # bộ. Sàn này chỉ nâng cho Jira, không đụng các nguồn khác.
    jira_min_lookback_days: int = Field(default=30, ge=1, le=365)

    # ---- Auto-sync nền (ADR-011) ----
    # Công tắc tổng, mặc định TẮT. Auto-sync là thay đổi material về privacy
    # (hệ thống gọi API của người dùng khi họ không ngồi trước máy), nên phải
    # bật có chủ đích ở từng môi trường sau khi ADR-011 được duyệt, chứ không
    # tự sống dậy chỉ vì ai đó deploy nhánh này.
    auto_sync_enabled: bool = False
    # Khoảng cách tối thiểu giữa hai lần tự sync của cùng một user. 180 phút
    # đủ để dữ liệu không cũ quá nửa buổi làm việc mà vẫn ~8 run/user/ngày.
    auto_sync_interval_minutes: int = Field(default=180, ge=15, le=1440)
    # Cửa sổ thời gian mà run tự động sẽ quét. Ngắn hơn hẳn Sync thủ công vì
    # đây là lần quét bồi, phần cũ đã nằm trong DB từ các run trước.
    auto_sync_range_hours: int = Field(default=24, ge=1, le=168)
    # Nhịp quét bảng tìm user tới hạn. Không cần dày: tới hạn trễ vài phút
    # không ai nhận ra, mà quét dày thì đốt connection pool vô ích.
    auto_sync_poll_seconds: float = Field(default=300.0, ge=10.0, le=3600.0)

    # ---- Thùng rác task ----
    # Huỷ task là đưa vào thùng rác; quá thời hạn này thì xoá vĩnh viễn. Thái
    # chốt 7 ngày (27/08). Đây là lần xoá KHÔNG hoàn tác được, nên có cờ tắt
    # riêng: gặp nghi ngờ thì tắt job, thùng rác phình ra vẫn hơn mất dữ liệu.
    task_trash_purge_enabled: bool = True
    task_trash_retention_days: int = Field(default=7, ge=1, le=365)
    # Nhịp quét. Một ngày một lần là đủ: hạn tính theo ngày, nên xoá trễ vài giờ
    # không ai nhận ra, còn quét dày chỉ tốn connection pool.
    task_trash_purge_poll_seconds: float = Field(default=86_400.0, ge=60.0, le=604_800.0)
    # Trần số task xoá trong MỘT vòng. Vòng sau dọn tiếp phần còn lại; giới hạn
    # này giữ cho một lần dọn dồn không khoá bảng tasks quá lâu.
    task_trash_purge_batch_limit: int = Field(default=500, ge=1, le=10_000)
    # Trần số user được enqueue trong MỘT vòng quét. Chặn kịch bản sáng thứ Hai
    # cả nghìn user cùng tới hạn, dồn một cục vào hàng đợi và làm Sync thủ công
    # của người đang ngồi chờ bị xếp sau hàng dài.
    auto_sync_max_users_per_tick: int = Field(default=20, ge=1, le=500)

    # ---- Làm mới bộ nhớ đệm lịch ở nền (FR-102) ----
    # Mặc định TẮT cùng lý do với auto_sync_enabled: hệ thống gọi API Google khi
    # người dùng không ngồi trước máy. Khác auto-sync ở chỗ vòng này không tạo
    # Run và không chạy LLM — nó chỉ đồng bộ tăng dần bằng syncToken đã lưu.
    calendar_auto_refresh_enabled: bool = False
    # Khoảng cách tối thiểu giữa hai lần làm mới lịch của cùng một user. Ngắn
    # hơn auto-sync nhiều vì đồng bộ tăng dần rất rẻ, mà lịch bị dời giờ là
    # thứ người dùng cần biết sớm.
    calendar_auto_refresh_interval_minutes: int = Field(default=30, ge=5, le=1440)
    # Nhịp quét tìm user tới hạn làm mới lịch.
    calendar_auto_refresh_poll_seconds: float = Field(default=300.0, ge=10.0, le=3600.0)
    # Trần user xử lý trong một vòng quét, cùng lý do với auto-sync: không dồn
    # cả bảng vào một lượt và chiếm hết hạn mức API.
    calendar_auto_refresh_max_users_per_tick: int = Field(default=20, ge=1, le=500)

    # ---- Daily brief tự động (2026-08-12) ----
    # Không có công tắc tổng như auto_sync_enabled: opt-in nằm ở từng user qua
    # NotificationPreference.daily_brief_hour (NULL = tắt). Vòng quét luôn
    # chạy nhưng không làm gì nếu chưa ai bật giờ nhận.
    daily_brief_poll_seconds: float = Field(default=300.0, ge=10.0, le=3600.0)

    # ---- Routines (2026-08-14) — automation lịch chạy do user tự đặt ----
    # Cùng cơ chế poll với daily brief: vòng quét luôn chạy, chỉ làm gì khi có
    # routine tới đúng giờ. Chạy agent thật (gọi LLM) nên nhịp mặc định giữ
    # bằng daily_brief để không dồn dập gọi mô hình mỗi vài giây.
    routines_poll_seconds: float = Field(default=300.0, ge=10.0, le=3600.0)
    sse_poll_seconds: float = Field(default=0.5, ge=0.1, le=10.0)
    llm_questions_per_day: int = Field(default=10, ge=1, le=1000)
    # Fernet key (base64, 32 byte) để mã hoá access/refresh token của các
    # dịch vụ đã kết nối trước khi lưu DB. Bắt buộc phải set ở production.
    token_encryption_key: str = ""

    # ---- Discord OAuth2 ----
    discord_client_id: str = ""
    discord_client_secret: str = ""
    discord_bot_token: str = ""
    discord_public_key: str = ""

    # ---- Google OAuth2 (Gmail, Calendar và Sheets chỉ đọc) ----
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""
    # Lệch với FR-020 (PRD chốt Calendar chỉ đọc) — thêm calendar.events để tạo
    # sự kiện trực tiếp qua API thay vì mẫu/.ics. Cần nêu rõ trong PR, chưa có
    # ADR cập nhật ADR-002.
    # drive.readonly để duyệt/tìm file Docs & Sheets của user (picker) thay vì
    # bắt dán URL; documents.readonly vì endpoint /google-docs/task-proposals
    # kiểm tra đúng scope này nhưng luồng cấp quyền trước đây không hề xin nó.
    google_scopes: str = (
        "openid email profile https://www.googleapis.com/auth/gmail.readonly "
        "https://www.googleapis.com/auth/calendar.readonly "
        "https://www.googleapis.com/auth/calendar.events "
        "https://www.googleapis.com/auth/spreadsheets.readonly "
        "https://www.googleapis.com/auth/documents.readonly "
        "https://www.googleapis.com/auth/drive.readonly"
    )

    # ---- Chống spam token khi đọc Google Docs/Sheets ----
    # Một người dùng có thể trỏ vào file khổng lồ để đốt token của hệ thống.
    # Ba lớp phòng: cắt nội dung trước khi vào LLM, giới hạn số lượt đọc mỗi
    # ngày, và cache theo revision để đọc lại cùng một file không tốn gì.
    # Mọi ngưỡng khai ở đây, không hardcode rải rác trong connector/API.
    google_document_reads_per_day: int = Field(default=20, ge=1, le=1000)
    google_document_max_chars: int = Field(default=20_000, ge=1_000, le=500_000)
    google_sheet_max_rows: int = Field(default=500, ge=10, le=50_000)
    google_sheet_max_columns: int = Field(default=20, ge=1, le=200)
    google_document_cache_ttl_seconds: int = Field(default=900, ge=0, le=86_400)
    google_drive_page_size_max: int = Field(default=50, ge=1, le=1000)
    # Ngưỡng CỨNG cho phản hồi tải về từ Google, chặn ngay ở tầng request:
    # cap 20.000 ký tự chỉ giới hạn token, không giới hạn RAM/băng thông. Một
    # Doc 20.000 ký tự kèm định dạng hiếm khi quá vài trăm KB, nên 8 MB đủ rộng
    # cho tài liệu thật mà vẫn chặn được file dựng riêng để bơm bộ nhớ.
    google_api_max_response_bytes: int = Field(default=8_000_000, ge=100_000, le=100_000_000)

    # ---- AnythingLLM-compatible Gmail read bridge ----
    # Opt-in only. The bridge is a single-user Apps Script endpoint, so keep
    # the endpoint/key outside the repository and pin it to one authenticated
    # app user instead of exposing another user's mailbox to the agent.
    anythingllm_gmail_bridge_enabled: bool = False
    anythingllm_gmail_bridge_url: str = ""
    anythingllm_gmail_bridge_api_key: str = ""
    anythingllm_gmail_bridge_user_id: str = ""
    anythingllm_gmail_bridge_timeout_seconds: float = Field(default=8.0, ge=1.0, le=30.0)
    anythingllm_gmail_bridge_max_results: int = Field(default=20, ge=1, le=50)

    # ---- Jira OAuth2 3LO ----
    jira_client_id: str = ""
    jira_client_secret: str = ""
    jira_scopes: str = "read:jira-work read:me offline_access"

    # ---- Slack OAuth v2 (user token — đọc DM/channel như chính user đang
    # kết nối, KHÔNG dùng bot token mời riêng từng channel) ----
    # Bám sát docs/projects/engineering/slack-detail.drawio: DRAFT, PRD hiện
    # loại Slack khỏi scope chính thức. channels:read/groups:read/im:read/
    # mpim:read cho list_sources() (conversations.list); *:history cho
    # fetch_range(); users:read để resolve tên hiển thị; team:read để lấy
    # domain workspace dựng deep_link — CẦN xác nhận lại tên scope thật khi
    # có Slack App/workspace test thật, chưa verify end-to-end.
    slack_client_id: str = ""
    slack_client_secret: str = ""
    slack_user_scopes: str = (
        "channels:history groups:history im:history mpim:history "
        "channels:read groups:read im:read mpim:read users:read team:read"
    )

    # ---- Microsoft identity platform (Outlook) — ADR-013 ----
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    # "common" nhận cả tài khoản cá nhân (outlook.com/hotmail.com) lẫn tài
    # khoản Microsoft 365 tổ chức — chương trình không giả định người dùng
    # dùng loại tài khoản nào.
    microsoft_tenant: str = "common"
    # Chỉ đọc mail (Mail.Read) — không xin Mail.ReadWrite/Mail.Send, P0 không
    # cần và xin thừa quyền là rủi ro privacy không cần thiết (ADR-013 mục 2).
    # User.Read bắt buộc phải có: openid/profile/email chỉ là scope OIDC cho
    # claim trong ID token, không tự cấp quyền gọi REST endpoint GET /me của
    # Graph — thiếu User.Read thì /me trả 401, fetch_account_profile() không
    # lấy được email, tự tạo tài khoản thất bại.
    microsoft_scopes: str = (
        "openid profile email offline_access "
        "https://graph.microsoft.com/User.Read "
        "https://graph.microsoft.com/Mail.Read"
    )

    # ---- Telegram (không có OAuth2 chuẩn — dùng Telegram Login Widget) ----
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""
    # BotFather/setWebhook secret. Bắt buộc khác bot token và không log giá trị.
    telegram_webhook_secret: str = ""
    # Outbound push là material behavior nên mặc định tắt cho tới khi deploy đã
    # cấu hình consent, webhook và bot đúng môi trường.
    telegram_delivery_enabled: bool = False
    telegram_delivery_poll_seconds: float = Field(default=30.0, ge=10.0, le=3600.0)

    # ---- Web Push (kênh giao thông báo thứ ba) ----
    # Mặc định TẮT, cùng lý do với telegram_delivery_enabled và auto_sync_enabled:
    # đây là hành vi gửi ra ngoài khi người dùng không ngồi trước máy, phải bật
    # có chủ đích sau khi môi trường đã có cặp khoá VAPID thật.
    web_push_enabled: bool = False
    # Khoá công khai VAPID — trình duyệt cần chuỗi này lúc đăng ký, nên nó được
    # trả qua GET /push/public-key và không phải bí mật.
    vapid_public_key: str = ""
    # Khoá riêng VAPID ký mọi lời gọi tới push service. Là bí mật thật: không
    # commit, không log, không trả về qua API.
    vapid_private_key: str = ""
    # Định danh liên hệ gửi kèm mỗi lời gọi để push service báo lại khi ta gửi
    # sai. Chuẩn VAPID đòi dạng "mailto:" hoặc URL.
    vapid_subject: str = "mailto:admin@example.com"
    # Nhịp quét reminder tới hạn của kênh Web Push. Dày như Telegram vì đây là
    # kênh người dùng mong nhận gần như tức thì.
    web_push_poll_seconds: float = Field(default=30.0, ge=10.0, le=3600.0)


@lru_cache
def get_settings() -> Settings:
    return Settings()


def allowed_web_origins() -> set[str]:
    """Tập origin web được phép nhận redirect sau OAuth — nguồn sự thật DUY NHẤT.

    Trước đây `auth.py` chỉ so với `web_app_public_url` (một origin), còn
    `connections.py` so với `cors_origins` (nhiều origin). Hệ quả thật: sau khi
    thêm domain mới vào CORS mà quên `WEB_APP_PUBLIC_URL`, đăng nhập Google chết
    trên domain mới với "ext_redirect_uri không hợp lệ" trong khi domain cũ vẫn
    chạy. Gộp về một hàm để không tái diễn.

    Vẫn so khớp nguyên origin (scheme + netloc), không dùng startswith — chuỗi
    "https://mondaiy.io.vn.evil.com" cũng "bắt đầu bằng" domain thật.
    """
    settings = get_settings()
    origins = {o.strip().rstrip("/") for o in settings.cors_origins.split(",") if o.strip()}
    for extra in (settings.web_app_public_url, settings.app_public_url):
        value = (extra or "").strip().rstrip("/")
        if value:
            origins.add(value)
    return origins
