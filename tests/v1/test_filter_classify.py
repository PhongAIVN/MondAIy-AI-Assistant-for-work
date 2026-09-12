from datetime import UTC, datetime, timedelta

from src.config import Settings
from src.services.filter_classify import FilterConfig, classify_email, filter_and_classify, has_valid_deep_link
from src.services.hf_mail_classifier import HfMailPrediction

NOW = datetime(2026, 8, 8, tzinfo=UTC)


def _email(**kwargs):
    return {
        "id": "m1",
        "thread_id": "t1",
        "author_id": "mentor@school.edu",
        "subject": "Action required: proposal deadline",
        "text": "Please submit the proposal before Friday.",
        "to": ["student@school.edu"],
        "cc": [],
        "sent_at": NOW,
        **kwargs,
    }


def test_classification_scores_direct_deadline_email_as_actionable():
    result = classify_email(
        _email(is_unread=True),
        FilterConfig(user_email="student@school.edu", trusted_senders=frozenset({"mentor@school.edu"})),
    )
    assert result.importance_score >= 80
    assert result.importance == "critical"
    assert result.brief_section == "needs_action"
    assert result.must_not_miss


def test_filter_drops_old_and_newsletter_noise_but_keeps_direct_reply():
    old = _email(id="old", sent_at=NOW - timedelta(days=30), text="Please read this old note")
    noise = _email(
        id="noise", author_id="noreply@shop.test", subject="Newsletter sale", text="Unsubscribe from sale", to=[], cc=[]
    )
    reply = _email(id="reply", subject="Quick question", text="Reply when you can")
    result = filter_and_classify([old, noise, reply], FilterConfig(user_email="student@school.edu"), now=NOW)
    assert {item["id"] for item in result["items"]} == {"reply"}
    assert {item["reason"] for item in result["rejected"]} >= {"outside_lookback", "negative_state"}


def test_filter_drops_bilingual_social_notification_noise():
    item = _email(
        id="linkedin-notification",
        author_id="linkedin@example.test",
        subject="Bạn có 8 thông báo mới trên LinkedIn",
        text=(
            "Bạn có thông báo mới. 8 người đã xem hồ sơ của bạn. "
            "3 kết nối đã đăng bài mới. Đăng nhập LinkedIn để xem chi tiết."
        ),
    )

    result = filter_and_classify([item], FilterConfig(user_email="student@school.edu"), now=NOW)

    assert result["items"] == []
    assert result["rejected"][0]["reason"] == "negative_state"


def test_filter_drops_vietnamese_bank_transfer_notification_despite_action_and_date_words():
    # "vui long" khớp ACTION_RE, "19/08" khớp DEADLINE_RE — trước khi có
    # TRANSACTIONAL_NOTIFICATION_FOLDED_TERMS, 2 tín hiệu này đủ để
    # must_not_miss=True, mail bị giữ lại như 1 task thật.
    item = _email(
        id="bank-notification",
        author_id="notify@somebank.example",
        subject="Thông báo biến động số dư",
        text=(
            "Giao dịch chuyển khoản thành công lúc 19/08. Biến động số dư: -500,000d. "
            "Vui lòng không trả lời email này."
        ),
        to=[],
        cc=[],
    )

    result = filter_and_classify([item], FilterConfig(user_email="student@school.edu"), now=NOW)

    assert result["items"] == []
    assert result["rejected"][0]["reason"] == "negative_state"


def test_filter_keeps_real_task_that_merely_mentions_transfer_or_invoice():
    # Đảm bảo term list mới không dập nhầm task thật chỉ vì nhắc "chuyển
    # khoản"/"hóa đơn" — giọng văn yêu cầu hành động thật, không phải giọng
    # biên nhận tự động.
    item = _email(
        id="real-task",
        subject="Nhờ chuyển khoản học phí",
        text="Em cần chuyển khoản học phí và thanh toán hóa đơn dự án trước thứ Sáu giúp anh.",
    )

    result = classify_email(item, FilterConfig(user_email="student@school.edu"))

    assert not result.reasons or "negative_state" not in result.reasons
    assert result.must_not_miss


