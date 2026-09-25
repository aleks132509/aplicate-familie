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
        
        # Includem rândul dacă are orice măsurătoare sau observație non-vidă
        cols_masuratori = [c for c in [glic_col_name, sis_col_name, dia_col_name, puls_col_name] if c in df_b.columns]
        if cols_masuratori:
            mask_are_date = pd.Series(False, index=df_b.index)
            for c in cols_masuratori:
                mask_are_date = mask_are_date | (pd.to_numeric(df_b[c], errors="coerce").fillna(0) > 0)
            if obs_col_name in df_b.columns:
                mask_are_date = mask_are_date | (df_b[obs_col_name].astype(str).str.strip() != "")
            df_b = df_b[mask_are_date]

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
        ultima_data = None
        if os.path.exists(BACKUP_LOG_FILE):
            try:
                with open(BACKUP_LOG_FILE, "r") as f:
                    ultima_data_str = f.read().strip()[:10]
                    ultima_data = datetime.strptime(ultima_data_str, "%Y-%m-%d").date()
            except:
                pass

        if ultima_data is None or ultima_data < azi:
            df_cron = get_chronological_backup_df()
            temp_backup_file = "temp_backup_cron.csv"
            temp_meds_backup = "temp_meds_backup.csv"
            temp_prog_backup = "temp_prog_backup.csv"
            attachments = {}
            fisiere_incluse = []
            fisiere_lipsa = []

            if not df_cron.empty:
                df_cron.to_csv(temp_backup_file, index=False)
                attachments["backup_date_medicale.csv"] = temp_backup_file
                fisiere_incluse.append("backup_date_medicale.csv")
            elif os.path.exists(DATA_FILE):
                try:
                    df_raw = pd.read_csv(DATA_FILE)
                    for col in df_raw.columns:
                        df_raw[col] = df_raw[col].apply(lambda x: remove_diacritics(str(x)) if pd.notna(x) and str(x).strip() not in ["nan", "None", ""] else "")
                    df_raw.columns = [remove_diacritics(c) for c in df_raw.columns]
                    df_raw.to_csv(temp_backup_file, index=False)
                    attachments["backup_date_medicale.csv"] = temp_backup_file
                    fisiere_incluse.append("backup_date_medicale.csv (date brute)")
                except:
                    fisiere_lipsa.append("backup_date_medicale.csv")
            else:
                fisiere_lipsa.append("backup_date_medicale.csv")

            if os.path.exists(MEDS_FILE):
                try:
                    df_m_temp = pd.read_csv(MEDS_FILE)
                    for col in df_m_temp.columns:
                        df_m_temp[col] = df_m_temp[col].apply(lambda x: remove_diacritics(str(x)) if pd.notna(x) and str(x).strip() not in ["nan", "None", ""] else "")
                    df_m_temp.columns = [remove_diacritics(c) for c in df_m_temp.columns]
                    df_m_temp.to_csv(temp_meds_backup, index=False)
                    attachments["medicamente.csv"] = temp_meds_backup
                    fisiere_incluse.append("medicamente.csv")
                except:
                    attachments["medicamente.csv"] = MEDS_FILE
                    fisiere_incluse.append("medicamente.csv")
            else:
                fisiere_lipsa.append("medicamente.csv")

            if os.path.exists(PROG_FILE):
                try:
                    df_p_temp = pd.read_csv(PROG_FILE)
                    for col in df_p_temp.columns:
                        df_p_temp[col] = df_p_temp[col].apply(lambda x: remove_diacritics(str(x)) if pd.notna(x) and str(x).strip() not in ["nan", "None", ""] else "")
                    df_p_temp.columns = [remove_diacritics(c) for c in df_p_temp.columns]
                    df_p_temp.to_csv(temp_prog_backup, index=False)
                    attachments["programari_medicale.csv"] = temp_prog_backup
                    fisiere_incluse.append("programari_medicale.csv")
                except:
                    attachments["programari_medicale.csv"] = PROG_FILE
                    fisiere_incluse.append("programari_medicale.csv")
            else:
                fisiere_lipsa.append("programari_medicale.csv")

            if attachments:
                mesaj_backup = (
                    f"Salut!\n\nAcesta este backup-ul tău zilnic automat generat la data de {azi.strftime('%d.%m.%Y')}.\n\n"
                    f"Fișiere incluse ({len(fisiere_incluse)}/3): {', '.join(fisiere_incluse)}\n"
                )
                if fisiere_lipsa:
                    mesaj_backup += f"⚠️ Fișiere NEincluse: {', '.join(fisiere_lipsa)}\n"
                mesaj_backup += "\nHealthTrack Pro System"

                succes, _ = trimite_email_cu_multiple_atasamente(
                    destinatar=email_dest,
                    subiect=f"💾 [Backup Zilnic Automat] HealthTrack Pro - {azi.strftime('%d.%m.%Y')} ({len(fisiere_incluse)}/3 fișiere)",
                    mesaj=mesaj_backup,
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
                        f.write(f"{azi.strftime('%Y-%m-%d')} {datetime.now().strftime('%H:%M')} ({len(fisiere_incluse)}/3 fișiere)")
                    if fisiere_lipsa:
                        with open(BACKUP_ERROR_LOG_FILE, "w") as f:
                            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M')} | Backup trimis, dar incomplet — lipsă: {', '.join(fisiere_lipsa)}")
                    elif os.path.exists(BACKUP_ERROR_LOG_FILE):
                        os.remove(BACKUP_ERROR_LOG_FILE)
                else:
                    with open(BACKUP_ERROR_LOG_FILE, "w") as f:
                        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M')} | {_}")
            else:
                with open(BACKUP_ERROR_LOG_FILE, "w") as f:
                    f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M')} | Nu există date de backup.")
    except Exception as e:
        try:
            with open(BACKUP_ERROR_LOG_FILE, "w") as f:
                f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M')} | Eroare neașteptată: {e}")
        except:
            pass

# ==========================================
# SESSION STATE INITIALIZATION
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

# ==========================================
# AUTENTIFICARE
# ==========================================
if not st.session_state.logged_in:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    _, col_b, _ = st.columns([1, 1.2, 1])

    with col_b:
        st.markdown("<h1 style='text-align: center; color: #38bdf8;'>🩺 HealthTrack Pro</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #94a3b8; font-size: 16px;'>Platformă de Monitorizare Medicală de Familie</p>", unsafe_allow_html=True)

        with st.container(border=True):
            username = st.text_input("👤 Utilizator")
            password = st.text_input("🔑 Parolă", type="password")
            remember_me = st.checkbox("🧠 Ține-mă minte", value=True)

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

# ==========================================
# DATE MEDICALE
# ==========================================
def get_initial_data():
    start_date = datetime.strptime("12.09.2026", "%d.%m.%Y").date()
    end_date = max(datetime.now().date(), start_date)
    
    all_dates_str = []
    curr = start_date
    while curr <= end_date:
        all_dates_str.append(curr.strftime("%d.%m.%Y"))
        curr += timedelta(days=1)
        
    full_template = []
    for d_str in all_dates_str:
        for m in moment_order:
            full_template.append({
                "Dată": d_str,
                "Moment Zi": m,
                "Glicemie": 0,
                "Sistolică": 0,
                "Diastolică": 0,
                "Puls": 0,
                "Observații": ""
            })
    df_template = pd.DataFrame(full_template)
    df_template["Dată_dt"] = parse_flexible_date(df_template["Dată"])

    initial_defaults = [
        {"Dată": "12.09.2026", "Moment Zi": "Dimineața - Înainte de masă", "Glicemie": 137, "Sistolică": 108, "Diastolică": 61, "Puls": 0, "Observații": "Prima zi cu tratament"},
        {"Dată": "12.09.2026", "Moment Zi": "Seara - Înainte de masă", "Glicemie": 134, "Sistolică": 132, "Diastolică": 61, "Puls": 0, "Observații": "Prima zi cu tratament"},
        {"Dată": "13.09.2026", "Moment Zi": "Dimineața - Înainte de masă", "Glicemie": 143, "Sistolică": 115, "Diastolică": 52, "Puls": 0, "Observații": "A doua zi cu tratament"},
        {"Dată": "13.09.2026", "Moment Zi": "Seara - După masă", "Glicemie": 133, "Sistolică": 114, "Diastolică": 50, "Puls": 0, "Observații": ""},
        {"Dată": "14.09.2026", "Moment Zi": "Dimineața - Înainte de masă", "Glicemie": 114, "Sistolică": 133, "Diastolică": 62, "Puls": 0, "Observații": ""},
        {"Dată": "14.09.2026", "Moment Zi": "Seara - Înainte de masă", "Glicemie": 114, "Sistolică": 0, "Diastolică": 0, "Puls": 0, "Observații": ""},
        {"Dată": "15.09.2026", "Moment Zi": "Dimineața - Înainte de masă", "Glicemie": 116, "Sistolică": 111, "Diastolică": 70, "Puls": 0, "Observații": ""},
        {"Dată": "15.09.2026", "Moment Zi": "Dimineața - După masă", "Glicemie": 151, "Sistolică": 0, "Diastolică": 0, "Puls": 0, "Observații": ""},
        {"Dată": "15.09.2026", "Moment Zi": "Seara - Înainte de masă", "Glicemie": 102, "Sistolică": 120, "Diastolică": 80, "Puls": 0, "Observații": ""},
        {"Dată": "16.09.2026", "Moment Zi": "Dimineața - Înainte de masă", "Glicemie": 108, "Sistolică": 105, "Diastolică": 64, "Puls": 0, "Observații": ""},
        {"Dată": "16.09.2026", "Moment Zi": "Seara - Înainte de masă", "Glicemie": 111, "Sistolică": 0, "Diastolică": 0, "Puls": 0, "Observații": ""},
        {"Dată": "17.09.2026", "Moment Zi": "Dimineața - Înainte de masă", "Glicemie": 105, "Sistolică": 106, "Diastolică": 68, "Puls": 78, "Observații": ""},
        {"Dată": "17.09.2026", "Moment Zi": "Seara - Înainte de masă", "Glicemie": 100, "Sistolică": 106, "Diastolică": 62, "Puls": 84, "Observații": ""},
        {"Dată": "18.09.2026", "Moment Zi": "Dimineața - Înainte de masă", "Glicemie": 127, "Sistolică": 114, "Diastolică": 72, "Puls": 78, "Observații": "mancat tarziu, baton orez expandat cu ciocolata 0 zahar, chipsuri proteice, inghetata fara zahar"},
        {"Dată": "18.09.2026", "Moment Zi": "Dimineața - După masă", "Glicemie": 143, "Sistolică": 0, "Diastolică": 0, "Puls": 0, "Observații": ""},
        {"Dată": "18.09.2026", "Moment Zi": "Prânz - Înainte de masă", "Glicemie": 112, "Sistolică": 0, "Diastolică": 0, "Puls": 0, "Observații": ""},
        {"Dată": "18.09.2026", "Moment Zi": "Seara - După masă", "Glicemie": 112, "Sistolică": 0, "Diastolică": 0, "Puls": 0, "Observații": ""},
        {"Dată": "19.09.2026", "Moment Zi": "Dimineața - Înainte de masă", "Glicemie": 95, "Sistolică": 0, "Diastolică": 0, "Puls": 0, "Observații": ""},
        {"Dată": "19.09.2026", "Moment Zi": "Seara - După masă", "Glicemie": 150, "Sistolică": 0, "Diastolică": 0, "Puls": 0, "Observații": ""},
        {"Dată": "20.09.2026", "Moment Zi": "Dimineața - Înainte de masă", "Glicemie": 122, "Sistolică": 120, "Diastolică": 78, "Puls": 70, "Observații": ""},
        {"Dată": "20.09.2026", "Moment Zi": "Prânz - Înainte de masă", "Glicemie": 154, "Sistolică": 0, "Diastolică": 0, "Puls": 0, "Observații": "cartofi prajiti, paine alba"},
        {"Dată": "20.09.2026", "Moment Zi": "Seara - După masă", "Glicemie": 149, "Sistolică": 0, "Diastolică": 0, "Puls": 0, "Observații": "paine alba, pizza, prajitura"},
        {"Dată": "21.09.2026", "Moment Zi": "Dimineața - Înainte de masă", "Glicemie": 126, "Sistolică": 0, "Diastolică": 0, "Puls": 0, "Observații": ""},
        {"Dată": "21.09.2026", "Moment Zi": "Prânz - După masă", "Glicemie": 127, "Sistolică": 114, "Diastolică": 73, "Puls": 80, "Observații": ""},
        {"Dată": "21.09.2026", "Moment Zi": "Seara - Înainte de masă", "Glicemie": 87, "Sistolică": 118, "Diastolică": 73, "Puls": 67, "Observații": "Sarmale si inghetata fara zahar"},
        {"Dată": "22.09.2026", "Moment Zi": "Dimineața - Înainte de masă", "Glicemie": 118, "Sistolică": 109, "Diastolică": 72, "Puls": 75, "Observații": ""},
        {"Dată": "22.09.2026", "Moment Zi": "Seara - Înainte de masă", "Glicemie": 104, "Sistolică": 115, "Diastolică": 70, "Puls": 72, "Observații": ""},
        {"Dată": "23.09.2026", "Moment Zi": "Dimineața - Înainte de masă", "Glicemie": 148, "Sistolică": 119, "Diastolică": 68, "Puls": 73, "Observații": "mancat seara tarziu, inghetata fara zahar"},
        {"Dată": "23.09.2026", "Moment Zi": "Seara - După masă", "Glicemie": 102, "Sistolică": 116, "Diastolică": 73, "Puls": 81, "Observații": ""},
        {"Dată": "24.09.2026", "Moment Zi": "Dimineața - Înainte de masă", "Glicemie": 118, "Sistolică": 110, "Diastolică": 69, "Puls": 74, "Observații": ""},
        {"Dată": "24.09.2026", "Moment Zi": "Prânz - Înainte de masă", "Glicemie": 113, "Sistolică": 123, "Diastolică": 83, "Puls": 71, "Observații": ""},
        {"Dată": "24.09.2026", "Moment Zi": "Prânz - După masă", "Glicemie": 107, "Sistolică": 118, "Diastolică": 79, "Puls": 76, "Observații": ""}
    ]

    for r_def in initial_defaults:
        d_dt = parse_flexible_date(r_def["Dată"])
        m_val = r_def["Moment Zi"]
        mask = (df_template["Dată_dt"] == d_dt) & (df_template["Moment Zi"] == m_val)
        if mask.any():
            for col in ["Glicemie", "Sistolică", "Diastolică", "Puls"]:
                if col in r_def:
                    df_template.loc[mask, col] = r_def[col]
            if r_def.get("Observații"):
                df_template.loc[mask, "Observații"] = clean_obs(r_def["Observații"])

    if os.path.exists(DATA_FILE):
        try:
            df_saved = pd.read_csv(DATA_FILE)
            if not df_saved.empty:
                date_col_name = 'Data' if 'Data' in df_saved.columns else 'Dată'
                if "Sistolica" in df_saved.columns:
                    df_saved = df_saved.rename(columns={"Sistolica": "Sistolică", "Diastolica": "Diastolică", "Observatii": "Observații"})
                
                df_saved["Dată_dt"] = parse_flexible_date(df_saved[date_col_name])
                df_saved = df_saved.dropna(subset=["Dată_dt"])
                
                for _, row in df_saved.iterrows():
                    d_dt = row["Dată_dt"]
                    m_val = str(row.get("Moment Zi", ""))
                    mask = (df_template["Dată_dt"] == d_dt) & (df_template["Moment Zi"] == m_val)
                    if mask.any():
                        for col in ["Glicemie", "Sistolică", "Diastolică", "Puls"]:
                            if col in row and pd.notna(row[col]):
                                df_template.loc[mask, col] = row[col]
                        obs_val = clean_obs(row.get("Observații", ""))
                        if obs_val:
                            existing_obs = clean_obs(str(df_template.loc[mask, "Observații"].values[0]))
                            if existing_obs:
                                if obs_val not in existing_obs:
                                    df_template.loc[mask, "Observații"] = f"{existing_obs}, {obs_val}"
                            else:
                                df_template.loc[mask, "Observații"] = obs_val
        except Exception as e:
            print(f"Erore citire CSV: {e}")

    df_template["Moment_Cat"] = pd.Categorical(df_template["Moment Zi"], categories=moment_order, ordered=True)
    df_template = df_template.sort_values(by=["Dată_dt", "Moment_Cat"]).drop(columns=["Dată_dt", "Moment_Cat"]).reset_index(drop=True)
    df_template.to_csv(DATA_FILE, index=False)
    return df_template

if "local_df_v2" not in st.session_state:
    st.session_state.local_df_v2 = get_initial_data()

df = st.session_state.local_df_v2.copy()

date_col = "Dată"
moment_col = "Moment Zi"
col_glic = "Glicemie"
col_sis = "Sistolică"
col_dia = "Diastolică"
col_puls = "Puls"
col_obs = "Observații"

if date_col in df.columns and not df.empty:
    df[date_col] = parse_flexible_date(df[date_col])
    df["Moment_Cat"] = pd.Categorical(df[moment_col], categories=moment_order, ordered=True)
    df = df.dropna(subset=[date_col]).sort_values(by=[date_col, "Moment_Cat"]).drop(columns=["Moment_Cat"]).reset_index(drop=True)

def save_local_record(date_str, moment_str, glic_v, sis_v, dia_v, puls_v, obs_v):
    global df
    current_df = st.session_state.local_df_v2.copy()
    if col_obs in current_df.columns:
        current_df[col_obs] = current_df[col_obs].apply(clean_obs)
    else:
        current_df[col_obs] = ""

    if not current_df.empty and date_col in current_df.columns:
        current_df["Dată_str"] = parse_flexible_date(current_df[date_col]).dt.strftime("%d.%m.%Y")
        mask = (current_df["Dată_str"] == date_str) & (current_df[moment_col].astype(str) == moment_str)
        current_df = current_df.drop(columns=["Dată_str"])
    else:
        mask = pd.Series([False] * len(current_df))

    obs_clean_val = clean_obs(obs_v)
    
    st.session_state.action_history_stack.append({
        "old_df": st.session_state.local_df_v2.copy(),
        "desc": f"Salvare înregistrare {date_str} - {moment_str}"
    })

    if mask.any():
        current_df.loc[mask, col_glic] = glic_v
        current_df.loc[mask, col_sis] = sis_v
        current_df.loc[mask, col_dia] = dia_v
        current_df.loc[mask, col_puls] = puls_v
        current_df.loc[mask, col_obs] = obs_clean_val
    else:
        new_record = {
            date_col: parse_flexible_date(date_str),
            moment_col: moment_str, col_glic: glic_v, col_sis: sis_v, col_dia: dia_v, col_puls: puls_v,
            col_obs: obs_clean_val,
        }
        current_df = pd.concat([current_df, pd.DataFrame([new_record])], ignore_index=True)

    current_df[date_col] = parse_flexible_date(current_df[date_col])
    dates_unique = sorted(current_df[date_col].dropna().unique())
    full_rows = []
    for d in dates_unique:
        d_str = pd.to_datetime(d).strftime("%d.%m.%Y")
        df_d = current_df[current_df[date_col] == d]
        for m in moment_order:
            row_m = df_d[df_d[moment_col] == m]
            if not row_m.empty:
                r = row_m.iloc[0].to_dict()
                r[date_col] = parse_flexible_date(d_str)
                full_rows.append(r)
            else:
                full_rows.append({
                    date_col: parse_flexible_date(d_str),
                    moment_col: m,
                    col_glic: 0,
                    col_sis: 0,
                    col_dia: 0,
                    col_puls: 0,
                    col_obs: ""
                })
    current_df = pd.DataFrame(full_rows)
    current_df["Moment_Cat"] = pd.Categorical(current_df[moment_col], categories=moment_order, ordered=True)
    current_df = current_df.sort_values(by=[date_col, "Moment_Cat"]).drop(columns=["Moment_Cat"]).reset_index(drop=True)

    st.session_state.local_df_v2 = current_df
    try:
        df_to_save = current_df.copy()
        df_to_save[date_col] = parse_flexible_date(df_to_save[date_col]).dt.strftime("%d.%m.%Y")
        df_to_save.to_csv(DATA_FILE, index=False)
    except Exception as e:
        print(f"Erore: {e}")

def format_table_column(series):
    return series.astype(str).str.strip().replace(["0", "0.0", "nan", "None", "", "<NA>"], "")

def evaluate_glic(val, moment_zi=""):
    try:
        v = float(val)
        if v == 0 or pd.isna(v): return ""
        m_clean = remove_diacritics(str(moment_zi)).lower()
        if "dupa masa" in m_clean:
            t_min, t_max = st.session_state.settings.get("target_glic_post_min", 70), st.session_state.settings.get("target_glic_post_max", 160)
        else:
            t_min, t_max = st.session_state.settings.get("target_glic_min", 70), st.session_state.settings.get("target_glic_max", 120)

        if t_min <= v <= t_max: return "🟢 Normală"
        elif v < t_min: return "🔴 Mică"
        else: return "🔴 Mare"
    except:
        return ""

def evaluate_ta(sis_val, dia_val):
    try:
        s, d = float(sis_val), float(dia_val)
        if s == 0 or d == 0 or pd.isna(s) or pd.isna(d): return ""
        max_s, max_d = st.session_state.settings["target_ta_sis"], st.session_state.settings["target_ta_dia"]
        if s <= max_s and d <= max_d: return "🟢 Normală"
        else: return "🔴 Crescută"
    except:
        return ""

def evaluate_puls(val):
    try:
        v = float(val)
        if v == 0 or pd.isna(v): return ""
        if 60 <= v <= 100: return "🟢 Normal"
        elif v < 60: return "🔴 Scăzut"
        else: return "🔴 Ridicat"
    except:
        return ""

def is_glic_spike(val, moment_zi=""):
    try:
        v = float(val)
        if v == 0 or pd.isna(v): return False
        m_clean = remove_diacritics(str(moment_zi)).lower()
        if "dupa masa" in m_clean:
            t_max = st.session_state.settings.get("target_glic_post_max", 160)
        else:
            t_max = st.session_state.settings.get("target_glic_max", 120)
        return v > t_max
    except:
        return False

def is_ta_spike(sis_val, dia_val):
    try:
        s, d = float(sis_val), float(dia_val)
        if s == 0 or d == 0 or pd.isna(s) or pd.isna(d): return False
        max_s = st.session_state.settings.get("target_ta_sis", 120)
        max_d = st.session_state.settings.get("target_ta_dia", 80)
        return s > max_s or d > max_d
    except:
        return False

def is_puls_spike(val):
    try:
        v = float(val)
        if v == 0 or pd.isna(v): return False
        return v < 60 or v > 100
    except:
        return False

def color_status(val):
    if not isinstance(val, str) or not val.strip(): return ""
    if "🟢" in val: return "background-color: #047857; color: #ffffff; font-weight: bold; text-align: center;"
    elif "🔴" in val: return "background-color: #b91c1c; color: #ffffff; font-weight: bold; text-align: center;"
    return ""

def apply_color_styling(df_to_style, subset_cols):
    try:
        if hasattr(df_to_style.style, "map"): return df_to_style.style.map(color_status, subset=subset_cols)
        else: return df_to_style.style.applymap(color_status, subset=subset_cols)
    except:
        return df_to_style

# ==========================================
# SIDEBAR & FILTRARE
# ==========================================
st.sidebar.markdown(f"### 👤 **{st.session_state.user}**")
st.sidebar.markdown(f"Rol: <span class='role-badge'>{current_role}</span>", unsafe_allow_html=True)
st.sidebar.markdown("<br>", unsafe_allow_html=True)

st.sidebar.markdown("### 🔍 Filtre Date")
if not df.empty:
    df['Luna_An'] = df[date_col].dt.strftime('%m-%Y')
    luni_disponibile = df['Luna_An'].unique().tolist()
    
    toate_lunile = st.sidebar.checkbox("Afișează toate lunile", value=True)
    if not toate_lunile:
        filtru_luni = st.sidebar.multiselect("📅 Selectează luna/lunile", options=luni_disponibile, default=luni_disponibile)
        if len(filtru_luni) > 0:
            view_df = df[df['Luna_An'].isin(filtru_luni)].copy()
        else:
            view_df = pd.DataFrame(columns=df.columns)
            filtru_luni = []
    else:
        view_df = df.copy()
        filtru_luni = luni_disponibile
        
    filtru_luni_str = ", ".join(filtru_luni) if not toate_lunile else "Istoric Complet"
else:
    view_df = df.copy()
    filtru_luni_str = "Fără date"

st.sidebar.markdown("<br>", unsafe_allow_html=True)
if st.sidebar.button("🚪 Deconectare", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.user = None
    trigger_rerun()
st.sidebar.markdown("---")

# ==========================================
# ORGANIZARE TAB-URI
# ==========================================
tab_titles = ["📊 Jurnal & Grafice"]
if is_admin: tab_titles.append("➕ Adaugă / Suprascrie")
tab_titles.append("💊 Tratament")
if is_admin: tab_titles.append("📅 Programări")
tab_titles.extend(["📄 Raport PDF", "⚙️ Setări"])

tabs = st.tabs(tab_titles)
tab_dict = {title: tabs[i] for i, title in enumerate(tab_titles)}

# ----------------- TAB: JURNAL & GRAFICE -----------------
with tab_dict["📊 Jurnal & Grafice"]:
    st.markdown("### 📊 Tablou de Bord Medical")
    st.caption(f"Filtru curent: **{filtru_luni_str}**")

    if view_df.empty:
        st.info("📭 Nu există nicio înregistrare pentru selecția curentă.")
    else:
        avg_glic_str = ""
        if col_glic in view_df.columns:
            s_glic_all = pd.to_numeric(view_df[col_glic], errors="coerce").fillna(0).replace(0, None).dropna()
            if not s_glic_all.empty: avg_glic_str = f"{int(s_glic_all.mean())} mg/dL"

        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        with kpi1:
            val_glic = ""
            if col_glic in view_df.columns:
                s_glic = pd.to_numeric(view_df[col_glic], errors="coerce").fillna(0).replace(0, None).dropna()
                if not s_glic.empty: val_glic = f"{int(s_glic.iloc[-1])} mg/dL"
            st.markdown(f'<div class="metric-card"><div class="metric-label">🩸 ULTIMA GLICEMIE</div><div class="metric-value">{val_glic}</div></div>', unsafe_allow_html=True)
        with kpi2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">📊 MEDIE GLICEMIE</div><div class="metric-value">{avg_glic_str}</div></div>', unsafe_allow_html=True)
        with kpi3:
            val_sis, val_dia = "", ""
            if col_sis in view_df.columns:
                s_sis = pd.to_numeric(view_df[col_sis], errors="coerce").fillna(0).replace(0, None).dropna()
                if not s_sis.empty: val_sis = int(s_sis.iloc[-1])
            if col_dia in view_df.columns:
                s_dia = pd.to_numeric(view_df[col_dia], errors="coerce").fillna(0).replace(0, None).dropna()
                if not s_dia.empty: val_dia = int(s_dia.iloc[-1])
            val_ta_str = f"{val_sis}/{val_dia}" if val_sis != "" or val_dia != "" else ""
            st.markdown(f'<div class="metric-card"><div class="metric-label">🫀 ULTIMA TENSIUNE</div><div class="metric-value">{val_ta_str}</div></div>', unsafe_allow_html=True)
        with kpi4:
            val_puls = ""
            if col_puls in view_df.columns:
                s_puls = pd.to_numeric(view_df[col_puls], errors="coerce").fillna(0).replace(0, None).dropna()
                if not s_puls.empty: val_puls = f"{int(s_puls.iloc[-1])} bpm"
            st.markdown(f'<div class="metric-card"><div class="metric-label">💓 ULTIM PULS</div><div class="metric-value">{val_puls}</div></div>', unsafe_allow_html=True)
        with kpi5:
            st.markdown(f'<div class="metric-card"><div class="metric-label">📅 TOTAL (FILTRU)</div><div class="metric-value">{len(view_df)}</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        sub_tab_glic, sub_tab_ta, sub_tab_puls, sub_tab_all = st.tabs(["🩸 Glicemie & Analiză Spike", "🫀 Tensiune Arterială", "💓 Puls", "📋 Toate Datele"])
        
        # Filtrări separate pentru fiecare tab/grafic pentru a nu pierde datele de Tensiune sau Puls când Glicemia e 0
        view_df_glic = view_df.copy()
        if col_glic in view_df_glic.columns:
            view_df_glic["Glic_num"] = pd.to_numeric(view_df_glic[col_glic], errors="coerce").fillna(0)
            view_df_glic = view_df_glic[view_df_glic["Glic_num"] > 0].drop(columns=["Glic_num"])

        view_df_ta_sub = view_df.copy()
        if col_sis in view_df_ta_sub.columns and col_dia in view_df_ta_sub.columns:
            view_df_ta_sub["Sis_num"] = pd.to_numeric(view_df_ta_sub[col_sis], errors="coerce").fillna(0)
            view_df_ta_sub["Dia_num"] = pd.to_numeric(view_df_ta_sub[col_dia], errors="coerce").fillna(0)
            view_df_ta_sub = view_df_ta_sub[(view_df_ta_sub["Sis_num"] > 0) | (view_df_ta_sub["Dia_num"] > 0)].drop(columns=["Sis_num", "Dia_num"])

        view_df_puls_sub = view_df.copy()
        if col_puls in view_df_puls_sub.columns:
            view_df_puls_sub["Puls_num"] = pd.to_numeric(view_df_puls_sub[col_puls], errors="coerce").fillna(0)
            view_df_puls_sub = view_df_puls_sub[view_df_puls_sub["Puls_num"] > 0].drop(columns=["Puls_num"])

        with sub_tab_glic:
            st.markdown("ℹ️ **Legendă Glicemie:** 🔵 Albastru = Valoare în intervalul optim | 🔴 Roșu = Valoare crescută / Spike peste prag.")
            if not view_df_glic.empty:
                x_labels_glic = [f"{d.strftime('%d.%m')} ({m[:3]})" for d, m in zip(view_df_glic[date_col], view_df_glic[moment_col])]
                glic_vals = pd.to_numeric(view_df_glic[col_glic], errors="coerce").replace(0, None)
                moments = view_df_glic[moment_col].tolist() if moment_col in view_df_glic.columns else [""] * len(view_df_glic)

                spike_colors, spike_texts = [], []
                for v, m in zip(glic_vals, moments):
                    if is_glic_spike(v, m):
                        spike_colors.append("#dc2626")
                    else:
                        spike_colors.append("#38bdf8")
                    spike_texts.append(str(int(v)) if pd.notna(v) else "")

                fig_g = go.Figure()
                fig_g.add_trace(go.Scatter(
                    x=x_labels_glic, y=glic_vals, mode="lines+markers+text", name="Glicemie",
                    line=dict(color="#38bdf8", width=2.5),
                    marker=dict(size=10, color=spike_colors),
                    text=spike_texts, textposition="top center",
                    textfont=dict(size=9.5, color="#ffffff"),
                    texttemplate="%{text}",
                    connectgaps=True
                ))
                
                max_post = st.session_state.settings.get("target_glic_post_max", 160)
                max_pre = st.session_state.settings.get("target_glic_max", 120)
                fig_g.add_hline(y=max_post, line_dash="dash", line_color="#dc2626", annotation_text=f"Prag Max După Masă ({max_post})")
                fig_g.add_hline(y=max_pre, line_dash="dot", line_color="#f59e0b", annotation_text=f"Prag Max Înainte Masă ({max_pre})")
                
                max_glic_data = glic_vals.max() if not glic_vals.dropna().empty else 200
                upper_limit_g = max(250, int(max_glic_data) + 50)
                
                fig_g.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=40, r=40, t=50, b=120), xaxis=dict(tickangle=-45, dtick=1), yaxis=dict(range=[0, upper_limit_g]))
                st.plotly_chart(fig_g, use_container_width=True)

                cols_g = [date_col, moment_col, col_glic, col_obs]
                df_g_tab = view_df_glic[cols_g].copy()
                df_g_tab[date_col] = df_g_tab[date_col].dt.strftime("%d.%m.%Y")
                df_g_tab["Status Glicemie"] = df_g_tab.apply(lambda r: evaluate_glic(r[col_glic], r[moment_col]), axis=1)
                df_g_tab[col_glic] = format_table_column(df_g_tab[col_glic])
                df_g_tab[col_obs] = df_g_tab[col_obs].apply(clean_obs)
                df_g_tab = df_g_tab[[date_col, moment_col, col_glic, "Status Glicemie", col_obs]]
                st.dataframe(apply_color_styling(df_g_tab, ["Status Glicemie"]), use_container_width=True, hide_index=True)
            else:
                st.info("Nicio înregistrare cu glicemie pentru selecția curentă.")

        with sub_tab_ta:
            st.markdown("ℹ️ **Legendă Tensiune:** 🔵 Albastru/Indigo = Sistolică normală | 🟠 Portocaliu = Diastolică | 🔴 Roșu = Valori Crescute.")
            if not view_df_ta_sub.empty:
                x_labels_ta = [f"{d.strftime('%d.%m')} ({m[:3]})" for d, m in zip(view_df_ta_sub[date_col], view_df_ta_sub[moment_col])]
                sis_vals = pd.to_numeric(view_df_ta_sub[col_sis], errors="coerce").replace(0, None)
                dia_vals = pd.to_numeric(view_df_ta_sub[col_dia], errors="coerce").replace(0, None)
                
                sis_colors = ["#dc2626" if is_ta_spike(s, d) else "#2563eb" for s, d in zip(sis_vals, dia_vals)]
                dia_colors = ["#dc2626" if is_ta_spike(s, d) else "#f59e0b" for s, d in zip(sis_vals, dia_vals)]

                fig_ta = go.Figure()
                fig_ta.add_trace(go.Scatter(
                    x=x_labels_ta, y=sis_vals, mode="lines+markers+text", name="Sistolică", 
                    line=dict(color="#2563eb", width=2.5), marker=dict(size=10, color=sis_colors), 
                    text=sis_vals, textposition="top center", textfont=dict(size=10, color="#ffffff"), 
                    texttemplate="<b>%{text}</b>", connectgaps=True
                ))
                fig_ta.add_trace(go.Scatter(
                    x=x_labels_ta, y=dia_vals, mode="lines+markers+text", name="Diastolică", 
                    line=dict(color="#f59e0b", width=2.5), marker=dict(size=10, color=dia_colors), 
                    text=dia_vals, textposition="bottom center", textfont=dict(size=10, color="#ffffff"), 
                    texttemplate="<b>%{text}</b>", connectgaps=True
                ))
                
                max_s_target = st.session_state.settings.get("target_ta_sis", 120)
                fig_ta.add_hline(y=max_s_target, line_dash="dash", line_color="#dc2626", annotation_text=f"Prag Max Sistolică ({max_s_target})")
                
                fig_ta.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=40, r=40, t=50, b=120), xaxis=dict(tickangle=-45, dtick=1))
                st.plotly_chart(fig_ta, use_container_width=True)
                
                cols_t = [date_col, moment_col, col_sis, col_dia, col_obs]
                df_t_tab = view_df_ta_sub[cols_t].copy()
                df_t_tab[date_col] = df_t_tab[date_col].dt.strftime("%d.%m.%Y")
                df_t_tab["Status Tensiune"] = df_t_tab.apply(lambda r: evaluate_ta(r[col_sis], r[col_dia]), axis=1)
                df_t_tab[col_sis] = format_table_column(df_t_tab[col_sis])
                df_t_tab[col_dia] = format_table_column(df_t_tab[col_dia])
                df_t_tab[col_obs] = df_t_tab[col_obs].apply(clean_obs)
                df_t_tab = df_t_tab[[date_col, moment_col, col_sis, col_dia, "Status Tensiune", col_obs]]
                st.dataframe(apply_color_styling(df_t_tab, ["Status Tensiune"]), use_container_width=True, hide_index=True)
            else:
                st.info("Nicio înregistrare cu tensiune arterială pentru selecția curentă.")

        with sub_tab_puls:
            st.markdown("ℹ️ **Legendă Puls:** 🟢 Verde = Interval normal (60-100 bpm) | 🔴 Roșu = Puls în afara limitelor.")
            if not view_df_puls_sub.empty:
                x_labels_puls = [f"{d.strftime('%d.%m')} ({m[:3]})" for d, m in zip(view_df_puls_sub[date_col], view_df_puls_sub[moment_col])]
                puls_vals = pd.to_numeric(view_df_puls_sub[col_puls], errors="coerce").replace(0, None)
                puls_colors = ["#dc2626" if is_puls_spike(p) else "#10b981" for p in puls_vals]

                fig_p = go.Figure()
                fig_p.add_trace(go.Scatter(
                    x=x_labels_puls, y=puls_vals, mode="lines+markers+text", name="Puls (bpm)", 
                    line=dict(color="#10b981", width=2.5), marker=dict(size=10, color=puls_colors), 
                    text=puls_vals, textposition="top center", textfont=dict(size=10, color="#ffffff"), 
                    texttemplate="<b>%{text}</b>", connectgaps=True
                ))
                fig_p.add_hline(y=100, line_dash="dash", line_color="#dc2626", annotation_text="Limită Maximă Puls (100)")
                fig_p.add_hline(y=60, line_dash="dash", line_color="#dc2626", annotation_text="Limită Minimă Puls (60)")
                
                fig_p.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=40, r=40, t=50, b=120), xaxis=dict(tickangle=-45, dtick=1))
                st.plotly_chart(fig_p, use_container_width=True)
                
                cols_p = [date_col, moment_col, col_puls, col_obs]
                df_p_tab = view_df_puls_sub[cols_p].copy()
                df_p_tab[date_col] = df_p_tab[date_col].dt.strftime("%d.%m.%Y")
                df_p_tab["Status Puls"] = df_p_tab[col_puls].apply(evaluate_puls)
                df_p_tab[col_puls] = format_table_column(df_p_tab[col_puls])
                df_p_tab[col_obs] = df_p_tab[col_obs].apply(clean_obs)
                df_p_tab = df_p_tab[[date_col, moment_col, col_puls, "Status Puls", col_obs]]
                st.dataframe(apply_color_styling(df_p_tab, ["Status Puls"]), use_container_width=True, hide_index=True)
            else:
                st.info("Nicio înregistrare cu puls pentru selecția curentă.")

        with sub_tab_all:
            df_all = view_df.copy()
            # Afișăm rândurile care au cel puțin o valoare sau observație
            mask_has_data = pd.Series(False, index=df_all.index)
            for c in [col_glic, col_sis, col_dia, col_puls]:
                if c in df_all.columns:
                    mask_has_data = mask_has_data | (pd.to_numeric(df_all[c], errors="coerce").fillna(0) > 0)
            if col_obs in df_all.columns:
                mask_has_data = mask_has_data | (df_all[col_obs].astype(str).str.strip() != "")
            df_all = df_all[mask_has_data]

            df_all[date_col] = df_all[date_col].dt.strftime("%d.%m.%Y")
            if col_glic in df_all.columns:
                df_all["St. Glicemie"] = df_all.apply(lambda r: evaluate_glic(r[col_glic], r[moment_col]), axis=1)
                df_all[col_glic] = format_table_column(df_all[col_glic])
            if col_sis in df_all.columns and col_dia in df_all.columns:
                df_all["St. Tensiune"] = df_all.apply(lambda r: evaluate_ta(r[col_sis], r[col_dia]), axis=1)
                df_all[col_sis] = format_table_column(df_all[col_sis])
                df_all[col_dia] = format_table_column(df_all[col_dia])
            if col_puls in df_all.columns:
                df_all["St. Puls"] = df_all[col_puls].apply(evaluate_puls)
                df_all[col_puls] = format_table_column(df_all[col_puls])
            df_all[col_obs] = df_all[col_obs].apply(clean_obs)
            if 'Luna_An' in df_all.columns: df_all = df_all.drop(columns=['Luna_An'])
            
            cols_order_all = [date_col, moment_col, col_glic, "St. Glicemie", col_sis, col_dia, "St. Tensiune", col_puls, "St. Puls", col_obs]
            existing_cols_all = [c for c in cols_order_all if c in df_all.columns]
            df_all = df_all[existing_cols_all]
            
            st.dataframe(df_all, use_container_width=True, height=800, hide_index=True)

