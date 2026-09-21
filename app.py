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
# GESTIONARE FIȘIERE PERSISTENTE & SETĂRI
# ==========================================
DATA_FILE = "date_medicale_utilizator.csv"
MEDS_FILE = "medicamente.csv"
MEDS_HIST_FILE = "istoric_medicamente.csv"
PROG_FILE = "programari_medicale.csv"
FOODS_FILE = "alimente_custom.csv"
APPLE_WATCH_FILE = "apple_watch_data.csv"
BACKUP_LOG_FILE = "ultimul_backup_auto.txt"
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

def normalize_apple_watch_df(df_aw):
    if df_aw.empty:
        return df_aw
    col_map = {}
    for c in df_aw.columns:
        c_clean = remove_diacritics(c).lower().strip()
        if c_clean in ["pasi", "steps"]:
            col_map[c] = "Pași"
        elif c_clean in ["calorii active", "active calories", "calorii"]:
            col_map[c] = "Calorii Active"
        elif c_clean in ["somn (ore)", "somn", "sleep"]:
            col_map[c] = "Somn (ore)"
        elif c_clean in ["hrv (ms)", "hrv"]:
            col_map[c] = "HRV (ms)"
        elif c_clean in ["spo2 (%)", "spo2"]:
            col_map[c] = "SpO2 (%)"
        elif c_clean in ["puls mediu", "puls"]:
            col_map[c] = "Puls Mediu"
        elif c_clean in ["data", "date"]:
            col_map[c] = "Dată"
    if col_map:
        df_aw = df_aw.rename(columns=col_map)
        
    expected_aw_cols = {
        "Pași": 0, "Calorii Active": 0, "Somn (ore)": 0.0, 
        "HRV (ms)": 0, "SpO2 (%)": 0, "Puls Mediu": 0, "Dată": ""
    }
    for col, default_val in expected_aw_cols.items():
        if col not in df_aw.columns:
            df_aw[col] = default_val
    return df_aw

def get_initial_apple_watch():
    if os.path.exists(APPLE_WATCH_FILE):
        try:
            df_aw = pd.read_csv(APPLE_WATCH_FILE)
            if not df_aw.empty:
                return normalize_apple_watch_df(df_aw)
        except:
            pass
            
    return pd.DataFrame(columns=["Dată", "Pași", "Calorii Active", "Somn (ore)", "HRV (ms)", "SpO2 (%)", "Puls Mediu"])

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
    if "apple_watch_df" in st.session_state:
        st.session_state.apple_watch_df.to_csv(APPLE_WATCH_FILE, index=False)

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
        if date_col_name in df_b.columns:
            df_b["Dată_dt"] = parse_flexible_date(df_b[date_col_name])
            df_b["Moment_Cat"] = pd.Categorical(df_b["Moment Zi"], categories=moment_order, ordered=True)
            df_b = df_b.dropna(subset=["Dată_dt"]).sort_values(by=["Dată_dt", "Moment_Cat"]).drop(columns=["Dată_dt", "Moment_Cat"])
        
        if "Glicemie" in df_b.columns:
            df_b["Glicemie_num"] = pd.to_numeric(df_b["Glicemie"], errors="coerce").fillna(0)
            df_b = df_b[df_b["Glicemie_num"] > 0].drop(columns=["Glicemie_num"])

        for col in df_b.columns:
            if df_b[col].dtype == object:
                df_b[col] = df_b[col].apply(lambda x: remove_diacritics(clean_obs(str(x))) if pd.notna(x) else x)
        df_b.columns = [remove_diacritics(c) for c in df_b.columns]
        if 'Luna_An' in df_b.columns: 
            df_b = df_b.drop(columns=['Luna_An'])
        return df_b
    except:
        return pd.DataFrame()

# ==========================================
# SUPORT WEBHOOK / SHORTCUTS iOS (APPLE WATCH)
# ==========================================
query_params = st.query_params
if "sync_aw" in query_params or "pasi" in query_params or "steps" in query_params:
    try:
        sync_date = query_params.get("data", query_params.get("date", datetime.now().strftime("%d.%m.%Y")))
        steps_val = int(query_params.get("pasi", query_params.get("steps", 0)))
        cals_val = int(query_params.get("calorii", query_params.get("calories", 0)))
        sleep_val = float(query_params.get("somn", query_params.get("sleep", 0.0)))
        hrv_val = int(query_params.get("hrv", 0))
        spo2_val = int(query_params.get("spo2", 98))
        puls_val = int(query_params.get("puls", query_params.get("pulse", 72)))
        
        df_aw_curr = get_initial_apple_watch()
        new_aw_row = {
            "Dată": sync_date,
            "Pași": steps_val,
            "Calorii Active": cals_val,
            "Somn (ore)": sleep_val,
            "HRV (ms)": hrv_val,
            "SpO2 (%)": spo2_val,
            "Puls Mediu": puls_val
        }
        if not df_aw_curr.empty and "Dată" in df_aw_curr.columns:
            mask_aw = df_aw_curr["Dată"] == sync_date
            if mask_aw.any():
                for k, v in new_aw_row.items():
                    df_aw_curr.loc[mask_aw, k] = v
            else:
                df_aw_curr = pd.concat([df_aw_curr, pd.DataFrame([new_aw_row])], ignore_index=True)
        else:
            df_aw_curr = pd.DataFrame([new_aw_row])
            
        df_aw_curr.to_csv(APPLE_WATCH_FILE, index=False)
        st.session_state.apple_watch_df = df_aw_curr
        st.success(f"✅ S-au sincronizat cu succes datele Apple Watch pentru {sync_date} primite prin Shortcut!")
    except Exception as e:
        st.error(f"Erore la sincronizarea Apple Watch: {e}")

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

