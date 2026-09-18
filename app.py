import io
import os
import re
import smtplib
import time
import unicodedata
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
# CONFIGURARE PAGINĂ & THEME (DARK MODE)
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
    return str(val).strip()

def trigger_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

# ==========================================
# GESTIONARE FIȘIERE PERSISTENTE
# ==========================================
DATA_FILE = "date_medicale_utilizator.csv"
MEDS_FILE = "medicamente.csv"
MEDS_HIST_FILE = "istoric_medicamente.csv"
PROG_FILE = "programari_medicale.csv"
FOODS_FILE = "alimente_custom.csv"
BACKUP_LOG_FILE = "ultimul_backup_auto.txt"

def get_initial_meds():
    if os.path.exists(MEDS_FILE):
        return pd.read_csv(MEDS_FILE)
    return pd.DataFrame([
        {"Medicament": "Glucophage", "Doză": "1000 mg", "Orar": "Dimineața / Seara", "Administrare": "După masă"},
        {"Medicament": "Lagosa", "Doză": "150 mg", "Orar": "Dimineața / Seara", "Administrare": "După masă"},
        {"Medicament": "Diaprel MR", "Doză": "60 mg (1/2)", "Orar": "Dimineața", "Administrare": "Înainte de masă"},
        {"Medicament": "Atacand", "Doză": "8 mg", "Orar": "Seara", "Administrare": "După masă"},
        {"Medicament": "Nebilet", "Doză": "5 mg", "Orar": "Dimineața", "Administrare": "După masă"},
    ])

def get_initial_history():
    if os.path.exists(MEDS_HIST_FILE):
        return pd.read_csv(MEDS_HIST_FILE)
    return pd.DataFrame(columns=["Data_Ora", "Acțiune", "Medicament", "Detalii"])

def get_initial_prog():
    if os.path.exists(PROG_FILE):
        try:
            df_p = pd.read_csv(PROG_FILE)
            if "Ora" not in df_p.columns: df_p["Ora"] = "10:00"
            if "Efectuat" not in df_p.columns: df_p["Efectuat"] = "Nu"
            if "Clinică" not in df_p.columns: df_p["Clinică"] = "-"
            if "Zile_Alerta" not in df_p.columns: df_p["Zile_Alerta"] = "1, 3"
            if "Observații" not in df_p.columns: df_p["Observații"] = ""
            return df_p
        except:
            pass
            
    return pd.DataFrame([
        {"Dată": "2026-09-25", "Ora": "09:00", "Tip": "Analize de laborator", "Clinică": "Regina Maria", "Zile_Alerta": "1, 3, 7", "Efectuat": "Nu", "Observații": "Repetare analize Diabet"},
        {"Dată": "2026-10-05", "Ora": "14:30", "Tip": "Consult Diabet", "Clinică": "Dr. Clenciu Craiova", "Zile_Alerta": "2, 5", "Efectuat": "Nu", "Observații": "Rețetă 3 luni"},
    ])

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
                cat = row["Categorie"]
                item = remove_diacritics(str(row["Element"])).strip().lower()
                if cat not in categories: categories[cat] = []
                if item not in categories[cat]: categories[cat].append(item)
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
            rows.append({"Categorie": cat, "Element": remove_diacritics(item).strip().lower()})
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
        if "Dată" in df_b.columns:
            df_b["Dată_dt"] = pd.to_datetime(df_b["Dată"].astype(str).str.strip(), format="%d.%m.%Y", errors="coerce")
            df_b = df_b.dropna(subset=["Dată_dt"]).sort_values(by="Dată_dt", ascending=True).drop(columns=["Dată_dt"])
        for col in df_b.columns:
            if df_b[col].dtype == object:
                df_b[col] = df_b[col].apply(lambda x: remove_diacritics(str(x)) if pd.notna(x) else x)
        df_b.columns = [remove_diacritics(c) for c in df_b.columns]
        if 'Luna_An' in df_b.columns: 
            df_b = df_b.drop(columns=['Luna_An'])
        return df_b
    except:
        return pd.DataFrame()