# ----------------- TAB: ADAUGĂ / SUPRASCRIE (ADMIN) -----------------
if is_admin and "➕ Adaugă / Suprascrie" in tab_dict:
    with tab_dict["➕ Adaugă / Suprascrie"]:
        st.markdown("### 📝 Formular Introducere / Suprascrie Măsurători")
        
        c_undo1, c_undo2 = st.columns([2, 5])
        with c_undo1:
            if st.session_state.action_history_stack:
                if st.button("↩️ Undo Ultima Modificare", type="secondary"):
                    last_action = st.session_state.action_history_stack.pop()
                    st.session_state.local_df_v2 = last_action["old_df"]
                    st.session_state.local_df_v2.to_csv(DATA_FILE, index=False)
                    st.success(f"S-a revenit cu succes! ({last_action['desc']})")
                    trigger_rerun()
        
        if "success_message" in st.session_state:
            st.success(st.session_state["success_message"])
            del st.session_state["success_message"]

        with st.container(border=True):
            selected_date = st.date_input("📅 Selectează Data", value=date.today(), key="input_date_picker")
            selected_moment = st.selectbox("🍽️ Momentul Măsurătorii", moment_order, key="input_moment_select")

            existing_row = pd.DataFrame()
            date_str = selected_date.strftime("%d.%m.%Y")
            has_real_record = False

            if not df.empty and date_col in df.columns and moment_col in df.columns:
                match = df[(parse_flexible_date(df[date_col]).dt.strftime("%d.%m.%Y") == date_str) & (df[moment_col] == selected_moment)]
                if not match.empty:
                    row_candidate = match.iloc[0]
                    g_check = float(row_candidate.get(col_glic, 0) or 0)
                    s_check = float(row_candidate.get(col_sis, 0) or 0)
                    d_check = float(row_candidate.get(col_dia, 0) or 0)
                    p_check = float(row_candidate.get(col_puls, 0) or 0)
                    o_check = clean_obs(row_candidate.get(col_obs, ""))
                    if g_check > 0 or s_check > 0 or d_check > 0 or p_check > 0 or o_check:
                        existing_row = row_candidate
                        has_real_record = True

            if has_real_record:
                st.warning(f"⚠️ Există deja o înregistrare pentru {date_str} - {selected_moment}. Valorile au fost încărcate pentru editare.")
            else:
                st.info(f"ℹ️ Nu există o înregistrare anterioară cu valori pentru {date_str} - {selected_moment}.")

            def get_val(col_name):
                if has_real_record and not existing_row.empty and col_name in existing_row:
                    try:
                        v = float(existing_row[col_name])
                        return int(v) if not pd.isna(v) else 0
                    except:
                        return 0
                return 0

            def get_obs():
                if has_real_record and not existing_row.empty and col_obs in existing_row:
                    return clean_obs(existing_row[col_obs])
                return ""

            session_form_key = f"form_state_{date_str}_{selected_moment}"
            if "last_form_key" not in st.session_state or st.session_state["last_form_key"] != session_form_key:
                st.session_state["last_form_key"] = session_form_key
                st.session_state["inp_glic"] = get_val(col_glic)
                st.session_state["inp_sis"] = get_val(col_sis)
                st.session_state["inp_dia"] = get_val(col_dia)
                st.session_state["inp_puls"] = get_val(col_puls)
                st.session_state["inp_obs"] = get_obs()
                for k in list(st.session_state.keys()):
                    if k.startswith("quick_"):
                        del st.session_state[k]

            all_known_foods = sorted(list(set([remove_diacritics(str(item)).lower() for items in st.session_state.food_categories.values() for item in items if pd.notna(item)])))

            c1, c2 = st.columns(2)
            with c1: 
                st.number_input("🩸 Glicemie (mg/dL) [0 = nemăsurat]", min_value=0, key="inp_glic")
            with c2:
                st.number_input("🫀 Tensiune Sistolică [0 = nemăsurat]", min_value=0, key="inp_sis")
                st.number_input("🫀 Tensiune Diastolică [0 = nemăsurat]", min_value=0, key="inp_dia")
                st.number_input("💓 Puls [0 = nemăsurat]", min_value=0, key="inp_puls")

            st.markdown("---")
            st.markdown("##### ⚡ Asistent Inteligent Mese & Indice Glicemic")
            
            valid_food_options = sorted(list(set([str(item) for items in st.session_state.food_categories.values() for item in items if pd.notna(item)])))
            search_food_input = st.selectbox(
                "🔍 Caută / Selectează rapid ingredient",
                options=[""] + valid_food_options,
                key="search_food_dropdown_instant"
            )
            
            cat_cols = st.columns(len(st.session_state.food_categories))
            search_query_clean = remove_diacritics(str(search_food_input).strip().lower())
            base_obs_text = clean_obs(st.session_state.get("inp_obs", get_obs())).lower()

            checked_foods_live = []
            for idx, (cat_name, items) in enumerate(st.session_state.food_categories.items()):
                with cat_cols[idx]:
                    st.caption(cat_name)
                    for item in sorted(items):
                        if pd.notna(item):
                            item_str = str(item)
                            item_clean = remove_diacritics(item_str).lower()
                            chk_key = f"quick_{cat_name}_{item_str}_{session_form_key}"
                            
                            if chk_key not in st.session_state:
                                is_already_present = item_clean in base_obs_text
                                is_default_checked = is_already_present or (search_query_clean and item_clean.startswith(search_query_clean))
                                st.session_state[chk_key] = bool(is_default_checked)

                            if st.checkbox(item_str, key=chk_key):
                                checked_foods_live.append(item_str.strip().lower())

            current_obs_val = st.session_state.get("inp_obs", "")
            existing_parts = [p.strip() for p in current_obs_val.split(",") if p.strip()]
            non_food_parts = [p for p in existing_parts if remove_diacritics(p).lower() not in all_known_foods]
            
            combined_parts = non_food_parts + sorted(list(set(checked_foods_live)))
            new_computed_obs = ", ".join([p for p in combined_parts if p])
            st.session_state["inp_obs"] = new_computed_obs

            st.text_area("✍️ Notițe / Observații", key="inp_obs")

            def handle_save_action():
                g_val = st.session_state.get("inp_glic", 0)
                s_val = st.session_state.get("inp_sis", 0)
                d_val = st.session_state.get("inp_dia", 0)
                p_val = st.session_state.get("inp_puls", 0)
                o_val = st.session_state.get("inp_obs", "")

                save_local_record(date_str, selected_moment, g_val, s_val, d_val, p_val, o_val)
                st.session_state["success_message"] = "✅ Salvare / Suprascrie efectuată cu succes!"
                trigger_rerun()

            st.markdown("---")
            st.button("💾 Salvează / Suprascrie Înregistrarea", type="primary", use_container_width=True, on_click=handle_save_action, key="bottom_save_btn")

