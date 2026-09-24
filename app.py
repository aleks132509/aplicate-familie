import io
import os
import json
import re
import smtplib
import time
import unicodedata
import base64
from datetime import date, datetime, timedelta
from email.message import EmailMessage
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import plotly.graph_objects as go
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import streamlit as st

# ==========================================
# CONFIGURARE PAGINĂ & THEME (DARK MODE + MULTISELECT LUX)
# ==========================================
st.set_page_config(
    page_title="HealthTrack Pro - Monitorizare Sănătate",
    layout="wide",
    page_icon="🩺",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp {
        background-color: #0e1117 !important;
        color: #f1f5f9 !important;
    }
    .metric-card {
        background-color: #1e222d;
        padding: 16px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.4);
        border: 1px solid #2e3545;
        text-align: center;
        margin-bottom: 12px;
    }
    .metric-value { 
        font-size: 24px; 
        font-weight: 700; 
        color: #38bdf8; 
    }
    .metric-label { 
        font-size: 11px; 
        color: #94a3b8; 
        font-weight: 600; 
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .stTextInput > div > div > input {
        color: #ffffff !important;
        background-color: #1e222d !important;
    }
    .role-badge {
        background-color: #0284c7;
        color: white;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: bold;
    }
    /* ========================================== */
    /* STIL DE LUX PENTRU st.multiselect (TAGS)    */
    /* ========================================== */
    .stMultiSelect [data-baseweb="tag"] {
        background: linear-gradient(135deg, #fef08a 0%, #fde047 30%, #eab308 100%) !important;
        color: #111827 !important;
        border: 1px solid #ca8a04 !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
    }
    .stMultiSelect [data-baseweb="tag"] span,
    .stMultiSelect [data-baseweb="tag"] div {
        color: #111827 !important;
    }
    .stMultiSelect [data-baseweb="tag"] svg {
        fill: #111827 !important;
    }
    .stMultiSelect div[data-baseweb="select"] > div {
        background-color: #1e222d !important;
        border-color: #2e3545 !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

def remove_diacritics(text):
    if not isinstance(text, str):
        text = str(text)
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )

def clean_obs(val):
    if not val or pd.isna(val) or str(val).strip().lower() in ["nan", "none", ""]:
        return ""
    res = str(val).strip()
    res = re.sub(r'^(azi,\s*)+', '', res, flags=re.IGNORECASE).strip()
    return res

def parse_flexible_date(series_or_str):
    if isinstance(series_or_str, pd.Series):
        s = series_or_str.astype(str).str.strip()
        dt1 = pd.to_datetime(s, format="%d.%m.%Y", errors="coerce")
        dt2 = pd.to_datetime(s, format="%Y-%m-%d", errors="coerce")
        dt3 = pd.to_datetime(s, errors="coerce")
        return dt1.fillna(dt2).fillna(dt3)
    else:
        s = str(series_or_str).strip()
        for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(s, fmt)
            except:
                pass
        return pd.to_datetime(s, errors="coerce")

def trigger_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

# ==========================================
# GESTIONARE FIȘIERE PERSISTENTE & SETĂRI EMAIL
# ==========================================
DATA_FILE = "date_medicale_utilizator.csv"
MEDS_FILE = "medicamente.csv"
MEDS_HIST_FILE = "istoric_medicamente.csv"
PROG_FILE = "programari_medicale.csv"
FOODS_FILE = "alimente_custom.csv"
BACKUP_LOG_FILE = "ultimul_backup_auto.txt"
BACKUP_ERROR_LOG_FILE = "ultima_eroare_backup_auto.txt"
SETTINGS_FILE = "setari_email.json"

moment_order = [
    'Dimineața - Înainte de masă',
    'Dimineața - După masă',
    'Prânz - Înainte de masă',
    'Prânz - După masă',
    'Seara - Înainte de masă',
    'Seara - După masă'
]

def load_persisted_settings():
    default_settings = {
        "notif_enabled": True, 
        "email_sender": "",
        "email_password": "",
        "target_glic_min": 70, "target_glic_max": 120,
        "target_glic_post_min": 70, "target_glic_post_max": 160,
        "target_ta_sis": 120, "target_ta_dia": 80,
    }
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                saved = json.load(f)
                default_settings.update(saved)
        except:
            pass
    return default_settings

def save_persisted_settings(settings_dict):
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings_dict, f)
    except:
        pass

def get_initial_meds():
    if os.path.exists(MEDS_FILE):
        try:
            df_m = pd.read_csv(MEDS_FILE)
            if not df_m.empty:
                return df_m
        except:
            pass
            
    df_init_m = pd.DataFrame([
        {"Medicament": "Glucophage", "Doză": "1000 mg", "Orar / Frecvență": "Dimineața și seara, dupa masa", "Observații": ""},
        {"Medicament": "Lagosa", "Doză": "150 mg", "Orar / Frecvență": "Dimineața și seara, dupa masa", "Observații": ""},
        {"Medicament": "Lipantil Nano", "Doză": "145 mg", "Orar / Frecvență": "Pranz, dupa masa", "Observații": ""},
        {"Medicament": "Sortis", "Doză": "20 mg", "Orar / Frecvență": "Seara, dupa masa", "Observații": ""},
        {"Medicament": "Omacor", "Doză": "1000 mg", "Orar / Frecvență": "Dimineața, la prânz și seara, dupa masa", "Observații": ""},
        {"Medicament": "Diaprel MR", "Doză": "60 mg", "Orar / Frecvență": "Dimineața, inainte masa", "Observații": "1/2 din doza"},
        {"Medicament": "Larginina", "Doză": "1000 mg", "Orar / Frecvență": "Pranz, dupa masa", "Observații": "10 zile pe luna"},
        {"Medicament": "Atacand", "Doză": "8 mg", "Orar / Frecvență": "Seara, dupa masa", "Observații": ""},
        {"Medicament": "Nebilet", "Doză": "5 mg", "Orar / Frecvență": "Dimineața, dupa masa", "Observații": ""},
        {"Medicament": "Aspenter", "Doză": "75 mg", "Orar / Frecvență": "Pranz, dupa masa", "Observații": ""},
    ])
    df_init_m.to_csv(MEDS_FILE, index=False)
    return df_init_m

def get_initial_history():
    if os.path.exists(MEDS_HIST_FILE):
        return pd.read_csv(MEDS_HIST_FILE)
    return pd.DataFrame(columns=["Data_Ora", "Acțiune", "Medicament", "Detalii"])

def get_initial_prog():
    if os.path.exists(PROG_FILE):
        try:
            df_p = pd.read_csv(PROG_FILE)
            if not df_p.empty:
                if "Ora" not in df_p.columns: df_p["Ora"] = "10:00"
                if "Efectuat" not in df_p.columns: df_p["Efectuat"] = "Nu"
                if "Clinică" not in df_p.columns: df_p["Clinică"] = "-"
                if "Zile_Alerta" not in df_p.columns: df_p["Zile_Alerta"] = "1, 3"
                if "Observații" not in df_p.columns: df_p["Observații"] = ""
                return df_p
        except:
            pass
            
    df_init_p = pd.DataFrame([
        {"Dată": "2026-10-05", "Ora": "10:00", "Tip": "Eliberare reteta", "Clinică": "Medic de familie", "Zile_Alerta": "1, 3", "Efectuat": "Nu", "Observații": "Ridicare reteta lunara"},
        {"Dată": "2026-11-29", "Ora": "09:00", "Tip": "Analize de laborator", "Clinică": "Regina Maria", "Zile_Alerta": "1, 3, 7", "Efectuat": "Nu", "Observații": "Repetare analize Diabet"},
        {"Dată": "2026-12-05", "Ora": "14:30", "Tip": "Consult Diabet", "Clinică": "Dr. Clenciu Craiova", "Zile_Alerta": "2, 5", "Efectuat": "Nu", "Observații": "Reteta 3 luni"},
    ])
    df_init_p.to_csv(PROG_FILE, index=False)
    return df_init_p

def get_initial_foods():
    default_foods = {
        "🔴 Indice Glicemic Ridicat": [
            "ciocolata", "prajitura", "tort", "inghetata", "zahar", "miere", "biscuiti",
            "paine alba", "pizza", "paste albe", "cartofi prajiti", "covrigi", "napolitane",
            "croissant", "gogosi", "patiserie", "cornuri", "suc", "cola", "fanta", "pepsi", "bere", "energizant"
        ],
        "🟡 Indice Glicemic Mediu": [
            "paine integrala", "paste integrale", "orez integral", "orez basmati", "orez alb",
            "fulgi de ovaz", "fulgi de mei", "fulgi de secara", "cartofi fierti", "porumb", "malai (mamaliga)", "mazare", "fasole boabe"
        ],
        "🟢 Indice Glicemic Scazut / Altele": [
            "cola 0", "pepsi zero", "apa minerala", "cafea fara zahăr", "ceai neindulcit", 
            "stres", "oboseala", "dupa efort fizic", "masa copioasa", "salata verde", "castraveti", "rosii"
        ]
    }
    if os.path.exists(FOODS_FILE):
        try:
            df_f = pd.read_csv(FOODS_FILE)
            categories = {}
            for _, row in df_f.iterrows():
                cat = str(row["Categorie"])
                item = remove_diacritics(str(row["Element"])).strip().lower()
                if cat not in categories: categories[cat] = []
                if item and item != "nan" and item not in categories[cat]: categories[cat].append(item)
            return categories
        except:
            pass
    return default_foods

def save_all_files():
    st.session_state.meds_df.to_csv(MEDS_FILE, index=False)
    st.session_state.meds_hist_df.to_csv(MEDS_HIST_FILE, index=False)
    st.session_state.prog_df.to_csv(PROG_FILE, index=False)

def save_custom_foods():
    rows = []
    for cat, items in st.session_state.food_categories.items():
        for item in items:
            if item and str(item).strip().lower() != "nan":
                rows.append({"Categorie": cat, "Element": remove_diacritics(str(item)).strip().lower()})
    pd.DataFrame(rows).to_csv(FOODS_FILE, index=False)

def add_history_entry(actiune, medicament, detalii):
    new_entry = {
        "Data_Ora": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "Acțiune": actiune,
        "Medicament": medicament,
        "Detalii": detalii
    }
    st.session_state.meds_hist_df = pd.concat([st.session_state.meds_hist_df, pd.DataFrame([new_entry])], ignore_index=True)
    save_all_files()

def get_chronological_backup_df():
    if not os.path.exists(DATA_FILE):
        return pd.DataFrame()
    try:
        df_b = pd.read_csv(DATA_FILE)
        date_col_name = 'Data' if 'Data' in df_b.columns else 'Dată'
        moment_col_name = 'Moment Zi' if 'Moment Zi' in df_b.columns else 'Moment Zi'
        glic_col_name = 'Glicemie'
        sis_col_name = 'Sistolică' if 'Sistolică' in df_b.columns else 'Sistolica'
        dia_col_name = 'Diastolică' if 'Diastolică' in df_b.columns else 'Diastolica'
        puls_col_name = 'Puls'
        obs_col_name = 'Observații' if 'Observații' in df_b.columns else 'Observatii'

        if date_col_name in df_b.columns:
            df_b["Dată_dt"] = parse_flexible_date(df_b[date_col_name])
            df_b["Moment_Cat"] = pd.Categorical(df_b[moment_col_name], categories=moment_order, ordered=True)
            df_b = df_b.dropna(subset=["Dată_dt"]).sort_values(by=["Dată_dt", "Moment_Cat"]).drop(columns=["Dată_dt", "Moment_Cat"])
        
        if glic_col_name in df_b.columns:
            df_b["Glic_num"] = pd.to_numeric(df_b[glic_col_name], errors="coerce").fillna(0)
            df_b = df_b[df_b["Glic_num"] > 0].drop(columns=["Glic_num"])

        df_all = df_b.copy()
        if date_col_name in df_all.columns:
            df_all[date_col_name] = parse_flexible_date(df_all[date_col_name]).dt.strftime("%d.%m.%Y")
        
        if glic_col_name in df_all.columns:
            df_all["St. Glicemie"] = df_all.apply(lambda r: evaluate_glic(r[glic_col_name], r[moment_col_name]), axis=1)
            df_all[glic_col_name] = format_table_column(df_all[glic_col_name])
        
        if sis_col_name in df_all.columns and dia_col_name in df_all.columns:
            df_all["St. Tensiune"] = df_all.apply(lambda r: evaluate_ta(r[sis_col_name], r[dia_col_name]), axis=1)
            df_all[sis_col_name] = format_table_column(df_all[sis_col_name])
            df_all[dia_col_name] = format_table_column(df_all[dia_col_name])
        
        if puls_col_name in df_all.columns:
            df_all["St. Puls"] = df_all[puls_col_name].apply(evaluate_puls)
            df_all[puls_col_name] = format_table_column(df_all[puls_col_name])
        
        if obs_col_name in df_all.columns:
            df_all[obs_col_name] = df_all[obs_col_name].apply(clean_obs)
        
        if 'Luna_An' in df_all.columns:
            df_all = df_all.drop(columns=['Luna_An'])

        cols_order_all = [date_col_name, moment_col_name, glic_col_name, "St. Glicemie", sis_col_name, dia_col_name, "St. Tensiune", puls_col_name, "St. Puls", obs_col_name]
        existing_cols_all = [c for c in cols_order_all if c in df_all.columns]
        df_all = df_all[existing_cols_all]

        for col in df_all.columns:
            df_all[col] = df_all[col].apply(lambda x: remove_diacritics(str(x)) if pd.notna(x) and str(x).strip() not in ["nan", "None", ""] else "")
        
        df_all.columns = [remove_diacritics(c) for c in df_all.columns]
        return df_all
    except:
        return pd.DataFrame()

def trimite_email_cu_multiple_atasamente(destinatar, subiect, mesaj, file_paths_dict):
    email_sender = st.session_state.settings.get("email_sender", "").strip()
    email_password = st.session_state.settings.get("email_password", "").strip()
    
    if not email_sender or not email_password:
        return False, "Datele de configurare email lipsesc din Setări."

    configs = [
        {"port": 587, "use_ssl": False},
        {"port": 465, "use_ssl": True}
    ]

    last_error = ""
    for cfg in configs:
        port = cfg["port"]
        use_ssl = cfg["use_ssl"]
        
        for attempt in range(2):
            try:
                msg = EmailMessage()
                msg.set_content(mesaj)
                msg['Subject'] = subiect
                msg['From'] = email_sender
                msg['To'] = destinatar

                for f_name, f_path in file_paths_dict.items():
                    if os.path.exists(f_path):
                        with open(f_path, "rb") as f:
                            file_data = f.read()
                        msg.add_attachment(file_data, maintype="application", subtype="octet-stream", filename=f_name)

                if use_ssl:
                    with smtplib.SMTP_SSL('smtp.mail.me.com', port, timeout=30) as smtp:
                        smtp.login(email_sender, email_password)
                        smtp.send_message(msg)
                else:
                    with smtplib.SMTP('smtp.mail.me.com', port, timeout=30) as smtp:
                        smtp.starttls()
                        smtp.login(email_sender, email_password)
                        smtp.send_message(msg)
                        
                return True, "Email cu toate fișierele de backup trimis cu succes prin iCloud!"
            except Exception as e:
                last_error = str(e)
                time.sleep(1)
                
    return False, f"Erore trimitere iCloud (toate porturile au eșuat): {last_error}"

def verifica_si_fa_backup_automat():
    try:
        email_dest = st.session_state.settings.get("email_sender", "").strip()
        if not email_dest:
            return 

        azi = datetime.now().date()
        # Am înlăturat condiția "ultima_data < azi" pentru a forța rularea
        # și trimiterea imediată a backup-ului în acest moment de testare.
        
        df_cron = get_chronological_backup_df()
        if not df_cron.empty:
            temp_backup_file = "temp_backup_cron.csv"
            df_cron.to_csv(temp_backup_file, index=False)
            
            attachments = {
                "backup_date_medicale.csv": temp_backup_file,
            }
            
            temp_meds_backup = "temp_meds_backup.csv"
            if os.path.exists(MEDS_FILE):
                try:
                    df_m_temp = pd.read_csv(MEDS_FILE)
                    for col in df_m_temp.columns:
                        df_m_temp[col] = df_m_temp[col].apply(lambda x: remove_diacritics(str(x)) if pd.notna(x) and str(x).strip() not in ["nan", "None", ""] else "")
                    df_m_temp.columns = [remove_diacritics(c) for c in df_m_temp.columns]
                    df_m_temp.to_csv(temp_meds_backup, index=False)
                    attachments["medicamente.csv"] = temp_meds_backup
                except:
                    attachments["medicamente.csv"] = MEDS_FILE

            temp_prog_backup = "temp_prog_backup.csv"
            if os.path.exists(PROG_FILE):
                try:
                    df_p_temp = pd.read_csv(PROG_FILE)
                    for col in df_p_temp.columns:
                        df_p_temp[col] = df_p_temp[col].apply(lambda x: remove_diacritics(str(x)) if pd.notna(x) and str(x).strip() not in ["nan", "None", ""] else "")
                    df_p_temp.columns = [remove_diacritics(c) for c in df_p_temp.columns]
                    df_p_temp.to_csv(temp_prog_backup, index=False)
                    attachments["programari_medicale.csv"] = temp_prog_backup
                except:
                    attachments["programari_medicale.csv"] = PROG_FILE

            succes, _ = trimite_email_cu_multiple_atasamente(
                destinatar=email_dest,
                subiect=f"💾 [Backup Zilnic Automat] HealthTrack Pro - {azi.strftime('%d.%m.%Y')}",
                mesaj=f"Salut!\n\nAcesta este backup-ul tău zilnic automat generat la data de {azi.strftime('%d.%m.%Y')}.\nSunt atașate fișierele CSV cu datele medicale (filtrate doar cu valori măsurate), schema de tratament și programările medicale.\n\nHealthTrack Pro System",
                file_paths_dict=attachments
            )
            if os.path.exists(temp_backup_file):
                os.remove(temp_backup_file)
            if os.path.exists(temp_meds_backup):
                os.remove(temp_meds_backup)
            if os.path.exists(temp_prog_backup):
                os.remove(temp_prog_backup)

            if succes:
                with open(BACKUP_LOG_FILE, "w") as f:
                    f.write(azi.strftime("%Y-%m-%d"))
                if os.path.exists(BACKUP_ERROR_LOG_FILE):
                    os.remove(BACKUP_ERROR_LOG_FILE)
            else:
                with open(BACKUP_ERROR_LOG_FILE, "w") as f:
                    f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M')} | {_}")
        else:
            with open(BACKUP_ERROR_LOG_FILE, "w") as f:
                f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M')} | Nu există date de backup (df_cron gol).")
    except Exception as e:
        try:
            with open(BACKUP_ERROR_LOG_FILE, "w") as f:
                f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M')} | Eroare neașteptată: {e}")
        except:
            pass

# ==========================================
# SESSION STATE INITIALIZATION & PERSISTENȚĂ LOGARE
# ==========================================
if "users" not in st.session_state:
    st.session_state.users = {
        "Alex": {"pass": "Aleks132509", "role": "Administrator"},
        "Ionut": {"pass": "Ionut061191", "role": "Membru"},
        "Doctor": {"pass": "Alex2026", "role": "Doctor"},
    }

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = None

if "settings" not in st.session_state:
    st.session_state.settings = load_persisted_settings()

BACKUP_TRIGGER_SECRET = "schimba-acest-cod-secret-1234"

if st.query_params.get("backup_trigger") == BACKUP_TRIGGER_SECRET:
    verifica_si_fa_backup_automat()
    st.write("Backup check executat.")
    st.stop()

if "meds_df" not in st.session_state:
    st.session_state.meds_df = get_initial_meds()
if "meds_hist_df" not in st.session_state:
    st.session_state.meds_hist_df = get_initial_history()
if "prog_df" not in st.session_state:
    st.session_state.prog_df = get_initial_prog()
if "food_categories" not in st.session_state:
    st.session_state.food_categories = get_initial_foods()

if "action_history_stack" not in st.session_state:
    st.session_state.action_history_stack = []

if not st.session_state.logged_in:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    _, col_b, _ = st.columns([1, 1.2, 1])

    with col_b:
        st.markdown("<h1 style='text-align: center; color: #38bdf8;'>🩺 HealthTrack Pro</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #94a3b8; font-size: 16px;'>Platformă de Monitorizare Medicală de Familie</p>", unsafe_allow_html=True)

        with st.container(border=True):
            username = st.text_input("👤 Utilizator")
            password = st.text_input("🔑 Parolă", type="password")
            remember_me = st.checkbox("🧠 Ține-mă minte (Rămâi autentificat)", value=True)

            if st.button("🔓 Autentificare", type="primary", use_container_width=True):
                user_data = st.session_state.users.get(username)
                if user_data and user_data["pass"] == password:
                    st.session_state.logged_in = True
                    st.session_state.user = username
                    verifica_si_fa_backup_automat()
                    trigger_rerun()
                else:
                    st.error("Utilizator sau parolă incorectă!")
    st.stop()

current_user_info = st.session_state.users.get(st.session_state.user, {"role": "Membru"})
current_role = current_user_info.get("role", "Membru")
is_admin = current_role == "Administrator"

verifica_si_fa_backup_automat()