def trimite_email_cu_atasament(destinatar, subiect, mesaj, file_path, file_name):
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

                if os.path.exists(file_path):
                    with open(file_path, "rb") as f:
                        file_data = f.read()
                    msg.add_attachment(file_data, maintype="application", subtype="octet-stream", filename=file_name)

                if use_ssl:
                    with smtplib.SMTP_SSL('smtp.mail.me.com', port, timeout=30) as smtp:
                        smtp.login(email_sender, email_password)
                        smtp.send_message(msg)
                else:
                    with smtplib.SMTP('smtp.mail.me.com', port, timeout=30) as smtp:
                        smtp.starttls()
                        smtp.login(email_sender, email_password)
                        smtp.send_message(msg)
                        
                return True, "Email trimis cu succes prin iCloud!"
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
                    ultima_data_str = f.read().strip()
                    ultima_data = datetime.strptime(ultima_data_str, "%Y-%m-%d").date()
            except:
                pass

        if ultima_data is None or (azi - ultima_data).days >= 2:
            df_cron = get_chronological_backup_df()
            if not df_cron.empty:
                temp_backup_file = "temp_backup_cron.csv"
                df_cron.to_csv(temp_backup_file, index=False)
                
                succes, _ = trimite_email_cu_atasament(
                    destinatar=email_dest,
                    subiect="💾 [Backup Automat] HealthTrack Pro - Date Medicale",
                    mesaj=f"Salut!\n\nAcesta este backup-ul tău automat cronologic generat la data de {azi.strftime('%d.%m.%Y')}.\nFișierul CSV cu toate datele medicale este atașat acestui mesaj.\n\nHealthTrack Pro System",
                    file_path=temp_backup_file,
                    file_name="backup_date_medicale.csv"
                )
                if os.path.exists(temp_backup_file):
                    os.remove(temp_backup_file)

                if succes:
                    with open(BACKUP_LOG_FILE, "w") as f:
                        f.write(azi.strftime("%Y-%m-%d"))
    except:
        pass

# ==========================================
# SESSION STATE INITIALIZATION & TIMEOUT (10 MIN)
# ==========================================
TIMEOUT_SEC = 600  # 10 minute

if "last_active_time" not in st.session_state:
    st.session_state.last_active_time = time.time()

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

# Verificare timeout inactivitate 10 minute
if st.session_state.logged_in:
    if time.time() - st.session_state.last_active_time > TIMEOUT_SEC:
        st.session_state.logged_in = False
        st.session_state.user = None

if "settings" not in st.session_state:
    st.session_state.settings = {
        "notif_enabled": True, 
        "email_sender": "",
        "email_password": "",
        "target_glic_min": 70, "target_glic_max": 120,
        "target_glic_post_min": 70, "target_glic_post_max": 160,
        "target_ta_sis": 120, "target_ta_dia": 80,
    }

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

# Actualizare timp activitate la fiecare acțiune validă
if st.session_state.logged_in:
    st.session_state.last_active_time = time.time()

# ==========================================
# AUTENTIFICARE
# ==========================================
if not st.session_state.logged_in:
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    _, col_b, _ = st.columns([1, 1.2, 1])

    with col_b:
        st.markdown("<h1 style='text-align: center; color: #38bdf8;'>🩺 HealthTrack Pro</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #94a3b8; font-size: 16px;'>Platformă de Monitorizare Medicală de Familie</p>", unsafe_allow_html=True)

        if time.time() - st.session_state.last_active_time > TIMEOUT_SEC and st.session_state.get("user") is None:
            st.warning("⏳ Ai fost deconectat automat din cauza inactivității (10 minute).")

        with st.container(border=True):
            username = st.text_input("👤 Utilizator")
            password = st.text_input("🔑 Parolă", type="password")

            if st.button("🔓 Autentificare", type="primary", use_container_width=True):
                user_data = st.session_state.users.get(username)
                if user_data and user_data["pass"] == password:
                    st.session_state.logged_in = True
                    st.session_state.user = username
                    st.session_state.last_active_time = time.time()
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
    if os.path.exists(DATA_FILE):
        try:
            df_saved = pd.read_csv(DATA_FILE)
            if "Dată" in df_saved.columns:
                df_saved["Dată"] = pd.to_datetime(
                    df_saved["Dată"].astype(str).str.strip(),
                    format="%d.%m.%Y", errors="coerce",
                )
                df_saved = df_saved.dropna(subset=["Dată"])
            if "Observații" not in df_saved.columns:
                df_saved["Observații"] = ""
            else:
                df_saved["Observații"] = df_saved["Observații"].apply(clean_obs)
            return df_saved
        except Exception:
            pass
    return pd.DataFrame(columns=["Dată", "Moment Zi", "Glicemie", "Sistolică", "Diastolică", "Puls", "Observații"])

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
    if pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    else:
        df[date_col] = pd.to_datetime(df[date_col].astype(str).str.strip(), format="%d.%m.%Y", errors="coerce")
    df = df.dropna(subset=[date_col])
    df = df.sort_values(by=date_col, ascending=True).reset_index(drop=True)