def test_filter_drops_mail_not_addressed_to_user_despite_action_and_deadline_signal():
    # Mail thật có header to/cc (Gmail) nhưng user không nằm trong đó — nhắc
    # việc của người khác (to=colleague), không phải task của user dù đủ
    # action+deadline+trusted signal.
    item = _email(
        author_id="mentor@school.edu",
        to=["colleague@school.edu"],
        cc=[],
    )
    result = filter_and_classify(
        [item],
        FilterConfig(user_email="student@school.edu", trusted_senders=frozenset({"mentor@school.edu"})),
        now=NOW,
    )
    assert result["items"] == []
    assert result["rejected"][0]["reason"] == "not_addressed"


def test_filter_keeps_mail_sent_to_a_group_alias_shown_as_a_name():
    """to hiện ra dưới dạng TÊN nhóm chứ không phải địa chỉ ("Engineering All")
    là thiếu bằng chứng, không phải bằng chứng "không gửi cho mình": người dùng
    vẫn nhận mail vì nằm trong nhóm. Loại thẳng ở đây cắt đúng phần mail công
    việc thật — golden dataset rơi 18/57 mail KEEP đúng vì lý do này."""
    item = _email(to=["Engineering All"], cc=[])
    result = filter_and_classify([item], FilterConfig(user_email="student@school.edu"), now=NOW)
    assert {i["id"] for i in result["items"]} == {"m1"}


def test_filter_keeps_mail_addressed_to_user_via_cc():
    item = _email(to=["colleague@school.edu"], cc=["student@school.edu"])
    result = filter_and_classify([item], FilterConfig(user_email="student@school.edu"), now=NOW)
    assert {i["id"] for i in result["items"]} == {"m1"}


def test_filter_drops_trusted_domain_newsletter_not_addressed_to_user():
    # trusted sender/domain một mình không còn đủ để dập noise — newsletter
    # broadcast từ domain tin cậy nhưng KHÔNG gửi riêng cho user vẫn phải bị
    # loại, không được auto must_not_miss chỉ vì domain quen.
    item = _email(
        id="broadcast",
        author_id="news@school.edu",
        subject="Newsletter tuần này",
        text="Unsubscribe anytime. Chương trình khuyến mãi tuần này cho toàn trường.",
        to=["all-students@school.edu"],
        cc=[],
    )
    result = filter_and_classify(
        [item],
        FilterConfig(
            user_email="student@school.edu",
            trusted_senders=frozenset({"news@school.edu"}),
            trusted_sender_domains=frozenset({"school.edu"}),
        ),
        now=NOW,
    )
    assert result["items"] == []


def test_filter_keeps_mail_addressed_to_connected_mailbox_different_from_app_login_email():
    # Bug thật đã xảy ra: user đăng nhập app bằng lynnhatsuki@gmail.com nhưng
    # connect Gmail account lyn.nhi3010@gmail.com để đồng bộ — mail thật gửi
    # cho lyn.nhi3010@gmail.com (mailbox_email, gmail.py normalize() stamp),
    # KHÔNG phải config.user_email (identity đăng nhập app). Dùng nhầm
    # config.user_email để so khớp to/cc từng khiến TOÀN BỘ mail bị coi là
    # "không gửi cho mình" và bị loại sạch.
    item = _email(
        to=["lyn.nhi3010@gmail.com"],
        cc=[],
        mailbox_email="lyn.nhi3010@gmail.com",
    )
    result = filter_and_classify(
        [item],
        FilterConfig(user_email="lynnhatsuki@gmail.com", trusted_senders=frozenset({"mentor@school.edu"})),
        now=NOW,
    )
    assert {i["id"] for i in result["items"]} == {"m1"}


def test_filter_drops_mail_addressed_to_a_different_mailbox_than_the_one_synced():
    item = _email(
        to=["someone-else@gmail.com"],
        cc=[],
        mailbox_email="lyn.nhi3010@gmail.com",
    )
    result = filter_and_classify(
        [item], FilterConfig(user_email="lynnhatsuki@gmail.com"), now=NOW
    )
    assert result["items"] == []
    assert result["rejected"][0]["reason"] == "not_addressed"


