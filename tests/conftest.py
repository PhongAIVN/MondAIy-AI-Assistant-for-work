import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

# Must be set before importing the FastAPI app: ``rate_limit`` builds its
# storage backend at import time.  This keeps every test (including pure agent
# tests that inherit the autouse fixture below) independent from Docker/Redis.
os.environ.setdefault("APP_ENV", "test")
# Khoá ký cố định chỉ dành cho test. Thiếu nó thì ~298 test đỏ vì Settings từ
# chối khởi tạo — nhưng chỉ khi CHẠY, còn `--collect-only` vẫn xanh, nên lỗi rất
# dễ bị đọc nhầm thành "suite ổn". Trên máy phát triển và trong CI biến này có
# sẵn (từ .env hoặc checks.yml), nên hỏng chỉ lộ ra ở clean checkout và ở
# worktree — đúng nơi agent hay chạy, và đúng nơi không ai nhìn kỹ. setdefault
# để giá trị thật của CI vẫn thắng.
os.environ.setdefault("APP_SECRET_KEY", "test-only-secret-key-not-for-any-real-environment")
# Google refresh tests mock token HTTP nhưng vẫn phải qua guard cấu hình thật.
# Chỉ dựng giá trị test-only ở đây, không nới runtime fallback khi thiếu secret.
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-client-secret")
# Fernet key cố định chỉ dành cho test; clean checkout không được phụ thuộc vào
# TOKEN_ENCRYPTION_KEY vô tình có trong .env của máy phát triển.
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
# Never send test traces to the production LangSmith project.  Production
# tracing remains opt-in through the real runtime environment.
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ.setdefault("APP_TIMEZONE", "Asia/Ho_Chi_Minh")
os.environ.setdefault("PROGRAM_COHORT_SLUG", "cohort-iii")

# Tests must not inherit DATABASE_URL from a developer's .env file.  A real
# Postgres test run remains opt-in through TEST_DATABASE_URL, so the default
# suite is isolated and reproducible on a clean checkout.
_test_db_path = Path(tempfile.gettempdir()) / f"p004-test-{os.getpid()}.db"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_test_db_path}")

# Unit tests must never reach the real OpenAI API.  A developer's .env carries
# a live key, and an ambient key silently flips the memory-intent path on:
# inferred facts get written through the LLM branch as ``confirmed`` instead of
# the regex branch as ``candidate``, breaking semantic tests AND spending real
# tokens on every run.  Tests that specifically exercise the LLM path override
# this on the settings instance (see fake_intents in test_memory_capture_intent).
os.environ["OPENAI_API_KEY"] = ""
# Cùng lý do, cho nhà cung cấp còn lại — và cái này đã bị bỏ sót.
#
# `embed_queries` (dùng chung cho intent lẫn RAG) gọi thẳng OpenRouter. Máy nào
# có .env là test gọi mạng THẬT ở mỗi lượt agent, ăn 402/429 rồi retry có
# backoff. Đo trên một test hội thoại: 18,12s khi có key, 1,61s khi không.
# Cả suite đi từ 19 phút xuống còn khoảng 6.
#
# Chậm mới là triệu chứng dễ thấy; vấn đề thật là test đọc kết quả mạng, nên
# kết quả của chúng phụ thuộc vào việc một tài khoản ở đâu đó còn credit hay không.
os.environ["OPENROUTER_API_KEY"] = ""

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from src.api.rate_limit import limiter  # noqa: E402
from src.db import Base, engine, ensure_runtime_schema  # noqa: E402
from src.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _create_tables():
    """Tạo bảng trước khi chạy test.

    create_all chỉ được gọi trong lifespan của FastAPI, mà ASGITransport của
    httpx không chạy lifespan. Trên máy đã từng chạy app thì file sqlite còn
    bảng cũ nên test vẫn xanh, còn trên checkout sạch như CI thì mọi test chạm
    DB đều hỏng vì không có bảng nào.

    ensure_runtime_schema phải chạy kèm: create_all không sửa bảng đã tồn tại,
    nên DB của máy đang dev thiếu đúng những cột thêm sau — chính là trường hợp
    lifespan xử lý được còn test thì không.
    """
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema()
    yield
    engine.dispose()
    if engine.dialect.name == "sqlite":
        _test_db_path.unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Test client dùng chung 1 IP giả lập nên phải xoá counter mỗi test,
    nếu không các test gọi /auth/register hoặc /auth/login liên tiếp sẽ
    dính 429 giữa chừng dù không phải test đang kiểm tra rate limit."""
    limiter.reset()
    yield
    limiter.reset()


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing API endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_llm():
    """Mock LLM to avoid calling OpenAI during tests.

    Usage in test:
        def test_something(mock_llm):
            # LLM calls will return mock response instead of hitting OpenAI
            ...
    """
    mock = AsyncMock()
    mock.ainvoke.return_value = AsyncMock(content="Mocked LLM response")
    return mock
