import io
import os
import re
import smtplib
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
        "🔴 Indice Glicemic Ridicat (Dulciuri / Făinoase / Fast-Food / Băuturi cu zahăr)": [
            "ciocolată", "prăjitură", "tort", "înghețată", "zahăr", "miere", "biscuiți",
            "pâine albă", "pizza", "paste albe", "cartofi prăjiți", "covrigi", "napolitane",
            "croissant", "gogoși", "patiserie", "cornuri", "suc", "cola", "fanta", "pepsi", "bere", "energizant"
        ],
        "🟡 Indice Glicemic Mediu (Cereale / Paste integrale / Legume amidonoase)": [
            "pâine integrală", "paste integrale", "orez integral", "orez basmati", "orez alb",
            "fulgi de ovăz", "fulgi de mei", "fulgi de secară", "cartofi fierți", "porumb", "mălai (mămăligă)", "mazăre", "fasole boabe"
        ],
        "🟢 Indice Glicemic Scăzut / Altele (Fără impact major sau băuturi zero)": [
            "cola 0", "pepsi zero", "apă minerală", "cafea fără zahăr", "ceai neîndulcit", 
            "stres", "oboseală", "după efort fizic", "masă copioasă", "salată verde", "castraveți", "roșii"
        ]
    }
    if os.path.exists(FOODS_FILE):
        try:
            df_f = pd.read_csv(FOODS_FILE)
            categories = {}
            for _, row in df_f.iterrows():
                cat = row["Categorie"]
                item = row["Element"]
                if cat not in categories: categories[cat] = []
                categories[cat].append(item)
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
            rows.append({"Categorie": cat, "Element": item})
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

