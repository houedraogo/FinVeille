import smtplib
import logging
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from typing import Any
from app.config import settings

logger = logging.getLogger(__name__)

# ─── Palette commune ────────────────────────────────────────────────────────────
_COLOR_PRIMARY   = "#2563eb"
_COLOR_ACCENT    = "#7c3aed"
_COLOR_SUCCESS   = "#059669"
_COLOR_WARN      = "#d97706"
_COLOR_SURFACE   = "#f8fafc"
_COLOR_BORDER    = "#e2e8f0"
_COLOR_TEXT      = "#1e293b"
_COLOR_MUTED     = "#64748b"


def _app_url(path: str = "") -> str:
    base = (settings.PUBLIC_APP_URL or "https://app.kafundo.com").rstrip("/")
    if not path:
        return base
    return f"{base}/{path.lstrip('/')}"


def _safe(value: Any) -> str:
    return escape(str(value or ""), quote=True)


def _button(label: str, href: str, color: str = _COLOR_PRIMARY) -> str:
    return f"""<a href="{_safe(href)}" style="display:inline-block;background:{color};color:white;text-decoration:none;font-weight:700;font-size:14px;padding:13px 24px;border-radius:10px;">
      {_safe(label)}
    </a>"""


def _key_value_rows(items: list[tuple[str, str]]) -> str:
    rows = []
    for index, (label, value) in enumerate(items):
        border = "" if index == len(items) - 1 else f"border-bottom:1px solid {_COLOR_BORDER};"
        rows.append(f"""
          <tr>
            <td style="padding:14px 18px;{border}">
              <span style="font-size:12px;color:{_COLOR_MUTED};text-transform:uppercase;letter-spacing:0.05em;">{_safe(label)}</span><br>
              <strong style="font-size:15px;color:{_COLOR_TEXT};">{_safe(value) or "—"}</strong>
            </td>
          </tr>""")
    return "".join(rows)

def _email_wrapper(content: str, preheader: str = "") -> str:
    """Enveloppe HTML commune pour tous les emails Kafundo."""
    pre = f'<div style="display:none;max-height:0;overflow:hidden;">{preheader}</div>' if preheader else ""
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kafundo</title></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
{pre}
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 0;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:white;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.06);">
      {content}
      <tr><td style="padding:24px 32px;background:#f8fafc;border-top:1px solid {_COLOR_BORDER};text-align:center;">
        <p style="margin:0;font-size:12px;color:{_COLOR_MUTED};">
          Kafundo — Plateforme de veille financement<br>
          Vous recevez cet email car vous avez un compte actif sur Kafundo.<br>
          <a href="#" style="color:{_COLOR_MUTED};">Se désabonner</a>
        </p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""

