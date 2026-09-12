from src.config import Settings
from src.services.hf_mail_classifier import HfMailPrediction, apply_prediction, classify_mail


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return [{"label": "LABEL_1", "score": 0.91}, {"label": "LABEL_0", "score": 0.09}]


def test_hf_client_sends_classifier_payload_and_parses_prediction(monkeypatch):
    calls = {}

    def fake_post(url, **kwargs):
        calls.update(url=url, **kwargs)
        return _Response()

    monkeypatch.setattr("src.services.hf_mail_classifier.httpx.post", fake_post)
    settings = Settings(
        app_env="test",
        hf_mail_filter_enabled=True,
        hf_mail_filter_token="secret-in-runtime-only",
        hf_mail_filter_model="DungND1107/modaiy_vin",
    )

    prediction = classify_mail({"subject": "Deadline", "text": "Please submit today."}, settings)

    assert prediction == HfMailPrediction("LABEL_1", 0.91)
    assert calls["url"].endswith("/models/DungND1107/modaiy_vin")
    assert calls["headers"]["Authorization"] == "Bearer secret-in-runtime-only"
    assert calls["json"]["inputs"].startswith("Subject: Deadline")


def test_hf_client_fails_closed_without_token(monkeypatch):
    def fail_post(*_args, **_kwargs):
        raise AssertionError("must not call Hugging Face without a token")

    monkeypatch.setattr("src.services.hf_mail_classifier.httpx.post", fail_post)
    settings = Settings(app_env="test", hf_mail_filter_enabled=True)

    assert classify_mail({"text": "message"}, settings) is None


def test_hf_prediction_requires_mapped_label_and_confidence():
    settings = Settings(app_env="test", hf_mail_filter_min_confidence=0.8)

    assert apply_prediction(HfMailPrediction("LABEL_1", 0.79), settings=settings) is None
    assert apply_prediction(HfMailPrediction("UNKNOWN", 0.99), settings=settings) is None
    assert apply_prediction(HfMailPrediction("LABEL_0", 0.93), settings=settings) == (
        "drop",
        0.93,
        "hf_drop",
    )