def trimite_email_alerta(destinatar, subiect, mesaj):
    email_sender = st.session_state.settings.get("email_sender", "")
    email_password = st.session_state.settings.get("email_password", "")
    
    if not email_sender or not email_password:
        return False, "Datele de configurare email lipsesc din Setări."

    try:
        msg = EmailMessage()
        msg.set_content(mesaj)
        msg['Subject'] = subiect
        msg['From'] = email_sender
        msg['To'] = destinatar

        with smtplib.SMTP_SSL('smtp.mail.me.com', 465, timeout=10) as smtp:
            smtp.login(email_sender, email_password)
            smtp.send_message(msg)
        return True, "Email trimis cu succes prin iCloud!"
    except Exception as e:
        return False, f"Erore trimitere iCloud: {str(e)}"

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
        
        x_labels_composed = [f"{d.strftime('%d.%m')} ({m})" for d, m in zip(view_df[date_col], view_df[moment_col])]

        with sub_tab_glic:
            if col_glic in view_df.columns:
                glic_vals = pd.to_numeric(view_df[col_glic], errors="coerce").replace(0, None)
                moments = view_df[moment_col].tolist() if moment_col in view_df.columns else [""] * len(view_df)
                obs_list = view_df[col_obs].tolist() if col_obs in view_df.columns else [""] * len(view_df)

                spike_colors = []
                spike_texts = []

                for v, m, obs in zip(glic_vals, moments, obs_list):
                    if is_glic_spike(v, m):
                        cause = check_food_cause(obs)
                        spike_colors.append("#ef4444")
                        spike_texts.append(f"⚠️ {int(v)}{cause}")
                    else:
                        spike_colors.append("#38bdf8")
                        spike_texts.append(str(int(v)) if pd.notna(v) else "")

                fig_g = go.Figure()
                fig_g.add_trace(go.Scatter(
                    x=x_labels_composed, y=glic_vals, mode="lines+markers+text", name="Glicemie",
                    line=dict(color="#38bdf8", width=3),
                    marker=dict(size=12, color=spike_colors),
                    text=spike_texts, textposition="top center",
                    textfont=dict(size=10, color="#ffffff"),
                    connectgaps=True
                ))
                
                max_post = st.session_state.settings.get("target_glic_post_max", 160)
                max_pre = st.session_state.settings.get("target_glic_max", 120)
                fig_g.add_hline(y=max_post, line_dash="dash", line_color="#ef4444", annotation_text=f"Prag Maxim După Masă ({max_post})")
                fig_g.add_hline(y=max_pre, line_dash="dot", line_color="#f59e0b", annotation_text=f"Prag Maxim Înainte Masă ({max_pre})")
                
                fig_g.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=40, r=40, t=50, b=80), xaxis=dict(tickangle=-35))
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
            if col_sis in view_df.columns and col_dia in view_df.columns:
                sis_vals = pd.to_numeric(view_df[col_sis], errors="coerce").replace(0, None)
                dia_vals = pd.to_numeric(view_df[col_dia], errors="coerce").replace(0, None)
                fig_ta = go.Figure()
                fig_ta.add_trace(go.Scatter(x=x_labels_composed, y=sis_vals, mode="lines+markers+text", name="Sistolică", line=dict(color="#ef4444", width=3), marker=dict(size=10), text=sis_vals, textposition="top center", textfont=dict(size=11, color="#ffffff"), texttemplate="<b>%{text}</b>", connectgaps=True))
                fig_ta.add_trace(go.Scatter(x=x_labels_composed, y=dia_vals, mode="lines+markers+text", name="Diastolică", line=dict(color="#f59e0b", width=3), marker=dict(size=10), text=dia_vals, textposition="bottom center", textfont=dict(size=11, color="#ffffff"), texttemplate="<b>%{text}</b>", connectgaps=True))
                fig_ta.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=40, r=40, t=50, b=80), xaxis=dict(tickangle=-35))
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
            if col_puls in view_df.columns:
                puls_vals = pd.to_numeric(view_df[col_puls], errors="coerce").replace(0, None)
                fig_p = go.Figure()
                fig_p.add_trace(go.Scatter(x=x_labels_composed, y=puls_vals, mode="lines+markers+text", name="Puls (bpm)", line=dict(color="#10b981", width=3), marker=dict(size=10), text=puls_vals, textposition="top center", textfont=dict(size=11, color="#ffffff"), texttemplate="<b>%{text}</b>", connectgaps=True))
                fig_p.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=40, r=40, t=50, b=80), xaxis=dict(tickangle=-35))
                st.plotly_chart(fig_p, use_container_width=True)
                cols_p = [date_col, moment_col, col_puls, col_obs]
                df_p_tab = view_df[cols_p].copy()
                df_p_tab[date_col] = df_p_tab[date_col].dt.strftime("%d.%m.%Y")
                df_p_tab["Status Puls"] = df_p_tab[col_puls].apply(evaluate_puls)
                df_p_tab[col_puls] = format_table_column(df_p_tab[col_puls])
                df_p_tab[col_obs] = df_p_tab[col_obs].apply(clean_obs)
                df_p_tab = df_p_tab[df_p_tab[col_puls] != ""]
                st.dataframe(apply_color_styling(df_p_tab, ["Status Puls"]), use_container_width=True)

        with sub_tab_all:
            df_all = view_df.copy()
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
            st.dataframe(df_all, use_container_width=True, height=800)

