import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.config import get_settings

logger = logging.getLogger(__name__)


def send_password_reset_email(to_email: str, reset_link: str) -> None:
    """Gửi email chứa link đặt lại mật khẩu.

    Nếu SMTP chưa được cấu hình, chỉ log link ra console thay vì gửi thật.
    Điều này cho phép chạy full luồng ở dev/pilot mà không cần SMTP secret.
    """
    settings = get_settings()

    if not settings.smtp_host:
        logger.warning(
            "SMTP chưa cấu hình — link đặt lại mật khẩu cho %s: %s",
            to_email,
            reset_link,
        )
        return

    expire_minutes = settings.password_reset_token_expire_minutes

    message = MIMEMultipart("alternative")
    message["Subject"] = "Mondaiy - Đặt lại mật khẩu"
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = to_email

    text_body = (
        "Xin chào,\n\n"
        "Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản của bạn.\n\n"
        "Bạn có thể đặt mật khẩu mới bằng cách mở liên kết sau:\n"
        f"{reset_link}\n\n"
        f"Liên kết này sẽ hết hạn sau {expire_minutes} phút để đảm bảo an toàn "
        "cho tài khoản.\n\n"
        "Nếu bạn không thực hiện yêu cầu này, bạn có thể bỏ qua email này. "
        "Mật khẩu hiện tại của bạn sẽ không bị thay đổi.\n\n"
        "Trân trọng,\n"
        "Đội ngũ Mondaiy"
    )

    html_body = f"""
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Đặt lại mật khẩu - Mondaiy</title>
    </head>
    <body style="
        margin: 0;
        padding: 0;
        background-color: #f5f7fa;
        font-family: Arial, Helvetica, sans-serif;
        color: #1f2937;
    ">
        <div style="
            max-width: 600px;
            margin: 0 auto;
            padding: 40px 20px;
        ">
            <div style="
                background-color: #ffffff;
                border-radius: 12px;
                padding: 40px;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
            ">
                <h1 style="
                    margin: 0 0 24px;
                    font-size: 24px;
                    line-height: 1.3;
                    color: #111827;
                ">
                    Đặt lại mật khẩu
                </h1>

                <p style="
                    margin: 0 0 16px;
                    font-size: 16px;
                    line-height: 1.6;
                ">
                    Xin chào,
                </p>

                <p style="
                    margin: 0 0 16px;
                    font-size: 16px;
                    line-height: 1.6;
                ">
                    Chúng tôi nhận được yêu cầu đặt lại mật khẩu
                    cho tài khoản của bạn.
                </p>

                <p style="
                    margin: 0 0 28px;
                    font-size: 16px;
                    line-height: 1.6;
                ">
                    Nhấn vào nút bên dưới để đặt mật khẩu mới:
                </p>

                <div style="
                    text-align: center;
                    margin: 0 0 28px;
                ">
                    <a
                        href="{reset_link}"
                        style="
                            display: inline-block;
                            padding: 14px 28px;
                            background-color: #2563eb;
                            color: #ffffff;
                            text-decoration: none;
                            border-radius: 8px;
                            font-size: 16px;
                            font-weight: 600;
                        "
                    >
                        Đặt lại mật khẩu
                    </a>
                </div>

                <p style="
                    margin: 0 0 16px;
                    font-size: 14px;
                    line-height: 1.6;
                    color: #6b7280;
                ">
                    Liên kết này sẽ hết hạn sau
                    <strong>{expire_minutes} phút</strong>
                    để đảm bảo an toàn cho tài khoản.
                </p>

                <p style="
                    margin: 0;
                    font-size: 14px;
                    line-height: 1.6;
                    color: #6b7280;
                ">
                    Nếu bạn không thực hiện yêu cầu này,
                    bạn có thể bỏ qua email này.
                    Mật khẩu hiện tại của bạn sẽ không bị thay đổi.
                </p>

                <hr style="
                    margin: 32px 0 24px;
                    border: 0;
                    border-top: 1px solid #e5e7eb;
                ">

                <p style="
                    margin: 0;
                    font-size: 14px;
                    line-height: 1.5;
                    color: #6b7280;
                ">
                    Trân trọng,<br>
                    <strong>Đội ngũ Mondaiy</strong>
                </p>
            </div>
        </div>
    </body>
    </html>
    """

    message.attach(MIMEText(text_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(
        settings.smtp_host,
        settings.smtp_port,
        timeout=10,
    ) as server:
        if settings.smtp_use_tls:
            server.starttls()

        if settings.smtp_username:
            server.login(
                settings.smtp_username,
                settings.smtp_password,
            )

        server.sendmail(
            settings.smtp_from_email,
            [to_email],
            message.as_string(),
        )