def _device_row(d: Any, *, base_url: str = "https://app.kafundo.com") -> str:
    """Ligne HTML pour un dispositif dans un email."""
    amount = ""
    if getattr(d, "amount_max", None):
        amount = f"jusqu'à {d.amount_max:,.0f} {getattr(d, 'currency', 'EUR')}"
    elif isinstance(d, dict) and d.get("amount_max"):
        amount = f"jusqu'à {d['amount_max']:,.0f} {d.get('currency', 'EUR')}"

    close_date = getattr(d, "close_date", None) or (d.get("close_date") if isinstance(d, dict) else None)
    if close_date and hasattr(close_date, "strftime"):
        close_str = close_date.strftime("%d/%m/%Y")
    elif close_date and isinstance(close_date, str):
        close_str = close_date[:10]
    else:
        close_str = "Non communiquée"

    title = getattr(d, "title", None) or (d.get("title", "—") if isinstance(d, dict) else "—")
    organism = getattr(d, "organism", "") or (d.get("organism", "") if isinstance(d, dict) else "")
    country = getattr(d, "country", "") or (d.get("country", "") if isinstance(d, dict) else "")
    device_id = getattr(d, "id", None) or (d.get("id", "") if isinstance(d, dict) else "")
    source_url = getattr(d, "source_url", "#") or (d.get("source_url", "#") if isinstance(d, dict) else "#")

    detail_url = f"{base_url}/devices/{device_id}" if device_id else source_url

    days_left = ""
    if close_date:
        try:
            if hasattr(close_date, "toordinal"):
                delta = (close_date - date.today()).days
            else:
                from datetime import datetime
                delta = (datetime.fromisoformat(str(close_date)[:10]).date() - date.today()).days
            if 0 <= delta <= 30:
                days_left = f' <span style="color:{_COLOR_WARN};font-weight:600;">J-{delta}</span>'
        except Exception:
            pass

    return f"""<tr>
      <td style="padding:14px 16px;border-bottom:1px solid {_COLOR_BORDER};vertical-align:top;">
        <strong style="color:{_COLOR_TEXT};font-size:14px;">{title}</strong><br>
        <span style="color:{_COLOR_MUTED};font-size:12px;">{organism} · {country}</span>
      </td>
      <td style="padding:14px 16px;border-bottom:1px solid {_COLOR_BORDER};font-size:13px;color:{_COLOR_MUTED};white-space:nowrap;">{amount}</td>
      <td style="padding:14px 16px;border-bottom:1px solid {_COLOR_BORDER};font-size:13px;color:{_COLOR_MUTED};white-space:nowrap;">{close_str}{days_left}</td>
      <td style="padding:14px 16px;border-bottom:1px solid {_COLOR_BORDER};text-align:right;">
        <a href="{detail_url}" style="color:{_COLOR_PRIMARY};font-size:13px;font-weight:600;text-decoration:none;">Voir →</a>
      </td>
    </tr>"""

def _device_table(rows_html: str) -> str:
    return f"""<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;border:1px solid {_COLOR_BORDER};border-radius:8px;overflow:hidden;">
      <thead><tr style="background:{_COLOR_SURFACE};">
        <th style="padding:10px 16px;text-align:left;font-size:12px;font-weight:600;color:{_COLOR_MUTED};text-transform:uppercase;letter-spacing:0.05em;">Dispositif</th>
        <th style="padding:10px 16px;text-align:left;font-size:12px;font-weight:600;color:{_COLOR_MUTED};text-transform:uppercase;letter-spacing:0.05em;">Montant</th>
        <th style="padding:10px 16px;text-align:left;font-size:12px;font-weight:600;color:{_COLOR_MUTED};text-transform:uppercase;letter-spacing:0.05em;">Clôture</th>
        <th style="padding:10px 16px;"></th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>"""