def save_local_record(date_str, moment_str, glic_v, sis_v, dia_v, puls_v, obs_v):
    global df
    current_df = st.session_state.local_df_v2.copy()
    if col_obs in current_df.columns:
        current_df[col_obs] = current_df[col_obs].apply(clean_obs)
    else:
        current_df[col_obs] = ""

    if not current_df.empty and date_col in current_df.columns:
        current_df["Dată_str"] = pd.to_datetime(current_df[date_col], errors="coerce").dt.strftime("%d.%m.%Y")
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
            date_col: pd.to_datetime(date_str, format="%d.%m.%Y"),
            moment_col: moment_str, col_glic: glic_v, col_sis: sis_v, col_dia: dia_v, col_puls: puls_v,
            col_obs: obs_clean_val,
        }
        current_df = pd.concat([current_df, pd.DataFrame([new_record])], ignore_index=True)

    st.session_state.local_df_v2 = current_df
    try:
        df_to_save = current_df.copy()
        if pd.api.types.is_datetime64_any_dtype(df_to_save[date_col]):
            df_to_save[date_col] = df_to_save[date_col].dt.strftime("%d.%m.%Y")
        else:
            df_to_save[date_col] = pd.to_datetime(df_to_save[date_col], errors="coerce").dt.strftime("%d.%m.%Y")
        df_to_save.to_csv(DATA_FILE, index=False)
    except Exception as e:
        print(f"Erore: {e}")

def format_table_column(series):
    return series.astype(str).str.strip().replace(["0", "0.0", "nan", "None", "", "<NA>"], "")

# ==========================================
# EVALUARE SPIKE & CAUZĂ ALIMENTARĂ
# ==========================================
def check_food_cause(obs_text):
    obs_clean_text = clean_obs(obs_text)
    if not obs_clean_text:
        return ""
    obs_clean = remove_diacritics(obs_clean_text.lower())
    found_foods = set()
    
    for cat, items in st.session_state.food_categories.items():
        for item in items:
            kw_clean = remove_diacritics(item.lower())
            if re.search(r'\b' + re.escape(kw_clean) + r'\b', obs_clean):
                found_foods.add(item)
    
    if found_foods:
        return f" (Cauză: {', '.join(sorted(found_foods))})"
    elif len(obs_clean_text) > 0:
        return f" ({obs_clean_text[:20]})"
    return ""

def is_glic_spike(val, moment_zi=""):
    try:
        v = float(val)
        if v == 0 or pd.isna(v): return False
        if "După masă" in str(moment_zi):
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

def evaluate_glic(val, moment_zi=""):
    try:
        v = float(val)
        if v == 0 or pd.isna(v): return "Nemăsurat"
        if "După masă" in str(moment_zi):
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
# SIDEBAR & FILTRARE + 1. BUTON SALVARE SIDEBAR
# ==========================================
st.sidebar.markdown(f"### 👤 **{st.session_state.user}**")
st.sidebar.markdown(f"Rol: <span class='role-badge'>{current_role}</span>", unsafe_allow_html=True)
st.sidebar.markdown("<br>", unsafe_allow_html=True)

