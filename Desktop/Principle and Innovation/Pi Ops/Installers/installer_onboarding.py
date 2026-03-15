#!/usr/bin/env python3
"""
Pi Ops – Installer Onboarding Workflow
=======================================
Two-phase workflow. Set WORKFLOW_PHASE in the RUN CONFIGURATION section at the bottom.

  PHASE 1 — "agreement"
    Send the blank Pi Primary Electrical Installation Agreement (HTML) to the installer.
    The installer must complete their details, sign, and return the PDF to Pi FIRST.
    Pi then countersigns and files the fully executed agreement.
    Steps:
      1. Creates the installer compliance folder
      2. Initialises the onboarding log
      3. Emails the agreement HTML attachment with step-by-step completion instructions

  PHASE 2 — "onboarding"
    Run once the signed-and-countersigned agreement is on file.
    Steps:
      1. Confirms / creates installer compliance folder
      2. Writes the full onboarding log with document checklist
      3. Sends the compliance documents request email to the installer

UPLOAD PORTAL:
  Installers receive a link to the Pi-OS upload portal:
    http://localhost:3000/installer-upload?installer=...&company=...&date=...
  (Development: localhost:3000 | Production: replace with live domain once deployed)

INTERIM LOCAL STORAGE:
  A compliance folder is created locally at:
  C:\\Users\\HP\\Desktop\\Principle and Innovation\\Pi Ops\\Installers\\{Company Name}\\
  Files uploaded via the portal are stored in Supabase Storage under:
    installer-documents/{Company Name}/{Category}/

FUTURE:
  - Connect to DocuSign/e-signature webhook for automatic triggering on agreement execution
  - Replace localhost:3000 with production domain once Pi-OS is deployed
  - Integrate with Pi CRM for automated installer profile activation

Usage:
  python installer_onboarding.py
  (Update INSTALLER and SMTP_CONFIG sections at the bottom before running)

Requirements:
  pip install python-dotenv  (optional, for .env file support)
"""

import os
import re
import smtplib
import getpass
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime
from pathlib import Path


# ── CONSTANTS ──────────────────────────────────────────────────────────────────

INSTALLERS_BASE_PATH = Path(r"C:\Users\HP\Desktop\Principle and Innovation\Pi Ops\Installers")

# Upload portal — development uses localhost:3000; swap for production domain when deployed
UPLOAD_PORTAL_BASE = "http://localhost:3000/installer-upload"

# Digital agreement template — attached to Phase 1 email
AGREEMENT_HTML_PATH = (
    INSTALLERS_BASE_PATH / "Pi_Primary_Electrical_Installation_Agreement_DIGITAL.html"
)

PI_EMAIL       = "admin@principleinnovation.tech"
PI_NAME        = "Slade Hata"
PI_COMPANY     = "Pi Ops Pty Ltd"
PI_ABN         = "85 685 996 114"
PI_ADDRESS     = "42 Colches Street, Casino NSW 2470"

# ── DRY RUN ────────────────────────────────────────────────────────────────────
# Set DRY_RUN = True in the RUN CONFIGURATION block below to test without sending
# any real emails. All output files are saved locally for inspection.
DRY_RUN = False

# Agreement URL — when set by app.py the email sends a clickable link instead of an attachment.
# Format: http://localhost:3000/agreement#d=BASE64DATA
AGREEMENT_URL: str | None = None

# Required documents as defined in the Installer Agreement (Clauses 4 & 7)
REQUIRED_DOCUMENTS = [
    {
        "category": "SAA / CEC Accreditation",
        "items": [
            "SAA / CEC Accreditation Certificate – current (shows accreditation number & expiry)",
            "Design Accreditation Certificate – if engaged as designer",
        ],
    },
    {
        "category": "Electrical Licences",
        "items": [
            "Electrical Contractor Licence – certified copy",
            "Electrical Work Licence – certified copy",
            "Any additional trade licences relevant to scope of work",
        ],
    },
    {
        "category": "Insurance – Certificates of Currency",
        "items": [
            "Public Liability Insurance – min. $10M (Certificate of Currency showing policy no., insurer, cover dates)",
            "Workers Compensation / Workplace Cover – Certificate of Currency",
            "Professional Indemnity Insurance – Certificate of Currency (if applicable)",
        ],
    },
    {
        "category": "Company / Business Documentation",
        "items": [
            "ABN / ACN confirmation – ASIC company extract or current ABN lookup printout",
            "Payment bank account details – BSB & Account Number for payment processing",
        ],
    },
]

# Document sub-folder structure created for each installer
DOCUMENT_SUBFOLDERS = [
    "Accreditations",
    "Licences",
    "Insurance",
    "Company Documents",
    "Agreements",
]


# ── UTILITIES ──────────────────────────────────────────────────────────────────

def sanitize_folder_name(name: str) -> str:
    """Strip characters that are invalid in Windows folder names."""
    return re.sub(r'[<>:"/\\|?*]', '', name).strip()


def get_display_name(company_name: str, installer_name: str) -> str:
    return company_name.strip() if company_name and company_name.strip() else installer_name.strip()


# ── STEP 1: CREATE FOLDER STRUCTURE ───────────────────────────────────────────

def create_installer_folder(company_name: str, installer_name: str) -> Path:
    """
    Create the installer's compliance folder under INSTALLERS_BASE_PATH.
    Uses company name if available, otherwise installer's full name.
    Returns the Path to the created folder.
    """
    raw_name = get_display_name(company_name, installer_name)
    folder_name = sanitize_folder_name(raw_name)
    folder_path = INSTALLERS_BASE_PATH / folder_name

    folder_path.mkdir(parents=True, exist_ok=True)
    for subfolder in DOCUMENT_SUBFOLDERS:
        (folder_path / subfolder).mkdir(exist_ok=True)

    print(f"  [OK] Installer folder created: {folder_path}")
    return folder_path


# ── STEP 2: WRITE ONBOARDING LOG ──────────────────────────────────────────────

def write_onboarding_log(folder_path: Path, installer_name: str, company_name: str,
                          installer_email: str, agreement_date: str) -> Path:
    """Write an onboarding log file with document checklist to the installer's folder."""
    log_file = folder_path / "onboarding_log.txt"

    with open(log_file, "w", encoding="utf-8") as f:
        f.write("PI OPS – INSTALLER ONBOARDING LOG\n")
        f.write("=" * 50 + "\n")
        f.write(f"Installer Name    : {installer_name}\n")
        f.write(f"Company Name      : {company_name or 'N/A'}\n")
        f.write(f"Email             : {installer_email}\n")
        f.write(f"Agreement Date    : {agreement_date}\n")
        f.write(f"Onboarding Date   : {datetime.now().strftime('%d %B %Y  %H:%M')}\n")
        f.write(f"Folder Path       : {folder_path}\n")
        f.write("\n" + "=" * 50 + "\n")
        f.write("DOCUMENT CHECKLIST\n")
        f.write("=" * 50 + "\n")
        for category in REQUIRED_DOCUMENTS:
            f.write(f"\n{category['category']}:\n")
            for item in category["items"]:
                f.write(f"  [ ] {item}\n")
        f.write("\n" + "=" * 50 + "\n")
        f.write("Document Receipt Log (update as docs received):\n")
        f.write("Date Received | Document | Notes\n")
        f.write("-" * 50 + "\n")

    print(f"  [OK] Onboarding log written: {log_file}")
    return log_file


# ── STEP 3: BUILD EMAIL HTML ───────────────────────────────────────────────────

def build_checklist_rows() -> str:
    """Build HTML table rows for the document checklist."""
    rows = ""
    for category in REQUIRED_DOCUMENTS:
        rows += f"""
        <tr>
          <td colspan="2" style="padding: 12px 0 4px 0; border-top: 1px solid #e8eaf0;">
            <strong style="color: #1a1a2e; font-size: 13px; text-transform: uppercase;
                           letter-spacing: 0.5px;">{category['category']}</strong>
          </td>
        </tr>"""
        for item in category["items"]:
            rows += f"""
        <tr>
          <td width="24" style="padding: 4px 8px 4px 0; vertical-align: top; color: #4a90d9;
                                 font-size: 16px;">&#9633;</td>
          <td style="padding: 4px 0; font-size: 13px; color: #444; line-height: 1.5;">{item}</td>
        </tr>"""
    return rows