def test_filter_drops_marketing_mail_whose_unsubscribe_text_was_already_stripped():
    # gmail.py normalize() xoá "unsubscribe"/preferences link khỏi text hiển
    # thị TRƯỚC khi tới đây — has_marketing_boilerplate là tín hiệu duy nhất
    # còn lại để biết đây là mail quảng cáo. Không có nó, mail này sẽ lọt qua
    # vì text không còn chữ "unsubscribe"/"newsletter" nào cả.
    item = _email(
        id="marketing",
        author_id="hello@marketing.fontawesome.test",
        subject="Live Icon Wizard demo, tomorrow at 1pm ET",
        text="Join us Wednesday for a live demo, a few sneak peeks at what's next.",
        has_marketing_boilerplate=True,
    )
    result = filter_and_classify([item], FilterConfig(user_email="student@school.edu"), now=NOW)
    assert result["items"] == []


def test_filter_drops_github_bot_notification_despite_review_boilerplate_wording():
    # Bug thật: comment bot GitHub/CI ("Please review", "Recommended focus
    # areas") có sẵn chữ action-y trong template — has_action_signal=True một
    # mình từng đủ override automated_penalty, sender bot vẫn lọt.
    item = _email(
        id="github-bot",
        author_id="notifications@github.com",
        subject="phoenix-mentor[bot] left a comment",
        text="Here are some key observations to aid the review process. Please review the PR before merging.",
        to=["student@school.edu"],
        cc=[],
    )
    result = filter_and_classify([item], FilterConfig(user_email="student@school.edu"), now=NOW)
    assert result["items"] == []


def test_filter_drops_otp_code_email():
    item = _email(
        id="otp",
        author_id="noreply@bank.example",
        subject="Mã OTP giao dịch",
        text="Mã OTP của bạn là 123456. Mã OTP có hiệu lực trong vòng 5 phút.",
    )
    result = filter_and_classify([item], FilterConfig(user_email="student@school.edu"), now=NOW)
    assert result["items"] == []


def test_filter_drops_bank_generic_safety_tip_boilerplate():
    item = _email(
        id="vcb-safety-tip",
        author_id="vcbdigibank@info.vietcombank.com.vn",
        subject="Cảnh báo về giao dịch trực tuyến",
        text="To ensure safety when transacting online, please follow Vietcombank's safe transaction guide.",
    )
    result = filter_and_classify([item], FilterConfig(user_email="student@school.edu"), now=NOW)
    assert result["items"] == []


def test_filter_ignores_addressing_gate_for_provider_without_recipient_data():
    # Slack/Jira normalize luôn to=[] cc=[] — not_addressed không được áp
    # dụng, nếu không mọi tin Slack/Jira sẽ bị loại oan khi có user_email.
    item = _email(to=[], cc=[])
    result = classify_email(item, FilterConfig(user_email="student@school.edu"))
    assert "not_addressed" not in result.reasons


def test_has_valid_deep_link_accepts_gmail_domain():
    assert has_valid_deep_link({"provider": "google", "deep_link": "https://mail.google.com/mail/u/0/#all/m1"})


def test_has_valid_deep_link_accepts_jira_site_domain():
    assert has_valid_deep_link({"provider": "jira", "deep_link": "https://mycompany.atlassian.net/browse/PROJ-1"})


def test_has_valid_deep_link_rejects_jira_item_with_gmail_style_link():
    assert not has_valid_deep_link({"provider": "jira", "deep_link": "https://mail.google.com/mail/u/0/#all/m1"})


def test_has_valid_deep_link_allows_unknown_provider_through():
    # Provider chưa có trong whitelist -> không chặn, tránh lặp lỗi hardcode
    # chỉ-Gmail chặn luôn mọi nguồn khác (đã xảy ra trước khi sửa).
    assert has_valid_deep_link({"provider": "discord", "deep_link": "https://discord.com/channels/1/2/3"})


def test_has_valid_deep_link_allows_empty_deep_link():
    assert has_valid_deep_link({"provider": "google", "deep_link": None})


def test_filter_rejects_jira_item_with_wrong_domain_deep_link():
    bad = _email(id="bad", provider="jira", deep_link="https://mail.google.com/mail/u/0/#all/x")
    result = filter_and_classify([bad], FilterConfig(user_email="student@school.edu"), now=NOW)
    assert {item["reason"] for item in result["rejected"]} == {"invalid_source_url"}