# Buton de salvare sus în sidebar
if st.sidebar.button("💾 Salvează Datele (Sidebar)", key="sidebar_save_btn", use_container_width=True):
    save_all_files()
    st.sidebar.success("Datele au fost salvate cu succes din sidebar!")

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
    # 2. Buton de salvare rapidă (Sus în pagină)
    top_col1, top_col2 = st.columns([4, 1])
    with top_col2:
        if st.button("💾 Salvează Rapid", key="fast_save_top", use_container_width=True):
            save_all_files()
            st.success("Salvat cu succes!")

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
        
        x_labels_composed = [f"{d.strftime('%d.%m')} ({m[:3]})" for d, m in zip(view_df[date_col], view_df[moment_col])]

        with sub_tab_glic:
            st.markdown("ℹ️ **Legendă Glicemie:** 🔵 Albastru = Valoare în intervalul optim | 🔴 Roșu = Valoare crescută / Spike peste prag.")
            if col_glic in view_df.columns:
                glic_vals = pd.to_numeric(view_df[col_glic], errors="coerce").replace(0, None)
                moments = view_df[moment_col].tolist() if moment_col in view_df.columns else [""] * len(view_df)

                spike_colors = []
                spike_texts = []

                for v, m in zip(glic_vals, moments):
                    if is_glic_spike(v, m):
                        spike_colors.append("#dc2626")
                    else:
                        spike_colors.append("#38bdf8")
                    spike_texts.append(str(int(v)) if pd.notna(v) else "")

                fig_g = go.Figure()
                fig_g.add_trace(go.Scatter(
                    x=x_labels_composed, y=glic_vals, mode="lines+markers+text", name="Glicemie",
                    line=dict(color="#38bdf8", width=2.5),
                    marker=dict(size=10, color=spike_colors),
                    text=spike_texts, textposition="top center",
                    textfont=dict(size=9.5, color="#ffffff"),
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
                df_g_tab = view_df[cols_g].copy()
                df_g_tab[date_col] = df_g_tab[date_col].dt.strftime("%d.%m.%Y")
                df_g_tab["Status Glicemie"] = df_g_tab.apply(lambda r: evaluate_glic(r[col_glic], r[moment_col]), axis=1)
                df_g_tab[col_glic] = format_table_column(df_g_tab[col_glic])
                df_g_tab[col_obs] = df_g_tab[col_obs].apply(clean_obs)
                df_g_tab = df_g_tab[df_g_tab[col_glic] != ""]
                st.dataframe(apply_color_styling(df_g_tab, ["Status Glicemie"]), use_container_width=True)

        with sub_tab_ta:
            st.markdown("ℹ️ **Legendă Tensiune:** 🔵 Albastru/Indigo = Tensiune Sistolică normală | 🟠 Portocaliu = Diastolică | 🔴 Roșu = Valori de Tensiune Crescută.")
            if col_sis in view_df.columns and col_dia in view_df.columns:
                sis_vals = pd.to_numeric(view_df[col_sis], errors="coerce").replace(0, None)
                dia_vals = pd.to_numeric(view_df[col_dia], errors="coerce").replace(0, None)
                
                sis_colors = ["#dc2626" if is_ta_spike(s, d) else "#2563eb" for s, d in zip(sis_vals, dia_vals)]
                dia_colors = ["#dc2626" if is_ta_spike(s, d) else "#f59e0b" for s, d in zip(sis_vals, dia_vals)]

                fig_ta = go.Figure()
                fig_ta.add_trace(go.Scatter(
                    x=x_labels_composed, y=sis_vals, mode="lines+markers+text", name="Sistolică", 
                    line=dict(color="#2563eb", width=2.5), marker=dict(size=10, color=sis_colors), 
                    text=sis_vals, textposition="top center", textfont=dict(size=10, color="#ffffff"), 
                    texttemplate="<b>%{text}</b>", connectgaps=True
                ))
                fig_ta.add_trace(go.Scatter(
                    x=x_labels_composed, y=dia_vals, mode="lines+markers+text", name="Diastolică", 
                    line=dict(color="#f59e0b", width=2.5), marker=dict(size=10, color=dia_colors), 
                    text=dia_vals, textposition="bottom center", textfont=dict(size=10, color="#ffffff"), 
                    texttemplate="<b>%{text}</b>", connectgaps=True
                ))
                
                max_s_target = st.session_state.settings.get("target_ta_sis", 120)
                fig_ta.add_hline(y=max_s_target, line_dash="dash", line_color="#dc2626", annotation_text=f"Prag Max Sistolică ({max_s_target})")
                
                fig_ta.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=40, r=40, t=50, b=120), xaxis=dict(tickangle=-45, dtick=1))
                st.plotly_chart(fig_ta, use_container_width=True)
                
                cols_t = [date_col, moment_col, col_sis, col_dia, col_obs]
                df_t_tab = view_df[cols_t].copy()
                df_t_tab[date_col] = df_t_tab[date_col].dt.strftime("%d.%m.%Y")
                df_t_tab["Status Tensiune"] = df_t_tab.apply(lambda r: evaluate_ta(r[col_sis], r[col_dia]), axis=1)
                df_t_tab[col_sis] = format_table_column(df_t_tab[col_sis])
                df_t_tab[col_dia] = format_table_column(df_t_tab[col_dia])
                df_t_tab[col_obs] = df_t_tab[col_obs].apply(clean_obs)
                df_t_tab = df_t_tab[(df_t_tab[col_sis] != "") | (df_t_tab[col_dia] != "")]
                st.dataframe(apply_color_styling(df_t_tab, ["Status Tensiune"]), use_container_width=True)

        with sub_tab_puls:
            st.markdown("ℹ️ **Legendă Puls:** 🔵 Albastru = Puls în intervalul normal (60-100 bpm) | 🔴 Roșu = Puls scăzut sau ridicat.")
            if col_puls in view_df.columns:
                puls_vals = pd.to_numeric(view_df[col_puls], errors="coerce").replace(0, None)
                puls_colors = ["#dc2626" if is_puls_spike(p) else "#38bdf8" for p in puls_vals]

                fig_p = go.Figure()
                fig_p.add_trace(go.Scatter(
                    x=x_labels_composed, y=puls_vals, mode="lines+markers+text", name="Puls",
                    line=dict(color="#38bdf8", width=2.5), marker=dict(size=10, color=puls_colors),
                    text=puls_vals, textposition="top center", textfont=dict(size=10, color="#ffffff"),
                    texttemplate="<b>%{text}</b>", connectgaps=True
                ))
                fig_p.add_hline(y=100, line_dash="dash", line_color="#dc2626", annotation_text="Prag Max Puls (100)")
                fig_p.add_hline(y=60, line_dash="dash", line_color="#f59e0b", annotation_text="Prag Min Puls (60)")
                fig_p.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=40, r=40, t=50, b=120), xaxis=dict(tickangle=-45, dtick=1))
                st.plotly_chart(fig_p, use_container_width=True)

                cols_p = [date_col, moment_col, col_puls, col_obs]
                df_p_tab = view_df[cols_p].copy()
                df_p_tab[date_col] = df_p_tab[date_col].dt.strftime("%d.%m.%Y")
                df_p_tab["Status Puls"] = df_p_tab.apply(lambda r: evaluate_puls(r[col_puls]), axis=1)
                df_p_tab[col_puls] = format_table_column(df_p_tab[col_puls])
                df_p_tab[col_obs] = df_p_tab[col_obs].apply(clean_obs)
                df_p_tab = df_p_tab[df_p_tab[col_puls] != ""]
                st.dataframe(apply_color_styling(df_p_tab, ["Status Puls"]), use_container_width=True)

        with sub_tab_all:
            st.markdown("### 📋 Istoric Complet Înregistrări")
            df_all_tab = view_df.copy()
            if not df_all_tab.empty:
                df_all_tab[date_col] = df_all_tab[date_col].dt.strftime("%d.%m.%Y")
                for c in [col_glic, col_sis, col_dia, col_puls]:
                    if c in df_all_tab.columns:
                        df_all_tab[c] = format_table_column(df_all_tab[c])
                st.dataframe(df_all_tab, use_container_width=True)

