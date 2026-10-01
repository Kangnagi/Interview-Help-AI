"""
이메일 발송 서비스 — 비밀번호 재설정 링크 전송
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from core.config import settings

logger = logging.getLogger(__name__)


async def send_password_reset_email(to_email: str, reset_token: str) -> bool:
    """
    비밀번호 재설정 링크를 담은 이메일을 발송합니다.
    SMTP 설정이 없으면 콘솔에 링크를 출력하고 True를 반환합니다(개발 모드).
    """
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        # 개발 환경: 콘솔 출력으로 대체
        logger.info(f"[개발 모드] 비밀번호 재설정 링크: {reset_url}")
        print(f"\n=== 비밀번호 재설정 링크 (개발 모드) ===\n{reset_url}\n")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "[Interview-Help-AI] 비밀번호 재설정 안내"
        msg["From"] = settings.SMTP_USER
        msg["To"] = to_email

        html_body = f"""
        <html><body>
        <h2>비밀번호 재설정 요청</h2>
        <p>아래 버튼을 클릭하여 비밀번호를 재설정하세요.</p>
        <p>이 링크는 <strong>30분</strong> 동안 유효합니다.</p>
        <br>
        <a href="{reset_url}"
           style="background:#4F46E5;color:white;padding:12px 24px;
                  border-radius:6px;text-decoration:none;font-weight:bold;">
           비밀번호 재설정
        </a>
        <br><br>
        <p>본인이 요청하지 않은 경우 이 이메일을 무시하세요.</p>
        </body></html>
        """

        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_USER, to_email, msg.as_string())

        logger.info(f"비밀번호 재설정 이메일 발송 완료: {to_email}")
        return True

    except Exception as e:
        logger.error(f"이메일 발송 실패 ({to_email}): {e}")
        return False