def test_filter_keeps_jira_item_with_valid_site_deep_link():
    good = _email(id="good", provider="jira", deep_link="https://mycompany.atlassian.net/browse/PROJ-1")
    result = filter_and_classify([good], FilterConfig(user_email="student@school.edu"), now=NOW)
    assert {item["id"] for item in result["items"]} == {"good"}


def test_filter_deduplicates_same_message_and_groups_threads():
    first = _email(id="m1", text="Please submit proposal before Friday")
    duplicate = _email(id="m1-copy", text="Please submit proposal before Friday")
    second = _email(id="m2", text="Please submit the revised proposal before Friday")
    result = filter_and_classify([first, duplicate, second], FilterConfig(), now=NOW)
    assert len(result["items"]) == 2
    assert all(item["thread_size"] == 2 for item in result["items"])


def test_hf_classifier_resolves_rule_uncertainty_without_llm():
    item = _email(subject="Quick question", text="Let me know your thoughts.")
    settings = Settings(
        app_env="test",
        hf_mail_filter_enabled=True,
        hf_mail_filter_token="test-token",
        hf_mail_filter_min_confidence=0.8,
    )

    def fake_classifier(_item, _settings):
        return HfMailPrediction("LABEL_1", 0.94)

    result = filter_and_classify(
        [item],
        FilterConfig(user_email="student@school.edu"),
        now=NOW,
        model_classifier=fake_classifier,
        model_settings=settings,
    )

    assert result["items"][0]["filter_route"] == "hf_classifier_keep"
    assert result["items"][0]["classifier_source"] == "hf_xlmr"
    assert result["items"][0]["triage_probability"] == 0.94


def test_hf_classifier_abstains_and_preserves_llm_route():
    item = _email(subject="Quick question", text="Let me know your thoughts.")
    settings = Settings(app_env="test", hf_mail_filter_enabled=True, hf_mail_filter_token="test-token")

    result = filter_and_classify(
        [item],
        FilterConfig(user_email="student@school.edu"),
        now=NOW,
        model_classifier=lambda _item, _settings: HfMailPrediction("UNKNOWN", 0.99),
        model_settings=settings,
    )

    assert result["items"][0]["filter_route"] == "llm_extraction"
    assert result["items"][0]["triage_stage"] == "cheap_classifier"


def test_filter_drops_daily_digest_that_says_nothing_is_waiting():
    """Thư digest định kỳ khẳng định KHÔNG có việc gì đang chờ, nhưng lại đầy
    từ khoá action ("reply", "merging", "deploying") nên regex một mình từng
    chấm 70 điểm -> important -> lọt vào hộp việc (bug thật, routine@)."""
    item = _email(
        id="digest",
        author_id="routine@littlebird.ai",
        author_name="Littlebird",
        subject="Your daily brief",
        text=(
            "No direct messages, emails, or Slack DMs from the last 24 hours are waiting on "
            "your reply. No overdue personal commitments found. If you have one productive hour "
            "today, keep momentum by finishing that branch and merging or deploying it. "
            "Everything looks under control."
        ),
        to=["student@school.edu"],
    )
    result = filter_and_classify([item], FilterConfig(user_email="student@school.edu"), now=NOW)
    assert result["items"] == []
    assert result["rejected"][0]["reason"] == "negative_state"


def test_filter_drops_bot_sender_using_a_routine_local_part():
    item = _email(id="bot", author_id="digest@example.com", to=["student@school.edu"])
    result = filter_and_classify([item], FilterConfig(user_email="student@school.edu"), now=NOW)
    assert result["items"] == []


def test_filter_keeps_jira_work_assignment_despite_notification_footer():
    """Chặn cứng "người gửi bot" chỉ được xét trên ĐỊA CHỈ. Quét cả thân mail
    khiến gần như mọi thư hệ thống trúng chữ "notification" ở chân trang — bug
    thật: việc Jira giao đích danh cho người dùng bị chấm 0 điểm và drop."""
    item = _email(
        id="jira-assign",
        author_id="jira@vinait004.atlassian.net",
        author_name="HoàiAn Thái (Jira)",
        subject="",
        text=(
            "HoàiAn Thái assigned this work item to you. T004 - AI Product Build. "
            "You're receiving this notification because you are a participant."
        ),
        to=["student@school.edu"],
    )
    result = filter_and_classify([item], FilterConfig(user_email="student@school.edu"), now=NOW)
    assert {i["id"] for i in result["items"]} == {"jira-assign"}