if "meds_df" not in st.session_state:
    st.session_state.meds_df = get_initial_meds()
if "apple_watch_df" not in st.session_state:
    st.session_state.apple_watch_df = get_initial_apple_watch()
else:
    st.session_state.apple_watch_df = normalize_apple_watch_df(st.session_state.apple_watch_df)

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

            if st.button("🔓 Autentificare", type="primary", use_container_width=True):
                user_data = st.session_state.users.get(username)
                if user_data and user_data["pass"] == password:
                    st.session_state.logged_in = True
                    st.session_state.user = username
                    trigger_rerun()
                else:
                    st.error("Utilizator sau parolă incorectă!")
    st.stop()

current_user_info = st.session_state.users.get(st.session_state.user, {"role": "Membru"})
current_role = current_user_info.get("role", "Membru")
is_admin = current_role == "Administrator"

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
        {"Dată": "20.09.2026", "Moment Zi": "Dimineața - Înainte de masă", "Glicemie": 122, "Sistolică": 120, "Diastolică": 78, "Puls": 70, "Observații": ""}
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
        if v == 0 or pd.isna(v): return "Nemăsurat"
        m_clean = remove_diacritics(str(moment_zi)).lower()
        if "dupa masa" in m_clean:
            t_min, t_max = st.session_state.settings.get("target_glic_post_min", 70), st.session_state.settings.get("target_glic_post_max", 160)
        else:
            t_min, t_max = st.session_state.settings.get("target_glic_min", 70), st.session_state.settings.get("target_glic_max", 120)

        if t_min <= v <= t_max: return "🟢 Normală"
        elif v < t_min: return "🔴 Mică"
        else: return "🔴 Mare"
    except:
        return "Nemăsurat"

def evaluate_ta(sis_val, dia_val):
    try:
        s, d = float(sis_val), float(dia_val)
        if s == 0 or d == 0 or pd.isna(s) or pd.isna(d): return "Nemăsurat"
        max_s, max_d = st.session_state.settings["target_ta_sis"], st.session_state.settings["target_ta_dia"]
        if s <= max_s and d <= max_d: return "🟢 Normală"
        else: return "🔴 Crescută"
    except:
        return "Nemăsurat"

