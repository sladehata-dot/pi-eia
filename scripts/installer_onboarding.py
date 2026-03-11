#!/usr/bin/env python3
"""
Pi Ops – Installer Onboarding Workflow
=======================================
Triggered upon execution of the Installer / Designer Services Agreement by both parties.

Workflow:
  1. Creates a compliance folder for the installer under Pi Ops\Installers\
  2. Logs the onboarding event with document checklist status
  3. Sends a branded email to the installer requesting required compliance documents
  4. Saves an HTML email draft locally if email delivery fails

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
from datetime import datetime
from pathlib import Path


# ── CONSTANTS ──────────────────────────────────────────────────────────────────

INSTALLERS_BASE_PATH = Path(r"C:\Users\HP\Desktop\Principle and Innovation\Pi Ops\Installers")

# Upload portal — development uses localhost:3000; swap for production domain when deployed
UPLOAD_PORTAL_BASE = "http://localhost:3000/installer-upload"

PI_EMAIL       = "slade@principleinnovation.tech"
PI_NAME        = "Slade Hata"
PI_COMPANY     = "Pi Ops Pty Ltd"
PI_ABN         = "85 685 996 114"
PI_ADDRESS     = "42 Colches Street, Casino NSW 2470"

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
        Kind regards,<br>
        <strong>{PI_NAME}</strong><br>
        <span style="color:#666;font-size:13px;">{PI_COMPANY}</span><br>
        <a href="mailto:{PI_EMAIL}" style="color:#4a90d9;font-size:13px;">{PI_EMAIL}</a>
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
                           installer_email: str, smtp_config: dict,
                           folder_path: Path) -> bool:
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
    msg["From"]    = f"{PI_NAME} <{smtp_config['smtp_user']}>"
    msg["To"]      = installer_email

    plain_body = build_plain_text_email(installer_name, company_name, upload_instructions_plain)
    html_body  = build_email_html(installer_name, company_name, upload_instructions_html)

    msg.attach(MIMEText(plain_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(smtp_config["smtp_host"], smtp_config["smtp_port"]) as server:
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
        installer_name, company_name, installer_email, smtp_config, folder_path
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

    return folder_path


# ── RUN CONFIGURATION ──────────────────────────────────────────────────────────
# Update the values below before running.

if __name__ == "__main__":

    # ── SMTP Settings ──────────────────────────────────────────
    # Gmail:          smtp_host="smtp.gmail.com",       smtp_port=587
    # Outlook/M365:   smtp_host="smtp.office365.com",   smtp_port=587
    # Custom domain:  check with your hosting provider (Cloudflare, cPanel, etc.)
    #
    # For Gmail, use an App Password (not your login password):
    #   Google Account > Security > 2-Step Verification > App Passwords
    # ----------------------------------------------------------

    SMTP_CONFIG = {
        "smtp_host"     : "smtp.gmail.com",     # ← update if needed
        "smtp_port"     : 587,
        "smtp_user"     : PI_EMAIL,             # ← sending address
        "smtp_password" : "",                   # ← leave blank to be prompted securely
    }

    # ── Installer Details ───────────────────────────────────────
    # Update these each time a new agreement is executed.
    # ─────────────────────────────────────────────────────────────

    INSTALLER = {
        "installer_name"  : "Jean-Jacques Tessier",
        "company_name"    : "Energy J Electrical Pty Ltd",  # set to "" for sole traders
        "installer_email" : "",                              # ← add installer email address
        "agreement_date"  : "11 March 2026",
    }

    # ── Password prompt (secure – not stored in script) ────────
    if not SMTP_CONFIG["smtp_password"]:
        SMTP_CONFIG["smtp_password"] = getpass.getpass(
            f"\nEnter email password / App Password for {PI_EMAIL}: "
        )

    # ── Execute ─────────────────────────────────────────────────
    run_onboarding(
        installer_name  = INSTALLER["installer_name"],
        company_name    = INSTALLER["company_name"],
        installer_email = INSTALLER["installer_email"],
        agreement_date  = INSTALLER["agreement_date"],
        smtp_config     = SMTP_CONFIG,
    )
