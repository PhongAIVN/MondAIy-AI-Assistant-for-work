"""Ngôn ngữ đầu ra cho phần LLM viết ra (title/summary/detail/brief).

Ngôn ngữ ở đây là ngôn ngữ GIAO DIỆN người dùng đang dùng, không phải ngôn ngữ
của mail nguồn: hộp thư tiếng Anh mà giao diện đang để tiếng Việt thì bản tóm
tắt phải là tiếng Việt, và ngược lại. Vì vậy mọi câu chỉ dẫn dưới đây đều nói
thẳng "dịch sang" chứ không chỉ "viết bằng" — mô hình rất hay bám theo ngôn ngữ
của tư liệu nếu không bị dặn rõ.

Ngoại lệ có chủ đích: evidence_quote và time_expression LUÔN giữ nguyên văn,
nguyên ngôn ngữ nguồn (xem extract_batch.py) — đó là bằng chứng, không phải văn
bản để đọc.

Thêm một ngôn ngữ = thêm 1 dòng vào mỗi dict ở dưới, không phải sửa logic.
"""

from __future__ import annotations

from typing import Literal

SupportedLanguage = Literal["vi", "en", "es", "fr", "de", "ja", "zh", "ko"]

SUPPORTED_LANGUAGES: tuple[str, ...] = ("vi", "en", "es", "fr", "de", "ja", "zh", "ko")

DEFAULT_LANGUAGE = "vi"

# Dùng cho extract_batch: model vừa viết title vừa viết summary.
TITLE_AND_SUMMARY_INSTRUCTION: dict[str, str] = {
    "vi": "Viết title và summary bằng tiếng Việt, dịch sang tiếng Việt nếu mail gốc viết bằng thứ tiếng khác.",
    "en": "Write title and summary in English, translating from the source language when the mail is not in English.",
    "es": "Escribe el title y el summary en español, traduciendo desde el idioma original cuando el correo no esté en español.",
    "fr": "Rédige le title et le summary en français, en traduisant depuis la langue source si le message n'est pas en français.",
    "de": "Schreibe title und summary auf Deutsch und übersetze aus der Ausgangssprache, wenn die E-Mail nicht auf Deutsch ist.",
    "ja": "title と summary は日本語で書き、メールが日本語でない場合は日本語に翻訳してください。",
    "zh": "请用中文撰写 title 和 summary；如果邮件原文不是中文，请翻译成中文。",
    "ko": "title과 summary는 한국어로 작성하고, 메일 원문이 한국어가 아니면 한국어로 번역하세요.",
}

# Dùng cho reduce và brief: chỉ có 1 đoạn văn xuôi.
SUMMARY_INSTRUCTION: dict[str, str] = {
    "vi": "Viết bằng tiếng Việt, dịch sang tiếng Việt nếu tư liệu viết bằng thứ tiếng khác.",
    "en": "Write in English, translating from the source language when the material is not in English.",
    "es": "Escribe en español, traduciendo desde el idioma original cuando el material no esté en español.",
    "fr": "Rédige en français, en traduisant depuis la langue source si le matériau n'est pas en français.",
    "de": "Schreibe auf Deutsch und übersetze aus der Ausgangssprache, wenn das Material nicht auf Deutsch ist.",
    "ja": "日本語で書いてください。資料が日本語でない場合は日本語に翻訳してください。",
    "zh": "请用中文撰写；如果材料原文不是中文，请翻译成中文。",
    "ko": "한국어로 작성하고, 자료가 한국어가 아니면 한국어로 번역하세요.",
}

# Tiêu đề lưới an toàn (extract_batch._safety_net_signal) — không qua LLM nên
# phải dịch sẵn ở đây.
SAFETY_NET_TITLE: dict[str, str] = {
    "vi": "Cần xem lại — có hạn và yêu cầu hành động",
    "en": "Needs review — deadline and action detected",
    "es": "Requiere revisión — se detectó fecha límite y acción",
    "fr": "À revoir — échéance et action détectées",
    "de": "Zu prüfen — Frist und Handlungsbedarf erkannt",
    "ja": "要確認 — 期限とアクションを検出",
    "zh": "需要复核 — 检测到截止时间和待办动作",
    "ko": "확인 필요 — 기한과 조치 사항 감지",
}


# Câu hiển thị khi một lần Sync không tìm được mail nào — không qua LLM nên
# phải dịch sẵn, y hệt SAFETY_NET_TITLE.
EMPTY_RESULT_MESSAGE: dict[str, str] = {
    "vi": "Không tìm thấy email phù hợp trong khoảng thời gian đã chọn.",
    "en": "No relevant email was found in the selected time range.",
    "es": "No se encontró ningún correo relevante en el rango de fechas seleccionado.",
    "fr": "Aucun e-mail pertinent n'a été trouvé dans la période sélectionnée.",
    "de": "Im gewählten Zeitraum wurde keine relevante E-Mail gefunden.",
    "ja": "選択した期間に該当するメールは見つかりませんでした。",
    "zh": "在所选时间范围内没有找到相关邮件。",
    "ko": "선택한 기간에서 관련 메일을 찾지 못했습니다.",
}


def resolve(language: str | None) -> str:
    """Ngôn ngữ hợp lệ gần nhất. Giá trị lạ (hoặc thiếu) rơi về mặc định thay
    vì làm hỏng cả run — ngôn ngữ hiển thị không đáng để đánh sập một lần Sync."""
    if language in SUPPORTED_LANGUAGES:
        return str(language)
    return DEFAULT_LANGUAGE


def title_and_summary_instruction(language: str | None) -> str:
    return TITLE_AND_SUMMARY_INSTRUCTION[resolve(language)]


def summary_instruction(language: str | None) -> str:
    return SUMMARY_INSTRUCTION[resolve(language)]


def safety_net_title(language: str | None) -> str:
    return SAFETY_NET_TITLE[resolve(language)]


def empty_result_message(language: str | None) -> str:
    return EMPTY_RESULT_MESSAGE[resolve(language)]