# ----------------- TAB: ADAUGĂ / SUPRASCRIE -----------------
if is_admin:
    with tab_dict["➕ Adaugă / Suprascrie"]:
        st.markdown("### ➕ Adăugare sau Suprascriere Măsurători")
        with st.form("form_add_record"):
            f_date = st.date_input("Dată", value=date.today())
            f_moment = st.selectbox("Moment Zi", ["Dimineața (Înainte de masă)", "Dimineața (După masă)", "Prânz (Înainte de masă)", "Prânz (După masă)", "Seara (Înainte de masă)", "Seara (După masă)", "Înainte de culcare", "Noaptea"])
            
            c1, c2, c3, c4 = st.columns(4)
            with c1: f_glic = st.number_input("Glicemie (mg/dL)", min_value=0, max_value=600, value=0)
            with c2: f_sis = st.number_input("Tensiune Sistolică", min_value=0, max_value=300, value=0)
            with c3: f_dia = st.number_input("Tensiune Diastolică", min_value=0, max_value=200, value=0)
            with c4: f_puls = st.number_input("Puls (bpm)", min_value=0, max_value=250, value=0)
            
            f_obs = st.text_input("Observații / Cauză alimentară", placeholder="Ex: am mancat o prajitura, stres, etc.")
            
            submitted = st.form_submit_button("💾 Salvează Înregistrarea", use_container_width=True)
            if submitted:
                save_local_record(f_date.strftime("%d.%m.%Y"), f_moment, f_glic, f_sis, f_dia, f_puls, f_obs)
                st.success(f"Înregistrarea pentru {f_date.strftime('%d.%m.%Y')} ({f_moment}) a fost salvată!")
                trigger_rerun()