# ----------------- TAB: TRATAMENT -----------------
with tab_dict["💊 Tratament"]:
    st.markdown("### 💊 Schemă Tratament Medical")
    st.dataframe(st.session_state.meds_df, use_container_width=True, hide_index=True)

    if is_admin:
        st.markdown("---")
        st.markdown("#### ⚙️ Gestiune Listă Tratament & Ștergere (Administrator)")
        col_m1, col_m2, col_m3 = st.columns(3)
        
        with col_m1:
            with st.container(border=True):
                st.markdown("##### ➕ Adaugă Nou")
                with st.form("add_med_form"):
                    m_nume = st.text_input("Nume")
                    m_doza = st.text_input("Doză")
                    m_orar = st.text_input("Orar / Frecvență")
                    m_obs_med = st.text_input("Observații")
                    if st.form_submit_button("Adaugă", type="primary"):
                        if m_nume:
                            new_row = pd.DataFrame([{"Medicament": m_nume, "Doză": m_doza, "Orar / Frecvență": m_orar, "Observații": m_obs_med}])
                            st.session_state.meds_df = pd.concat([st.session_state.meds_df, new_row], ignore_index=True)
                            add_history_entry("Adăugare", m_nume, f"Doză: {m_doza}, Orar: {m_orar}")
                            save_all_files()
                            st.success(f"{m_nume} adăugat!")
                            trigger_rerun()

        with col_m2:
            with st.container(border=True):
                st.markdown("##### ✏️ Editează Existent")
                if not st.session_state.meds_df.empty:
                    med_to_edit = st.selectbox("Selectează", st.session_state.meds_df["Medicament"].tolist(), key="edit_med_select")
                    med_data = st.session_state.meds_df[st.session_state.meds_df["Medicament"] == med_to_edit].iloc[0]
                    with st.form("edit_med_form"):
                        e_doza = st.text_input("Doză", value=med_data["Doză"])
                        e_orar = st.text_input("Orar / Frecvență", value=med_data["Orar / Frecvență"])
                        e_obs_med = st.text_input("Observații", value=med_data.get("Observații", ""))
                        if st.form_submit_button("Salvează Modificarea", type="primary"):
                            idx = st.session_state.meds_df.index[st.session_state.meds_df["Medicament"] == med_to_edit][0]
                            st.session_state.meds_df.loc[idx, "Doză"] = e_doza
                            st.session_state.meds_df.loc[idx, "Orar / Frecvență"] = e_orar
                            st.session_state.meds_df.loc[idx, "Observații"] = e_obs_med
                            add_history_entry("Modificare", med_to_edit, f"Doză: -> {e_doza}")
                            save_all_files()
                            st.success("Actualizat!")
                            trigger_rerun()

        with col_m3:
            with st.container(border=True):
                st.markdown("##### 🗑️ Șterge Medicament")
                if not st.session_state.meds_df.empty:
                    with st.form("delete_med_form"):
                        to_delete = st.selectbox("Selectează de șters", st.session_state.meds_df["Medicament"].tolist())
                        btn_del_med = st.form_submit_button("Șterge Definitiv", type="secondary")
                        if btn_del_med:
                            st.session_state.meds_df = st.session_state.meds_df[st.session_state.meds_df["Medicament"] != to_delete].reset_index(drop=True)
                            add_history_entry("Ștergere", to_delete, "Eliminat din schemă.")
                            save_all_files()
                            st.success(f"{to_delete} șters cu succes!")
                            trigger_rerun()