def evaluate_puls(val):
    try:
        v = float(val)
        if v == 0 or pd.isna(v): return "Nemăsurat"
        if 60 <= v <= 100: return "🟢 Normal"
        elif v < 60: return "🔴 Scăzut"
        else: return "🔴 Ridicat"
    except:
        return "Nemăsurat"

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
    if not isinstance(val, str): return ""
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
tab_titles = ["📊 Jurnal & Grafice", "⌚ Apple Watch"]
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
        avg_glic_str = "Nemăsurat"
        if col_glic in view_df.columns:
            s_glic_all = pd.to_numeric(view_df[col_glic], errors="coerce").fillna(0).replace(0, None).dropna()
            if not s_glic_all.empty: avg_glic_str = f"{int(s_glic_all.mean())} mg/dL"

        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        with kpi1:
            val_glic = "Nemăsurat"
            if col_glic in view_df.columns:
                s_glic = pd.to_numeric(view_df[col_glic], errors="coerce").fillna(0).replace(0, None).dropna()
                if not s_glic.empty: val_glic = f"{int(s_glic.iloc[-1])} mg/dL"
            st.markdown(f'<div class="metric-card"><div class="metric-label">🩸 ULTIMA GLICEMIE</div><div class="metric-value">{val_glic}</div></div>', unsafe_allow_html=True)
        with kpi2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">📊 MEDIE GLICEMIE</div><div class="metric-value">{avg_glic_str}</div></div>', unsafe_allow_html=True)
        with kpi3:
            val_sis, val_dia = "-", "-"
            if col_sis in view_df.columns:
                s_sis = pd.to_numeric(view_df[col_sis], errors="coerce").fillna(0).replace(0, None).dropna()
                if not s_sis.empty: val_sis = int(s_sis.iloc[-1])
            if col_dia in view_df.columns:
                s_dia = pd.to_numeric(view_df[col_dia], errors="coerce").fillna(0).replace(0, None).dropna()
                if not s_dia.empty: val_dia = int(s_dia.iloc[-1])
            val_ta_str = f"{val_sis}/{val_dia}" if val_sis != "-" or val_dia != "-" else "Nemăsurat"
            st.markdown(f'<div class="metric-card"><div class="metric-label">🫀 ULTIMA TENSIUNE</div><div class="metric-value">{val_ta_str}</div></div>', unsafe_allow_html=True)
        with kpi4:
            val_puls = "Nemăsurat"
            if col_puls in view_df.columns:
                s_puls = pd.to_numeric(view_df[col_puls], errors="coerce").fillna(0).replace(0, None).dropna()
                if not s_puls.empty: val_puls = f"{int(s_puls.iloc[-1])} bpm"
            st.markdown(f'<div class="metric-card"><div class="metric-label">💓 ULTIM PULS</div><div class="metric-value">{val_puls}</div></div>', unsafe_allow_html=True)
        with kpi5:
            st.markdown(f'<div class="metric-card"><div class="metric-label">📅 TOTAL (FILTRU)</div><div class="metric-value">{len(view_df)}</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        sub_tab_glic, sub_tab_ta, sub_tab_puls, sub_tab_all = st.tabs(["🩸 Glicemie & Analiză Spike", "🫀 Tensiune Arterială", "💓 Puls", "📋 Toate Datele"])
        
        view_df_measured = view_df.copy()
        if col_glic in view_df_measured.columns:
            view_df_measured["Glic_num"] = pd.to_numeric(view_df_measured[col_glic], errors="coerce").fillna(0)
            view_df_measured = view_df_measured[view_df_measured["Glic_num"] > 0].drop(columns=["Glic_num"])

        x_labels_composed = [f"{d.strftime('%d.%m')} ({m[:3]})" for d, m in zip(view_df_measured[date_col], view_df_measured[moment_col])]

        with sub_tab_glic:
            st.markdown("ℹ️ **Legendă Glicemie:** 🔵 Albastru = Valoare optimă | 🔴 Roșu = Valoare crescută / Spike.")
            if col_glic in view_df_measured.columns:
                glic_vals = pd.to_numeric(view_df_measured[col_glic], errors="coerce").replace(0, None)
                moments = view_df_measured[moment_col].tolist() if moment_col in view_df_measured.columns else [""] * len(view_df_measured)

                spike_colors = ["#dc2626" if is_glic_spike(v, m) else "#38bdf8" for v, m in zip(glic_vals, moments)]
                spike_texts = [str(int(v)) if pd.notna(v) else "" for v in glic_vals]

                fig_g = go.Figure()
                fig_g.add_trace(go.Scatter(
                    x=x_labels_composed, y=glic_vals, mode="lines+markers+text", name="Glicemie",
                    line=dict(color="#38bdf8", width=2.5),
                    marker=dict(size=10, color=spike_colors),
                    text=spike_texts, textposition="top center",
                    textfont=dict(size=9.5, color="#ffffff"),
                    texttemplate="%{text}", connectgaps=True
                ))
                
                max_post = st.session_state.settings.get("target_glic_post_max", 160)
                max_pre = st.session_state.settings.get("target_glic_max", 120)
                fig_g.add_hline(y=max_post, line_dash="dash", line_color="#dc2626", annotation_text=f"Prag Max După Masă ({max_post})")
                fig_g.add_hline(y=max_pre, line_dash="dot", line_color="#f59e0b", annotation_text=f"Prag Max Înainte Masă ({max_pre})")
                
                max_glic_data = glic_vals.max() if not glic_vals.dropna().empty else 200
                fig_g.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=40, r=40, t=50, b=120), xaxis=dict(tickangle=-45, dtick=1), yaxis=dict(range=[0, max(250, int(max_glic_data) + 50)]))
                st.plotly_chart(fig_g, use_container_width=True)

                # CORRECȚIE KEYERROR: Creare corectă a tabelei Glicemie
                df_g_tab = view_df_measured.copy()
                df_g_tab["Status Glicemie"] = df_g_tab.apply(lambda r: evaluate_glic(r[col_glic], r[moment_col]), axis=1)
                df_g_tab[date_col] = df_g_tab[date_col].dt.strftime("%d.%m.%Y")
                df_g_tab[col_glic] = format_table_column(df_g_tab[col_glic])
                df_g_tab[col_obs] = df_g_tab[col_obs].apply(clean_obs)
                df_g_tab = df_g_tab[df_g_tab[col_glic] != ""]
                cols_g = [date_col, moment_col, col_glic, "Status Glicemie", col_obs]
                df_g_tab = df_g_tab[cols_g]
                st.dataframe(apply_color_styling(df_g_tab, ["Status Glicemie"]), use_container_width=True, hide_index=True)

        with sub_tab_ta:
            st.markdown("ℹ️ **Legendă Tensiune:** Sistolică / Diastolică | 🔴 Roșu = Valori Crescute.")
            if col_sis in view_df_measured.columns and col_dia in view_df_measured.columns:
                sis_vals = pd.to_numeric(view_df_measured[col_sis], errors="coerce").replace(0, None)
                dia_vals = pd.to_numeric(view_df_measured[col_dia], errors="coerce").replace(0, None)
                
                sis_colors = ["#dc2626" if is_ta_spike(s, d) else "#2563eb" for s, d in zip(sis_vals, dia_vals)]
                dia_colors = ["#dc2626" if is_ta_spike(s, d) else "#f59e0b" for s, d in zip(sis_vals, dia_vals)]

                fig_ta = go.Figure()
                fig_ta.add_trace(go.Scatter(x=x_labels_composed, y=sis_vals, mode="lines+markers+text", name="Sistolică", line=dict(color="#2563eb", width=2.5), marker=dict(size=10, color=sis_colors), text=sis_vals, textposition="top center", textfont=dict(size=10, color="#ffffff"), texttemplate="<b>%{text}</b>", connectgaps=True))
                fig_ta.add_trace(go.Scatter(x=x_labels_composed, y=dia_vals, mode="lines+markers+text", name="Diastolică", line=dict(color="#f59e0b", width=2.5), marker=dict(size=10, color=dia_colors), text=dia_vals, textposition="bottom center", textfont=dict(size=10, color="#ffffff"), texttemplate="<b>%{text}</b>", connectgaps=True))
                fig_ta.add_hline(y=st.session_state.settings.get("target_ta_sis", 120), line_dash="dash", line_color="#dc2626", annotation_text="Prag Max Sistolică")
                fig_ta.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=40, r=40, t=50, b=120), xaxis=dict(tickangle=-45, dtick=1))
                st.plotly_chart(fig_ta, use_container_width=True)
                
                # CORRECȚIE KEYERROR: Creare corectă a tabelei Tensiune
                df_t_tab = view_df_measured.copy()
                df_t_tab["Status Tensiune"] = df_t_tab.apply(lambda r: evaluate_ta(r[col_sis], r[col_dia]), axis=1)
                df_t_tab[date_col] = df_t_tab[date_col].dt.strftime("%d.%m.%Y")
                df_t_tab[col_sis] = format_table_column(df_t_tab[col_sis])
                df_t_tab[col_dia] = format_table_column(df_t_tab[col_dia])
                df_t_tab[col_obs] = df_t_tab[col_obs].apply(clean_obs)
                df_t_tab = df_t_tab[(df_t_tab[col_sis] != "") | (df_t_tab[col_dia] != "")]
                cols_t = [date_col, moment_col, col_sis, col_dia, "Status Tensiune", col_obs]
                df_t_tab = df_t_tab[cols_t]
                st.dataframe(apply_color_styling(df_t_tab, ["Status Tensiune"]), use_container_width=True, hide_index=True)

        with sub_tab_puls:
            st.markdown("ℹ️ **Legendă Puls:** 🟢 Verde = Interval normal (60-100 bpm)")
            if col_puls in view_df_measured.columns:
                puls_vals = pd.to_numeric(view_df_measured[col_puls], errors="coerce").replace(0, None)
                puls_colors = ["#dc2626" if is_puls_spike(p) else "#10b981" for p in puls_vals]

                fig_p = go.Figure()
                fig_p.add_trace(go.Scatter(x=x_labels_composed, y=puls_vals, mode="lines+markers+text", name="Puls (bpm)", line=dict(color="#10b981", width=2.5), marker=dict(size=10, color=puls_colors), text=puls_vals, textposition="top center", textfont=dict(size=10, color="#ffffff"), texttemplate="<b>%{text}</b>", connectgaps=True))
                fig_p.add_hline(y=100, line_dash="dash", line_color="#dc2626", annotation_text="Limită Max (100)")
                fig_p.add_hline(y=60, line_dash="dash", line_color="#dc2626", annotation_text="Limită Min (60)")
                fig_p.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=40, r=40, t=50, b=120), xaxis=dict(tickangle=-45, dtick=1))
                st.plotly_chart(fig_p, use_container_width=True)
                
                # CORRECȚIE KEYERROR: Creare corectă a tabelei Puls
                df_p_tab = view_df_measured.copy()
                df_p_tab["Status Puls"] = df_p_tab[col_puls].apply(evaluate_puls)
                df_p_tab[date_col] = df_p_tab[date_col].dt.strftime("%d.%m.%Y")
                df_p_tab[col_puls] = format_table_column(df_p_tab[col_puls])
                df_p_tab[col_obs] = df_p_tab[col_obs].apply(clean_obs)
                df_p_tab = df_p_tab[df_p_tab[col_puls] != ""]
                cols_p = [date_col, moment_col, col_puls, "Status Puls", col_obs]
                df_p_tab = df_p_tab[cols_p]
                st.dataframe(apply_color_styling(df_p_tab, ["Status Puls"]), use_container_width=True, hide_index=True)

        with sub_tab_all:
            df_all = view_df_measured.copy()
            df_all[date_col] = df_all[date_col].dt.strftime("%d.%m.%Y")
            if col_glic in df_all.columns:
                df_all[col_glic] = format_table_column(df_all[col_glic])
            if col_sis in df_all.columns:
                df_all[col_sis] = format_table_column(df_all[col_sis])
            if col_dia in df_all.columns:
                df_all[col_dia] = format_table_column(df_all[col_dia])
            if col_puls in df_all.columns:
                df_all[col_puls] = format_table_column(df_all[col_puls])
            
            cols_all_order = [date_col, moment_col, col_glic, col_sis, col_dia, col_puls, col_obs]
            cols_all_existing = [c for c in cols_all_order if c in df_all.columns]
            df_all = df_all[cols_all_existing]
            df_all[col_obs] = df_all[col_obs].apply(clean_obs)
            st.dataframe(df_all, use_container_width=True, height=800, hide_index=True)