# ----------------- TAB: ADAUGĂ / SUPRASCRIE (ADMIN) -----------------
if is_admin and "➕ Adaugă / Suprascrie" in tab_dict:
    with tab_dict["➕ Adaugă / Suprascrie"]:
        st.markdown("### 📝 Formular Introducere / Suprascriere Măsurători")
        if "success_message" in st.session_state:
            st.success(st.session_state["success_message"])
            del st.session_state["success_message"]

        with st.container(border=True):
            selected_date = st.date_input("📅 Selectează Data", value=date.today(), key="input_date_picker")
            
            momente_opțiuni = [
                "Dimineața - Înainte de masă", 
                "Dimineața - După masă", 
                "Prânz - Înainte de masă", 
                "Prânz - După masă", 
                "Seara - Înainte de masă", 
                "Seara - După masă"
            ]
            selected_moment = st.selectbox("🍽️ Momentul Măsurătorii", momente_opțiuni, key="input_moment_select")

            existing_row = pd.DataFrame()
            if not df.empty and date_col in df.columns and moment_col in df.columns:
                date_str = selected_date.strftime("%d.%m.%Y")
                match = df[(df[date_col].dt.strftime("%d.%m.%Y") == date_str) & (df[moment_col] == selected_moment)]
                if not match.empty:
                    existing_row = match.iloc[0]
                    st.warning(f"⚠️ Există deja o înregistrare pentru {date_str} - {selected_moment}. Salvarea va SUPRASCRIE.")

            def get_val(col_name):
                if not existing_row.empty and col_name in existing_row:
                    try: return int(float(existing_row[col_name])) if not pd.isna(existing_row[col_name]) else 0
                    except: return 0
                return 0

            def get_obs():
                if not existing_row.empty and col_obs in existing_row:
                    return clean_obs(existing_row[col_obs])
                return ""

            st.markdown("##### ⚡ Asistent Inteligent Mese & Indice Glicemic (Cu Căutare Rapidă)")
            
            search_food_input = st.text_input("🔍 Caută rapid alimente / elemente în categorii", key="search_food_add_input")
            
            key_suffix = f"_{selected_date.strftime('%Y%m%d')}_{selected_moment}"
            selected_quick_items = []
            
            cat_cols = st.columns(len(st.session_state.food_categories))
            for idx, (cat_name, items) in enumerate(st.session_state.food_categories.items()):
                with cat_cols[idx]:
                    st.caption(cat_name)
                    filtered_items = [i for i in items if search_food_input.strip().lower() in i.lower()] if search_food_input else items
                    for item in filtered_items:
                        if st.checkbox(item, key=f"quick_{cat_name}_{item}{key_suffix}"):
                            selected_quick_items.append(item)

            base_obs_initial = get_obs()
            if selected_quick_items:
                joined_quick = ", ".join(selected_quick_items)
                if base_obs_initial:
                    if joined_quick not in base_obs_initial:
                        base_obs_initial = f"{base_obs_initial}, {joined_quick}"
                else:
                    base_obs_initial = joined_quick

            with st.form("form_add_overwrite"):
                c1, c2 = st.columns(2)
                with c1: glic_input = st.number_input("🩸 Glicemie (mg/dL) [0 = nemăsurat]", min_value=0, value=get_val(col_glic))
                with c2:
                    sis_input = st.number_input("🫀 Tensiune Sistolică [0 = nemăsurat]", min_value=0, value=get_val(col_sis))
                    dia_input = st.number_input("🫀 Tensiune Diastolică [0 = nemăsurat]", min_value=0, value=get_val(col_dia))
                    puls_input = st.number_input("💓 Puls [0 = nemăsurat]", min_value=0, value=get_val(col_puls))

                obs_input = st.text_area("✍️ Notițe / Observații (poți edita/adăuga liber)", value=base_obs_initial)
                submitted = st.form_submit_button("💾 Salvează / Suprascrie", type="primary", use_container_width=True)

                if submitted:
                    save_local_record(selected_date.strftime("%d.%m.%Y"), selected_moment, glic_input, sis_input, dia_input, puls_input, obs_input)
                    st.session_state["success_message"] = "✅ Salvare efectuată cu succes!"
                    trigger_rerun()