def build_email_html(installer_name: str, company_name: str, upload_instructions: str) -> str:
    """Return a full Pi-branded HTML email."""
    display_name = get_display_name(company_name, installer_name)
    checklist_rows = build_checklist_rows()
    year = datetime.now().year

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Pi Ops – Installer Compliance Documents Required</title></head>
<body style="margin:0;padding:0;background-color:#f0f2f5;font-family:Arial,Helvetica,sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f0f2f5;padding:30px 10px;">
<tr><td align="center">
<table width="620" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:10px;overflow:hidden;
              box-shadow:0 4px 16px rgba(0,0,0,0.10);max-width:100%;">

  <!-- HEADER -->
  <tr>
    <td style="background:#1a1a2e;padding:32px 40px;text-align:center;">
      <h1 style="color:#4a90d9;margin:0;font-size:26px;letter-spacing:3px;font-weight:700;">
        PRINCIPLE AND INNOVATION
      </h1>
      <p style="color:#888;margin:8px 0 0;font-style:italic;font-size:12px;letter-spacing:1px;">
        to seek truth and be true
      </p>
    </td>
  </tr>

  <!-- BANNER -->
  <tr>
    <td style="background:#4a90d9;padding:10px 40px;">
      <p style="color:#fff;margin:0;font-size:13px;letter-spacing:0.5px;text-align:center;">
        INSTALLER ONBOARDING &nbsp;|&nbsp; COMPLIANCE DOCUMENTATION REQUIRED
      </p>
    </td>
  </tr>

  <!-- BODY -->
  <tr>
    <td style="padding:36px 40px;">

      <p style="color:#333;line-height:1.7;margin:0 0 16px;">Dear {installer_name},</p>

      <p style="color:#333;line-height:1.7;margin:0 0 16px;">
        Thank you for executing the <strong>Pi Ops Installer / Designer Services Agreement</strong>.
        We are pleased to welcome <strong>{display_name}</strong> to the Pi Installer Network.
      </p>

      <p style="color:#333;line-height:1.7;margin:0 0 24px;">
        To complete your onboarding and activate your profile — enabling Work Orders to be issued
        to you — please provide the compliance documentation listed below. This is a requirement
        under <strong>Clause 4 (Standards &amp; Compliance)</strong> and
        <strong>Clause 7 (Insurance)</strong> of your Agreement.
        <strong>No Work Orders can be issued until all documentation has been received and
        verified.</strong>
      </p>

      <!-- CHECKLIST BOX -->
      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:#f8f9ff;border:1px solid #dde3f0;border-radius:8px;margin:0 0 24px;">
        <tr>
          <td style="padding:20px 24px;">
            <p style="color:#1a1a2e;margin:0 0 12px;font-size:14px;font-weight:700;">
              Required Documentation Checklist
            </p>
            <table width="100%" cellpadding="0" cellspacing="0">
              {checklist_rows}
            </table>
          </td>
        </tr>
      </table>

      <!-- UPLOAD INSTRUCTIONS -->
      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:#e8f4fd;border-left:4px solid #4a90d9;border-radius:0 8px 8px 0;
                    margin:0 0 24px;">
        <tr>
          <td style="padding:16px 20px;">
            <p style="color:#1a1a2e;margin:0 0 8px;font-size:13px;font-weight:700;
                      text-transform:uppercase;letter-spacing:0.5px;">
              How to Submit Your Documents
            </p>
            <p style="color:#333;margin:0;font-size:13px;line-height:1.7;">
              {upload_instructions}
            </p>
          </td>
        </tr>
      </table>

      <!-- WARNING BOX -->
      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:#fff8e7;border:1px solid #ffd966;border-radius:8px;margin:0 0 24px;">
        <tr>
          <td style="padding:14px 20px;">
            <p style="color:#7a5c00;margin:0;font-size:12.5px;line-height:1.7;">
              <strong>&#9888;&nbsp; Important:</strong> All documents must be current and valid at the
              time of submission. Certificates of Currency must clearly show the insurer name, policy
              number, coverage amount, and cover period. Expired, incomplete, or illegible documents
              will not be accepted and will delay your activation.
            </p>
          </td>
        </tr>
      </table>

      <p style="color:#333;line-height:1.7;margin:0 0 8px;">
        If you have any questions, please contact us at
        <a href="mailto:{PI_EMAIL}" style="color:#4a90d9;">{PI_EMAIL}</a>.
      </p>

      <p style="color:#333;line-height:1.7;margin:24px 0 0;">
        Sincerely,<br>
        <strong>Admin Team &mdash; Principle and Innovation (Pi)</strong><br>
        <a href="mailto:admin@principleinnovation.tech" style="color:#4a90d9;font-size:13px;">admin@principleinnovation.tech</a>
      </p>

    </td>
  </tr>

  <!-- FOOTER -->
  <tr>
    <td style="background:#f0f0f0;padding:18px 40px;text-align:center;
               border-top:1px solid #ddd;">
      <p style="color:#999;font-size:11px;margin:0;line-height:1.6;">
        Pi Ops Pty Ltd &nbsp;|&nbsp; ABN: {PI_ABN} &nbsp;|&nbsp; {PI_ADDRESS}<br>
        This email was generated automatically as part of the Pi Installer onboarding process.
        &copy; {year} Principle and Innovation.
      </p>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def build_plain_text_email(installer_name: str, company_name: str,
                            upload_instructions_plain: str) -> str:
    """Fallback plain-text version of the onboarding email."""
    display_name = get_display_name(company_name, installer_name)
    lines = [
        f"Dear {installer_name},",
        "",
        f"Thank you for executing the Pi Ops Installer / Designer Services Agreement. "
        f"We are pleased to welcome {display_name} to the Pi Installer Network.",
        "",
        "To complete your onboarding, please provide the following compliance documents.",
        "No Work Orders can be issued until all documentation has been received and verified.",
        "",
        "REQUIRED DOCUMENTATION:",
        "-" * 40,
    ]
    for category in REQUIRED_DOCUMENTS:
        lines.append(f"\n{category['category']}:")
        for item in category["items"]:
            lines.append(f"  [ ] {item}")
    lines += [
        "",
        "-" * 40,
        "HOW TO SUBMIT:",
        upload_instructions_plain,
        "",
        "Kind regards,",
        PI_NAME,
        PI_COMPANY,
        PI_EMAIL,
    ]
    return "\n".join(lines)


# ── STEP 4: SEND EMAIL ─────────────────────────────────────────────────────────