# ----------------- TAB: APPLE WATCH -----------------
with tab_dict["⌚ Apple Watch"]:
    st.markdown("### ⌚ Monitorizare Activitate & Biometrie Apple Watch (Valori Reale)")
    st.caption("Date reale sincronizate din Apple Health / Apple Watch sau via Scurtături iOS.")

    st.session_state.apple_watch_df = normalize_apple_watch_df(st.session_state.apple_watch_df)
    aw_df = st.session_state.apple_watch_df.copy()

    if not aw_df.empty:
        aw_df["Dată_dt"] = parse_flexible_date(aw_df["Dată"])
        aw_df = aw_df.sort_values(by="Dată_dt").drop(columns=["Dată_dt"])

        last_aw = aw_df.iloc[-1]
        
        aw_kpi1, aw_kpi2, aw_kpi3, aw_kpi4, aw_kpi5 = st.columns(5)
        with aw_kpi1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">👟 PAȘI ZILNICI</div><div class="metric-value">{int(last_aw.get("Pași", 0)):,}</div></div>', unsafe_allow_html=True)
        with aw_kpi2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">🔥 CALORII ACTIVE</div><div class="metric-value">{int(last_aw.get("Calorii Active", 0))} kcal</div></div>', unsafe_allow_html=True)
        with aw_kpi3:
            st.markdown(f'<div class="metric-card"><div class="metric-label">🌙 SOMN (ORE)</div><div class="metric-value">{float(last_aw.get("Somn (ore)", 0))} h</div></div>', unsafe_allow_html=True)
        with aw_kpi4:
            st.markdown(f'<div class="metric-card"><div class="metric-label">🫀 HRV (MS)</div><div class="metric-value">{int(last_aw.get("HRV (ms)", 0))} ms</div></div>', unsafe_allow_html=True)
        with aw_kpi5:
            st.markdown(f'<div class="metric-card"><div class="metric-label">🩸 SpO2 / PULS</div><div class="metric-value">{int(last_aw.get("SpO2 (%)", 0))}% / {int(last_aw.get("Puls Mediu", 0))}</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        sub_tab_aw_act, sub_tab_aw_sleep, sub_tab_aw_table = st.tabs(["👟 Pași & Calorii Active", "🌙 Somn, HRV & SpO2", "📋 Tabel Date Apple Watch"])

        x_aw_dates = aw_df["Dată"].tolist()

        with sub_tab_aw_act:
            steps_vals = pd.to_numeric(aw_df["Pași"], errors="coerce").tolist()
            cal_vals = pd.to_numeric(aw_df["Calorii Active"], errors="coerce").tolist()

            fig_aw_act = go.Figure()
            fig_aw_act.add_trace(go.Bar(x=x_aw_dates, y=steps_vals, name="Pași", marker_color="#38bdf8", opacity=0.85))
            fig_aw_act.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=40, r=40, t=40, b=80), xaxis=dict(tickangle=-45))
            st.plotly_chart(fig_aw_act, use_container_width=True)

            fig_aw_cal = go.Figure()
            fig_aw_cal.add_trace(go.Scatter(x=x_aw_dates, y=cal_vals, mode="lines+markers", name="Calorii Active (kcal)", line=dict(color="#f59e0b", width=2.5), marker=dict(size=8)))
            fig_aw_cal.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=40, r=40, t=40, b=80), xaxis=dict(tickangle=-45))
            st.plotly_chart(fig_aw_cal, use_container_width=True)

        with sub_tab_aw_sleep:
            sleep_vals = pd.to_numeric(aw_df["Somn (ore)"], errors="coerce").tolist()
            hrv_vals = pd.to_numeric(aw_df["HRV (ms)"], errors="coerce").tolist()

            fig_aw_sleep = go.Figure()
            fig_aw_sleep.add_trace(go.Scatter(x=x_aw_dates, y=sleep_vals, mode="lines+markers", name="Somn (ore)", line=dict(color="#10b981", width=2.5), marker=dict(size=8)))
            fig_aw_sleep.add_trace(go.Scatter(x=x_aw_dates, y=hrv_vals, mode="lines+markers", name="HRV (ms)", line=dict(color="#8b5cf6", width=2.5), marker=dict(size=8)))
            fig_aw_sleep.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=40, r=40, t=40, b=80), xaxis=dict(tickangle=-45))
            st.plotly_chart(fig_aw_sleep, use_container_width=True)

        with sub_tab_aw_table:
            st.dataframe(aw_df, use_container_width=True, hide_index=True)
    else:
        st.info("📭 Nu există date Apple Watch înregistrate. Poți adăuga manual mai jos sau poți configura Scurtătura iOS pentru a trimite datele automat.")

    if is_admin:
        st.markdown("---")
        st.markdown("#### ➕ Adaugă / Actualizează Valori Apple Watch (Manual)")
        with st.form("form_add_apple_watch"):
            aw_date_inp = st.date_input("Dată", value=date.today())
            c_aw1, c_aw2, c_aw3 = st.columns(3)
            with c_aw1:
                aw_steps = st.number_input("Pași", min_value=0, value=7500)
                aw_cals = st.number_input("Calorii Active (kcal)", min_value=0, value=500)
            with c_aw2:
                aw_sleep = st.number_input("Somn (ore)", min_value=0.0, max_value=24.0, value=7.5, step=0.1)
                aw_hrv = st.number_input("HRV (ms)", min_value=0, value=50)
            with c_aw3:
                aw_spo2 = st.number_input("SpO2 (%)", min_value=0, max_value=100, value=98)
                aw_puls = st.number_input("Puls Mediu", min_value=0, value=72)

            if st.form_submit_button("💾 Salvează Datele Apple Watch", type="primary"):
                d_str_aw = aw_date_inp.strftime("%d.%m.%Y")
                existing_idx = st.session_state.apple_watch_df.index[st.session_state.apple_watch_df["Dată"] == d_str_aw]
                new_row_data = {
                    "Dată": d_str_aw, "Pași": aw_steps, "Calorii Active": aw_cals,
                    "Somn (ore)": aw_sleep, "HRV (ms)": aw_hrv, "SpO2 (%)": aw_spo2, "Puls Mediu": aw_puls
                }
                if len(existing_idx) > 0:
                    for k, v in new_row_data.items():
                        st.session_state.apple_watch_df.loc[existing_idx[0], k] = v
                else:
                    st.session_state.apple_watch_df = pd.concat([st.session_state.apple_watch_df, pd.DataFrame([new_row_data])], ignore_index=True)
                
                st.session_state.apple_watch_df.to_csv(APPLE_WATCH_FILE, index=False)
                st.success(f"Datele Apple Watch pentru {d_str_aw} au fost salvate!")
                trigger_rerun()

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
                    st.success(f"S-a revenit la starea anterioară! ({last_action['desc']})")
                    trigger_rerun()
        
        if "success_message" in st.session_state:
            st.success(st.session_state["success_message"])
            del st.session_state["success_message"]

        with st.container(border=True):
            selected_date = st.date_input("📅 Selectează Data", value=date.today())
            selected_moment = st.selectbox("🍽️ Momentul Măsurătorii", moment_order)

            existing_row = pd.DataFrame()
            date_str = selected_date.strftime("%d.%m.%Y")
            has_real_record = False

            if not df.empty and date_col in df.columns and moment_col in df.columns:
                match = df[(parse_flexible_date(df[date_col]).dt.strftime("%d.%m.%Y") == date_str) & (df[moment_col] == selected_moment)]
                if not match.empty:
                    row_candidate = match.iloc[0]
                    if any(float(row_candidate.get(c, 0) or 0) > 0 for c in [col_glic, col_sis, col_dia, col_puls]) or clean_obs(row_candidate.get(col_obs, "")):
                        existing_row = row_candidate
                        has_real_record = True

            def get_val(col_name):
                if has_real_record and not existing_row.empty and col_name in existing_row:
                    try: return int(float(existing_row[col_name]))
                    except: return 0
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

            all_known_foods = sorted(list(set([remove_diacritics(str(item)).lower() for items in st.session_state.food_categories.values() for item in items if pd.notna(item)])))

            c1, c2 = st.columns(2)
            with c1: st.number_input("🩸 Glicemie (mg/dL) [0 = nemăsurat]", min_value=0, key="inp_glic")
            with c2:
                st.number_input("🫀 Tensiune Sistolică [0 = nemăsurat]", min_value=0, key="inp_sis")
                st.number_input("🫀 Tensiune Diastolică [0 = nemăsurat]", min_value=0, key="inp_dia")
                st.number_input("💓 Puls [0 = nemăsurat]", min_value=0, key="inp_puls")

            st.markdown("---")
            search_food_input = st.selectbox("🔍 Caută / Selectează rapid ingredient", options=[""] + sorted(list(set([str(item) for items in st.session_state.food_categories.values() for item in items if pd.notna(item)]))))
            
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
                                st.session_state[chk_key] = bool(item_clean in base_obs_text or (search_query_clean and item_clean.startswith(search_query_clean)))
                            if st.checkbox(item_str, key=chk_key):
                                checked_foods_live.append(item_str.strip().lower())

            current_obs_val = st.session_state.get("inp_obs", "")
            non_food_parts = [p for p in [p.strip() for p in current_obs_val.split(",") if p.strip()] if remove_diacritics(p).lower() not in all_known_foods]
            st.session_state["inp_obs"] = ", ".join([p for p in non_food_parts + sorted(list(set(checked_foods_live))) if p])

            st.text_area("✍️ Notițe / Observații", key="inp_obs")

            def handle_save_action():
                save_local_record(date_str, selected_moment, st.session_state.get("inp_glic", 0), st.session_state.get("inp_sis", 0), st.session_state.get("inp_dia", 0), st.session_state.get("inp_puls", 0), st.session_state.get("inp_obs", ""))
                st.session_state["success_message"] = "✅ Înregistrare salvată cu succes!"
                trigger_rerun()

            st.button("💾 Salvează / Suprascrie Înregistrarea", type="primary", use_container_width=True, on_click=handle_save_action)