class NotificationService:

    # ─── Core sender ────────────────────────────────────────────────────────────

    @staticmethod
    def _make_connection(timeout: int = 20):
        """
        Retourne le bon contexte SMTP selon le port :
        - Port 465 → SSL direct (SMTP_SSL)
        - Autres   → plain + STARTTLS si dispo (port 587, 25…)
        """
        import ssl
        host = settings.SMTP_HOST
        port = settings.SMTP_PORT
        if port == 465:
            # cPanel partagé : le certificat est souvent émis pour le hostname du serveur
            # (ex: whgi.net) et non pour le nom SMTP → on désactive la vérif de hostname
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return smtplib.SMTP_SSL(host, port, context=ctx, timeout=timeout)
        else:
            server = smtplib.SMTP(host, port, timeout=timeout)
            server.ehlo()
            if server.has_extn("STARTTLS"):
                server.starttls()
                server.ehlo()
            return server

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

            with NotificationService._make_connection() as server:
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.EMAIL_FROM, to, msg.as_string())

            logger.info(f"[Email] ✓ Envoyé à {to} — {subject}")
            return True
        except Exception as e:
            logger.error(f"[Email] ✗ Échec envoi à {to} — {e}")
            return False

    # ─── Notifications admin ────────────────────────────────────────────────────

    @staticmethod
    def send_welcome_email(
        user_email: str,
        user_name: str,
        method: str = "email",
    ) -> bool:
        """Email d'accueil envoyé au nouvel utilisateur après création du compte."""
        first_name = (user_name or "").strip().split(" ")[0] or "bienvenue"
        method_label = "Google" if method == "google" else "email et mot de passe"
        content = f"""
      <tr><td style="padding:32px 32px 22px;background:linear-gradient(135deg,{_COLOR_PRIMARY},{_COLOR_ACCENT});">
        <p style="margin:0 0 8px;font-size:12px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:rgba(255,255,255,0.78);">Bienvenue sur Kafundo</p>
        <h1 style="margin:0;color:white;font-size:24px;font-weight:800;line-height:1.25;">Votre espace de veille financement est prêt</h1>
        <p style="margin:12px 0 0;color:rgba(255,255,255,0.88);font-size:14px;line-height:1.6;">
          Bonjour {_safe(first_name)}, votre compte a bien été créé.
        </p>
      </td></tr>
      <tr><td style="padding:28px 32px 8px;">
        <p style="margin:0 0 16px;font-size:15px;color:{_COLOR_TEXT};line-height:1.7;">
          Kafundo vous aide à repérer les appels, subventions, programmes d'accompagnement et financements utiles pour vos projets en France et en Afrique.
        </p>
        <table width="100%" cellpadding="0" cellspacing="0" style="background:{_COLOR_SURFACE};border:1px solid {_COLOR_BORDER};border-radius:12px;">
          {_key_value_rows([
              ("Connexion", user_email),
              ("Méthode utilisée", method_label),
              ("Première étape", "Compléter votre profil pour recevoir des recommandations plus pertinentes"),
          ])}
        </table>
      </td></tr>
      <tr><td style="padding:20px 32px 8px;">
        <div style="border:1px solid #bfdbfe;background:#eff6ff;border-radius:12px;padding:16px 18px;">
          <p style="margin:0;font-size:14px;color:#1e40af;line-height:1.65;">
            Conseil de démarrage : indiquez vos pays, secteurs et types de financement recherchés. Le catalogue sera ensuite filtré pour prioriser les opportunités les plus actionnables.
          </p>
        </div>
      </td></tr>
      <tr><td style="padding:22px 32px 30px;text-align:center;">
        {_button("Configurer ma veille", _app_url("/onboarding"))}
        <p style="margin:14px 0 0;font-size:12px;color:{_COLOR_MUTED};">
          Vous pourrez modifier ces préférences à tout moment depuis votre profil.
        </p>
      </td></tr>
        """
        return NotificationService.send_email(
            to=user_email,
            subject="Bienvenue sur Kafundo — votre compte est prêt",
            html_body=_email_wrapper(content, preheader="Votre compte Kafundo est prêt à être configuré."),
        )

    @staticmethod
    def notify_admin_new_user(
        user_email: str,
        user_name: str,
        method: str = "email",
    ) -> bool:
        """Notifie l'admin quand un nouvel utilisateur crée un compte."""
        from datetime import datetime
        now = datetime.now().strftime("%d/%m/%Y à %H:%M")
        method_label = "Google OAuth" if method == "google" else "Email / mot de passe"
        html = _email_wrapper(f"""
      <tr><td style="padding:28px 32px 16px;background:linear-gradient(135deg,#0b1f59,#1646c8);text-align:center;">
        <p style="margin:0;font-size:13px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:rgba(255,255,255,0.7);">Kafundo · Admin</p>
        <h1 style="margin:8px 0 0;font-size:22px;font-weight:800;color:white;">Nouveau compte créé</h1>
      </td></tr>
      <tr><td style="padding:28px 32px;">
        <p style="margin:0 0 16px;font-size:14px;color:{_COLOR_MUTED};line-height:1.65;">
          Un utilisateur vient de créer un compte. Pensez à vérifier le profil si c'est un prospect important ou une organisation cliente.
        </p>
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;border-radius:12px;border:1px solid #e2e8f0;">
          {_key_value_rows([
              ("Nom", user_name or "—"),
              ("Email", user_email),
              ("Méthode d'inscription", method_label),
              ("Date", now),
          ])}
        </table>
        <div style="margin-top:24px;text-align:center;">
          {_button("Voir dans l'admin", _app_url("/admin"))}
        </div>
      </td></tr>
        """, preheader=f"Nouvel utilisateur : {user_email}")
        return NotificationService.send_email(
            to=settings.ADMIN_EMAIL,
            subject=f"[Kafundo] Nouvel utilisateur : {user_name or user_email}",
            html_body=html,
        )

    @staticmethod
    def notify_admin_new_subscription(
        user_email: str,
        user_name: str,
        plan: str,
        amount_eur: float | None = None,
    ) -> bool:
        """Notifie l'admin quand un utilisateur souscrit à un plan payant."""
        from datetime import datetime
        now = datetime.now().strftime("%d/%m/%Y à %H:%M")
        amount_str = f"{amount_eur:.0f} €/mois" if amount_eur else "—"
        html = _email_wrapper(f"""
      <tr><td style="padding:28px 32px 12px;background:linear-gradient(135deg,#064e3b,#059669);text-align:center;">
        <p style="margin:0;font-size:13px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:rgba(255,255,255,0.7);">Kafundo · Facturation</p>
        <h1 style="margin:8px 0 0;font-size:22px;font-weight:800;color:white;">💳 Nouvel abonnement</h1>
      </td></tr>
      <tr><td style="padding:28px 32px;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0fdf4;border-radius:12px;border:1px solid #bbf7d0;">
          <tr>
            <td style="padding:14px 20px;border-bottom:1px solid #bbf7d0;">
              <span style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;">Utilisateur</span><br>
              <strong style="font-size:15px;color:#1e293b;">{user_name or user_email}</strong>
            </td>
          </tr>
          <tr>
            <td style="padding:14px 20px;border-bottom:1px solid #bbf7d0;">
              <span style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;">Email</span><br>
              <strong style="font-size:15px;color:#1e293b;">{user_email}</strong>
            </td>
          </tr>
          <tr>
            <td style="padding:14px 20px;border-bottom:1px solid #bbf7d0;">
              <span style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;">Plan souscrit</span><br>
              <strong style="font-size:15px;color:#059669;text-transform:capitalize;">{plan}</strong>
            </td>
          </tr>
          <tr>
            <td style="padding:14px 20px;">
              <span style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:0.05em;">Montant · Date</span><br>
              <strong style="font-size:15px;color:#1e293b;">{amount_str} — {now}</strong>
            </td>
          </tr>
        </table>
        <div style="margin-top:24px;text-align:center;">
          <a href="https://app.kafundo.com/admin" style="display:inline-block;background:#059669;color:white;text-decoration:none;font-weight:700;font-size:14px;padding:12px 28px;border-radius:12px;">
            Voir dans l'admin →
          </a>
        </div>
      </td></tr>
        """, preheader=f"Nouvel abonnement {plan} : {user_email}")
        return NotificationService.send_email(
            to=settings.ADMIN_EMAIL,
            subject=f"[Kafundo] 💳 Abonnement {plan} — {user_name or user_email}",
            html_body=html,
        )

    @staticmethod
    def build_password_reset_email(user_name: str, reset_url: str) -> str:
        first_name = (user_name or "").strip().split(" ")[0] or "bonjour"
        content = f"""
      <tr><td style="padding:30px 32px 20px;background:linear-gradient(135deg,#0f172a,{_COLOR_PRIMARY});">
        <p style="margin:0 0 8px;font-size:12px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:rgba(255,255,255,0.72);">Sécurité Kafundo</p>
        <h1 style="margin:0;color:white;font-size:22px;font-weight:800;">Réinitialisation du mot de passe</h1>
      </td></tr>
      <tr><td style="padding:28px 32px 10px;">
        <p style="margin:0 0 14px;font-size:15px;color:{_COLOR_TEXT};line-height:1.7;">
          Bonjour {_safe(first_name)},
        </p>
        <p style="margin:0 0 18px;font-size:14px;color:{_COLOR_MUTED};line-height:1.7;">
          Nous avons reçu une demande de réinitialisation pour votre compte Kafundo. Le lien ci-dessous est valable pendant 2 heures.
        </p>
        <div style="text-align:center;margin:26px 0;">
          {_button("Choisir un nouveau mot de passe", reset_url)}
        </div>
        <p style="margin:0;font-size:13px;color:{_COLOR_MUTED};line-height:1.65;">
          Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet email. Votre mot de passe actuel restera inchangé.
        </p>
      </td></tr>
        """
        return _email_wrapper(content, preheader="Lien de réinitialisation valable 2 heures.")

    @staticmethod
    def build_organization_invitation_email(
        invite_url: str,
        organization_name: str,
        inviter_name: str,
        role: str,
    ) -> str:
        role_label = {
            "org_admin": "Administrateur",
            "member": "Membre",
            "viewer": "Lecteur",
        }.get(role, role)
        content = f"""
      <tr><td style="padding:30px 32px 20px;background:linear-gradient(135deg,{_COLOR_ACCENT},{_COLOR_PRIMARY});">
        <p style="margin:0 0 8px;font-size:12px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:rgba(255,255,255,0.76);">Invitation équipe</p>
        <h1 style="margin:0;color:white;font-size:22px;font-weight:800;">Rejoignez {_safe(organization_name)} sur Kafundo</h1>
      </td></tr>
      <tr><td style="padding:28px 32px 8px;">
        <p style="margin:0 0 18px;font-size:15px;color:{_COLOR_TEXT};line-height:1.7;">
          {_safe(inviter_name or "Un administrateur")} vous invite à collaborer sur Kafundo pour suivre les opportunités de financement de votre organisation.
        </p>
        <table width="100%" cellpadding="0" cellspacing="0" style="background:{_COLOR_SURFACE};border:1px solid {_COLOR_BORDER};border-radius:12px;">
          {_key_value_rows([
              ("Organisation", organization_name),
              ("Rôle proposé", role_label),
              ("Validité", "Invitation valable 14 jours"),
          ])}
        </table>
        <div style="text-align:center;margin:26px 0 12px;">
          {_button("Accepter l'invitation", invite_url)}
        </div>
        <p style="margin:0;font-size:12px;color:{_COLOR_MUTED};line-height:1.6;text-align:center;">
          Connectez-vous avec cette adresse email avant d'accepter l'invitation.
        </p>
      </td></tr>
        """
        return _email_wrapper(content, preheader=f"Invitation à rejoindre {organization_name} sur Kafundo.")

    @staticmethod
    def smtp_status() -> dict:
        """Vérifie si le SMTP est joignable. Utilisé par l'endpoint de test."""
        if not settings.SMTP_HOST:
            return {"configured": False, "reachable": False, "message": "SMTP_HOST non défini"}
        try:
            with NotificationService._make_connection(timeout=10) as server:
                return {
                    "configured": True,
                    "reachable": True,
                    "host": settings.SMTP_HOST,
                    "port": settings.SMTP_PORT,
                    "ssl": settings.SMTP_PORT == 465,
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
            <h1 style="color:white;margin:0;font-size:20px">Kafundo — Veille : {alert_name}</h1>
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
                Vous recevez cet email car vous avez configuré une veille sur Kafundo.<br>
                <a href="#">Se désabonner</a>
            </p>
        </div>
        </body></html>
        """

    # ─── Alerte nouvelle opportunité ────────────────────────────────────────────

    @staticmethod
    def build_new_opportunity_alert_email(
        user_name: str,
        alert_name: str,
        devices: list,
        total_matched: int = 0,
    ) -> str:
        """
        Email envoyé quand une alerte détecte de nouvelles opportunités.
        Utilise le template partagé (_email_wrapper / _device_row / _device_table).
        """
        count = len(devices)
        total = max(total_matched, count)
        rows = "".join(_device_row(d) for d in devices[:10])
        extra_line = ""
        if total > 10:
            extra_line = (
                f'<p style="margin:12px 0 0;text-align:center;font-size:13px;color:{_COLOR_MUTED};">'
                f"+ {total - 10} autre(s) opportunité(s) correspondent à cette alerte</p>"
            )

        content = f"""
      <tr>
        <td style="padding:32px 32px 20px;background:linear-gradient(135deg,{_COLOR_ACCENT} 0%,{_COLOR_PRIMARY} 100%);">
          <p style="margin:0 0 6px;font-size:11px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:rgba(255,255,255,0.7);">Veille Kafundo</p>
          <h1 style="margin:0 0 8px;color:white;font-size:22px;font-weight:700;line-height:1.3;">
            🔔 {count} nouvelle(s) opportunité(s) détectée(s)
          </h1>
          <p style="margin:0;color:rgba(255,255,255,0.85);font-size:14px;">
            Votre alerte <strong>«&nbsp;{alert_name}&nbsp;»</strong> a trouvé de nouvelles pistes.
          </p>
        </td>
      </tr>
      <tr>
        <td style="padding:28px 32px 8px;">
          <p style="margin:0 0 6px;font-size:15px;color:{_COLOR_TEXT};">
            Bonjour <strong>{user_name}</strong>,
          </p>
          <p style="margin:0 0 20px;font-size:14px;color:{_COLOR_MUTED};line-height:1.65;">
            {total} dispositif(s) correspondent à votre veille <strong>«&nbsp;{alert_name}&nbsp;»</strong>.
            Consultez-les dès maintenant pour ne pas laisser filer les plus pertinents.
          </p>
          {_device_table(rows)}
          {extra_line}
          <div style="margin:28px 0 8px;text-align:center;">
            <a href="https://app.kafundo.com/devices"
               style="display:inline-block;padding:12px 28px;background:{_COLOR_PRIMARY};
                      color:white;font-size:14px;font-weight:600;border-radius:10px;
                      text-decoration:none;letter-spacing:0.02em;">
              Explorer toutes les opportunités →
            </a>
          </div>
        </td>
      </tr>
      <tr>
        <td style="padding:16px 32px 28px;">
          <div style="border-radius:12px;background:{_COLOR_SURFACE};border:1px solid {_COLOR_BORDER};padding:16px 20px;">
            <p style="margin:0;font-size:12px;color:{_COLOR_MUTED};line-height:1.6;">
              💡 <strong>Conseil :</strong> Ajoutez les opportunités les plus prometteuses à votre
              <a href="https://app.kafundo.com/workspace" style="color:{_COLOR_PRIMARY};">pipeline de suivi</a>
              pour ne pas perdre le fil.
            </p>
          </div>
        </td>
      </tr>"""

        return _email_wrapper(
            content,
            preheader=f"{count} nouvelle(s) opportunité(s) détectée(s) — {alert_name}",
        )

    # ─── Digest hebdomadaire ─────────────────────────────────────────────────────

    @staticmethod
    def build_digest_email(
        user_name: str,
        new_devices: list,
        closing_devices: list,
        pipeline_count: int = 0,
    ) -> str:
        """Email digest hebdomadaire : nouvelles opportunités + deadlines à venir."""
        first_name = user_name.split()[0] if user_name else "vous"

        # Section nouvelles opportunités
        new_rows = "".join(_device_row(d) for d in new_devices[:8])
        new_section = ""
        if new_devices:
            new_section = f"""<tr><td style="padding:24px 32px 8px;">
              <h2 style="margin:0 0 4px;font-size:16px;font-weight:700;color:{_COLOR_TEXT};">
                🆕 {len(new_devices)} nouvelle(s) opportunité(s) cette semaine
              </h2>
              <p style="margin:0 0 16px;font-size:14px;color:{_COLOR_MUTED};">
                Passez-les en revue avant qu'elles ne disparaissent du radar.
              </p>
              {_device_table(new_rows)}
            </td></tr>"""

        # Section deadlines proches
        close_rows = "".join(_device_row(d) for d in closing_devices[:5])
        close_section = ""
        if closing_devices:
            close_section = f"""<tr><td style="padding:24px 32px 8px;">
              <h2 style="margin:0 0 4px;font-size:16px;font-weight:700;color:{_COLOR_WARN};">
                ⏰ {len(closing_devices)} deadline(s) dans les 7 prochains jours
              </h2>
              <p style="margin:0 0 16px;font-size:14px;color:{_COLOR_MUTED};">
                Ces opportunités ferment bientôt — vérifiez votre suivi.
              </p>
              {_device_table(close_rows)}
            </td></tr>"""

        empty_msg = "" if (new_devices or closing_devices) else f"""<tr><td style="padding:32px;text-align:center;color:{_COLOR_MUTED};font-size:14px;">
              Aucune nouvelle opportunité ni deadline urgente cette semaine.<br>
              <a href="https://app.kafundo.com/devices" style="color:{_COLOR_PRIMARY};font-weight:600;">Parcourir le catalogue →</a>
            </td></tr>"""

        pipeline_mention = f" · {pipeline_count} opportunité(s) dans ton suivi" if pipeline_count else ""

        content = f"""
          <tr><td style="background:linear-gradient(135deg,{_COLOR_ACCENT},{_COLOR_PRIMARY});padding:28px 32px;">
            <p style="margin:0 0 4px;color:rgba(255,255,255,0.75);font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.1em;">Kafundo — Digest hebdomadaire</p>
            <h1 style="margin:0;color:white;font-size:22px;font-weight:700;">Bonjour {first_name} 👋</h1>
          </td></tr>
          <tr><td style="padding:20px 32px 8px;">
            <p style="margin:0;font-size:15px;color:{_COLOR_TEXT};">
              Voici ce qui s'est passé sur Kafundo cette semaine{pipeline_mention}.
            </p>
          </td></tr>
          {new_section}
          {close_section}
          {empty_msg}
          <tr><td style="padding:20px 32px 28px;text-align:center;">
            <a href="https://app.kafundo.com/workspace" style="display:inline-block;background:{_COLOR_PRIMARY};color:white;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;">
              Voir mon espace de suivi →
            </a>
          </td></tr>
        """
        return _email_wrapper(content, preheader=f"{len(new_devices)} nouvelles opportunités cette semaine")

    # ─── Rappels deadline J-7 ────────────────────────────────────────────────────

    @staticmethod
    def build_deadline_reminder_email(user_name: str, deadline_devices: list) -> str:
        """Email de rappel pour les opportunités dont la clôture est dans 7 jours ou moins."""
        first_name = user_name.split()[0] if user_name else "vous"
        count = len(deadline_devices)
        rows = "".join(_device_row(d) for d in deadline_devices[:10])

        content = f"""
          <tr><td style="background:linear-gradient(135deg,#b45309,{_COLOR_WARN});padding:28px 32px;">
            <p style="margin:0 0 4px;color:rgba(255,255,255,0.75);font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.1em;">Kafundo — Rappel deadline</p>
            <h1 style="margin:0;color:white;font-size:22px;font-weight:700;">⏰ {count} deadline(s) imminente(s)</h1>
          </td></tr>
          <tr><td style="padding:20px 32px 8px;">
            <p style="margin:0 0 4px;font-size:15px;color:{_COLOR_TEXT};">Bonjour {first_name},</p>
            <p style="margin:8px 0 0;font-size:14px;color:{_COLOR_MUTED};">
              {count} opportunité(s) que vous suivez ferment dans les 7 prochains jours.
              Vérifiez votre avancement avant qu'il ne soit trop tard.
            </p>
          </td></tr>
          <tr><td style="padding:8px 32px 8px;">
            {_device_table(rows)}
          </td></tr>
          <tr><td style="padding:20px 32px 28px;text-align:center;">
            <a href="https://app.kafundo.com/workspace" style="display:inline-block;background:{_COLOR_WARN};color:white;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;">
              Vérifier mon suivi →
            </a>
          </td></tr>
        """
        return _email_wrapper(content, preheader=f"Action requise : {count} deadline(s) dans 7 jours")