def test_filter_keeps_reminder_listing_one_resolved_item_among_open_ones():
    """Từ trạng thái đứng một mình ("resolved") không chứng minh mail nói việc
    đã xong — bản nhắc liệt kê nhiều việc, 1 việc Resolved từng kéo cả mail
    xuống negative_state, chôn luôn các việc CHƯA xong nằm cùng mail."""
    item = _email(
        id="jira-remind",
        author_id="jira@vinait004.atlassian.net",
        author_name="Jira automation",
        subject="[Jira][T004] 4 công việc cần cập nhật",
        text=(
            "Đây là bản nhắc công việc. Việc định kỳ: nộp daily stand-up. "
            "TAPB-174 In Progress. TAPB-178 Resolved. Vui lòng cập nhật trạng thái trước thứ Sáu."
        ),
        to=["student@school.edu"],
    )
    result = filter_and_classify([item], FilterConfig(user_email="student@school.edu"), now=NOW)
    assert {i["id"] for i in result["items"]} == {"jira-remind"}


def test_filter_still_drops_a_confluence_recommendation_digest():
    item = _email(
        id="confluence",
        author_id="confluence@vinait004.atlassian.net",
        author_name="Confluence",
        subject="",
        text="Stay connected to people and their work. Your weekly content recommendations, ready to explore.",
        to=["student@school.edu"],
    )
    result = filter_and_classify([item], FilterConfig(user_email="student@school.edu"), now=NOW)
    assert result["items"] == []


def test_filter_still_drops_mail_saying_the_work_item_was_resolved():
    item = _email(
        id="done",
        author_id="jira@vinait004.atlassian.net",
        subject="",
        text="TAPB-178 has been resolved. Không cần làm gì thêm.",
        to=["student@school.edu"],
    )
    result = filter_and_classify([item], FilterConfig(user_email="student@school.edu"), now=NOW)
    assert result["items"] == []


def test_filter_keeps_request_to_send_back_an_updated_version():
    """"đã cập nhật" trần cùng loại lỗi với "resolved": "gửi lại bản đã cập
    nhật để cô review tiếp" là YÊU CẦU làm ra bản mới, không phải báo việc đã
    xong. Bug thật: mail giao việc kèm file benchmark bị drop vì đúng câu này."""
    item = _email(
        id="benchmark",
        author_id="mentor@school.edu",
        subject="KIỂM TRA BẢN BENCHMARK ĐỂ BỔ SUNG BÀI BÁO",
        text=(
            "Em kiểm tra lại file benchmark gồm 15 bài báo mà cô đã gửi. "
            "Em hoàn thành phần này rồi gửi lại bản đã cập nhật để cô review tiếp. "
            "Hạn cuối là thứ Sáu tuần này."
        ),
        to=["student@school.edu"],
    )
    result = filter_and_classify([item], FilterConfig(user_email="student@school.edu"), now=NOW)
    assert {i["id"] for i in result["items"]} == {"benchmark"}
    assert result["items"][0]["importance"] in {"critical", "important"}


def test_filter_keeps_notice_that_an_event_was_updated():
    """Không biến thể nào của "cập nhật" được coi là "hết việc": "Sự kiện đã
    được cập nhật, địa điểm mới..." là thay đổi người dùng PHẢI biết."""
    item = _email(
        id="moved",
        author_id="organizer@school.edu",
        subject="Updated invitation: Weekly Sync — đổi phòng họp",
        text="Sự kiện đã được cập nhật. Địa điểm mới: Phòng HN-5A. Địa điểm cũ: Phòng HN-3C.",
        to=["student@school.edu"],
    )
    result = filter_and_classify([item], FilterConfig(user_email="student@school.edu"), now=NOW)
    assert {i["id"] for i in result["items"]} == {"moved"}


def test_filter_still_drops_mail_saying_the_request_was_completed():
    item = _email(
        id="done-req",
        author_id="system@school.edu",
        subject="",
        text="Yêu cầu của bạn đã xử lý hoàn tất.",
        to=["student@school.edu"],
    )
    result = filter_and_classify([item], FilterConfig(user_email="student@school.edu"), now=NOW)
    assert result["items"] == []