# ----------------- TAB: TRATAMENT -----------------
with tab_dict["💊 Tratament"]:
    st.markdown("### 💊 Schemă Tratament Medical")
    st.dataframe(st.session_state.meds_df, use_container_width=True, hide_index=True)

# ----------------- TAB: PROGRAMĂRI -----------------
if is_admin and "📅 Programări" in tab_dict:
    with tab_dict["📅 Programări"]:
        st.markdown("### 📅 Programări Medicale")
        st.dataframe(st.session_state.prog_df, use_container_width=True, hide_index=True)

# ----------------- TAB: RAPORT PDF -----------------
with tab_dict["📄 Raport PDF"]:
    st.markdown("### 📄 Generare Raport Medical PDF (Curățat de Diacritice)")
    st.caption("Generează un raport PDF profesional cu diacritice curățate, observații pe ultima coloană și opțiune pentru secțiunea Apple Watch.")

    opt_aw_pdf = st.checkbox("Include secțiunea Apple Watch în PDF", value=True)

    if st.button("📥 Generează și Descarcă PDF", type="primary"):
        pdf_buffer = io.BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        story = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle('ReportTitle', parent=styles['Heading1'], fontSize=16, leading=20, textColor=colors.HexColor('#0284c7'), alignment=1, spaceAfter=10)
        subtitle_style = ParagraphStyle('ReportSubtitle', parent=styles['Normal'], fontSize=9, leading=13, textColor=colors.HexColor('#64748b'), alignment=1, spaceAfter=15)
        heading_style = ParagraphStyle('ReportHeading', parent=styles['Heading2'], fontSize=12, leading=16, textColor=colors.HexColor('#0f172a'), spaceBefore=12, spaceAfter=8)
        cell_style = ParagraphStyle('ReportCell', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#1e293b'))
        cell_header_style = ParagraphStyle('ReportHeaderCell', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor('#ffffff'), fontName='Helvetica-Bold')

        story.append(Paragraph(remove_diacritics("HealthTrack Pro - Raport Medical și Jurnal Sănătate"), title_style))
        story.append(Paragraph(remove_diacritics(f"Generat la data: {datetime.now().strftime('%d.%m.%Y %H:%M')} | Perioada: {filtru_luni_str}"), subtitle_style))
        story.append(Spacer(1, 10))

        story.append(Paragraph(remove_diacritics("1. Jurnal Măsurători Medicale (Glicemie, Tensiune, Puls, Observații)"), heading_style))
        
        pdf_df = view_df.copy()
        if date_col in pdf_df.columns:
            pdf_df[date_col] = pdf_df[date_col].dt.strftime("%d.%m.%Y")
        
        base_cols_order = [date_col, moment_col, col_glic, col_sis, col_dia, col_puls, col_obs]
        existing_cols = [c for c in base_cols_order if c in pdf_df.columns]
        pdf_df = pdf_df[existing_cols]

        col_rename_pdf = {
            date_col: "Data", moment_col: "Moment", col_glic: "Glicemie",
            col_sis: "Sistolica", col_dia: "Diastolica", col_puls: "Puls", col_obs: "Observatii"
        }
        pdf_df = pdf_df.rename(columns=col_rename_pdf)

        table_data = []
        header_row = [remove_diacritics(str(c)) for c in pdf_df.columns]
        table_data.append([Paragraph(h, cell_header_style) for h in header_row])

        for _, row in pdf_df.iterrows():
            row_cells = []
            for col in pdf_df.columns:
                val = row[col]
                if col == "Observatii":
                    val_clean = remove_diacritics(clean_obs(str(val)))
                elif col in ["Glicemie", "Sistolica", "Diastolica", "Puls"]:
                    val_clean = str(val) if pd.notna(val) and float(val) > 0 else "-"
                else:
                    val_clean = remove_diacritics(str(val))
                row_cells.append(Paragraph(val_clean, cell_style))
            table_data.append(row_cells)

        t_med = Table(table_data, colWidths=[65, 95, 55, 55, 55, 45, 140])
        t_med.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0284c7')),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,0), 5),
            ('TOPPADDING', (0,0), (-1,0), 5),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')])
        ]))
        story.append(t_med)
        story.append(Spacer(1, 10))

        if opt_aw_pdf and not st.session_state.apple_watch_df.empty:
            story.append(Paragraph(remove_diacritics("2. Secțiunea Apple Watch & Biometrie Zilnică"), heading_style))
            aw_pdf_df = st.session_state.apple_watch_df.copy()
            aw_pdf_cols = ["Dată", "Pași", "Calorii Active", "Somn (ore)", "HRV (ms)", "SpO2 (%)", "Puls Mediu"]
            aw_pdf_cols_existing = [c for c in aw_pdf_cols if c in aw_pdf_df.columns]
            aw_pdf_df = aw_pdf_df[aw_pdf_cols_existing]
            
            aw_rename_pdf = {
                "Dată": "Data", "Pași": "Pasi", "Calorii Active": "Calorii", 
                "Somn (ore)": "Somn (h)", "HRV (ms)": "HRV", "SpO2 (%)": "SpO2", "Puls Mediu": "Puls"
            }
            aw_pdf_df = aw_pdf_df.rename(columns=aw_rename_pdf)

            aw_table_data = []
            aw_header_row = [remove_diacritics(str(c)) for c in aw_pdf_df.columns]
            aw_table_data.append([Paragraph(h, cell_header_style) for h in aw_header_row])

            df_aw_to_iter = aw_pdf_df.tail(25) if len(aw_pdf_df) > 25 else aw_pdf_df
            for _, row in df_aw_to_iter.iterrows():
                row_cells = []
                for col in aw_pdf_df.columns:
                    row_cells.append(Paragraph(remove_diacritics(str(row[col])), cell_style))
                aw_table_data.append(row_cells)

            t_aw = Table(aw_table_data, colWidths=[70, 70, 70, 60, 60, 50, 60])
            t_aw.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#059669')),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOTTOMPADDING', (0,0), (-1,0), 5),
                ('TOPPADDING', (0,0), (-1,0), 5),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')])
            ]))
            story.append(t_aw)
            story.append(Spacer(1, 10))

        story.append(Paragraph(remove_diacritics("3. Schema de Tratament Curentă"), heading_style))
        meds_pdf_df = st.session_state.meds_df.copy()
        meds_pdf_cols = ["Medicament", "Doză", "Orar / Frecvență", "Observații"]
        meds_pdf_cols_ext = [c for c in meds_pdf_cols if c in meds_pdf_df.columns]
        meds_pdf_df = meds_pdf_df[meds_pdf_cols_ext]
        
        meds_rename_pdf = {"Medicament": "Medicament", "Doză": "Doza", "Orar / Frecvență": "Orar", "Observații": "Observatii"}
        meds_pdf_df = meds_pdf_df.rename(columns=meds_rename_pdf)

        meds_table_data = []
        meds_header_row = [remove_diacritics(str(c)) for c in meds_pdf_df.columns]
        meds_table_data.append([Paragraph(h, cell_header_style) for h in meds_header_row])

        for _, row in meds_pdf_df.iterrows():
            row_cells = []
            for col in meds_pdf_df.columns:
                row_cells.append(Paragraph(remove_diacritics(str(row[col])), cell_style))
            meds_table_data.append(row_cells)

        t_meds = Table(meds_table_data, colWidths=[120, 80, 150, 150])
        t_meds.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0284c7')),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('BOTTOMPADDING', (0,0), (-1,0), 5),
            ('TOPPADDING', (0,0), (-1,0), 5),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')])
        ]))
        story.append(t_meds)

        doc.build(story)
        pdf_data = pdf_buffer.getvalue()
        pdf_buffer.close()

        st.success("✅ Raportul PDF a fost generat cu succes!")
        st.download_button(
            label="📥 Descarcă Raport PDF Complet",
            data=pdf_data,
            file_name=f"Raport_Medical_HealthTrack_{datetime.now().strftime('%d_%m_%Y')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

# ----------------- TAB: SETĂRI -----------------
with tab_dict["⚙️ Setări"]:
    st.markdown("### ⚙️ Setări Aplicație & Notificări")
    with st.form("settings_form"):
        s_email = st.text_input("Email Expeditor (iCloud)", value=st.session_state.settings.get("email_sender", ""))
        s_pass = st.text_input("Parolă de aplicație iCloud", type="password", value=st.session_state.settings.get("email_password", ""))
        
        if st.form_submit_button("Salvează Setările", type="primary"):
            st.session_state.settings["email_sender"] = s_email
            st.session_state.settings["email_password"] = s_pass
            save_persisted_settings(st.session_state.settings)
            st.success("Setările au fost salvate cu succes!")