# ----------------- TAB: TRATAMENT -----------------
with tab_dict["💊 Tratament"]:
    st.markdown("### 💊 Schema de Tratament Curentă")
    st.dataframe(st.session_state.meds_df, use_container_width=True)
    
    st.markdown("---")
    st.markdown("### 📜 Istoric Administrare Medicamente")
    if not st.session_state.meds_hist_df.empty:
        st.dataframe(st.session_state.meds_hist_df, use_container_width=True)
    else:
        st.info("Nicio acțiune înregistrată în istoric.")

# ----------------- TAB: PROGRAMĂRI -----------------
if is_admin:
    with tab_dict["📅 Programări"]:
        st.markdown("### 📅 Programări Medicale")
        st.dataframe(st.session_state.prog_df, use_container_width=True)

# ----------------- TAB: RAPORT PDF -----------------
with tab_dict["📄 Raport PDF"]:
    st.markdown("### 📄 Generare Raport Medical PDF")
    st.write("Poți genera și descărca un raport detaliat în format PDF cu măsurătorile tale.")
    if st.button("📥 Generează Raport PDF", use_container_width=True):
        st.info("Funcționalitate pregătită pentru export PDF.")

# ----------------- TAB: SETĂRI -----------------
with tab_dict["⚙️ Setări"]:
    st.markdown("### ⚙️ Setări Aplicație & Notificări")
    with st.form("settings_form"):
        s_email = st.text_input("Email Sender (iCloud)", value=st.session_state.settings.get("email_sender", ""))
        s_pass = st.text_input("Parolă aplicație (App-Specific Password)", type="password", value=st.session_state.settings.get("email_password", ""))
        
        c_s1, c_s2 = st.columns(2)
        with c_s1:
            t_g_max = st.number_input("Prag Maxim Glicemie (Înainte de masă)", value=int(st.session_state.settings.get("target_glic_max", 120)))
            t_gp_max = st.number_input("Prag Maxim Glicemie (După masă)", value=int(st.session_state.settings.get("target_glic_post_max", 160)))
        with c_s2:
            t_s_sis = st.number_input("Prag Maxim Tensiune Sistolică", value=int(st.session_state.settings.get("target_ta_sis", 120)))
            t_s_dia = st.number_input("Prag Maxim Tensiune Diastolică", value=int(st.session_state.settings.get("target_ta_dia", 80)))

        saved_set = st.form_submit_button("💾 Salvează Setările", use_container_width=True)
        if saved_set:
            st.session_state.settings["email_sender"] = s_email
            st.session_state.settings["email_password"] = s_pass
            st.session_state.settings["target_glic_max"] = t_g_max
            st.session_state.settings["target_glic_post_max"] = t_gp_max
            st.session_state.settings["target_ta_sis"] = t_s_sis
            st.session_state.settings["target_ta_dia"] = t_s_dia
            st.success("Setările au fost salvate cu succes!")

# ==========================================
# 3. ZONA DE JOS: BUTONUL CLASIC DE SALVARE
# ==========================================
st.markdown("<br><hr>", unsafe_allow_html=True)
c_bot1, c_bot2, c_bot3 = st.columns([1, 2, 1])
with c_bot2:
    if st.button("💾 Salvează Toate Datele (Jos)", key="bottom_save_btn", type="primary", use_container_width=True):
        save_all_files()
        st.success("Toate fișierele și datele au fost salvate cu succes din partea de jos a paginii!")

st.caption("🔒 Sesiunea ta este securizată. Dacă părăsești aplicația și trec 10 minute de inactivitate, vei fi deconectat automat.")
