import os
import sys
from playwright.sync_api import sync_playwright

APP_URL = os.environ["APP_URL"].rstrip("/")
SECRET = os.environ["BACKUP_TRIGGER_SECRET"]


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        print(f"Deschid aplicația: {APP_URL}")
        page.goto(APP_URL, wait_until="networkidle", timeout=90000)

        # Dacă aplicația "doarme" (inactivă de prea mult timp), Streamlit
        # Community Cloud arată un buton "Yes, get this app back up!" —
        # îl căutăm și îl apăsăm ca un vizitator real.
        try:
            wake_btn = page.get_by_text("get this app back up", exact=False)
            if wake_btn.count() > 0:
                print("Aplicația era adormită — apăs butonul de trezire...")
                wake_btn.first.click()
                page.wait_for_timeout(15000)
                page.wait_for_load_state("networkidle", timeout=90000)
        except Exception as e:
            print(f"Nu am găsit butonul de trezire (probabil aplicația era deja activă): {e}")

        trigger_url = f"{APP_URL}/?backup_trigger={SECRET}"
        print(f"Accesez link-ul de backup...")
        page.goto(trigger_url, wait_until="networkidle", timeout=90000)

        content = page.content()
        if "Backup check executat" in content:
            print("✅ OK: backup trigger accesat cu succes.")
        else:
            print("⚠️ ATENȚIE: nu am găsit confirmarea așteptată pe pagină. Conținut primit:")
            print(content[:800])
            browser.close()
            sys.exit(1)

        browser.close()


if __name__ == "__main__":
    run()
