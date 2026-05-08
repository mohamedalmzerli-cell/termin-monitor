"""
Termin-Monitor: Bürgeramt Osnabrück – Reisepass beantragen
Läuft via GitHub Actions – alle 10 Minuten Mo–Fr 7:00–17:00 Uhr
"""

import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime, timedelta
import logging
import sys

# ──────────────────────────────────────────
# KONFIGURATION (aus GitHub Secrets)
# ──────────────────────────────────────────

EMPFAENGER_EMAIL  = os.environ.get("EMPFAENGER_EMAIL", "mohamedalmzerli@gmail.com")
ABSENDER_EMAIL    = os.environ.get("ABSENDER_EMAIL", "mohamedalmzerli@gmail.com")
ABSENDER_PASSWORT = os.environ.get("ABSENDER_PASSWORT", "mmow offb ipsn eawb")

TAGE_IM_VORAUS = 14
BOOKING_URL    = "https://timeacle.com/booking/company/stadt-osnabruck/branch/burgeramt-osnabruck/queue/burgeramt/summary"
API_BASE       = "https://timeacle.com/api/v1"
COMPANY        = "stadt-osnabruck"
BRANCH         = "burgeramt-osnabruck"
QUEUE          = "burgeramt"

# ──────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)

# ──────────────────────────────────────────
# TERMIN PRÜFEN
# ──────────────────────────────────────────

def termin_pruefen():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/html",
        "Referer": BOOKING_URL,
    }

    verfuegbare_termine = []
    heute    = datetime.now()
    deadline = heute + timedelta(days=TAGE_IM_VORAUS)

    # Methode 1: Timeacle API
    try:
        api_url = f"{API_BASE}/company/{COMPANY}/branch/{BRANCH}/queue/{QUEUE}/available-days"
        params  = {
            "from": heute.strftime("%Y-%m-%d"),
            "to":   deadline.strftime("%Y-%m-%d"),
        }
        resp = requests.get(api_url, headers=headers, params=params, timeout=15)

        if resp.status_code == 200:
            daten = resp.json()
            tage  = daten if isinstance(daten, list) else daten.get("days", [])

            for tag in tage:
                datum_str = tag if isinstance(tag, str) else tag.get("date", "")
                if datum_str:
                    slots_url  = f"{API_BASE}/company/{COMPANY}/branch/{BRANCH}/queue/{QUEUE}/slots"
                    slots_resp = requests.get(
                        slots_url,
                        headers=headers,
                        params={"date": datum_str},
                        timeout=15
                    )
                    if slots_resp.status_code == 200:
                        slots       = slots_resp.json()
                        slots_liste = slots if isinstance(slots, list) else slots.get("slots", [])
                        for slot in slots_liste:
                            uhrzeit = slot if isinstance(slot, str) else slot.get("time", "")
                            if uhrzeit:
                                verfuegbare_termine.append(f"{datum_str} um {uhrzeit} Uhr")

        if verfuegbare_termine:
            return verfuegbare_termine

    except Exception as e:
        log.warning(f"API-Methode fehlgeschlagen: {e}")

    # Methode 2: HTML parsen (Fallback)
    try:
        resp      = requests.get(BOOKING_URL, headers=headers, timeout=15)
        soup      = BeautifulSoup(resp.text, "html.parser")
        seiten_text = soup.get_text().lower()

        keine_termine_keywords = [
            "keine termine", "no appointments", "nicht verfügbar",
            "ausgebucht", "no slots", "not available"
        ]
        for keyword in keine_termine_keywords:
            if keyword in seiten_text:
                log.info(f"Seite zeigt: '{keyword}' → keine Termine")
                return []

        slot_elemente = soup.find_all(class_=lambda c: c and any(
            w in c for w in ["slot", "time", "available", "booking", "termin", "date"]
        ))
        for el in slot_elemente:
            text = el.get_text(strip=True)
            if text and len(text) < 50:
                verfuegbare_termine.append(text)

    except Exception as e:
        log.warning(f"HTML-Methode fehlgeschlagen: {e}")

    return verfuegbare_termine


# ──────────────────────────────────────────
# E-MAIL SENDEN
# ──────────────────────────────────────────

def email_senden(termine):
    termine_text = "\n".join(f"  • {t}" for t in termine)
    betreff      = "🎉 Reisepass-Termin verfügbar – Bürgeramt Osnabrück!"
    inhalt       = f"""Hallo Mohamed,

ein Termin beim Bürgeramt Osnabrück (Reisepass beantragen) ist jetzt verfügbar!

Verfügbare Termine:
{termine_text}

👉 Jetzt sofort buchen:
{BOOKING_URL}

Beeil dich – Termine werden schnell vergeben!

──────────────────
Termin-Monitor via GitHub Actions
Geprüft am: {datetime.now().strftime("%d.%m.%Y um %H:%M Uhr")}
"""

    msg            = MIMEMultipart()
    msg["From"]    = ABSENDER_EMAIL
    msg["To"]      = EMPFAENGER_EMAIL
    msg["Subject"] = betreff
    msg.attach(MIMEText(inhalt, "plain", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(ABSENDER_EMAIL, ABSENDER_PASSWORT)
            server.sendmail(ABSENDER_EMAIL, EMPFAENGER_EMAIL, msg.as_string())
        log.info(f"✅ E-Mail gesendet an {EMPFAENGER_EMAIL}")
        return True
    except Exception as e:
        log.error(f"❌ E-Mail Fehler: {e}")
        return False


# ──────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────

def main():
    log.info("=" * 50)
    log.info("Termin-Monitor gestartet (GitHub Actions)")
    log.info(f"Empfänger: {EMPFAENGER_EMAIL}")
    log.info("=" * 50)

    termine = termin_pruefen()

    if termine:
        log.info(f"🎉 {len(termine)} Termin(e) gefunden!")
        email_senden(termine)
        sys.exit(0)
    else:
        log.info("❌ Keine Termine verfügbar.")
        sys.exit(0)


if __name__ == "__main__":
    main()