def send_onboarding_email(installer_name: str, company_name: str,
                           installer_email: str, agreement_date: str,
                           smtp_config: dict, folder_path: Path) -> bool:
    """
    Send the onboarding email to the installer.
    Saves an HTML draft locally if sending fails.
    Returns True on success, False on failure.
    """
    display_name = get_display_name(company_name, installer_name)
    subject = (
        f"Pi Ops – Action Required: Submit Compliance Documents | {display_name}"
    )

    # Build upload portal URL with installer details as query params
    portal_params = urllib.parse.urlencode({
        "installer": installer_name,
        "company":   company_name or "",
        "date":      agreement_date,
    })
    portal_url = f"{UPLOAD_PORTAL_BASE}?{portal_params}"

    # Upload instructions — portal link is primary; email fallback is secondary
    upload_instructions_html = (
        f"Click the button below to open your secure document upload portal. "
        f"Upload each document in the relevant category. "
        f"All uploads are stored securely and sent directly to Pi Ops for review.<br><br>"
        f"<a href='{portal_url}' "
        f"   style='display:inline-block;background:#4a90d9;color:#fff;font-weight:700;"
        f"          padding:12px 28px;border-radius:8px;text-decoration:none;"
        f"          font-size:14px;letter-spacing:0.5px;margin:8px 0;'>"
        f"  &#8599;&nbsp; Open Document Upload Portal"
        f"</a><br><br>"
        f"<span style='font-size:12px;color:#888;'>"
        f"Link not working? Email documents directly to "
        f"<a href='mailto:{PI_EMAIL}' style='color:#4a90d9;'>{PI_EMAIL}</a> "
        f"with clear file names (e.g. <em>SAA_Certificate.pdf</em>, "
        f"<em>PublicLiability_CoC.pdf</em>)."
        f"</span>"
    )

    upload_instructions_plain = (
        f"Open your document upload portal here:\n  {portal_url}\n\n"
        f"Upload each document in the relevant category.\n\n"
        f"Alternatively, email documents directly to {PI_EMAIL} with clear file names "
        f"(e.g. SAA_Certificate.pdf, PublicLiability_CoC.pdf)."
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{PI_NAME} <{PI_EMAIL}>"
    msg["To"]      = installer_email

    plain_body = build_plain_text_email(installer_name, company_name, upload_instructions_plain)
    html_body  = build_email_html(installer_name, company_name, upload_instructions_html)

    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    draft_path = folder_path / "onboarding_email_DRAFT.html"

    # ── Dry-run: skip SMTP, save all outputs locally ────────────────────────────
    if DRY_RUN:
        with open(draft_path, "w", encoding="utf-8") as f:
            f.write(html_body)
        print(f"  [DRY RUN] No email sent.")
        print(f"  [DRY RUN] Subject  : {subject}")
        print(f"  [DRY RUN] To       : {installer_email}")
        print(f"  [DRY RUN] Draft    : {draft_path}")
        print(f"  [DRY RUN] → Open draft in browser to verify email layout.")
        log_file = folder_path / "onboarding_log.txt"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\nOnboarding DRY RUN : {datetime.now().strftime('%d %B %Y  %H:%M')}\n")
            f.write(f"Would Send To      : {installer_email}\n")
            f.write(f"Draft Saved        : {draft_path}\n")
        return True

    try:
        port = smtp_config["smtp_port"]
        if port == 465:
            import ssl as _ssl
            ctx = _ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode    = _ssl.CERT_NONE
            with smtplib.SMTP_SSL(smtp_config["smtp_host"], port, context=ctx) as server:
                server.login(smtp_config["smtp_user"], smtp_config["smtp_password"])
                server.sendmail(smtp_config["smtp_user"], installer_email, msg.as_string())
        else:
            with smtplib.SMTP(smtp_config["smtp_host"], port) as server:
                server.ehlo()
                server.starttls()
                server.login(smtp_config["smtp_user"], smtp_config["smtp_password"])
                server.sendmail(smtp_config["smtp_user"], installer_email, msg.as_string())

        print(f"  [OK] Onboarding email sent to {installer_email}")

        # Append to log
        log_file = folder_path / "onboarding_log.txt"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\nEmail Sent        : {datetime.now().strftime('%d %B %Y  %H:%M')}\n")
            f.write(f"Email Address     : {installer_email}\n")

        return True

    except Exception as e:
        print(f"  [WARN] Email delivery failed: {e}")
        print(f"         A draft has been saved locally for manual sending.")

        # Save draft for manual sending
        draft_path = folder_path / "onboarding_email_DRAFT.html"
        with open(draft_path, "w", encoding="utf-8") as f:
            draft_upload_text = (
                f"Open your document upload portal here:<br><br>"
                f"<a href='{portal_url}' style='color:#4a90d9;'>{portal_url}</a><br><br>"
                f"<span style='font-size:12px;color:#888;'>Or email documents to "
                f"<a href='mailto:{PI_EMAIL}' style='color:#4a90d9;'>{PI_EMAIL}</a>.</span>"
            )
            f.write(build_email_html(installer_name, company_name, draft_upload_text))

        print(f"  [INFO] Draft saved: {draft_path}")
        print(f"  [INFO] Open in a browser to review, then forward/copy to {installer_email}")

        log_file = folder_path / "onboarding_log.txt"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\nEmail Send FAILED : {datetime.now().strftime('%d %B %Y  %H:%M')}\n")
            f.write(f"Error             : {e}\n")
            f.write(f"Draft Saved To    : {draft_path}\n")

        return False


# ── NOTIFY PI: INSTALLER HAS SIGNED ──────────────────────────────────────────

def send_signed_to_pi(installer_name: str, company_name: str,
                      installer_email: str, abn: str, inst_date: str,
                      signed_html: str, smtp_cfg: dict) -> None:
    """Email Pi with the signed agreement HTML as an attachment for countersigning.
    Called automatically by app.py /submit-agreement when the installer submits."""
    safe_name = re.sub(r'[^a-zA-Z0-9]+', '_', company_name)
    filename  = f"Pi_Agreement_Signed_{safe_name}.html"
    port      = int(smtp_cfg.get("smtp_port", 465))

    msg            = MIMEMultipart("mixed")
    msg["Subject"] = f"Pi \u2013 Installer Agreement Signed | {company_name}"
    msg["From"]    = f"Pi Onboarding <{PI_EMAIL}>"
    msg["To"]      = PI_EMAIL

    body_html = f"""<p style="font-family:Arial,sans-serif;font-size:14px;color:#333;">
        The installer agreement for <strong>{company_name}</strong> has been signed
        and submitted digitally.</p>
      <table style="font-family:Arial,sans-serif;font-size:13px;color:#444;border-collapse:collapse;">
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Installer</td><td>{installer_name}</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Company</td><td>{company_name}</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">ABN</td><td>{abn}</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Installer email</td><td>{installer_email}</td></tr>
        <tr><td style="padding:4px 16px 4px 0;font-weight:bold;">Signed</td><td>{inst_date}</td></tr>
      </table>
      <p style="font-family:Arial,sans-serif;font-size:13px;color:#555;margin-top:16px;">
        Open the attached HTML file in Chrome or Edge, review the agreement,
        draw your countersignature and click <strong>Execute Agreement</strong>.</p>"""

    body_part = MIMEMultipart("alternative")
    body_part.attach(MIMEText(body_html, "html"))
    msg.attach(body_part)

    att = MIMEApplication(signed_html.encode("utf-8"), Name=filename)
    att.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(att)

    import ssl as _ssl
    ctx = _ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode    = _ssl.CERT_NONE
    if port == 465:
        with smtplib.SMTP_SSL(smtp_cfg["smtp_host"], port, context=ctx) as server:
            server.login(smtp_cfg["smtp_user"], smtp_cfg["smtp_password"])
            server.sendmail(PI_EMAIL, [PI_EMAIL], msg.as_string())
    else:
        with smtplib.SMTP(smtp_cfg["smtp_host"], port) as server:
            server.starttls(context=ctx)
            server.login(smtp_cfg["smtp_user"], smtp_cfg["smtp_password"])
            server.sendmail(PI_EMAIL, [PI_EMAIL], msg.as_string())


# ── NOTIFY BOTH: EXECUTED AGREEMENT ──────────────────────────────────────────

def send_executed_to_both(installer_name: str, company_name: str,
                          installer_email: str, ref: str, exec_date: str,
                          executed_html: str, smtp_cfg: dict) -> None:
    """Email the fully executed agreement to the installer and BCC Pi.
    Called by app.py /execute-agreement after Pi countersigns."""
    safe_name = re.sub(r'[^a-zA-Z0-9]+', '_', company_name)
    filename  = f"Pi_Agreement_EXECUTED_{safe_name}.html"
    port      = int(smtp_cfg.get("smtp_port", 465))
    to_email  = installer_email or PI_EMAIL

    msg            = MIMEMultipart("mixed")
    msg["Subject"] = f"Pi \u2013 Fully Executed Installer Agreement | {company_name}"
    msg["From"]    = f"Admin Team \u2014 Principle and Innovation (Pi) <{PI_EMAIL}>"
    msg["To"]      = to_email
    msg["Bcc"]     = PI_EMAIL

    body_html = f"""<p style="font-family:Arial,sans-serif;font-size:14px;color:#333;margin:0 0 16px;">
        Dear {installer_name},</p>
      <p style="font-family:Arial,sans-serif;font-size:14px;color:#333;margin:0 0 16px;">
        Your <strong>Pi Primary Electrical Installation Agreement</strong> has been
        fully executed by both parties. The executed copy is attached for your records.</p>
      <table style="font-family:Arial,sans-serif;font-size:13px;color:#444;border-collapse:collapse;margin:0 0 20px;">
        <tr><td style="padding:4px 20px 4px 0;font-weight:bold;">Company</td><td>{company_name}</td></tr>
        <tr><td style="padding:4px 20px 4px 0;font-weight:bold;">Reference</td><td>{ref}</td></tr>
        <tr><td style="padding:4px 20px 4px 0;font-weight:bold;">Execution Date</td><td>{exec_date}</td></tr>
      </table>
      <p style="font-family:Arial,sans-serif;font-size:13px;color:#555;margin:0 0 24px;">
        Open the attached HTML file in Chrome or Edge to view or print your executed copy.</p>
      <p style="font-family:Arial,sans-serif;font-size:14px;color:#333;margin:0;">
        Sincerely,<br>
        <strong>Admin Team &mdash; Principle and Innovation (Pi)</strong><br>
        <a href="mailto:{PI_EMAIL}" style="color:#0A84FF;">{PI_EMAIL}</a></p>"""

    body_part = MIMEMultipart("alternative")
    body_part.attach(MIMEText(body_html, "html"))
    msg.attach(body_part)

    att = MIMEApplication(executed_html.encode("utf-8"), Name=filename)
    att.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(att)

    import ssl as _ssl
    ctx = _ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode    = _ssl.CERT_NONE
    if port == 465:
        with smtplib.SMTP_SSL(smtp_cfg["smtp_host"], port, context=ctx) as server:
            server.login(smtp_cfg["smtp_user"], smtp_cfg["smtp_password"])
            server.sendmail(PI_EMAIL, [to_email, PI_EMAIL], msg.as_string())
    else:
        with smtplib.SMTP(smtp_cfg["smtp_host"], port) as server:
            server.starttls(context=ctx)
            server.login(smtp_cfg["smtp_user"], smtp_cfg["smtp_password"])
            server.sendmail(PI_EMAIL, [to_email, PI_EMAIL], msg.as_string())


# ── STEP 0: AGREEMENT EMAIL (PHASE 1) ─────────────────────────────────────────

def build_agreement_email_html(installer_name: str, company_name: str,
                               agreement_url: str = None) -> str:
    """Branded HTML email delivering the agreement to the installer.

    When agreement_url is supplied the email contains a clickable link button.
    When it is None a plain instruction set is shown (attachment workflow).
    """
    display_name = get_display_name(company_name, installer_name)
    year = datetime.now().year

    if agreement_url:
        action_block = f"""
      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:#f8f9ff;border:1px solid #dde3f0;border-radius:8px;margin:0 0 24px;">
        <tr>
          <td style="padding:24px;">
            <p style="color:#0D1B2A;margin:0 0 18px;font-size:14px;font-weight:700;">
              Your agreement is ready — click the button below to open and sign it online:
            </p>
            <table cellpadding="0" cellspacing="0" style="margin:0 0 22px;">
              <tr>
                <td style="background:#0A84FF;border-radius:8px;text-align:center;
                           padding:14px 32px;">
                  <a href="{agreement_url}"
                     style="color:#fff;text-decoration:none;font-size:15px;
                            font-weight:700;letter-spacing:0.3px;">
                    Open &amp; Sign Agreement &nbsp;&#8594;
                  </a>
                </td>
              </tr>
            </table>
            <p style="color:#0D1B2A;margin:0 0 12px;font-size:13px;font-weight:700;">
              Once the link is open:
            </p>
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="width:34px;vertical-align:top;padding:0 10px 14px 0;">
                  <table width="24" cellpadding="0" cellspacing="0" border="0"><tr><td width="24" height="24" style="width:24px;height:24px;background:#0A84FF;border-radius:12px;color:#fff;font-family:Arial,Helvetica,sans-serif;font-size:12px;font-weight:bold;line-height:24px;text-align:center;padding:0;">1</td></tr></table>
                </td>
                <td style="padding:0 0 14px;font-size:13px;color:#444;line-height:1.6;">
                  <strong>Complete your details</strong> — Business Name, ABN, Responsible
                  Individual, Primary Contact, Address, Phone, and Email.
                </td>
              </tr>
              <tr>
                <td style="width:34px;vertical-align:top;padding:0 10px 14px 0;">
                  <table width="24" cellpadding="0" cellspacing="0" border="0"><tr><td width="24" height="24" style="width:24px;height:24px;background:#0A84FF;border-radius:12px;color:#fff;font-family:Arial,Helvetica,sans-serif;font-size:12px;font-weight:bold;line-height:24px;text-align:center;padding:0;">2</td></tr></table>
                </td>
                <td style="padding:0 0 14px;font-size:13px;color:#444;line-height:1.6;">
                  <strong>Select your hardware delivery preference</strong> and
                  add any relevant details.
                </td>
              </tr>
              <tr>
                <td style="width:34px;vertical-align:top;padding:0 10px 14px 0;">
                  <table width="24" cellpadding="0" cellspacing="0" border="0"><tr><td width="24" height="24" style="width:24px;height:24px;background:#0A84FF;border-radius:12px;color:#fff;font-family:Arial,Helvetica,sans-serif;font-size:12px;font-weight:bold;line-height:24px;text-align:center;padding:0;">3</td></tr></table>
                </td>
                <td style="padding:0 0 14px;font-size:13px;color:#444;line-height:1.6;">
                  <strong>Draw your signature</strong> and enter your full name,
                  position, and today's date.
                </td>
              </tr>
              <tr>
                <td style="width:34px;vertical-align:top;padding:0 10px 14px 0;">
                  <table width="24" cellpadding="0" cellspacing="0" border="0"><tr><td width="24" height="24" style="width:24px;height:24px;background:#0A84FF;border-radius:12px;color:#fff;font-family:Arial,Helvetica,sans-serif;font-size:12px;font-weight:bold;line-height:24px;text-align:center;padding:0;">4</td></tr></table>
                </td>
                <td style="padding:0 0 14px;font-size:13px;color:#444;line-height:1.6;">
                  <strong>Tick the agreement checkbox</strong> and click
                  <strong>Submit to Pi for Countersigning</strong>.
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>"""
    else:
        action_block = """
      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:#f8f9ff;border:1px solid #dde3f0;border-radius:8px;margin:0 0 24px;">
        <tr>
          <td style="padding:20px 24px;">
            <p style="color:#0D1B2A;margin:0 0 16px;font-size:14px;font-weight:700;">
              Complete these steps in order:
            </p>
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="width:34px;vertical-align:top;padding:0 10px 14px 0;">
                  <table width="24" cellpadding="0" cellspacing="0" border="0"><tr><td width="24" height="24" style="width:24px;height:24px;background:#0A84FF;border-radius:12px;color:#fff;font-family:Arial,Helvetica,sans-serif;font-size:12px;font-weight:bold;line-height:24px;text-align:center;padding:0;">1</td></tr></table>
                </td>
                <td style="padding:0 0 14px;font-size:13px;color:#444;line-height:1.6;">
                  <strong>Open the attached file</strong> in Chrome or Edge.
                </td>
              </tr>
              <tr>
                <td style="width:34px;vertical-align:top;padding:0 10px 14px 0;">
                  <table width="24" cellpadding="0" cellspacing="0" border="0"><tr><td width="24" height="24" style="width:24px;height:24px;background:#0A84FF;border-radius:12px;color:#fff;font-family:Arial,Helvetica,sans-serif;font-size:12px;font-weight:bold;line-height:24px;text-align:center;padding:0;">2</td></tr></table>
                </td>
                <td style="padding:0 0 14px;font-size:13px;color:#444;line-height:1.6;">
                  <strong>Complete your details</strong> — Business Name, ABN, Responsible
                  Individual, Primary Contact, Address, Phone, and Email.
                </td>
              </tr>
              <tr>
                <td style="width:34px;vertical-align:top;padding:0 10px 14px 0;">
                  <table width="24" cellpadding="0" cellspacing="0" border="0"><tr><td width="24" height="24" style="width:24px;height:24px;background:#0A84FF;border-radius:12px;color:#fff;font-family:Arial,Helvetica,sans-serif;font-size:12px;font-weight:bold;line-height:24px;text-align:center;padding:0;">3</td></tr></table>
                </td>
                <td style="padding:0 0 14px;font-size:13px;color:#444;line-height:1.6;">
                  <strong>Select your hardware delivery preference</strong>.
                </td>
              </tr>
              <tr>
                <td style="width:34px;vertical-align:top;padding:0 10px 14px 0;">
                  <table width="24" cellpadding="0" cellspacing="0" border="0"><tr><td width="24" height="24" style="width:24px;height:24px;background:#0A84FF;border-radius:12px;color:#fff;font-family:Arial,Helvetica,sans-serif;font-size:12px;font-weight:bold;line-height:24px;text-align:center;padding:0;">4</td></tr></table>
                </td>
                <td style="padding:0 0 14px;font-size:13px;color:#444;line-height:1.6;">
                  <strong>Draw your signature</strong>, enter your name, position, and today's date.
                </td>
              </tr>
              <tr>
                <td style="width:34px;vertical-align:top;padding:0 10px 0 0;">
                  <table width="24" cellpadding="0" cellspacing="0" border="0"><tr><td width="24" height="24" style="width:24px;height:24px;background:#0A84FF;border-radius:12px;color:#fff;font-family:Arial,Helvetica,sans-serif;font-size:12px;font-weight:bold;line-height:24px;text-align:center;padding:0;">5</td></tr></table>
                </td>
                <td style="padding:0;font-size:13px;color:#444;line-height:1.6;">
                  <strong>Tick the checkbox</strong> and click <strong>Submit to Pi for Countersigning</strong>.
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Pi Ops – Agreement for Review and Signature</title></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f2f5;padding:30px 10px;">
<tr><td align="center">
<table width="620" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:10px;overflow:hidden;
              box-shadow:0 4px 16px rgba(0,0,0,0.10);max-width:100%;">

  <tr>
    <td style="background:#0D1B2A;padding:32px 40px;text-align:center;">
      <h1 style="color:#0A84FF;margin:0;font-size:26px;letter-spacing:3px;font-weight:700;">
        PRINCIPLE AND INNOVATION
      </h1>
      <p style="color:#888;margin:8px 0 0;font-style:italic;font-size:12px;letter-spacing:1px;">
        to seek truth and be true
      </p>
    </td>
  </tr>

  <tr>
    <td style="background:#0A84FF;padding:10px 40px;">
      <p style="color:#fff;margin:0;font-size:13px;letter-spacing:0.5px;text-align:center;">
        PRIMARY ELECTRICAL INSTALLATION AGREEMENT &nbsp;|&nbsp; ACTION REQUIRED
      </p>
    </td>
  </tr>

  <tr>
    <td style="padding:36px 40px;">

      <p style="color:#333;line-height:1.7;margin:0 0 16px;">Dear {installer_name},</p>
      <p style="color:#333;line-height:1.7;margin:0 0 20px;">
        Please review and sign the <strong>Pi – Primary Electrical Installation Agreement</strong>
        for <strong>{display_name}</strong>. This agreement governs your engagement as an
        independent installer within the Pi network.
      </p>
{action_block}

      <table width="100%" cellpadding="0" cellspacing="0"
             style="background:#fff8e7;border:1px solid #ffd966;border-radius:8px;margin:0 0 24px;">
        <tr>
          <td style="padding:14px 20px;">
            <p style="color:#7a5c00;margin:0;font-size:12.5px;line-height:1.7;">
              <strong>&#9888;&nbsp; Important:</strong> Please complete all fields and
              draw your signature before submitting. Your work allocation will be
              activated once the fully executed agreement is on file.
            </p>
          </td>
        </tr>
      </table>

      <p style="color:#333;line-height:1.7;margin:0 0 8px;">
        Questions? Contact us at
        <a href="mailto:{PI_EMAIL}" style="color:#0A84FF;">{PI_EMAIL}</a>.
      </p>
      <p style="color:#333;line-height:1.7;margin:24px 0 0;">
        Sincerely,<br>
        <strong>Admin Team &mdash; Principle and Innovation (Pi)</strong><br>
        <a href="mailto:admin@principleinnovation.tech"
           style="color:#0A84FF;font-size:13px;">admin@principleinnovation.tech</a>
      </p>

    </td>
  </tr>

  <tr>
    <td style="background:#f0f0f0;padding:18px 40px;text-align:center;
               border-top:1px solid #ddd;">
      <p style="color:#999;font-size:11px;margin:0;line-height:1.6;">
        Pi Ops Pty Ltd &nbsp;|&nbsp; ABN: {PI_ABN} &nbsp;|&nbsp; {PI_ADDRESS}<br>
        &copy; {year} Principle and Innovation. Generated automatically.
      </p>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def build_agreement_plain_email(installer_name: str, company_name: str,
                                agreement_url: str = None) -> str:
    """Plain-text fallback for the agreement delivery email."""
    display_name = get_display_name(company_name, installer_name)
    if agreement_url:
        steps = [
            "TO SIGN YOUR AGREEMENT:",
            f"1. Click the link below to open the agreement in your browser:",
            f"   {agreement_url}",
            "2. Complete your business details.",
            "3. Select your hardware delivery preference.",
            "4. Draw your signature and enter your name, position, and today's date.",
            "5. Tick the checkbox and click 'Submit to Pi for Countersigning'.",
        ]
        intro = (f"Your Pi Primary Electrical Installation Agreement for {display_name} "
                 f"is ready to sign online.")
    else:
        steps = [
            "STEPS TO COMPLETE:",
            "1. Open the attached .html file in Chrome or Edge.",
            "2. Fill in your business details.",
            "3. Select your preferred hardware delivery option.",
            "4. Draw your signature, enter your name, position, and today's date.",
            "5. Tick the checkbox and click 'Submit to Pi for Countersigning'.",
        ]
        intro = (f"Please find attached the Pi Primary Electrical Installation Agreement "
                 f"for {display_name}.")
    return "\n".join([
        f"Dear {installer_name},",
        "",
        intro,
        "",
        *steps,
        "",
        "IMPORTANT: Please complete all fields and draw your signature before submitting.",
        "Your work allocation is activated once the fully executed agreement is on file.",
        "",
        f"Questions? Contact us at {PI_EMAIL}.",
        "",
        "Kind regards,",
        PI_NAME,
        PI_COMPANY,
        PI_EMAIL,
    ])


def send_agreement_to_installer(installer_name: str, company_name: str,
                                 installer_email: str, smtp_config: dict,
                                 folder_path: Path) -> bool:
    """
    Email the blank digital agreement HTML to the installer for completion and signature.
    Installer must sign and return the PDF before Pi countersigns.
    Saves a draft locally if sending fails.
    Returns True on success, False on failure.
    """
    display_name  = get_display_name(company_name, installer_name)
    subject       = f"Pi Ops – Agreement for Review & Signature | {display_name}"
    log_file      = folder_path / "onboarding_log.txt"
    draft_path    = folder_path / "agreement_email_DRAFT.html"
    url           = AGREEMENT_URL   # None → attach file;  set → send link

    if url:
        print(f"  [INFO] Mode       : LINK  (installer clicks link to open agreement)")
        print(f"  [INFO] Link       : {url}")
    else:
        print(f"  [INFO] Mode       : ATTACHMENT  (AGREEMENT_URL not set — attaching HTML file)")

    # ── Dry-run: no SMTP ─────────────────────────────────────────────────────────
    if DRY_RUN:
        with open(draft_path, "w", encoding="utf-8") as f:
            f.write(build_agreement_email_html(installer_name, company_name, url))
        print(f"  [DRY RUN] No email sent.")
        print(f"  [DRY RUN] Subject  : {subject}")
        print(f"  [DRY RUN] To       : {installer_email}")
        if url:
            print(f"  [DRY RUN] Link     : {url}")
        else:
            print(f"  [DRY RUN] Attach   : {AGREEMENT_HTML_PATH.name}  (not read in DRY RUN)")
        print(f"  [DRY RUN] Draft    : {draft_path}")
        print(f"  [DRY RUN] → Open draft in browser to verify email layout.")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\nAgreement DRY RUN : {datetime.now().strftime('%d %B %Y  %H:%M')}\n")
            f.write(f"Would Send To     : {installer_email}\n")
            f.write(f"Draft Saved       : {draft_path}\n")
        return True

    # ── Live mode: build message ─────────────────────────────────────────────────
    if url:
        # Link mode — no attachment
        msg = MIMEMultipart("alternative")
    else:
        # Attachment mode — verify file exists first
        if not AGREEMENT_HTML_PATH.exists():
            print(f"  [ERROR] Agreement HTML not found at: {AGREEMENT_HTML_PATH}")
            return False
        msg = MIMEMultipart("mixed")

    msg["Subject"] = subject
    msg["From"]    = f"{PI_NAME} <{PI_EMAIL}>"
    msg["To"]      = installer_email

    # Body (plain + HTML)
    body_part = MIMEMultipart("alternative")
    body_part.attach(MIMEText(
        build_agreement_plain_email(installer_name, company_name, url), "plain"
    ))
    body_part.attach(MIMEText(
        build_agreement_email_html(installer_name, company_name, url), "html"
    ))
    if url:
        # Link mode: attach body directly (msg is already alternative)
        msg.attach(body_part.get_payload(0))
        msg.attach(body_part.get_payload(1))
    else:
        msg.attach(body_part)
        # Attachment mode: attach the HTML file
        with open(AGREEMENT_HTML_PATH, "rb") as f:
            att = MIMEApplication(f.read(), _subtype="octet-stream")
            att.add_header(
                "Content-Disposition", "attachment",
                filename="Pi_Primary_Electrical_Installation_Agreement.html",
            )
        msg.attach(att)

    try:
        port = smtp_config["smtp_port"]
        if port == 465:
            import ssl as _ssl
            ctx = _ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode    = _ssl.CERT_NONE
            with smtplib.SMTP_SSL(smtp_config["smtp_host"], port, context=ctx) as server:
                server.login(smtp_config["smtp_user"], smtp_config["smtp_password"])
                server.sendmail(smtp_config["smtp_user"], installer_email, msg.as_string())
        else:
            with smtplib.SMTP(smtp_config["smtp_host"], port) as server:
                server.ehlo()
                server.starttls()
                server.login(smtp_config["smtp_user"], smtp_config["smtp_password"])
                server.sendmail(smtp_config["smtp_user"], installer_email, msg.as_string())

        print(f"  [OK] Agreement emailed to {installer_email}")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\nAgreement Sent    : {datetime.now().strftime('%d %B %Y  %H:%M')}\n")
            f.write(f"Sent To           : {installer_email}\n")
            f.write(f"Status            : Agreement sent — awaiting digital completion\n")
            f.write(f"Next Step         : Installer completes and signs digitally in the form\n")
        return True

    except Exception as e:
        print(f"  [ERROR] Email delivery failed: {e}")
        with open(draft_path, "w", encoding="utf-8") as f:
            f.write(build_agreement_email_html(installer_name, company_name))
        print(f"  [INFO] Email draft saved : {draft_path}")
        print(f"  [INFO] Manually attach   : {AGREEMENT_HTML_PATH}")
        print(f"  [INFO] Forward draft to  : {installer_email}")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\nAgreement Send FAILED : {datetime.now().strftime('%d %B %Y  %H:%M')}\n")
            f.write(f"Error                 : {e}\n")
            f.write(f"Draft Saved           : {draft_path}\n")
            f.write(f"Action Required       : Manually attach agreement HTML and send to "
                    f"{installer_email}\n")
        return False


def run_agreement_phase(installer_name: str, company_name: str,
                        installer_email: str, smtp_config: dict) -> Path:
    """
    Phase 1 of 2 — Create the installer folder and send the blank agreement to the
    installer for completion and signature. Installer signs first; Pi countersigns on return.

    After the fully executed agreement is on file, run Phase 2 by setting:
        WORKFLOW_PHASE = "onboarding"
    """
    display_name = get_display_name(company_name, installer_name)

    print()
    print("=" * 62)
    print("  PI OPS – SEND AGREEMENT  (Phase 1 of 2)")
    print("=" * 62)
    print(f"  Installer : {installer_name}")
    print(f"  Company   : {company_name or '(sole trader)'}")
    print(f"  Email     : {installer_email}")
    print("=" * 62)

    # Step 1 – Create folder
    print("\n[Step 1/2]  Creating installer folder...")
    folder_path = create_installer_folder(company_name, installer_name)

    # Initialise log (only if it doesn't already exist)
    log_file = folder_path / "onboarding_log.txt"
    if not log_file.exists():
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("PI OPS – INSTALLER ONBOARDING LOG\n")
            f.write("=" * 50 + "\n")
            f.write(f"Installer Name    : {installer_name}\n")
            f.write(f"Company Name      : {company_name or 'N/A'}\n")
            f.write(f"Email             : {installer_email}\n")
            f.write(f"Initiated         : {datetime.now().strftime('%d %B %Y  %H:%M')}\n")
            f.write(f"Folder Path       : {folder_path}\n")
            f.write(f"Status            : Agreement sent — awaiting digital completion\n")
            f.write("\n" + "=" * 50 + "\n")
        print(f"  [OK] Log initialised: {log_file}")

    # Step 2 – Send agreement
    print(f"\n[Step 2/2]  Sending agreement to installer ({installer_email})...")
    email_ok = send_agreement_to_installer(
        installer_name, company_name, installer_email, smtp_config, folder_path
    )

    print()
    print("=" * 62)
    if email_ok:
        print("  PHASE 1 COMPLETE  ✓  Agreement sent to installer")
        print()
        print("  NEXT STEPS:")
        print(f"  1. Installer clicks the link in the email to open the agreement")
        print(f"  2. Installer completes their details and draws their digital signature")
        print(f"  3. Installer clicks 'Submit to Pi for Countersigning'")
        print(f"  4. Pi countersigns — both parties receive the executed copy")
        print(f"  5. Select Phase 2 in the form and run again")
    else:
        print("  PHASE 1 — EMAIL FAILED")
        print(f"  Manually attach {AGREEMENT_HTML_PATH.name}")
        print(f"  and send to: {installer_email}")
    print(f"  Folder: {folder_path}")
    print("=" * 62)
    print()

    return email_ok


# ── MAIN ORCHESTRATOR ──────────────────────────────────────────────────────────

def run_onboarding(installer_name: str, company_name: str, installer_email: str,
                   agreement_date: str, smtp_config: dict) -> Path:
    """
    Execute the full onboarding workflow for a newly signed installer.

    Args:
        installer_name  : Director / responsible person name
        company_name    : Company name (or empty string if sole trader)
        installer_email : Installer's email address for notification
        agreement_date  : Date the agreement was executed (display string)
        smtp_config     : Dict with smtp_host, smtp_port, smtp_user, smtp_password

    Returns:
        Path to the created installer folder.
    """
    display_name = get_display_name(company_name, installer_name)

    print()
    print("=" * 62)
    print("  PI OPS – INSTALLER ONBOARDING WORKFLOW")
    print("=" * 62)
    print(f"  Installer      : {installer_name}")
    print(f"  Company        : {company_name or '(sole trader)'}")
    print(f"  Email          : {installer_email}")
    print(f"  Agreement Date : {agreement_date}")
    print(f"  Display Name   : {display_name}")
    print("=" * 62)

    # Step 1 – Create folder
    print("\n[Step 1/3]  Creating installer compliance folder...")
    folder_path = create_installer_folder(company_name, installer_name)

    # Step 2 – Write onboarding log
    print("\n[Step 2/3]  Writing onboarding log...")
    write_onboarding_log(folder_path, installer_name, company_name,
                         installer_email, agreement_date)

    # Step 3 – Send email
    print(f"\n[Step 3/3]  Sending onboarding email to installer...")
    email_ok = send_onboarding_email(
        installer_name, company_name, installer_email, agreement_date, smtp_config, folder_path
    )

    print()
    print("=" * 62)
    if email_ok:
        print("  ONBOARDING COMPLETE  ✓")
    else:
        print("  ONBOARDING COMPLETE (email draft saved – manual send required)")
    print(f"  Folder: {folder_path}")
    print("=" * 62)
    print()

    return email_ok


# ── RUN CONFIGURATION ──────────────────────────────────────────────────────────
# Update the values below before running.

if __name__ == "__main__":
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
    import threading
    import sys

    # ── Thread-safe stdout → GUI log widget ──────────────────────────────────────

    class _LogRedirect:
        """Sends print() output to the GUI log widget (thread-safe via after())."""
        def __init__(self, root: tk.Tk, widget):
            self._root   = root
            self._widget = widget

        def write(self, s: str):
            self._root.after(0, lambda: self._append(s))

        def _append(self, s: str):
            self._widget.configure(state="normal")
            self._widget.insert("end", s)
            self._widget.see("end")
            self._widget.configure(state="disabled")

        def flush(self):
            pass

    # ── Main GUI ─────────────────────────────────────────────────────────────────

    class App:

        # Mail provider presets  {display name: (host, port) or None for custom}
        _MAIL = {
            "Principle Innovation (.tech)"   : ("mail.principleinnovation.tech", 465),
            "Gmail  (smtp.gmail.com)"        : ("smtp.gmail.com",     587),
            "Outlook / Microsoft 365"        : ("smtp.office365.com", 587),
            "Zoho Mail  (smtp.zoho.com.au)"  : ("smtp.zoho.com.au",   465),
            "Custom SMTP…"                   : None,
        }

        # Colour palette
        _NAV  = "#1a1a2e"
        _BLUE = "#4a90d9"
        _GRN  = "#27ae60"
        _BG   = "#f0f2f5"
        _CARD = "#ffffff"
        _DIM  = "#aaaaaa"

        def __init__(self, root: tk.Tk):
            self.root = root
            root.title("Pi Ops – Installer Onboarding")
            root.configure(bg=self._BG)
            root.resizable(True, True)
            root.minsize(560, 480)
            self._build()
            root.update_idletasks()
            # Size: 640px wide, up to 90% of screen height
            w  = 640
            sh = root.winfo_screenheight()
            h  = min(root.winfo_reqheight(), int(sh * 0.90))
            x  = (root.winfo_screenwidth()  - w) // 2
            y  = max(0, (sh - h) // 2)
            root.geometry(f"{w}x{h}+{x}+{y}")

        # ── Build all widgets ─────────────────────────────────────────────────────

        def _build(self):

            # Header bar
            hdr = tk.Frame(self.root, bg=self._NAV, pady=16)
            hdr.pack(fill="x")
            tk.Label(hdr, text="PI OPS  —  INSTALLER ONBOARDING",
                     bg=self._NAV, fg=self._BLUE,
                     font=("Segoe UI", 13, "bold")).pack()
            tk.Label(hdr, text="Principle and Innovation",
                     bg=self._NAV, fg="#888",
                     font=("Segoe UI", 9, "italic")).pack()

            # ── Scrollable body ───────────────────────────────────────────────
            _outer = tk.Frame(self.root, bg=self._BG)
            _outer.pack(fill="both", expand=True)

            _vsb    = ttk.Scrollbar(_outer, orient="vertical")
            _canvas = tk.Canvas(_outer, bg=self._BG, highlightthickness=0,
                                yscrollcommand=_vsb.set)
            _vsb.configure(command=_canvas.yview)
            _vsb.pack(side="right", fill="y")
            _canvas.pack(side="left", fill="both", expand=True)

            body = tk.Frame(_canvas, bg=self._BG, padx=20, pady=16)
            _cwin = _canvas.create_window((0, 0), window=body, anchor="nw")

            def _on_body_resize(e=None):
                _canvas.configure(scrollregion=_canvas.bbox("all"))

            def _on_canvas_resize(e):
                _canvas.itemconfig(_cwin, width=e.width)

            def _on_mousewheel(e):
                _canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

            body.bind("<Configure>", _on_body_resize)
            _canvas.bind("<Configure>", _on_canvas_resize)
            _canvas.bind_all("<MouseWheel>", _on_mousewheel)

            # ── STEP 1 — Workflow Phase ───────────────────────────────────────────
            self._section(body, "STEP 1  —  WORKFLOW PHASE")
            pc = self._card(body)
            self.phase_var = tk.StringVar(value="agreement")
            for val, title, desc in (
                ("agreement",
                 "Phase 1 – Send Agreement",
                 "    Send the blank agreement to the installer for signature.  "
                 "Run this first."),
                ("onboarding",
                 "Phase 2 – Request Compliance Documents",
                 "    Run after the signed and countersigned agreement is on file."),
            ):
                tk.Radiobutton(
                    pc, text=title,
                    variable=self.phase_var, value=val,
                    command=self._on_phase,
                    bg=self._CARD, fg=self._NAV,
                    font=("Segoe UI", 10, "bold"),
                    activebackground=self._CARD,
                ).pack(anchor="w", pady=(4, 0))
                tk.Label(pc, text=desc,
                         bg=self._CARD, fg="#666",
                         font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 4))

            # ── STEP 2 — Installer Details ────────────────────────────────────────
            self._section(body, "STEP 2  —  INSTALLER DETAILS")
            dc = self._card(body)

            self.name_var    = tk.StringVar()
            self.company_var = tk.StringVar()
            self.email_var   = tk.StringVar()
            self.date_var    = tk.StringVar()

            self._field(dc, "Installer Name *",
                        self.name_var,
                        "Full name of the responsible individual  (e.g.  John Smith)")
            self._field(dc, "Company / Trading Name",
                        self.company_var,
                        "Leave blank if sole trader")
            self._field(dc, "Installer Email *",
                        self.email_var,
                        "Email address to send the agreement or compliance documents to")

            # Agreement date — enabled only for Phase 2
            self.date_lbl, self.date_ent, self.date_hlbl = self._field(
                dc,
                "Agreement Execution Date",
                self.date_var,
                "e.g.  12 March 2026   —   required for Phase 2 only",
                return_all=True,
            )
            self._on_phase()   # set initial greyed-out state

            # ── STEP 3 — Email Settings ───────────────────────────────────────────
            self._section(body, "STEP 3  —  EMAIL SETTINGS")
            ec = self._card(body)

            tk.Label(ec, text="Mail Provider  (click the arrow to change)",
                     bg=self._CARD, fg="#333",
                     font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 4))
            self.provider_var = tk.StringVar(value="Principle Innovation (.tech)")
            prov_cb = ttk.Combobox(
                ec, textvariable=self.provider_var,
                values=list(self._MAIL.keys()),
                state="normal", width=46,
                font=("Segoe UI", 10),
            )
            prov_cb.pack(anchor="w")
            prov_cb.set("Principle Innovation (.tech)")
            prov_cb.bind("<<ComboboxSelected>>", self._on_provider)
            tk.Label(
                ec,
                text="\u2713  Principle Innovation, Gmail, and Outlook are pre-configured.",
                bg=self._CARD, fg=self._GRN,
                font=("Segoe UI", 9),
            ).pack(anchor="w", pady=(4, 0))

            # Custom SMTP fields (hidden unless "Custom SMTP…" is chosen)
            self.smtp_host_var = tk.StringVar()
            self.smtp_port_var = tk.StringVar(value="587")
            self.custom_frame  = tk.Frame(ec, bg=self._CARD)
            self._field(self.custom_frame, "SMTP Host *",
                        self.smtp_host_var, "e.g.  mail.yourdomain.com")
            self._field(self.custom_frame, "SMTP Port",
                        self.smtp_port_var, "Usually 587 (TLS) or 465 (SSL)")
            self._on_provider()   # hide custom frame (not needed for preset providers)

            tk.Label(
                ec,
                text="Gmail: use an App Password — not your normal login password.\n"
                     "Google Account  →  Security  →  2-Step Verification  →  App Passwords.",
                bg=self._CARD, fg="#888",
                font=("Segoe UI", 8), justify="left",
            ).pack(anchor="w", pady=(8, 0))

            # ── Action buttons ────────────────────────────────────────────────────
            bf = tk.Frame(body, bg=self._BG)
            bf.pack(fill="x", pady=(10, 12))

            self.test_btn = tk.Button(
                bf, text="  Test Run  (no email sent)  ",
                command=self._test,
                bg=self._BLUE, fg="white",
                font=("Segoe UI", 10, "bold"),
                relief="flat", padx=16, pady=10, cursor="hand2",
                activebackground="#357abd", activeforeground="white",
            )
            self.test_btn.pack(side="left", padx=(0, 10))

            self.send_btn = tk.Button(
                bf, text="  Send Real Email  ",
                command=self._send,
                bg=self._GRN, fg="white",
                font=("Segoe UI", 10, "bold"),
                relief="flat", padx=16, pady=10, cursor="hand2",
                activebackground="#1e8449", activeforeground="white",
            )
            self.send_btn.pack(side="left")

            tk.Button(
                bf, text="Clear Log",
                command=self._clear_log,
                bg="#e0e0e0", fg="#555",
                font=("Segoe UI", 9),
                relief="flat", padx=12, pady=10, cursor="hand2",
            ).pack(side="right")

            # ── Output log ────────────────────────────────────────────────────────
            self._section(body, "OUTPUT LOG")
            self.log = scrolledtext.ScrolledText(
                body, height=13,
                font=("Consolas", 9),
                bg=self._NAV, fg="#d0d0d0",
                relief="flat", state="disabled", wrap="word",
            )
            self.log.pack(fill="both", expand=True)
            self._log_write(
                "  Ready.\n\n"
                "  Fill in the installer details above, then click a button:\n\n"
                "  Test Run      — checks everything works without sending any email\n"
                "  Send Email    — sends the real email (you will be asked for your password)\n"
            )

        # ── Widget helpers ────────────────────────────────────────────────────────

        def _section(self, parent, text: str):
            tk.Label(parent, text=text,
                     bg=self._BG, fg=self._NAV,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(10, 3))

        def _card(self, parent) -> tk.Frame:
            f = tk.Frame(parent, bg=self._CARD,
                         highlightbackground="#dde3f0",
                         highlightthickness=1,
                         padx=16, pady=12)
            f.pack(fill="x", pady=(0, 4))
            return f

        def _field(self, parent, label: str, var: tk.StringVar,
                   hint: str = "", return_all: bool = False):
            lbl = tk.Label(parent, text=label,
                           bg=self._CARD, fg="#333",
                           font=("Segoe UI", 10, "bold"))
            lbl.pack(anchor="w", pady=(8, 2))
            ent = tk.Entry(parent, textvariable=var,
                           font=("Segoe UI", 10), width=50,
                           relief="solid", bd=1,
                           disabledbackground="#f4f4f4",
                           disabledforeground="#aaa")
            ent.pack(anchor="w")
            hlbl = None
            if hint:
                hlbl = tk.Label(parent, text=hint,
                                bg=self._CARD, fg="#888",
                                font=("Segoe UI", 8))
                hlbl.pack(anchor="w")
            if return_all:
                return lbl, ent, hlbl
            return ent

        # ── Event handlers ────────────────────────────────────────────────────────

        def _on_phase(self, *_):
            """Enable or disable the Agreement Date field based on phase selection."""
            p2 = self.phase_var.get() == "onboarding"
            self.date_lbl.configure(fg="#333" if p2 else self._DIM)
            self.date_ent.configure(state="normal" if p2 else "disabled")
            if self.date_hlbl:
                self.date_hlbl.configure(fg="#888" if p2 else "#ccc")
            if not p2:
                self.date_var.set("")

        def _on_provider(self, *_):
            """Show or hide the custom SMTP fields."""
            if self.provider_var.get() == "Custom SMTP…":
                self.custom_frame.pack(fill="x")
            else:
                self.custom_frame.pack_forget()

        # ── Validation ────────────────────────────────────────────────────────────

        def _validate(self) -> bool:
            errs = []
            if not self.name_var.get().strip():
                errs.append("  Installer Name is required")
            em = self.email_var.get().strip()
            if not em:
                errs.append("  Installer Email is required")
            elif "@" not in em:
                errs.append("  Installer Email doesn't look valid")
            if (self.phase_var.get() == "onboarding"
                    and not self.date_var.get().strip()):
                errs.append("  Agreement Date is required for Phase 2")
            if (self.provider_var.get() == "Custom SMTP…"
                    and not self.smtp_host_var.get().strip()):
                errs.append("  SMTP Host is required for a custom mail provider")
            if errs:
                messagebox.showerror(
                    "Missing Information",
                    "Please fill in the following before continuing:\n\n"
                    + "\n".join(errs),
                    parent=self.root,
                )
                return False
            return True

        # ── Run actions ───────────────────────────────────────────────────────────

        def _test(self):
            if self._validate():
                self._execute(dry_run=True, password="")

        def _send(self):
            if self._validate():
                self._pw_dialog()

        def _pw_dialog(self):
            """Password entry dialog — shown before a live email send."""
            win = tk.Toplevel(self.root)
            win.title("Email Password")
            win.configure(bg=self._BG)
            win.resizable(False, False)
            win.grab_set()

            tk.Label(win, text="Enter your email password",
                     bg=self._BG, fg=self._NAV,
                     font=("Segoe UI", 12, "bold")).pack(pady=(24, 4), padx=36)
            tk.Label(
                win,
                text=f"Sending from:  {PI_EMAIL}\n\n"
                     "Enter your email account password.",
                bg=self._BG, fg="#555",
                font=("Segoe UI", 9), justify="center",
            ).pack(padx=36)

            pwd_var = tk.StringVar()
            pwd_ent = tk.Entry(win, textvariable=pwd_var, show="*",
                               font=("Segoe UI", 11), width=26,
                               relief="solid", bd=1)
            pwd_ent.pack(pady=14, padx=36)
            pwd_ent.focus_set()

            def ok(*_):
                p = pwd_var.get()
                if not p:
                    messagebox.showerror("Required",
                                         "Please enter your email password.",
                                         parent=win)
                    return
                win.destroy()
                self._execute(dry_run=False, password=p)

            pwd_ent.bind("<Return>", ok)
            tk.Button(win, text="Send Email", command=ok,
                      bg=self._GRN, fg="white",
                      font=("Segoe UI", 10, "bold"),
                      relief="flat", padx=20, pady=8,
                      cursor="hand2").pack(pady=(0, 24))

            win.update_idletasks()
            mx = self.root.winfo_x() + (self.root.winfo_width()  - win.winfo_width())  // 2
            my = self.root.winfo_y() + (self.root.winfo_height() - win.winfo_height()) // 2
            win.geometry(f"+{mx}+{my}")

        def _execute(self, dry_run: bool, password: str):
            """Collect form values and run the selected workflow in a background thread."""
            global DRY_RUN
            DRY_RUN = dry_run

            name    = self.name_var.get().strip()
            company = self.company_var.get().strip()
            email   = self.email_var.get().strip()
            date    = self.date_var.get().strip()
            phase   = self.phase_var.get()

            prov = self.provider_var.get()
            if self._MAIL[prov] is None:   # Custom SMTP
                host = self.smtp_host_var.get().strip()
                try:
                    port = int(self.smtp_port_var.get())
                except ValueError:
                    port = 587
            else:
                host, port = self._MAIL[prov]

            smtp_cfg = {
                "smtp_host"    : host,
                "smtp_port"    : port,
                "smtp_user"    : PI_EMAIL,
                "smtp_password": password,
            }

            # Disable buttons while running
            self.test_btn.configure(state="disabled")
            self.send_btn.configure(state="disabled")
            self._clear_log()

            # Redirect print() to the log widget
            old_stdout  = sys.stdout
            sys.stdout  = _LogRedirect(self.root, self.log)

            def run():
                email_ok = False
                ran_ok   = False
                def re_enable():
                    self.test_btn.configure(state="normal")
                    self.send_btn.configure(state="normal")
                try:
                    if phase == "agreement":
                        email_ok = run_agreement_phase(name, company, email, smtp_cfg)
                    else:
                        email_ok = run_onboarding(name, company, email, date, smtp_cfg)
                    ran_ok = True
                except Exception as ex:
                    print(f"\n[ERROR] An unexpected error occurred:\n  {ex}\n")
                finally:
                    sys.stdout = old_stdout
                    self.root.after(0, re_enable)
                    if ran_ok:
                        self.root.after(
                            200,
                            lambda ok=email_ok: self._after_run(phase, dry_run, ok),
                        )

            threading.Thread(target=run, daemon=True).start()

        # ── Post-run guidance ─────────────────────────────────────────────────────

        def _after_run(self, phase: str, dry_run: bool, email_ok: bool = True):
            """Show a plain-English popup telling the user what to do next."""
            if dry_run:
                messagebox.showinfo(
                    "Test Run Complete",
                    "Test run finished — no email was sent.\n\n"
                    "Review the log above to check everything looks correct,\n"
                    "then click  Send Real Email  when you're ready.",
                    parent=self.root,
                )
                return

            if not email_ok:
                messagebox.showwarning(
                    "Email Not Sent",
                    "The workflow ran but the email could not be sent.\n\n"
                    "Check the log above for the error detail.\n\n"
                    "Common causes:\n"
                    "  \u2022  Wrong password (Gmail: use an App Password)\n"
                    "  \u2022  2-Step Verification not enabled on your Google account\n"
                    "  \u2022  Firewall or network blocking SMTP\n\n"
                    "A draft email has been saved in the installer's folder\n"
                    "so you can send it manually if needed.",
                    parent=self.root,
                )
                return

            if phase == "agreement":
                messagebox.showinfo(
                    "Phase 1 Complete \u2713",
                    "The agreement has been emailed to the installer.\n\n"
                    "Next steps:\n"
                    "  1. Installer completes and signs the agreement\n"
                    "  2. Installer emails the signed PDF back to Pi\n"
                    "  3. Pi countersigns and files the agreement\n"
                    "  4. Come back here, select  Phase 2  and run again\n\n"
                    "Switching the form to Phase 2 now \u2014 just enter the\n"
                    "Agreement Date when you're ready to continue.",
                    parent=self.root,
                )
                # Auto-advance the radio button to Phase 2
                self.phase_var.set("onboarding")
                self._on_phase()
            else:
                messagebox.showinfo(
                    "Phase 2 Complete \u2713",
                    "Onboarding email sent successfully!\n\n"
                    "The installer now has everything they need to get started.\n"
                    "You can close this window or run another installer through.",
                    parent=self.root,
                )

        # ── Log helpers ───────────────────────────────────────────────────────────

        def _log_write(self, text: str):
            self.log.configure(state="normal")
            self.log.insert("end", text)
            self.log.see("end")
            self.log.configure(state="disabled")

        def _clear_log(self):
            self.log.configure(state="normal")
            self.log.delete("1.0", "end")
            self.log.configure(state="disabled")

    # ── Launch ────────────────────────────────────────────────────────────────────
    root = tk.Tk()
    App(root)
    root.mainloop()
