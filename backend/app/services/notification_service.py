import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List
from app.config import settings

logger = logging.getLogger(__name__)


class NotificationService:

    @staticmethod
    def send_email(to: str, subject: str, html_body: str) -> bool:
        if not settings.SMTP_HOST:
            logger.warning("[Email] SMTP_HOST non configuré — email ignoré")
            return False
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.EMAIL_FROM
            msg["To"] = to
            msg.attach(MIMEText(html_body, "html", "utf-8"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.ehlo()
                # STARTTLS seulement si le serveur le propose (pas Mailhog)
                if server.has_extn("STARTTLS"):
                    server.starttls()
                    server.ehlo()
                # Login seulement si des credentials sont fournis
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.EMAIL_FROM, to, msg.as_string())

            logger.info(f"[Email] ✓ Envoyé à {to} — {subject}")
            return True
        except Exception as e:
            logger.error(f"[Email] ✗ Échec envoi à {to} — {e}")
            return False

    @staticmethod
    def smtp_status() -> dict:
        """Vérifie si le SMTP est joignable. Utilisé par l'endpoint de test."""
        if not settings.SMTP_HOST:
            return {"configured": False, "reachable": False, "message": "SMTP_HOST non défini"}
        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=5) as server:
                server.ehlo()
                return {
                    "configured": True,
                    "reachable": True,
                    "host": settings.SMTP_HOST,
                    "port": settings.SMTP_PORT,
                    "auth_required": bool(settings.SMTP_USER),
                    "message": "SMTP joignable",
                }
        except Exception as e:
            return {
                "configured": True,
                "reachable": False,
                "host": settings.SMTP_HOST,
                "port": settings.SMTP_PORT,
                "message": str(e),
            }

    @staticmethod
    def build_alert_email(user_name: str, devices: list, alert_name: str) -> str:
        rows = ""
        for d in devices[:20]:
            status_label = {"open": "Ouvert", "closed": "Fermé", "recurring": "Récurrent"}.get(
                d.status, d.status
            )
            amount = ""
            if d.amount_max:
                amount = f"jusqu'à {d.amount_max:,.0f} {d.currency}"
            close = f"Clôture : {d.close_date.strftime('%d/%m/%Y')}" if d.close_date else ""

            rows += f"""
            <tr>
                <td style="padding:10px;border-bottom:1px solid #eee;">
                    <strong>{d.title}</strong><br>
                    <small>{d.organism} · {d.country}</small>
                </td>
                <td style="padding:10px;border-bottom:1px solid #eee;">{d.device_type}</td>
                <td style="padding:10px;border-bottom:1px solid #eee;">{amount}</td>
                <td style="padding:10px;border-bottom:1px solid #eee;">{close}</td>
                <td style="padding:10px;border-bottom:1px solid #eee;">
                    <a href="{d.source_url}" style="color:#2563eb;">Voir →</a>
                </td>
            </tr>"""

        return f"""
        <html><body style="font-family:sans-serif;color:#1f2937;max-width:800px;margin:auto">
        <div style="background:#2563eb;padding:20px;border-radius:8px 8px 0 0">
            <h1 style="color:white;margin:0;font-size:20px">FinVeille — Alerte : {alert_name}</h1>
        </div>
        <div style="padding:20px;background:#f9fafb;">
            <p>Bonjour {user_name},</p>
            <p>{len(devices)} dispositif(s) correspondent à votre veille <strong>{alert_name}</strong> :</p>
            <table style="width:100%;border-collapse:collapse;background:white;border-radius:8px;overflow:hidden">
                <thead>
                    <tr style="background:#dbeafe">
                        <th style="padding:10px;text-align:left">Dispositif</th>
                        <th style="padding:10px;text-align:left">Type</th>
                        <th style="padding:10px;text-align:left">Montant</th>
                        <th style="padding:10px;text-align:left">Date</th>
                        <th style="padding:10px;text-align:left">Lien</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
            <p style="color:#6b7280;font-size:12px;margin-top:20px">
                Vous recevez cet email car vous avez configuré une alerte sur FinVeille.<br>
                <a href="#">Se désabonner</a>
            </p>
        </div>
        </body></html>
        """