# ----------------- TAB: PROGRAMĂRI -----------------
if is_admin and "📅 Programări" in tab_dict:
    with tab_dict["📅 Programări"]:
        st.markdown("### 📅 Programări Medicale, Editare, Ștergere & Alerte")
        st.dataframe(st.session_state.prog_df, use_container_width=True, hide_index=True)

        st.markdown("---")
        col_p1, col_p2, col_p3 = st.columns(3)

        with col_p1:
            with st.container(border=True):
                st.markdown("#### ➕ Adaugă Programare")
                with st.form("form_add_prog"):
                    p_data = st.date_input("Dată", value=date.today())
                    p_ora = st.text_input("Ora (ex: 10:30)", value="10:00")
                    p_tip = st.text_input("Tip (ex: Analize, Consult)")
                    p_clinica = st.text_input("Clinică / Doctor")
                    p_alerta = st.text_input("Zile Alertă", value="1, 3")
                    p_obs = st.text_area("Observații")

                    if st.form_submit_button("Salvează", type="primary"):
                        if p_tip:
                            new_p = pd.DataFrame([{
                                "Dată": p_data.strftime("%Y-%m-%d"),
                                "Ora": p_ora,
                                "Tip": p_tip,
                                "Clinică": p_clinica,
                                "Zile_Alerta": p_alerta,
                                "Efectuat": "Nu",
                                "Observații": clean_obs(p_obs)
                            }])
                            st.session_state.prog_df = pd.concat([st.session_state.prog_df, new_p], ignore_index=True)
                            save_all_files()
                            st.success("Programare salvată!")
                            trigger_rerun()

        with col_p2:
            with st.container(border=True):
                st.markdown("#### ✏️ Editează / Șterge / Status")
                if not st.session_state.prog_df.empty:
                    prog_indices = list(st.session_state.prog_df.index)
                    prog_labels = [f"{row.get('Dată', '')} {row.get('Ora', '10:00')} - {row.get('Tip', '')} ({row.get('Clinică', '')})" for _, row in st.session_state.prog_df.iterrows()]
                    selected_prog_idx = st.selectbox("Alege programare", prog_indices, format_func=lambda i: prog_labels[i])
                    
                    row_data = st.session_state.prog_df.loc[selected_prog_idx]
                    
                    with st.form("form_edit_prog"):
                        try:
                            default_dt = datetime.strptime(str(row_data.get("Dată", date.today().strftime("%Y-%m-%d"))), "%Y-%m-%d").date()
                        except:
                            default_dt = date.today()
                            
                        e_p_data = st.date_input("Dată Nouă", value=default_dt)
                        e_p_ora = st.text_input("Ora Nouă", value=str(row_data.get("Ora", "10:00")))
                        e_p_tip = st.text_input("Tip Nou", value=str(row_data.get("Tip", "")))
                        e_p_clinica = st.text_input("Clinică Nouă", value=str(row_data.get("Clinică", "")))
                        e_p_alerta = st.text_input("Zile Alertă Noi", value=str(row_data.get("Zile_Alerta", "1, 3")))
                        
                        stat_opts = ["Nu", "Da (Done)"]
                        curr_stat = str(row_data.get("Efectuat", "Nu"))
                        e_p_efectuat = st.selectbox("Status", stat_opts, index=1 if "Da" in curr_stat else 0)
                        
                        e_p_obs = st.text_area("Observații Noi", value=str(row_data.get("Observații", "")))
                        
                        col_sub1, col_sub2 = st.columns(2)
                        with col_sub1:
                            btn_mod = st.form_submit_button("💾 Salvează Modificări", type="primary")
                        with col_sub2:
                            btn_del = st.form_submit_button("🗑️ Șterge Programarea", type="secondary")
                            
                        if btn_mod:
                            st.session_state.prog_df.loc[selected_prog_idx, "Dată"] = e_p_data.strftime("%Y-%m-%d")
                            st.session_state.prog_df.loc[selected_prog_idx, "Ora"] = e_p_ora
                            st.session_state.prog_df.loc[selected_prog_idx, "Tip"] = e_p_tip
                            st.session_state.prog_df.loc[selected_prog_idx, "Clinică"] = e_p_clinica
                            st.session_state.prog_df.loc[selected_prog_idx, "Zile_Alerta"] = e_p_alerta
                            st.session_state.prog_df.loc[selected_prog_idx, "Efectuat"] = "Da" if "Da" in e_p_efectuat else "Nu"
                            st.session_state.prog_df.loc[selected_prog_idx, "Observații"] = clean_obs(e_p_obs)
                            save_all_files()
                            st.success("Programare actualizată!")
                            trigger_rerun()
                            
                        if btn_del:
                            st.session_state.prog_df = st.session_state.prog_df.drop(selected_prog_idx).reset_index(drop=True)
                            save_all_files()
                            st.success("Programare ștersă!")
                            trigger_rerun()

        with col_p3:
            with st.container(border=True):
                st.markdown("#### 📨 Trimitere & Test iCloud")
                destinatar_auto = st.text_input("Email Destinatar", value=st.session_state.settings.get("email_sender", ""))
                
                if st.button("🚀 Trimite Alerte Automat Acum", type="primary"):
                    if not destinatar_auto:
                        st.error("Completează adresa de email.")
                    else:
                        trimis_ok = 0
                        azi = datetime.now().date()
                        mesaj_final = "🔔 ALERTE AUTOMATE PROGRAMĂRI MEDICALE - HEALTHTRACK PRO\n\n"
                        
                        for _, row in st.session_state.prog_df.iterrows():
                            if str(row.get("Efectuat", "Nu")) == "Da":
                                continue
                            try:
                                p_date = datetime.strptime(str(row["Dată"]), "%Y-%m-%d").date()
                                zile_ramase = (p_date - azi).days
                                zile_alerta_list = [int(x.strip()) for x in str(row["Zile_Alerta"]).split(",") if x.strip().isdigit()]
                                
                                if zile_ramase in zile_alerta_list or zile_ramase == 0:
                                    mesaj_final += f"• {row['Tip']} la {row['Clinică']} pe data de {row['Dată']} ora {row.get('Ora', '')} (Rămas {zile_ramase} zile!)\n"
                                    trimis_ok += 1
                            except:
                                pass
                        
                        if trimis_ok > 0:
                            succes, rez = trimite_email_cu_multiple_atasamente(destinatar_auto, "🔔 Notificare Programare Medicală", mesaj_final, {
                                "date_medicale.csv": DATA_FILE,
                                "medicamente.csv": MEDS_FILE,
                                "programari_medicale.csv": PROG_FILE
                            })
                            if succes:
                                st.success("Notificările au fost trimise prin iCloud împreună cu fișierele!")
                            else:
                                st.error(rez)
                        else:
                            st.info("Nicio programare activă nu necesită alertă astăzi.")