# ----------------- TAB: TRATAMENT -----------------
with tab_dict["💊 Tratament"]:
    st.markdown("### 💊 Schemă Tratament Medical")
    st.dataframe(st.session_state.meds_df, use_container_width=True)

    if is_admin:
        st.markdown("---")
        st.markdown("#### ⚙️ Gestiune Listă Tratament (Administrator)")
        col_m1, col_m2, col_m3 = st.columns(3)
        
        with col_m1:
            with st.container(border=True):
                st.markdown("##### ➕ Adaugă Nou")
                with st.form("add_med_form"):
                    m_nume = st.text_input("Nume")
                    m_doza = st.text_input("Doză")
                    m_orar = st.text_input("Orar")
                    m_admin = st.selectbox("Moment", ["Înainte de masă", "După masă", "Oriunde"])
                    if st.form_submit_button("Adaugă", type="primary"):
                        if m_nume:
                            new_row = pd.DataFrame([{"Medicament": m_nume, "Doză": m_doza, "Orar": m_orar, "Administrare": m_admin}])
                            st.session_state.meds_df = pd.concat([st.session_state.meds_df, new_row], ignore_index=True)
                            add_history_entry("Adăugare", m_nume, f"Doză: {m_doza}, Orar: {m_orar}")
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
                        e_orar = st.text_input("Orar", value=med_data["Orar"])
                        admin_opts = ["Înainte de masă", "După masă", "Oriunde"]
                        idx_admin = admin_opts.index(med_data["Administrare"]) if med_data["Administrare"] in admin_opts else 0
                        e_admin = st.selectbox("Moment nou", admin_opts, index=idx_admin)
                        if st.form_submit_button("Salvează Modificarea", type="primary"):
                            idx = st.session_state.meds_df.index[st.session_state.meds_df["Medicament"] == med_to_edit][0]
                            st.session_state.meds_df.loc[idx, "Doză"] = e_doza
                            st.session_state.meds_df.loc[idx, "Orar"] = e_orar
                            st.session_state.meds_df.loc[idx, "Administrare"] = e_admin
                            add_history_entry("Modificare", med_to_edit, f"Doză: -> {e_doza}")
                            st.success("Actualizat!")
                            trigger_rerun()

        with col_m3:
            with st.container(border=True):
                st.markdown("##### 🗑️ Șterge")
                if not st.session_state.meds_df.empty:
                    to_delete = st.selectbox("Selectează de șters", st.session_state.meds_df["Medicament"].tolist())
                    if st.button("Șterge Definitiv", type="secondary"):
                        st.session_state.meds_df = st.session_state.meds_df[st.session_state.meds_df["Medicament"] != to_delete].reset_index(drop=True)
                        add_history_entry("Ștergere", to_delete, "Eliminat din schemă.")
                        st.success(f"{to_delete} șters!")
                        trigger_rerun()

# ----------------- TAB: PROGRAMĂRI -----------------
if is_admin and "📅 Programări" in tab_dict:
    with tab_dict["📅 Programări"]:
        st.markdown("### 📅 Programări Medicale, Editare, Ștergere & Alerte")
        st.dataframe(st.session_state.prog_df, use_container_width=True)

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
                            st.success("Programare actualizată cu succes!")
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
                                    mesaj_final += f"• {row['Tip']} la {row['Clinică']} pe data de {row['Dată']} ora {row.get('Ora', '')} (Au rămas {zile_ramase} zile!)\n"
                                    trimis_ok += 1
                            except:
                                pass
                        
                        if trimis_ok > 0:
                            succes, rez = trimite_email_alerta(destinatar_auto, "🔔 Notificare Programare Medicală", mesaj_final)
                            if succes:
                                st.success("Notificările automate au fost trimise prin iCloud!")
                            else:
                                st.error(rez)
                        else:
                            st.info("Nicio programare activă nu necesită alertă astăzi.")