# ----------------- TAB: SETĂRI & ADMIN -----------------
with tab_dict["⚙️ Setări"]:
    st.markdown("### ⚙️ Setări Generale, Test Conexiune iCloud & Gestiune Utilizatori")
    
    if is_admin:
        col_u1, col_u2 = st.columns(2)
        with col_u1:
            with st.container(border=True):
                st.markdown("#### ➕ Adaugă Utilizator Nou")
                with st.form("form_new_user"):
                    new_u_name = st.text_input("Nume Utilizator Nou")
                    new_u_pass = st.text_input("Parolă", type="password")
                    new_u_role = st.selectbox("Rol", ["Membru", "Doctor", "Administrator"])
                    if st.form_submit_button("Creează Cont", type="primary"):
                        if new_u_name and new_u_pass:
                            if new_u_name in st.session_state.users:
                                st.error("Utilizatorul există deja!")
                            else:
                                st.session_state.users[new_u_name] = {"pass": new_u_pass, "role": new_u_role}
                                st.success(f"Utilizatorul {new_u_name} a fost creat!")
                                trigger_rerun()
                        else:
                            st.warning("Completează numele și parola.")

        with col_u2:
            with st.container(border=True):
                st.markdown("#### 👥 Editează / Șterge Utilizator")
                user_list = list(st.session_state.users.keys())
                target_user = st.selectbox("Selectează utilizator", user_list, key="sel_user_manage")
                
                with st.form("form_manage_user"):
                    current_target_role = st.session_state.users[target_user].get("role", "Membru")
                    role_options = ["Membru", "Doctor", "Administrator"]
                    updated_role = st.selectbox("Schimbă Rol", role_options, index=role_options.index(current_target_role))
                    updated_pass = st.text_input("Parolă Nouă (opțional)", type="password", key="pass_edit_user")
                    
                    c_ub1, c_ub2 = st.columns(2)
                    with c_ub1:
                        btn_save_u = st.form_submit_button("💾 Salvează Modificări", type="primary")
                    with c_ub2:
                        btn_del_u = st.form_submit_button("🗑️ Șterge Utilizator", type="secondary")
                        
                    if btn_save_u:
                        st.session_state.users[target_user]["role"] = updated_role
                        if updated_pass:
                            st.session_state.users[target_user]["pass"] = updated_pass
                        st.success(f"Detaliile pentru {target_user} au fost actualizate!")
                        trigger_rerun()
                        
                    if btn_del_u:
                        if target_user == "Alex" and len(st.session_state.users) <= 1:
                            st.error("Nu poți șterge administratorul principal!")
                        else:
                            del st.session_state.users[target_user]
                            st.success(f"Utilizatorul {target_user} a fost șters!")
                            trigger_rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("#### 🍎 Gestiune Elemente Mese & Indice Glicemic")
            fc_cat = st.selectbox("Selectează Categoria", list(st.session_state.food_categories.keys()))
            
            c_f1, c_f2 = st.columns(2)
            with c_f1:
                new_food_item = st.text_input("Adaugă ingredient nou")
                if st.button("➕ Adaugă în Categorie"):
                    if new_food_item and new_food_item.strip():
                        item_clean = remove_diacritics(new_food_item).strip().lower()
                        existing_all = [remove_diacritics(str(x)).lower() for x in st.session_state.food_categories[fc_cat] if pd.notna(x)]
                        if item_clean in existing_all:
                            st.warning(f"⚠️ Ingredientul există deja în această categorie!")
                        else:
                            st.session_state.food_categories[fc_cat].append(item_clean)
                            save_custom_foods()
                            st.success(f"Ingredientul '{item_clean}' a fost adăugat!")
                            trigger_rerun()
            with c_f2:
                all_items_flat = sorted(list(set([str(x) for x in st.session_state.food_categories[fc_cat] if pd.notna(x)])))
                if all_items_flat:
                    del_food_item = st.selectbox("Selectează ingredient de șters", all_items_flat, key="del_food_select")
                    if st.button("🗑️ Șterge Ingredientul Selectat"):
                        st.session_state.food_categories[fc_cat].remove(del_food_item)
                        save_custom_foods()
                        st.success(f"Ingredientul '{del_food_item}' a fost șters!")
                        trigger_rerun()
                else:
                    st.info("Niciun element în categorie.")

    st.markdown("---")
    col_set1, col_set2 = st.columns(2)
    with col_set1:
        st.markdown("#### ✉️ Configurare Server iCloud Mail & Test Zilnic")
        
        entered_sender = st.text_input("Adresa ta de iCloud (expeditor)", value=st.session_state.settings.get("email_sender", ""))
        entered_password = st.text_input("Parolă specifică de aplicație iCloud (App-Specific Password)", type="password", value=st.session_state.settings.get("email_password", ""))
        
        if st.button("💾 Salvează Datele Email Permanent", type="primary"):
            st.session_state.settings["email_sender"] = entered_sender
            st.session_state.settings["email_password"] = entered_password
            save_persisted_settings(st.session_state.settings)
            st.success("✅ Datele de email au fost salvate permanent pe disc!")

        st.markdown("<small>💡 *Notă: Folosește o App-Specific Password generată din contul tău Apple ID.*</small>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        if os.path.exists(BACKUP_LOG_FILE):
            try:
                with open(BACKUP_LOG_FILE, "r") as f:
                    last_ok = f.read().strip()
                st.success(f"✅ Ultimul backup automat reușit: {last_ok}")
            except:
                pass
        else:
            st.info("ℹ️ Nu a fost trimis încă niciun backup automat.")

        if os.path.exists(BACKUP_ERROR_LOG_FILE):
            try:
                with open(BACKUP_ERROR_LOG_FILE, "r") as f:
                    last_err = f.read().strip()
                st.error(f"❌ Ultima eroare la backup automat: {last_err}")
            except:
                pass

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("🔌 Forțează Trimite Backup Complet Acum (Toate Fișierele)", type="primary"):
            test_dest = st.session_state.settings.get("email_sender", "")
            if not test_dest:
                st.error("Completează și salvează mai întâi adresa de email a expeditorului.")
            else:
                temp_test_file = "temp_test_backup.csv"
                temp_meds_backup = "temp_meds_backup.csv"
                temp_prog_backup = "temp_prog_backup.csv"
                attachments = {}
                fisiere_incluse = []
                fisiere_lipsa = []

                df_test_cron = get_chronological_backup_df()
                if not df_test_cron.empty:
                    df_test_cron.to_csv(temp_test_file, index=False)
                    attachments["backup_date_medicale.csv"] = temp_test_file
                    fisiere_incluse.append("backup_date_medicale.csv")
                elif os.path.exists(DATA_FILE):
                    try:
                        df_raw = pd.read_csv(DATA_FILE)
                        for col in df_raw.columns:
                            df_raw[col] = df_raw[col].apply(lambda x: remove_diacritics(str(x)) if pd.notna(x) and str(x).strip() not in ["nan", "None", ""] else "")
                        df_raw.columns = [remove_diacritics(c) for c in df_raw.columns]
                        df_raw.to_csv(temp_test_file, index=False)
                        attachments["backup_date_medicale.csv"] = temp_test_file
                        fisiere_incluse.append("backup_date_medicale.csv (date brute)")
                    except:
                        fisiere_lipsa.append("backup_date_medicale.csv")
                else:
                    fisiere_lipsa.append("backup_date_medicale.csv")

                if os.path.exists(MEDS_FILE):
                    try:
                        df_m_temp = pd.read_csv(MEDS_FILE)
                        for col in df_m_temp.columns:
                            df_m_temp[col] = df_m_temp[col].apply(lambda x: remove_diacritics(str(x)) if pd.notna(x) and str(x).strip() not in ["nan", "None", ""] else "")
                        df_m_temp.columns = [remove_diacritics(c) for c in df_m_temp.columns]
                        df_m_temp.to_csv(temp_meds_backup, index=False)
                        attachments["medicamente.csv"] = temp_meds_backup
                        fisiere_incluse.append("medicamente.csv")
                    except:
                        attachments["medicamente.csv"] = MEDS_FILE
                        fisiere_incluse.append("medicamente.csv")
                else:
                    fisiere_lipsa.append("medicamente.csv")

                if os.path.exists(PROG_FILE):
                    try:
                        df_p_temp = pd.read_csv(PROG_FILE)
                        for col in df_p_temp.columns:
                            df_p_temp[col] = df_p_temp[col].apply(lambda x: remove_diacritics(str(x)) if pd.notna(x) and str(x).strip() not in ["nan", "None", ""] else "")
                        df_p_temp.columns = [remove_diacritics(c) for c in df_p_temp.columns]
                        df_p_temp.to_csv(temp_prog_backup, index=False)
                        attachments["programari_medicale.csv"] = temp_prog_backup
                        fisiere_incluse.append("programari_medicale.csv")
                    except:
                        attachments["programari_medicale.csv"] = PROG_FILE
                        fisiere_incluse.append("programari_medicale.csv")
                else:
                    fisiere_lipsa.append("programari_medicale.csv")

                success_t, msg_t = trimite_email_cu_multiple_atasamente(
                    test_dest,
                    f"🧪 Test Forțat / Backup HealthTrack Pro ({len(fisiere_incluse)}/3 fișiere)",
                    f"Salut! Acesta este un email de test forțat.\n\nFișiere incluse ({len(fisiere_incluse)}/3): {', '.join(fisiere_incluse) if fisiere_incluse else 'niciunul'}\n"
                    + (f"⚠️ Fișiere NEincluse: {', '.join(fisiere_lipsa)}\n" if fisiere_lipsa else ""),
                    attachments
                )
                
                if os.path.exists(temp_test_file): os.remove(temp_test_file)
                if os.path.exists(temp_meds_backup): os.remove(temp_meds_backup)
                if os.path.exists(temp_prog_backup): os.remove(temp_prog_backup)

                if success_t:
                    with open(BACKUP_LOG_FILE, "w") as f:
                        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M')} ({len(fisiere_incluse)}/3 fișiere)")
                    if fisiere_lipsa:
                        st.warning(f"⚠️ Trimis, dar incomplet — {len(fisiere_incluse)}/3 fișiere. Lipsă: {', '.join(fisiere_lipsa)}")
                    else:
                        st.success(f"✅ Emailul de backup a fost trimis cu succes prin iCloud, cu toate cele 3 fișiere!")
                else:
                    st.error(f"❌ {msg_t}")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 💾 Backup Manual (CSV Cronologic Date Medicale)")
        df_backup_cron = get_chronological_backup_df()
        if not df_backup_cron.empty:
            csv_data = df_backup_cron.to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 Descarcă Backup CSV Cronologic", data=csv_data, file_name="backup_date_medicale.csv", mime="text/csv", use_container_width=True)

    with col_set2:
        st.markdown("#### 🎯 Valori Țintă Medicale")
        st.session_state.settings["target_glic_min"] = st.number_input("Glicemie Min Înainte Masă", value=st.session_state.settings["target_glic_min"], disabled=not is_admin)
        st.session_state.settings["target_glic_max"] = st.number_input("Glicemie Max Înainte Masă", value=st.session_state.settings["target_glic_max"], disabled=not is_admin)
        st.session_state.settings["target_glic_post_max"] = st.number_input("Glicemie Max După Masă", value=st.session_state.settings["target_glic_post_max"], disabled=not is_admin)
        st.session_state.settings["target_ta_sis"] = st.number_input("TA Sistolică Max Țintă", value=st.session_state.settings["target_ta_sis"], disabled=not is_admin)
        st.session_state.settings["target_ta_dia"] = st.number_input("TA Diastolică Max Țintă", value=st.session_state.settings["target_ta_dia"], disabled=not is_admin)

# ----------------- TAB: RAPORT PDF -----------------
with tab_dict["📄 Raport PDF"]:
    st.markdown("### 📄 Generare Raport PDF Personalizat și Profesional")
    st.markdown(f"Raportul va include datele conform filtrului aplicat: **{filtru_luni_str}**.")

    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        opt_glic = st.checkbox("Include Grafic Glicemie 🩸", value=True)
        opt_ta = st.checkbox("Include Grafic Tensiune Arterială 🫀", value=True)
    with col_opt2:
        opt_puls = st.checkbox("Include Grafic Puls 💓", value=True)
        opt_tabele = st.checkbox("Include Tabelul Centralizator (Doar Valori Măsurate) 📋", value=True)

    def generate_pdf_chart_glic(x_vals, y_vals, moments_list, title, ylabel, color_hex):
        plt.figure(figsize=(9.5, 3.4))
        for i in range(len(y_vals) - 1):
            x_seg = [x_vals[i], x_vals[i+1]]
            y_seg = [y_vals[i], y_vals[i+1]]
            is_spike1 = is_glic_spike(y_vals[i], moments_list[i])
            is_spike2 = is_glic_spike(y_vals[i+1], moments_list[i+1])
            seg_color = "#dc2626" if (is_spike1 or is_spike2) else color_hex
            plt.plot(x_seg, y_seg, linestyle="-", color=seg_color, linewidth=2.5)

        for xi, yi, m in zip(x_vals, y_vals, moments_list):
            if yi > 0:
                is_spike = is_glic_spike(yi, m)
                dot_color = "#dc2626" if is_spike else color_hex
                plt.plot(xi, yi, marker="o", markersize=6.5, color=dot_color)
                plt.annotate(str(int(yi)), (xi, yi), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=7.5, fontweight="bold", bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=dot_color, alpha=0.95))
        
        max_y = max(y_vals) if y_vals and max(y_vals) > 0 else 200
        plt.ylim(0, max(max_y * 1.25, 220))
        plt.title(title + " | Legenda: Albastru = Normal, Rosu = Spike / Afara pragului", fontsize=9.5, fontweight="bold", color="#1e3a8a", pad=15)
        plt.ylabel(ylabel, fontsize=9, fontweight="bold")
        plt.xticks(rotation=35, fontsize=7.5, ha="right")
        plt.yticks(fontsize=8)
        plt.grid(True, linestyle=":", alpha=0.7)
        plt.tight_layout()

        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format="png", dpi=250)
        plt.close()
        img_buffer.seek(0)
        return img_buffer

    def generate_pdf_chart_ta(x_vals, sis_vals, dia_vals, title):
        plt.figure(figsize=(9.5, 3.4))
        for i in range(len(sis_vals) - 1):
            x_seg = [x_vals[i], x_vals[i+1]]
            s_seg = [sis_vals[i], sis_vals[i+1]]
            d_seg = [dia_vals[i], dia_vals[i+1]]
            is_spike1 = is_ta_spike(sis_vals[i], dia_vals[i])
            is_spike2 = is_ta_spike(sis_vals[i+1], dia_vals[i+1])
            s_color = "#dc2626" if (is_spike1 or is_spike2) else "#2563eb"
            d_color = "#dc2626" if (is_spike1 or is_spike2) else "#f59e0b"
            plt.plot(x_seg, s_seg, linestyle="-", color=s_color, linewidth=2.5)
            plt.plot(x_seg, d_seg, linestyle="-", color=d_color, linewidth=2.5)
        
        for xi, s, d in zip(x_vals, sis_vals, dia_vals):
            if s > 0 and d > 0:
                is_spike = is_ta_spike(s, d)
                s_color = "#dc2626" if is_spike else "#2563eb"
                d_color = "#dc2626" if is_spike else "#f59e0b"
                plt.plot(xi, s, marker="o", markersize=6.5, color=s_color)
                plt.annotate(f"S:{int(s)}", (xi, s), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=7, fontweight="bold", bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=s_color, alpha=0.95))
                plt.plot(xi, d, marker="o", markersize=6.5, color=d_color)
                plt.annotate(f"D:{int(d)}", (xi, d), textcoords="offset points", xytext=(0, -12), ha="center", fontsize=7, fontweight="bold", bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=d_color, alpha=0.95))
                
        all_ta = [s for s in sis_vals if s > 0] + [d for d in dia_vals if d > 0]
        max_t = max(all_ta) if all_ta else 180
        plt.ylim(0, max(max_t * 1.25, 200))
        plt.title(title + " | Legenda: Albastru = Sistolica, Galben = Diastolica, Rosu = Crescuta", fontsize=9.5, fontweight="bold", color="#1e3a8a", pad=15)
        plt.ylabel("mmHg", fontsize=9, fontweight="bold")
        plt.xticks(rotation=35, fontsize=7.5, ha="right")
        plt.yticks(fontsize=8)
        plt.grid(True, linestyle=":", alpha=0.7)
        plt.tight_layout()

        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format="png", dpi=250)
        plt.close()
        img_buffer.seek(0)
        return img_buffer

    def generate_pdf_chart_puls(x_vals, puls_vals, title):
        plt.figure(figsize=(9.5, 3.4))
        for i in range(len(puls_vals) - 1):
            x_seg = [x_vals[i], x_vals[i+1]]
            p_seg = [puls_vals[i], puls_vals[i+1]]
            is_spike1 = is_puls_spike(puls_vals[i])
            is_spike2 = is_puls_spike(puls_vals[i+1])
            p_color = "#dc2626" if (is_spike1 or is_spike2) else "#10b981"
            plt.plot(x_seg, p_seg, linestyle="-", color=p_color, linewidth=2.5)

        for xi, p in zip(x_vals, puls_vals):
            if p > 0:
                is_spike = is_puls_spike(p)
                p_color = "#dc2626" if is_spike else "#10b981"
                plt.plot(xi, p, marker="o", markersize=6.5, color=p_color)
                plt.annotate(str(int(p)), (xi, p), textcoords="offset points", xytext=(0, 7), ha="center", fontsize=7.5, fontweight="bold", bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=p_color, alpha=0.95))
                
        max_p = max(puls_vals) if puls_vals and max(puls_vals) > 0 else 100
        plt.ylim(30, max(max_p * 1.25, 140))
        plt.title(title + " | Legenda: Verde = Normal (60-100), Rosu = Afara intervalului", fontsize=9.5, fontweight="bold", color="#1e3a8a", pad=15)
        plt.ylabel("bpm", fontsize=9, fontweight="bold")
        plt.xticks(rotation=35, fontsize=7.5, ha="right")
        plt.yticks(fontsize=8)
        plt.grid(True, linestyle=":", alpha=0.7)
        plt.tight_layout()

        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format="png", dpi=250)
        plt.close()
        img_buffer.seek(0)
        return img_buffer

    def make_pdf_report(data_frame, include_glic, include_ta, include_puls, include_tables):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
        story = []
        styles = getSampleStyleSheet()

        title_text = remove_diacritics("RAPORT MEDICAL DE MONITORIZARE - HEALTHTRACK PRO")
        date_text = remove_diacritics(f"Generat la: {datetime.now().strftime('%d.%m.%Y %H:%M')} | Perioada: {filtru_luni_str}")

        story.append(Paragraph(f"<b>{title_text}</b>", ParagraphStyle("TitleStyle", parent=styles["Heading1"], fontSize=13, textColor=colors.HexColor("#1e3a8a"), alignment=1, spaceAfter=12)))
        story.append(Paragraph(date_text, ParagraphStyle("DateStyle", parent=styles["Normal"], alignment=1, spaceAfter=15)))

        if not data_frame.empty:
            df_pdf_measured = data_frame.copy()
            # Doar rândurile cu măsurători efective
            mask_pdf = pd.Series(False, index=df_pdf_measured.index)
            for c in [col_glic, col_sis, col_dia, col_puls]:
                if c in df_pdf_measured.columns:
                    mask_pdf = mask_pdf | (pd.to_numeric(df_pdf_measured[c], errors="coerce").fillna(0) > 0)
            if col_obs in df_pdf_measured.columns:
                mask_pdf = mask_pdf | (df_pdf_measured[col_obs].astype(str).str.strip() != "")
            df_pdf_measured = df_pdf_measured[mask_pdf]

            if not df_pdf_measured.empty:
                x_data = [f"{d.strftime('%d.%m')} ({m[:3]})" for d, m in zip(df_pdf_measured[date_col], df_pdf_measured[moment_col])]
                moments_arr = df_pdf_measured[moment_col].tolist() if moment_col in df_pdf_measured.columns else [""] * len(df_pdf_measured)
                
                if include_glic and col_glic in df_pdf_measured.columns:
                    g_vals = pd.to_numeric(df_pdf_measured[col_glic], errors='coerce').fillna(0).tolist()
                    story.append(Paragraph("Evolutie Glicemie", styles["Heading2"]))
                    img_buf = generate_pdf_chart_glic(x_data, g_vals, moments_arr, "Glicemie (mg/dL)", "mg/dL", "#38bdf8")
                    story.append(Image(img_buf, width=480, height=170))
                    story.append(Spacer(1, 10))
                    
                if include_ta and col_sis in df_pdf_measured.columns and col_dia in df_pdf_measured.columns:
                    s_vals = pd.to_numeric(df_pdf_measured[col_sis], errors='coerce').fillna(0).tolist()
                    d_vals = pd.to_numeric(df_pdf_measured[col_dia], errors='coerce').fillna(0).tolist()
                    story.append(Paragraph("Evolutie Tensiune Arteriala", styles["Heading2"]))
                    img_buf = generate_pdf_chart_ta(x_data, s_vals, d_vals, "Tensiune Arteriala (mmHg)")
                    story.append(Image(img_buf, width=480, height=170))
                    story.append(Spacer(1, 10))
                    
                if include_puls and col_puls in df_pdf_measured.columns:
                    p_vals = pd.to_numeric(df_pdf_measured[col_puls], errors='coerce').fillna(0).tolist()
                    story.append(Paragraph("Evolutie Puls", styles["Heading2"]))
                    img_buf = generate_pdf_chart_puls(x_data, p_vals, "Puls (bpm)")
                    story.append(Image(img_buf, width=480, height=170))
                    story.append(Spacer(1, 10))

                if include_tables:
                    story.append(Paragraph("Date Tabelare si Observatii", styles["Heading2"]))
                    table_data = [["Data", "Moment", "Glic", "TA", "Puls", "Observatii"]]
                    
                    t_style = [
                        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0284c7")),
                        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                        ('ALIGN', (5,1), (5,-1), 'LEFT'),
                        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0,0), (-1,0), 9),
                        ('FONTSIZE', (0,1), (-1,-1), 8),
                        ('TOPPADDING', (0,0), (-1,0), 7),
                        ('BOTTOMPADDING', (0,0), (-1,0), 7),
                        ('TOPPADDING', (0,1), (-1,-1), 6),
                        ('BOTTOMPADDING', (0,1), (-1,-1), 6),
                        ('LEFTPADDING', (0,0), (-1,-1), 6),
                        ('RIGHTPADDING', (0,0), (-1,-1), 6),
                        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
                    ]
                    
                    obs_style_pdf = ParagraphStyle(
                        'ObsStylePDF',
                        parent=styles['Normal'],
                        fontName='Helvetica',
                        fontSize=8,
                        leading=11,
                        textColor=colors.HexColor("#1e293b")
                    )

                    r_idx = 1
                    for _, row in df_pdf_measured.iterrows():
                        dt_str = row[date_col].strftime("%d.%m.%Y")
                        mm = remove_diacritics(str(row.get(moment_col, "")))
                        obs_val = clean_obs(row.get(col_obs, ""))
                        obs_str = remove_diacritics(obs_val)
                        obs_paragraph = Paragraph(obs_str, obs_style_pdf)
                        
                        glic_v = row.get(col_glic, 0)
                        sis_v = row.get(col_sis, 0)
                        dia_v = row.get(col_dia, 0)
                        puls_v = row.get(col_puls, 0)
                        
                        g_str = str(int(glic_v)) if pd.notna(glic_v) and float(glic_v)>0 else ""
                        ta_str = f"{int(sis_v)}/{int(dia_v)}" if pd.notna(sis_v) and float(sis_v)>0 else ""
                        p_str = str(int(puls_v)) if pd.notna(puls_v) and float(puls_v)>0 else ""
                        
                        table_data.append([dt_str, mm, g_str, ta_str, p_str, obs_paragraph])
                        
                        if r_idx % 2 == 0:
                            t_style.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor("#f8fafc")))
                        else:
                            t_style.append(('BACKGROUND', (0, r_idx), (-1, r_idx), colors.HexColor("#ffffff")))
                        
                        r_idx += 1
                    
                    t = Table(table_data, colWidths=[65, 115, 40, 55, 40, 200], repeatRows=1)
                    t.setStyle(TableStyle(t_style))
                    story.append(t)
            else:
                story.append(Paragraph("Nu exista date masurate pentru perioada selectata.", styles["Normal"]))
        else:
            story.append(Paragraph("Nu exista date pentru perioada selectata.", styles["Normal"]))

        doc.build(story)
        buffer.seek(0)
        return buffer

    if st.button("Crează Raport PDF", type="primary"):
        pdf_buffer = make_pdf_report(view_df, opt_glic, opt_ta, opt_puls, opt_tabele)
        file_name = f"Raport_Medical_{filtru_luni_str.replace(', ', '_')}.pdf"
        
        b64_pdf = base64.b64encode(pdf_buffer.getvalue()).decode('utf-8')
        href = f'''
        <div style="text-align: center; margin-top: 15px;">
            <a href="data:application/pdf;base64,{b64_pdf}" download="{file_name}" target="_blank" style="display:inline-block; padding: 14px 24px; background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%); color: white; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
                📥 Descarcă / Deschide Raport PDF (Fereastră Nouă)
            </a>
        </div>
        '''
        st.markdown(href, unsafe_allow_html=True)
        st.success("✅ Raportul PDF a fost generat cu succes!")