# ----------------- TAB: SETĂRI & ADMIN -----------------
with tab_dict["⚙️ Setări"]:
    st.markdown("### ⚙️ Setări Generale, Test Conexiune iCloud & Elemente Mese")
    
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
                target_user = st.selectbox("Selectează utilizator", user_list)
                current_target_role = st.session_state.users[target_user].get("role", "Membru")
                role_options = ["Membru", "Doctor", "Administrator"]
                updated_role = st.selectbox("Schimbă Rol", role_options, index=role_options.index(current_target_role))
                updated_pass = st.text_input("Parolă Nouă (opțional)", type="password", key="pass_edit_user")

                if st.button("💾 Salvează Modificări Utilizator"):
                    st.session_state.users[target_user]["role"] = updated_role
                    if updated_pass:
                        st.session_state.users[target_user]["pass"] = updated_pass
                    st.success(f"Detaliile pentru {target_user} au fost actualizate!")
                    trigger_rerun()
        st.markdown("<br>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("#### 🍎 Gestiune Elemente Mese & Indice Glicemic (Cu Căutare pentru Ștergere)")
            fc_cat = st.selectbox("Selectează Categoria", list(st.session_state.food_categories.keys()))
            
            c_f1, c_f2 = st.columns(2)
            with c_f1:
                new_food_item = st.text_input("Adaugă element nou (ex: cola 0, cereale integrale etc.)")
                if st.button("➕ Adaugă în Categorie"):
                    if new_food_item and new_food_item.strip():
                        item_clean = new_food_item.strip().lower()
                        if item_clean not in st.session_state.food_categories[fc_cat]:
                            st.session_state.food_categories[fc_cat].append(item_clean)
                            save_custom_foods()
                            st.success(f"Elementul '{item_clean}' a fost adăugat!")
                            trigger_rerun()
            with c_f2:
                search_del_item = st.text_input("🔍 Caută element de șters", key="search_del_food_input")
                items_to_show = [i for i in st.session_state.food_categories[fc_cat] if search_del_item.strip().lower() in i.lower()] if search_del_item else st.session_state.food_categories[fc_cat]
                
                if items_to_show:
                    del_food_item = st.selectbox("Selectează element existent", items_to_show, key="del_food_select")
                    if st.button("🗑️ Șterge Elementul Selectat"):
                        st.session_state.food_categories[fc_cat].remove(del_food_item)
                        save_custom_foods()
                        st.success(f"Elementul '{del_food_item}' a fost șters!")
                        trigger_rerun()
                else:
                    st.info("Niciun element găsit după căutare.")

    st.markdown("---")
    col_set1, col_set2 = st.columns(2)
    with col_set1:
        st.markdown("#### ✉️ Configurare Server iCloud Mail & Test")
        st.session_state.settings["email_sender"] = st.text_input("Adresa ta de iCloud (expeditor, ex: nume@icloud.com)", value=st.session_state.settings.get("email_sender", ""))
        st.session_state.settings["email_password"] = st.text_input("Parolă specifică de aplicație iCloud (App-Specific Password)", type="password", value=st.session_state.settings.get("email_password", ""))
        st.markdown("<small>💡 *Notă: Nu folosi parola ta principală Apple ID. Vezi mai jos ghidul de generare.*</small>", unsafe_allow_html=True)
        
        # Buton dedicat pentru testarea conexiunii SMTP și eliminarea erorii de timeout
        if st.button("🔌 Testează Conexiunea iCloud (Trimite Email Test)", type="primary"):
            test_dest = st.session_state.settings.get("email_sender", "")
            if not test_dest:
                st.error("Completează mai întâi adresa de email a expeditorului.")
            else:
                success_t, msg_t = trimite_email_alerta(test_dest, "🧪 Test Conexiune HealthTrack Pro", "Salut! Conexiunea SMTP cu serverul iCloud funcționează perfect.")
                if success_t:
                    st.success("✅ Conexiune reușită! Emailul de test a fost trimis.")
                else:
                    st.error(f"❌ {msg_t}")

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 💾 Backup Manual (CSV)")
        if not view_df.empty:
            df_backup = view_df.copy()
            if date_col in df_backup.columns:
                if not pd.api.types.is_datetime64_any_dtype(df_backup[date_col]):
                    df_backup[date_col] = pd.to_datetime(df_backup[date_col], errors="coerce")
                df_backup = df_backup.dropna(subset=[date_col]).sort_values(by=date_col, ascending=True).reset_index(drop=True)
                df_backup[date_col] = df_backup[date_col].dt.strftime("%d.%m.%Y")
                
            for col in df_backup.columns:
                if df_backup[col].dtype == object:
                    df_backup[col] = df_backup[col].apply(lambda x: remove_diacritics(str(x)) if pd.notna(x) else x)
            df_backup.columns = [remove_diacritics(c) for c in df_backup.columns]
            
            if 'Luna_An' in df_backup.columns: df_backup = df_backup.drop(columns=['Luna_An'])
                
            csv_data = df_backup.to_csv(index=False).encode('utf-8')
            st.download_button(label="📥 Descarcă Backup CSV", data=csv_data, file_name="backup_date_medicale.csv", mime="text/csv", use_container_width=True)

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
        opt_tabele = st.checkbox("Include Tabelul Centralizator (Curat, Fără Diacritice/Nan) 📋", value=True)

    def generate_pdf_chart_glic(x_vals, y_vals, moments_list, title, ylabel, color_hex):
        plt.figure(figsize=(8.0, 2.6))
        plt.plot(x_vals, y_vals, marker="o", linestyle="-", color=color_hex, linewidth=2.2, markersize=5)
        
        # Puncte roșii pentru spike-uri pe grafic, exact ca în jurnal
        for xi, yi, m in zip(x_vals, y_vals, moments_list):
            if yi > 0:
                is_spike = is_glic_spike(yi, m)
                dot_color = "#ef4444" if is_spike else color_hex
                plt.plot(xi, yi, marker="o", markersize=6, color=dot_color)
                plt.annotate(str(int(yi)), (xi, yi), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=7.5, fontweight="bold", bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=dot_color, alpha=0.9))
                
        plt.title(title, fontsize=10, fontweight="bold", color="#1e3a8a", pad=14)
        plt.ylabel(ylabel, fontsize=9, fontweight="bold")
        plt.xticks(rotation=35, fontsize=7.5, ha="right")
        plt.yticks(fontsize=8)
        plt.grid(True, linestyle=":", alpha=0.6)
        plt.tight_layout()

        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format="png", dpi=220)
        plt.close()
        img_buffer.seek(0)
        return img_buffer

    def generate_pdf_chart_simple(x_vals, y_vals, title, ylabel, color_hex):
        plt.figure(figsize=(8.0, 2.6))
        plt.plot(x_vals, y_vals, marker="o", linestyle="-", color=color_hex, linewidth=2.2, markersize=5)
        for xi, yi in zip(x_vals, y_vals):
            if yi > 0:
                plt.annotate(str(int(yi)), (xi, yi), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=7.5, fontweight="bold", bbox=dict(boxstyle="round,pad=0.15", fc="white", ec=color_hex, alpha=0.9))
        plt.title(title, fontsize=10, fontweight="bold", color="#1e3a8a", pad=14)
        plt.ylabel(ylabel, fontsize=9, fontweight="bold")
        plt.xticks(rotation=35, fontsize=7.5, ha="right")
        plt.yticks(fontsize=8)
        plt.grid(True, linestyle=":", alpha=0.6)
        plt.tight_layout()

        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format="png", dpi=220)
        plt.close()
        img_buffer.seek(0)
        return img_buffer

    def make_pdf_report(data_frame, include_glic, include_ta, include_puls, include_tables):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
        story = []
        styles = getSampleStyleSheet()

        title_text = remove_diacritics("RAPORT MEDICAL DE MONITORIZARE - HEALTHTRACK PRO")
        date_text = remove_diacritics(f"Generat la: {datetime.now().strftime('%d.%m.%Y %H:%M')} | Perioada: {filtru_luni_str}")

        story.append(Paragraph(f"<b>{title_text}</b>", ParagraphStyle("TitleStyle", parent=styles["Heading1"], fontSize=13, textColor=colors.HexColor("#1e3a8a"), alignment=1, spaceAfter=15)))
        story.append(Paragraph(date_text, ParagraphStyle("DateStyle", parent=styles["Normal"], alignment=1, spaceAfter=20)))

        if not data_frame.empty:
            x_data = [f"{d.strftime('%d.%m')} ({m[:3]})" for d, m in zip(data_frame[date_col], data_frame[moment_col])]
            moments_arr = data_frame[moment_col].tolist() if moment_col in data_frame.columns else [""] * len(data_frame)
            
            if include_glic and col_glic in data_frame.columns:
                g_vals = pd.to_numeric(data_frame[col_glic], errors='coerce').fillna(0).tolist()
                story.append(Paragraph("Evolutie Glicemie", styles["Heading2"]))
                img_buf = generate_pdf_chart_glic(x_data, g_vals, moments_arr, "Glicemie (mg/dL)", "mg/dL", "#38bdf8")
                story.append(Image(img_buf, width=470, height=150))
                story.append(Spacer(1, 15))
                
            if include_ta and col_sis in data_frame.columns:
                s_vals = pd.to_numeric(data_frame[col_sis], errors='coerce').fillna(0).tolist()
                story.append(Paragraph("Evolutie Tensiune Sistolica", styles["Heading2"]))
                img_buf = generate_pdf_chart_simple(x_data, s_vals, "Tensiune Sistolica (mmHg)", "mmHg", "#ef4444")
                story.append(Image(img_buf, width=470, height=150))
                story.append(Spacer(1, 15))
                
            if include_puls and col_puls in data_frame.columns:
                p_vals = pd.to_numeric(data_frame[col_puls], errors='coerce').fillna(0).tolist()
                story.append(Paragraph("Evolutie Puls", styles["Heading2"]))
                img_buf = generate_pdf_chart_simple(x_data, p_vals, "Puls (bpm)", "bpm", "#10b981")
                story.append(Image(img_buf, width=470, height=150))
                story.append(Spacer(1, 15))

            if include_tables:
                story.append(Paragraph("Date Tabelare si Observatii", styles["Heading2"]))
                table_data = [["Data", "Moment", "Glic", "TA", "Puls", "Observatii"]]
                
                t_style = [
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e3a8a")),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (-1,-1), 8),
                    ('BOTTOMPADDING', (0,0), (-1,0), 10),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ]
                
                r_idx = 1
                for _, row in data_frame.iterrows():
                    dt_str = row[date_col].strftime("%d.%m.%Y")
                    mm = remove_diacritics(str(row.get(moment_col, "")))
                    obs_val = clean_obs(row.get(col_obs, ""))
                    obs_str = remove_diacritics(obs_val)
                    
                    glic_v = row.get(col_glic, 0)
                    sis_v = row.get(col_sis, 0)
                    dia_v = row.get(col_dia, 0)
                    puls_v = row.get(col_puls, 0)
                    
                    g_str = str(int(glic_v)) if pd.notna(glic_v) and float(glic_v)>0 else ""
                    ta_str = f"{int(sis_v)}/{int(dia_v)}" if pd.notna(sis_v) and float(sis_v)>0 else ""
                    p_str = str(int(puls_v)) if pd.notna(puls_v) and float(puls_v)>0 else ""
                    
                    table_data.append([dt_str, mm, g_str, ta_str, p_str, obs_str])
                    
                    ev_g = evaluate_glic(glic_v, mm)
                    if "🟢" in ev_g: t_style.append(('TEXTCOLOR', (2, r_idx), (2, r_idx), colors.HexColor("#16a34a")))
                    elif "🔴" in ev_g: t_style.append(('TEXTCOLOR', (2, r_idx), (2, r_idx), colors.HexColor("#dc2626")))
                    
                    ev_ta = evaluate_ta(sis_val=sis_v, dia_val=dia_v)
                    if "🟢" in ev_ta: t_style.append(('TEXTCOLOR', (3, r_idx), (3, r_idx), colors.HexColor("#16a34a")))
                    elif "🔴" in ev_ta: t_style.append(('TEXTCOLOR', (3, r_idx), (3, r_idx), colors.HexColor("#dc2626")))
                    
                    ev_p = evaluate_puls(puls_v)
                    if "🟢" in ev_p: t_style.append(('TEXTCOLOR', (4, r_idx), (4, r_idx), colors.HexColor("#16a34a")))
                    elif "🔴" in ev_p: t_style.append(('TEXTCOLOR', (4, r_idx), (4, r_idx), colors.HexColor("#dc2626")))
                    
                    r_idx += 1
                
                t = Table(table_data, colWidths=[60, 110, 40, 50, 40, 200])
                t.setStyle(TableStyle(t_style))
                story.append(t)
        else:
            story.append(Paragraph("Nu exista date pentru perioada selectata.", styles["Normal"]))

        doc.build(story)
        buffer.seek(0)
        return buffer

    if st.button("Crează Raport PDF", type="primary"):
        pdf_buffer = make_pdf_report(view_df, opt_glic, opt_ta, opt_puls, opt_tabele)
        file_name = f"Raport_Medical_{filtru_luni_str.replace(', ', '_')}.pdf"
        st.download_button(label="⬇️ Descarcă PDF", data=pdf_buffer, file_name=file_name, mime="application/pdf", use_container_width=True)
