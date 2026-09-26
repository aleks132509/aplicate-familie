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
# CONFIGURARE PAGINA & THEME (DARK MODE + MULTISELECT LUX)
# ==========================================
st.set_page_config(
    page_title="HealthTrack Pro - Monitorizare Sanatate",
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
# GESTIONARE FISIERE PERSISTENTE & SETARI EMAIL
# ==========================================
DATA_FILE = "date_medicale_utilizator.csv"
MEDS_FILE = "medicamente.csv"
MEDS_HIST_FILE = "istoric_medicamente.csv"
PROG_FILE = "programari_medicale.csv"
FOODS_FILE = "alimente_custom.csv"
BACKUP_LOG_FILE = "ultimul_backup_auto.txt"
BACKUP_ERROR_LOG_FILE = "ultima_eroare_backup_auto.txt"
ALERT_23_LOG = "ultima_alerta_23.txt"
ALERT_GAP_LOG = "ultima_alerta_gap.txt"
SETTINGS_FILE = "setari_email.json"

moment_order = [
    'Dimineata - Inainte de masa',
    'Dimineata - Dupa masa',
    'Pranz - Inainte de masa',
    'Pranz - Dupa masa',
    'Seara - Inainte de masa',
    'Seara - Dupa masa'
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
        {"Medicament": "Glucophage", "Doza": "1000 mg", "Orar / Frecventa": "Dimineata si seara, dupa masa", "Observatii": ""},
        {"Medicament": "Lagosa", "Doza": "150 mg", "Orar / Frecventa": "Dimineata si seara, dupa masa", "Observatii": ""},
        {"Medicament": "Lipantil Nano", "Doza": "145 mg", "Orar / Frecventa": "Pranz, dupa masa", "Observatii": ""},
        {"Medicament": "Sortis", "Doza": "20 mg", "Orar / Frecventa": "Seara, dupa masa", "Observatii": ""},
        {"Medicament": "Omacor", "Doza": "1000 mg", "Orar / Frecventa": "Dimineata, la pranz si seara, dupa masa", "Observatii": ""},
        {"Medicament": "Diaprel MR", "Doza": "60 mg", "Orar / Frecventa": "Dimineata, inainte masa", "Observatii": "1/2 din doza"},
        {"Medicament": "Larginina", "Doza": "1000 mg", "Orar / Frecventa": "Pranz, dupa masa", "Observatii": "10 zile pe luna"},
        {"Medicament": "Atacand", "Doza": "8 mg", "Orar / Frecventa": "Seara, dupa masa", "Observatii": ""},
        {"Medicament": "Nebilet", "Doza": "5 mg", "Orar / Frecventa": "Dimineata, dupa masa", "Observatii": ""},
        {"Medicament": "Aspenter", "Doza": "75 mg", "Orar / Frecventa": "Pranz, dupa masa", "Observatii": ""},
    ])
    df_init_m.to_csv(MEDS_FILE, index=False)
    return df_init_m

def get_initial_history():
    if os.path.exists(MEDS_HIST_FILE):
        return pd.read_csv(MEDS_HIST_FILE)
    return pd.DataFrame(columns=["Data_Ora", "Actiune", "Medicament", "Detalii"])

def get_initial_prog():
    if os.path.exists(PROG_FILE):
        try:
            df_p = pd.read_csv(PROG_FILE)
            if not df_p.empty:
                if "Ora" not in df_p.columns: df_p["Ora"] = "10:00"
                if "Efectuat" not in df_p.columns: df_p["Efectuat"] = "Nu"
                if "Clinica" not in df_p.columns: df_p["Clinica"] = "-"
                if "Zile_Alerta" not in df_p.columns: df_p["Zile_Alerta"] = "1, 3"
                if "Observatii" not in df_p.columns: df_p["Observatii"] = ""
                return df_p
        except:
            pass
            
    df_init_p = pd.DataFrame([
        {"Data": "2026-10-05", "Ora": "10:00", "Tip": "Eliberare reteta", "Clinica": "Medic de familie", "Zile_Alerta": "1, 3", "Efectuat": "Nu", "Observatii": "Ridicare reteta lunara"},
        {"Data": "2026-11-29", "Ora": "09:00", "Tip": "Analize de laborator", "Clinica": "Regina Maria", "Zile_Alerta": "1, 3, 7", "Efectuat": "Nu", "Observatii": "Repetare analize Diabet"},
        {"Data": "2026-12-05", "Ora": "14:30", "Tip": "Consult Diabet", "Clinica": "Dr. Clenciu Craiova", "Zile_Alerta": "2, 5", "Efectuat": "Nu", "Observatii": "Reteta 3 luni"},
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
            "cola 0", "pepsi zero", "apa minerala", "cafea fara zahar", "ceai neindulcit", 
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
        "Actiune": actiune,
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
        date_col_name = 'Data' if 'Data' in df_b.columns else 'Data'
        moment_col_name = 'Moment Zi' if 'Moment Zi' in df_b.columns else 'Moment Zi'
        glic_col_name = 'Glicemie'
        sis_col_name = 'Sistolica' if 'Sistolica' in df_b.columns else 'Sistolica'
        dia_col_name = 'Diastolica' if 'Diastolica' in df_b.columns else 'Diastolica'
        puls_col_name = 'Puls'
        obs_col_name = 'Observatii' if 'Observatii' in df_b.columns else 'Observatii'

        if date_col_name in df_b.columns:
            df_b["Data_dt"] = parse_flexible_date(df_b[date_col_name])
            df_b["Moment_Cat"] = pd.Categorical(df_b[moment_col_name], categories=moment_order, ordered=True)
            df_b = df_b.dropna(subset=["Data_dt"]).sort_values(by=["Data_dt", "Moment_Cat"]).drop(columns=["Data_dt", "Moment_Cat"])
        
        cols_masuratori = [c for c in [glic_col_name, sis_col_name, dia_col_name, puls_col_name] if c in df_b.columns]
        mask_are_date = pd.Series(False, index=df_b.index)
        if cols_masuratori:
            for c in cols_masuratori:
                mask_are_date = mask_are_date | (pd.to_numeric(df_b[c], errors="coerce").fillna(0) > 0)
        if obs_col_name in df_b.columns:
            cleaned_obs = df_b[obs_col_name].apply(clean_obs)
            mask_are_date = mask_are_date | (cleaned_obs != "")
        
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
        return False, "Datele de configurare email lipsesc din Setari."

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
                        
                return True, "Email trimis cu succes prin iCloud!"
            except Exception as e:
                last_error = str(e)
                time.sleep(1)
                
    return False, f"Eroare trimitere iCloud: {last_error}"

def verifica_si_fa_backup_automat():
    try:
        email_dest = st.session_state.settings.get("email_sender", "").strip()
        if not email_dest:
            return 

        azi = datetime.now().date()
        ora_curenta = datetime.now().hour

        save_all_files()

        if ora_curenta >= 23:
            ultima_alerta_23 = ""
            if os.path.exists(ALERT_23_LOG):
                try:
                    with open(ALERT_23_LOG, "r") as f:
                        ultima_alerta_23 = f.read().strip()
                except:
                    pass
            
            if ultima_alerta_23 != azi.strftime("%Y-%m-%d"):
                if os.path.exists(DATA_FILE):
                    df_chk = pd.read_csv(DATA_FILE)
                    df_chk["Data_dt"] = parse_flexible_date(df_chk["Data" if "Data" in df_chk.columns else "Data"])
                    df_azi = df_chk[df_chk["Data_dt"].dt.date == azi]
                    
                    are_date_azi = False
                    for _, r in df_azi.iterrows():
                        g = float(r.get("Glicemie", 0) or 0)
                        s = float(r.get("Sistolica" if "Sistolica" in df_azi.columns else "Sistolica", 0) or 0)
                        d = float(r.get("Diastolica" if "Diastolica" in df_azi.columns else "Diastolica", 0) or 0)
                        p = float(r.get("Puls", 0) or 0)
                        o = clean_obs(r.get("Observatii" if "Observatii" in df_azi.columns else "Observatii", ""))
                        if g > 0 or s > 0 or d > 0 or p > 0 or o:
                            are_date_azi = True
                            break
                    
                    if not are_date_azi:
                        msg_23 = f"ATENTIE! Este ora {datetime.now().strftime('%H:%M')} si nu ați înregistrat nicio masuratoare sau notita pentru ziua de astazi ({azi.strftime('%d.%m.%Y')}). Va rugam sa actualizati jurnalul in HealthTrack Pro."
                        trimite_email_cu_multiple_atasamente(email_dest, f"[Alerta Jurnal Gol] HealthTrack Pro - {azi.strftime('%d.%m.%Y')}", msg_23, {})
                        with open(ALERT_23_LOG, "w") as f:
                            f.write(azi.strftime("%Y-%m-%d"))

        ultima_alerta_gap = ""
        if os.path.exists(ALERT_GAP_LOG):
            try:
                with open(ALERT_GAP_LOG, "r") as f:
                    ultima_alerta_gap = f.read().strip()
            except:
                pass

        if ultima_alerta_gap != azi.strftime("%Y-%m-%d") and os.path.exists(DATA_FILE):
            df_gaps = pd.read_csv(DATA_FILE)
            df_gaps["Data_dt"] = parse_flexible_date(df_gaps["Data" if "Data" in df_gaps.columns else "Data"])
            df_gaps = df_gaps.dropna(subset=["Data_dt"])
            
            if not df_gaps.empty:
                min_d = df_gaps["Data_dt"].dt.date.min()
                zile_lipsa = []
                curr_d = min_d
                while curr_d < azi:
                    df_zi = df_gaps[df_gaps["Data_dt"].dt.date == curr_d]
                    zi_valida = False
                    for _, r in df_zi.iterrows():
                        g = float(r.get("Glicemie", 0) or 0)
                        s = float(r.get("Sistolica" if "Sistolica" in df_gaps.columns else "Sistolica", 0) or 0)
                        d = float(r.get("Diastolica" if "Diastolica" in df_gaps.columns else "Diastolica", 0) or 0)
                        p = float(r.get("Puls", 0) or 0)
                        o = clean_obs(r.get("Observatii" if "Observatii" in df_gaps.columns else "Observatii", ""))
                        if g > 0 or s > 0 or d > 0 or p > 0 or o:
                            zi_valida = True
                            break
                    if not zi_valida:
                        zile_lipsa.append(curr_d.strftime("%d.%m.%Y"))
                    curr_d += timedelta(days=1)
                
                if zile_lipsa:
                    msg_gap = f"ALERTA INTEGRITATE JURNAL - HEALTHTRACK PRO\n\nS-au detectat zile anterioare in care nu exista nicio valoare sau observatie inregistrata:\n"
                    for z_l in zile_lipsa[-5:]:
                        msg_gap += f"- Data de {z_l} este complet goala sau lipsa.\n"
                    msg_gap += "\nVa rugam sa verificati aplicatia pentru a asigura continuitatea istoricului medical."
                    
                    trimite_email_cu_multiple_atasamente(email_dest, f"[Alerta Zile Lipsa] HealthTrack Pro - Detectat gap in jurnal", msg_gap, {})
                    with open(ALERT_GAP_LOG, "w") as f:
                        f.write(azi.strftime("%Y-%m-%d"))

        ultima_data = None
        if os.path.exists(BACKUP_LOG_FILE):
            try:
                with open(BACKUP_LOG_FILE, "r") as f:
                    ultima_data_str = f.read().strip()[:10]
                    ultima_data = datetime.strptime(ultima_data_str, "%Y-%m-%d").date()
            except:
                pass

        if ultima_data is None or ultima_data < azi:
            temp_backup_file = "temp_backup_cron.csv"
            attachments = {}
            fisiere_incluse = []

            df_cron = get_chronological_backup_df()
            if not df_cron.empty:
                df_cron.to_csv(temp_backup_file, index=False)
                attachments["backup_date_medicale.csv"] = temp_backup_file
                fisiere_incluse.append("backup_date_medicale.csv")

            if os.path.exists(DATA_FILE):
                attachments["date_medicale_utilizator.csv"] = DATA_FILE
                fisiere_incluse.append("date_medicale_utilizator.csv")

            if os.path.exists(MEDS_FILE):
                attachments["medicamente.csv"] = MEDS_FILE
                fisiere_incluse.append("medicamente.csv")

            if os.path.exists(PROG_FILE):
                attachments["programari_medicale.csv"] = PROG_FILE
                fisiere_incluse.append("programari_medicale.csv")

            if attachments:
                mesaj_backup = f"Salut!\n\nAcesta este backup-ul tau zilnic automat generat la data de {azi.strftime('%d.%m.%Y')}.\nContine toate fisierele up-to-date.\n\nHealthTrack Pro System"
                succes, _ = trimite_email_cu_multiple_atasamente(
                    destinatar=email_dest,
                    subiect=f"[Backup Zilnic Automat] HealthTrack Pro - {azi.strftime('%d.%m.%Y')}",
                    mesaj=mesaj_backup,
                    file_paths_dict=attachments
                )
                if os.path.exists(temp_backup_file): os.remove(temp_backup_file)

                if succes:
                    with open(BACKUP_LOG_FILE, "w") as f:
                        f.write(f"{azi.strftime('%Y-%m-%d')} {datetime.now().strftime('%H:%M')}")
    except Exception as e:
        try:
            with open(BACKUP_ERROR_LOG_FILE, "w") as f:
                f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M')} | {e}")
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
        st.markdown("<p style='text-align: center; color: #94a3b8; font-size: 16px;'>Platforma de Monitorizare Medicala de Familie</p>", unsafe_allow_html=True)

        with st.container(border=True):
            username = st.text_input("👤 Utilizator")
            password = st.text_input("🔑 Parola", type="password")
            remember_me = st.checkbox("🧠 Tine-ma minte", value=True)

            if st.button("🔓 Autentificare", type="primary", use_container_width=True):
                user_data = st.session_state.users.get(username)
                if user_data and user_data["pass"] == password:
                    st.session_state.logged_in = True
                    st.session_state.user = username
                    verifica_si_fa_backup_automat()
                    trigger_rerun()
                else:
                    st.error("Utilizator sau parola incorecta!")
    st.stop()

current_user_info = st.session_state.users.get(st.session_state.user, {"role": "Membru"})
current_role = current_user_info.get("role", "Membru")
is_admin = current_role == "Administrator"

verifica_si_fa_backup_automat()

# ==========================================
# DATE MEDICALE (DINAMICE & INTEGRALE)
# ==========================================
def get_initial_data():
    start_date = datetime.strptime("12.09.2026", "%d.%m.%Y").date()
    
    if os.path.exists(DATA_FILE):
        try:
            df_temp_check = pd.read_csv(DATA_FILE)
            date_col_name = 'Data' if 'Data' in df_temp_check.columns else 'Data'
            if date_col_name in df_temp_check.columns:
                dt_parsed = parse_flexible_date(df_temp_check[date_col_name]).dt.date.dropna()
                if not dt_parsed.empty:
                    start_date = min(start_date, dt_parsed.min())
        except:
            pass

    end_date = max(datetime.now().date(), start_date)
    if os.path.exists(DATA_FILE):
        try:
            df_temp_check = pd.read_csv(DATA_FILE)
            date_col_name = 'Data' if 'Data' in df_temp_check.columns else 'Data'
            if date_col_name in df_temp_check.columns:
                dt_parsed = parse_flexible_date(df_temp_check[date_col_name]).dt.date.dropna()
                if not dt_parsed.empty:
                    end_date = max(end_date, dt_parsed.max())
        except:
            pass

    all_dates_str = []
    curr = start_date
    while curr <= end_date:
        all_dates_str.append(curr.strftime("%d.%m.%Y"))
        curr += timedelta(days=1)
        
    full_template = []
    for d_str in all_dates_str:
        for m in moment_order:
            full_template.append({
                "Data": d_str,
                "Moment Zi": m,
                "Glicemie": 0,
                "Sistolica": 0,
                "Diastolica": 0,
                "Puls": 0,
                "Observatii": ""
            })
    df_template = pd.DataFrame(full_template)
    df_template["Data_dt"] = parse_flexible_date(df_template["Data"])

    initial_defaults = [
        {"Data": "12.09.2026", "Moment Zi": "Dimineata - Inainte de masa", "Glicemie": 137, "Sistolica": 108, "Diastolica": 61, "Puls": 0, "Observatii": "Prima zi cu tratament"},
        {"Data": "12.09.2026", "Moment Zi": "Seara - Inainte de masa", "Glicemie": 134, "Sistolica": 132, "Diastolica": 61, "Puls": 0, "Observatii": "Prima zi cu tratament"},
        {"Data": "13.09.2026", "Moment Zi": "Dimineata - Inainte de masa", "Glicemie": 143, "Sistolica": 115, "Diastolica": 52, "Puls": 0, "Observatii": "A doua zi cu tratament"},
        {"Data": "13.09.2026", "Moment Zi": "Seara - Dupa masa", "Glicemie": 133, "Sistolica": 114, "Diastolica": 50, "Puls": 0, "Observatii": ""},
        {"Data": "14.09.2026", "Moment Zi": "Dimineata - Inainte de masa", "Glicemie": 114, "Sistolica": 133, "Diastolica": 62, "Puls": 0, "Observatii": ""},
        {"Data": "14.09.2026", "Moment Zi": "Seara - Inainte de masa", "Glicemie": 114, "Sistolica": 0, "Diastolica": 0, "Puls": 0, "Observatii": ""},
        {"Data": "15.09.2026", "Moment Zi": "Dimineata - Inainte de masa", "Glicemie": 116, "Sistolica": 111, "Diastolica": 70, "Puls": 0, "Observatii": ""},
        {"Data": "15.09.2026", "Moment Zi": "Dimineata - Dupa masa", "Glicemie": 151, "Sistolica": 0, "Diastolica": 0, "Puls": 0, "Observatii": ""},
        {"Data": "15.09.2026", "Moment Zi": "Seara - Inainte de masa", "Glicemie": 102, "Sistolica": 120, "Diastolica": 80, "Puls": 0, "Observatii": ""},
        {"Data": "16.09.2026", "Moment Zi": "Dimineata - Inainte de masa", "Glicemie": 108, "Sistolica": 105, "Diastolica": 64, "Puls": 0, "Observatii": ""},
        {"Data": "16.09.2026", "Moment Zi": "Seara - Inainte de masa", "Glicemie": 111, "Sistolica": 0, "Diastolica": 0, "Puls": 0, "Observatii": ""},
        {"Data": "17.09.2026", "Moment Zi": "Dimineata - Inainte de masa", "Glicemie": 105, "Sistolica": 106, "Diastolica": 68, "Puls": 78, "Observatii": ""},
        {"Data": "17.09.2026", "Moment Zi": "Seara - Inainte de masa", "Glicemie": 100, "Sistolica": 106, "Diastolica": 62, "Puls": 84, "Observatii": ""},
        {"Data": "18.09.2026", "Moment Zi": "Dimineata - Inainte de masa", "Glicemie": 127, "Sistolica": 114, "Diastolica": 72, "Puls": 78, "Observatii": "mancat tarziu, baton orez expandat cu ciocolata 0 zahar, chipsuri proteice, inghetata fara zahar"},
        {"Data": "18.09.2026", "Moment Zi": "Dimineata - Dupa masa", "Glicemie": 143, "Sistolica": 0, "Diastolica": 0, "Puls": 0, "Observatii": ""},
        {"Data": "18.09.2026", "Moment Zi": "Pranz - Inainte de masa", "Glicemie": 112, "Sistolica": 0, "Diastolica": 0, "Puls": 0, "Observatii": ""},
        {"Data": "18.09.2026", "Moment Zi": "Seara - Dupa masa", "Glicemie": 112, "Sistolica": 0, "Diastolica": 0, "Puls": 0, "Observatii": ""},
        {"Data": "19.09.2026", "Moment Zi": "Dimineata - Inainte de masa", "Glicemie": 95, "Sistolica": 0, "Diastolica": 0, "Puls": 0, "Observatii": ""},
        {"Data": "19.09.2026", "Moment Zi": "Seara - Dupa masa", "Glicemie": 150, "Sistolica": 0, "Diastolica": 0, "Puls": 0, "Observatii": "cartofi prajiti, paine alba"},
        {"Data": "20.09.2026", "Moment Zi": "Dimineata - Inainte de masa", "Glicemie": 122, "Sistolica": 120, "Diastolica": 78, "Puls": 70, "Observatii": "mancat seara prost"},
        {"Data": "20.09.2026", "Moment Zi": "Pranz - Inainte de masa", "Glicemie": 154, "Sistolica": 0, "Diastolica": 0, "Puls": 0, "Observatii": "cartofi prajiti, paine alba"},
        {"Data": "20.09.2026", "Moment Zi": "Seara - Dupa masa", "Glicemie": 149, "Sistolica": 0, "Diastolica": 0, "Puls": 0, "Observatii": "paine alba, pizza, prajitura"},
        {"Data": "21.09.2026", "Moment Zi": "Dimineata - Inainte de masa", "Glicemie": 126, "Sistolica": 0, "Diastolica": 0, "Puls": 0, "Observatii": ""},
        {"Data": "21.09.2026", "Moment Zi": "Pranz - Dupa masa", "Glicemie": 127, "Sistolica": 114, "Diastolica": 73, "Puls": 80, "Observatii": ""},
        {"Data": "21.09.2026", "Moment Zi": "Seara - Inainte de masa", "Glicemie": 87, "Sistolica": 118, "Diastolica": 73, "Puls": 67, "Observatii": "Sarmale si inghetata fara zahar"},
        {"Data": "22.09.2026", "Moment Zi": "Dimineata - Inainte de masa", "Glicemie": 118, "Sistolica": 109, "Diastolica": 72, "Puls": 75, "Observatii": ""},
        {"Data": "22.09.2026", "Moment Zi": "Seara - Inainte de masa", "Glicemie": 104, "Sistolica": 115, "Diastolica": 70, "Puls": 72, "Observatii": ""},
        {"Data": "23.09.2026", "Moment Zi": "Dimineata - Inainte de masa", "Glicemie": 148, "Sistolica": 119, "Diastolica": 68, "Puls": 73, "Observatii": "mancat seara tarziu, inghetata fara zahar"},
        {"Data": "23.09.2026", "Moment Zi": "Seara - Dupa masa", "Glicemie": 102, "Sistolica": 116, "Diastolica": 73, "Puls": 81, "Observatii": ""},
        {"Data": "24.09.2026", "Moment Zi": "Dimineata - Inainte de masa", "Glicemie": 118, "Sistolica": 110, "Diastolica": 69, "Puls": 74, "Observatii": ""},
        {"Data": "24.09.2026", "Moment Zi": "Pranz - Inainte de masa", "Glicemie": 113, "Sistolica": 123, "Diastolica": 83, "Puls": 71, "Observatii": ""},
        {"Data": "24.09.2026", "Moment Zi": "Pranz - Dupa masa", "Glicemie": 107, "Sistolica": 118, "Diastolica": 79, "Puls": 76, "Observatii": ""},
        {"Data": "24.09.2026", "Moment Zi": "Seara - Inainte de masa", "Glicemie": 110, "Sistolica": 115, "Diastolica": 72, "Puls": 74, "Observatii": ""},
        {"Data": "25.09.2026", "Moment Zi": "Dimineata - Inainte de masa", "Glicemie": 123, "Sistolica": 115, "Diastolica": 71, "Puls": 78, "Observatii": ""},
        {"Data": "25.09.2026", "Moment Zi": "Pranz - Inainte de masa", "Glicemie": 92, "Sistolica": 128, "Diastolica": 78, "Puls": 86, "Observatii": ""},
        {"Data": "25.09.2026", "Moment Zi": "Seara - Inainte de masa", "Glicemie": 113, "Sistolica": 130, "Diastolica": 88, "Puls": 74, "Observatii": ""},
        {"Data": "26.09.2026", "Moment Zi": "Dimineata - Inainte de masa", "Glicemie": 121, "Sistolica": 116, "Diastolica": 72, "Puls": 81, "Observatii": "mancat tarziu"}
    ]

    for r_def in initial_defaults:
        d_dt = parse_flexible_date(r_def["Data"])
        m_val = r_def["Moment Zi"]
        mask = (df_template["Data_dt"] == d_dt) & (df_template["Moment Zi"] == m_val)
        if mask.any():
            for col in ["Glicemie", "Sistolica", "Diastolica", "Puls"]:
                if col in r_def:
                    df_template.loc[mask, col] = r_def[col]
            if r_def.get("Observatii"):
                df_template.loc[mask, "Observatii"] = clean_obs(r_def["Observatii"])

    if os.path.exists(DATA_FILE):
        try:
            df_saved = pd.read_csv(DATA_FILE)
            if not df_saved.empty:
                date_col_name = 'Data' if 'Data' in df_saved.columns else 'Data'
                if "Sistolica" in df_saved.columns:
                    df_saved = df_saved.rename(columns={"Sistolica": "Sistolica", "Diastolica": "Diastolica", "Observatii": "Observatii"})
                
                df_saved["Data_dt"] = parse_flexible_date(df_saved[date_col_name])
                df_saved = df_saved.dropna(subset=["Data_dt"])
                
                for _, row in df_saved.iterrows():
                    d_dt = row["Data_dt"]
                    m_val = str(row.get("Moment Zi", ""))
                    mask = (df_template["Data_dt"] == d_dt) & (df_template["Moment Zi"] == m_val)
                    if mask.any():
                        for col in ["Glicemie", "Sistolica", "Diastolica", "Puls"]:
                            if col in row and pd.notna(row[col]):
                                try:
                                    val_num = float(row[col])
                                    if val_num > 0:
                                        df_template.loc[mask, col] = val_num
                                except:
                                    pass
                        obs_val = clean_obs(row.get("Observatii", ""))
                        if obs_val:
                            existing_obs = clean_obs(str(df_template.loc[mask, "Observatii"].values[0]))
                            if existing_obs:
                                if obs_val not in existing_obs:
                                    df_template.loc[mask, "Observatii"] = f"{existing_obs}, {obs_val}"
                            else:
                                df_template.loc[mask, "Observatii"] = obs_val
        except Exception as e:
            print(f"Erore: {e}")

    df_template["Moment_Cat"] = pd.Categorical(df_template["Moment Zi"], categories=moment_order, ordered=True)
    df_template = df_template.sort_values(by=["Data_dt", "Moment_Cat"]).drop(columns=["Data_dt", "Moment_Cat"]).reset_index(drop=True)
    df_template.to_csv(DATA_FILE, index=False)
    return df_template

if "local_df_v2" not in st.session_state:
    st.session_state.local_df_v2 = get_initial_data()

df = st.session_state.local_df_v2.copy()

date_col = "Data"
moment_col = "Moment Zi"
col_glic = "Glicemie"
col_sis = "Sistolica"
col_dia = "Diastolica"
col_puls = "Puls"
col_obs = "Observatii"

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
        current_df["Data_str"] = parse_flexible_date(current_df[date_col]).dt.strftime("%d.%m.%Y")
        mask = (current_df["Data_str"] == date_str) & (current_df[moment_col].astype(str) == moment_str)
        current_df = current_df.drop(columns=["Data_str"])
    else:
        mask = pd.Series([False] * len(current_df))

    obs_clean_val = clean_obs(obs_v)
    
    st.session_state.action_history_stack.append({
        "old_df": st.session_state.local_df_v2.copy(),
        "desc": f"Salvare inregistrare {date_str} - {moment_str}"
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

        if t_min <= v <= t_max: return "🟢 Normala"
        elif v < t_min: return "🔴 Mica"
        else: return "🔴 Mare"
    except:
        return ""

def evaluate_ta(sis_val, dia_val):
    try:
        s, d = float(sis_val), float(dia_val)
        if s == 0 or d == 0 or pd.isna(s) or pd.isna(d): return ""
        max_s, max_d = st.session_state.settings["target_ta_sis"], st.session_state.settings["target_ta_dia"]
        if s <= max_s and d <= max_d: return "🟢 Normala"
        else: return "🔴 Crescuta"
    except:
        return ""

def evaluate_puls(val):
    try:
        v = float(val)
        if v == 0 or pd.isna(v): return ""
        if 60 <= v <= 100: return "🟢 Normal"
        elif v < 60: return "🔴 Scazut"
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
    
    toate_lunile = st.sidebar.checkbox("Afiseaza toate lunile", value=True)
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
    filtru_luni_str = "Fara date"

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
        st.info("📭 Nu exista nicio inregistrare pentru selectia curenta.")
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
        sub_tab_glic, sub_tab_ta, sub_tab_puls, sub_tab_all = st.tabs(["🩸 Glicemie & Analiză Spike", "🫀 Tensiune Arterială", "💓 Puls", "📋 Toate Datele (Doar Înregistrări Active)"])
        
        df_glic_view = view_df[pd.to_numeric(view_df[col_glic], errors="coerce").fillna(0) > 0].copy()
        df_ta_view = view_df[(pd.to_numeric(view_df[col_sis], errors="coerce").fillna(0) > 0) | (pd.to_numeric(view_df[col_dia], errors="coerce").fillna(0) > 0)].copy()
        df_puls_view = view_df[pd.to_numeric(view_df[col_puls], errors="coerce").fillna(0) > 0].copy()
        
        df_all_view = view_df[
            (pd.to_numeric(view_df[col_glic], errors="coerce").fillna(0) > 0) |
            (pd.to_numeric(view_df[col_sis], errors="coerce").fillna(0) > 0) |
            (pd.to_numeric(view_df[col_dia], errors="coerce").fillna(0) > 0) |
            (pd.to_numeric(view_df[col_puls], errors="coerce").fillna(0) > 0) |
            (view_df[col_obs].astype(str).str.strip() != "")
        ].copy()

        with sub_tab_glic:
            st.markdown("ℹ️ **Legenda Glicemie:** 🔵 Albastru = Valoare in intervalul optim | 🔴 Rosu = Valoare crescuta / Spike peste prag.")
            if not df_glic_view.empty and col_glic in df_glic_view.columns:
                x_labels_g = [f"{d.strftime('%d.%m')} ({m[:3]})" for d, m in zip(df_glic_view[date_col], df_glic_view[moment_col])]
                glic_vals = pd.to_numeric(df_glic_view[col_glic], errors="coerce").replace(0, None)
                moments = df_glic_view[moment_col].tolist()

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
                    x=x_labels_g, y=glic_vals, mode="lines+markers+text", name="Glicemie",
                    line=dict(color="#38bdf8", width=2.5),
                    marker=dict(size=10, color=spike_colors),
                    text=spike_texts, textposition="top center",
                    textfont=dict(size=9.5, color="#ffffff"),
                    texttemplate="%{text}",
                    connectgaps=True
                ))
                
                max_post = st.session_state.settings.get("target_glic_post_max", 160)
                max_pre = st.session_state.settings.get("target_glic_max", 120)
                fig_g.add_hline(y=max_post, line_dash="dash", line_color="#dc2626", annotation_text=f"Prag Max Dupa Masa ({max_post})")
                fig_g.add_hline(y=max_pre, line_dash="dot", line_color="#f59e0b", annotation_text=f"Prag Max Inainte Masa ({max_pre})")
                
                max_glic_data = glic_vals.max() if not glic_vals.dropna().empty else 200
                upper_limit_g = max(250, int(max_glic_data) + 50)
                
                fig_g.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=40, r=40, t=50, b=120), xaxis=dict(tickangle=-45, dtick=1), yaxis=dict(range=[0, upper_limit_g]))
                st.plotly_chart(fig_g, use_container_width=True)

                cols_g = [date_col, moment_col, col_glic, col_obs]
                df_g_tab = df_glic_view[cols_g].copy()
                df_g_tab[date_col] = df_g_tab[date_col].dt.strftime("%d.%m.%Y")
                df_g_tab["Status Glicemie"] = df_g_tab.apply(lambda r: evaluate_glic(r[col_glic], r[moment_col]), axis=1)
                df_g_tab[col_glic] = format_table_column(df_g_tab[col_glic])
                df_g_tab[col_obs] = df_g_tab[col_obs].apply(clean_obs)
                df_g_tab = df_g_tab[[date_col, moment_col, col_glic, "Status Glicemie", col_obs]]
                st.dataframe(apply_color_styling(df_g_tab, ["Status Glicemie"]), use_container_width=True, hide_index=True)
            else:
                st.info("Nicio inregistrare de glicemie pentru selectia curenta.")

        with sub_tab_ta:
            st.markdown("ℹ️ **Legenda Tensiune:** 🔵 Albastru/Indigo = Tensiune Sistolica normala | 🟠 Portocaliu = Diastolica | 🔴 Rosu = Valori de Tensiune Crescuta.")
            if not df_ta_view.empty and col_sis in df_ta_view.columns and col_dia in df_ta_view.columns:
                x_labels_ta = [f"{d.strftime('%d.%m')} ({m[:3]})" for d, m in zip(df_ta_view[date_col], df_ta_view[moment_col])]
                sis_vals = pd.to_numeric(df_ta_view[col_sis], errors="coerce").replace(0, None)
                dia_vals = pd.to_numeric(df_ta_view[col_dia], errors="coerce").replace(0, None)
                
                sis_colors = ["#dc2626" if is_ta_spike(s, d) else "#2563eb" for s, d in zip(sis_vals, dia_vals)]
                dia_colors = ["#dc2626" if is_ta_spike(s, d) else "#f59e0b" for s, d in zip(sis_vals, dia_vals)]

                fig_ta = go.Figure()
                fig_ta.add_trace(go.Scatter(
                    x=x_labels_ta, y=sis_vals, mode="lines+markers+text", name="Sistolica", 
                    line=dict(color="#2563eb", width=2.5), marker=dict(size=10, color=sis_colors), 
                    text=sis_vals, textposition="top center", textfont=dict(size=10, color="#ffffff"), 
                    texttemplate="<b>%{text}</b>", connectgaps=True
                ))
                fig_ta.add_trace(go.Scatter(
                    x=x_labels_ta, y=dia_vals, mode="lines+markers+text", name="Diastolica", 
                    line=dict(color="#f59e0b", width=2.5), marker=dict(size=10, color=dia_colors), 
                    text=dia_vals, textposition="bottom center", textfont=dict(size=10, color="#ffffff"), 
                    texttemplate="<b>%{text}</b>", connectgaps=True
                ))
                
                max_s_target = st.session_state.settings.get("target_ta_sis", 120)
                fig_ta.add_hline(y=max_s_target, line_dash="dash", line_color="#dc2626", annotation_text=f"Prag Max Sistolica ({max_s_target})")
                
                fig_ta.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=40, r=40, t=50, b=120), xaxis=dict(tickangle=-45, dtick=1))
                st.plotly_chart(fig_ta, use_container_width=True)
                
                cols_t = [date_col, moment_col, col_sis, col_dia, col_obs]
                df_t_tab = df_ta_view[cols_t].copy()
                df_t_tab[date_col] = df_t_tab[date_col].dt.strftime("%d.%m.%Y")
                df_t_tab["Status Tensiune"] = df_t_tab.apply(lambda r: evaluate_ta(r[col_sis], r[col_dia]), axis=1)
                df_t_tab[col_sis] = format_table_column(df_t_tab[col_sis])
                df_t_tab[col_dia] = format_table_column(df_t_tab[col_dia])
                df_t_tab[col_obs] = df_t_tab[col_obs].apply(clean_obs)
                df_t_tab = df_t_tab[[date_col, moment_col, col_sis, col_dia, "Status Tensiune", col_obs]]
                st.dataframe(apply_color_styling(df_t_tab, ["Status Tensiune"]), use_container_width=True, hide_index=True)
            else:
                st.info("Nicio inregistrare de tensiune arteriala pentru selectia curenta.")

        with sub_tab_puls:
            st.markdown("ℹ️ **Legenda Puls:** 🟢 Verde = Interval normal (60-100 bpm) | 🔴 Rosu = Puls in afara limitelor.")
            if not df_puls_view.empty and col_puls in df_puls_view.columns:
                x_labels_p = [f"{d.strftime('%d.%m')} ({m[:3]})" for d, m in zip(df_puls_view[date_col], df_puls_view[moment_col])]
                puls_vals = pd.to_numeric(df_puls_view[col_puls], errors="coerce").replace(0, None)
                puls_colors = ["#dc2626" if is_puls_spike(p) else "#10b981" for p in puls_vals]

                fig_p = go.Figure()
                fig_p.add_trace(go.Scatter(
                    x=x_labels_p, y=puls_vals, mode="lines+markers+text", name="Puls (bpm)", 
                    line=dict(color="#10b981", width=2.5), marker=dict(size=10, color=puls_colors), 
                    text=puls_vals, textposition="top center", textfont=dict(size=10, color="#ffffff"), 
                    texttemplate="<b>%{text}</b>", connectgaps=True
                ))
                fig_p.add_hline(y=100, line_dash="dash", line_color="#dc2626", annotation_text="Limita Maxima Puls (100)")
                fig_p.add_hline(y=60, line_dash="dash", line_color="#dc2626", annotation_text="Limita Minima Puls (60)")
                
                fig_p.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=40, r=40, t=50, b=120), xaxis=dict(tickangle=-45, dtick=1))
                st.plotly_chart(fig_p, use_container_width=True)
                
                cols_p = [date_col, moment_col, col_puls, col_obs]
                df_p_tab = df_puls_view[cols_p].copy()
                df_p_tab[date_col] = df_p_tab[date_col].dt.strftime("%d.%m.%Y")
                df_p_tab["Status Puls"] = df_p_tab[col_puls].apply(evaluate_puls)
                df_p_tab[col_puls] = format_table_column(df_p_tab[col_puls])
                df_p_tab[col_obs] = df_p_tab[col_obs].apply(clean_obs)
                df_p_tab = df_p_tab[[date_col, moment_col, col_puls, "Status Puls", col_obs]]
                st.dataframe(apply_color_styling(df_p_tab, ["Status Puls"]), use_container_width=True, hide_index=True)
            else:
                st.info("Nicio inregistrare de puls pentru selectia curenta.")

        with sub_tab_all:
            if not df_all_view.empty:
                df_all = df_all_view.copy()
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
            else:
                st.info("Nicio inregistrare disponibila.")

# ----------------- TAB: ADAUGA / SUPRASCRIE (ADMIN) -----------------
if is_admin and "➕ Adaugă / Suprascrie" in tab_dict:
    with tab_dict["➕ Adaugă / Suprascrie"]:
        st.markdown("### 📝 Formular Introducere / Suprascrie Masuratori")
        
        c_undo1, c_undo2 = st.columns([2, 5])
        with c_undo1:
            if st.session_state.action_history_stack:
                if st.button("↩️ Undo Ultima Modificare", type="secondary"):
                    last_action = st.session_state.action_history_stack.pop()
                    st.session_state.local_df_v2 = last_action["old_df"]
                    st.session_state.local_df_v2.to_csv(DATA_FILE, index=False)
                    st.success(f"S-a revenit cu succes la starea anterioara! ({last_action['desc']})")
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
                st.warning(f"⚠️ Exista deja o inregistrare cu valori pentru {date_str} - {selected_moment}. Valorile existente au fost incarcate pentru editare/suprascriere.")
            else:
                st.info(f"ℹ️ Nu exista o inregistrare anterioara cu valori pentru {date_str} - {selected_moment}. Campurile pornesc de la 0.")

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
                st.number_input("🩸 Glicemie (mg/dL) [0 = nemasurat]", min_value=0, key="inp_glic")
            with c2:
                st.number_input("🫀 Tensiune Sistolica [0 = nemasurat]", min_value=0, key="inp_sis")
                st.number_input("🫀 Tensiune Diastolica [0 = nemasurat]", min_value=0, key="inp_dia")
                st.number_input("💓 Puls [0 = nemasurat]", min_value=0, key="inp_puls")

            st.markdown("---")
            st.markdown("##### ⚡ Asistent Inteligent Mese & Indice Glicemic (Actualizare Instantanee)")
            
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

            st.text_area("✍️ Notite / Observatii", key="inp_obs")

            def handle_save_action():
                g_val = st.session_state.get("inp_glic", 0)
                s_val = st.session_state.get("inp_sis", 0)
                d_val = st.session_state.get("inp_dia", 0)
                p_val = st.session_state.get("inp_puls", 0)
                o_val = st.session_state.get("inp_obs", "")

                save_local_record(date_str, selected_moment, g_val, s_val, d_val, p_val, o_val)
                st.session_state["success_message"] = "✅ Salvare / Suprascriere efectuata cu succes!"
                trigger_rerun()

            st.markdown("---")
            st.button("💾 Salveaza / Suprascrie Inregistrarea", type="primary", use_container_width=True, on_click=handle_save_action, key="bottom_save_btn")

# ----------------- TAB: TRATAMENT -----------------
with tab_dict["💊 Tratament"]:
    st.markdown("### 💊 Schema Tratament Medical")
    
    if "success_message" in st.session_state:
        st.success(st.session_state["success_message"])
        del st.session_state["success_message"]

    st.dataframe(st.session_state.meds_df, use_container_width=True, hide_index=True)

    if is_admin:
        st.markdown("---")
        st.markdown("#### ⚙️ Gestiune Lista Tratament & Stergere (Administrator)")
        col_m1, col_m2, col_m3 = st.columns(3)
        
        with col_m1:
            with st.container(border=True):
                st.markdown("##### ➕ Adauga Nou")
                with st.form("add_med_form"):
                    m_nume = st.text_input("Nume")
                    m_doza = st.text_input("Doza")
                    m_orar = st.text_input("Orar / Frecventa")
                    m_obs_med = st.text_input("Observatii")
                    if st.form_submit_button("Adauga", type="primary"):
                        if m_nume:
                            new_row = pd.DataFrame([{"Medicament": m_nume, "Doza": m_doza, "Orar / Frecventa": m_orar, "Observatii": m_obs_med}])
                            st.session_state.meds_df = pd.concat([st.session_state.meds_df, new_row], ignore_index=True)
                            add_history_entry("Adaugare", m_nume, f"Doza: {m_doza}, Orar: {m_orar}")
                            save_all_files()
                            st.session_state["success_message"] = f"Medicamentul {m_nume} a fost adaugat cu succes!"
                            trigger_rerun()

        with col_m2:
            with st.container(border=True):
                st.markdown("##### ✏️ Editeaza Existent")
                if not st.session_state.meds_df.empty:
                    med_to_edit = st.selectbox("Selecteaza", st.session_state.meds_df["Medicament"].tolist(), key="edit_med_select")
                    med_data = st.session_state.meds_df[st.session_state.meds_df["Medicament"] == med_to_edit].iloc[0]
                    with st.form("edit_med_form"):
                        e_doza = st.text_input("Doza", value=med_data["Doza"])
                        e_orar = st.text_input("Orar / Frecventa", value=med_data["Orar / Frecventa"])
                        e_obs_med = st.text_input("Observatii", value=med_data.get("Observatii", ""))
                        if st.form_submit_button("Salveaza Modificarea", type="primary"):
                            idx = st.session_state.meds_df.index[st.session_state.meds_df["Medicament"] == med_to_edit][0]
                            st.session_state.meds_df.loc[idx, "Doza"] = e_doza
                            st.session_state.meds_df.loc[idx, "Orar / Frecventa"] = e_orar
                            st.session_state.meds_df.loc[idx, "Observatii"] = e_obs_med
                            add_history_entry("Modificare", med_to_edit, f"Doza: -> {e_doza}")
                            save_all_files()
                            st.session_state["success_message"] = "Modificarile au fost salvate cu succes!"
                            trigger_rerun()

        with col_m3:
            with st.container(border=True):
                st.markdown("##### 🗑️ Sterge Medicament")
                if not st.session_state.meds_df.empty:
                    with st.form("delete_med_form"):
                        to_delete = st.selectbox("Selecteaza de sters", st.session_state.meds_df["Medicament"].tolist())
                        btn_del_med = st.form_submit_button("Sterge Definitiv", type="secondary")
                        if btn_del_med:
                            st.session_state.meds_df = st.session_state.meds_df[st.session_state.meds_df["Medicament"] != to_delete].reset_index(drop=True)
                            add_history_entry("Stergere", to_delete, "Eliminat din schema.")
                            save_all_files()
                            st.session_state["success_message"] = f"Medicamentul {to_delete} a fost sters!"
                            trigger_rerun()

# ----------------- TAB: PROGRAMARI -----------------
if is_admin and "📅 Programări" in tab_dict:
    with tab_dict["📅 Programări"]:
        st.markdown("### 📅 Programari Medicale, Editare, Stergere & Alerte")
        st.dataframe(st.session_state.prog_df, use_container_width=True, hide_index=True)

        st.markdown("---")
        col_p1, col_p2, col_p3 = st.columns(3)

        with col_p1:
            with st.container(border=True):
                st.markdown("#### ➕ Adauga Programare")
                with st.form("form_add_prog"):
                    p_data = st.date_input("Data", value=date.today())
                    p_ora = st.text_input("Ora (ex: 10:30)", value="10:00")
                    p_tip = st.text_input("Tip (ex: Analize, Consult)")
                    p_clinica = st.text_input("Clinica / Doctor")
                    p_alerta = st.text_input("Zile Alerta", value="1, 3")
                    p_obs = st.text_area("Observatii")

                    if st.form_submit_button("Salveaza", type="primary"):
                        if p_tip:
                            new_p = pd.DataFrame([{
                                "Data": p_data.strftime("%Y-%m-%d"),
                                "Ora": p_ora,
                                "Tip": p_tip,
                                "Clinica": p_clinica,
                                "Zile_Alerta": p_alerta,
                                "Efectuat": "Nu",
                                "Observatii": clean_obs(p_obs)
                            }])
                            st.session_state.prog_df = pd.concat([st.session_state.prog_df, new_p], ignore_index=True)
                            save_all_files()
                            st.success("Programare salvata!")
                            trigger_rerun()

        with col_p2:
            with st.container(border=True):
                st.markdown("#### ✏️ Editeaza / Sterge / Status")
                if not st.session_state.prog_df.empty:
                    prog_indices = list(st.session_state.prog_df.index)
                    prog_labels = [f"{row.get('Data', '')} {row.get('Ora', '10:00')} - {row.get('Tip', '')} ({row.get('Clinica', '')})" for _, row in st.session_state.prog_df.iterrows()]
                    selected_prog_idx = st.selectbox("Alege programare", prog_indices, format_func=lambda i: prog_labels[i])
                    
                    row_data = st.session_state.prog_df.loc[selected_prog_idx]
                    
                    with st.form("form_edit_prog"):
                        try:
                            default_dt = datetime.strptime(str(row_data.get("Data", date.today().strftime("%Y-%m-%d"))), "%Y-%m-%d").date()
                        except:
                            default_dt = date.today()
                            
                        e_p_data = st.date_input("Data Noua", value=default_dt)
                        e_p_ora = st.text_input("Ora Noua", value=str(row_data.get("Ora", "10:00")))
                        e_p_tip = st.text_input("Tip Nou", value=str(row_data.get("Tip", "")))
                        e_p_clinica = st.text_input("Clinica Noua", value=str(row_data.get("Clinica", "")))
                        e_p_alerta = st.text_input("Zile Alerta Noi", value=str(row_data.get("Zile_Alerta", "1, 3")))
                        
                        stat_opts = ["Nu", "Da (Done)"]
                        curr_stat = str(row_data.get("Efectuat", "Nu"))
                        e_p_efectuat = st.selectbox("Status", stat_opts, index=1 if "Da" in curr_stat else 0)
                        
                        e_p_obs = st.text_area("Observatii Noi", value=str(row_data.get("Observatii", "")))
                        
                        col_sub1, col_sub2 = st.columns(2)
                        with col_sub1:
                            btn_mod = st.form_submit_button("💾 Salveaza Modificari", type="primary")
                        with col_sub2:
                            btn_del = st.form_submit_button("🗑️ Sterge Programarea", type="secondary")
                            
                        if btn_mod:
                            st.session_state.prog_df.loc[selected_prog_idx, "Data"] = e_p_data.strftime("%Y-%m-%d")
                            st.session_state.prog_df.loc[selected_prog_idx, "Ora"] = e_p_ora
                            st.session_state.prog_df.loc[selected_prog_idx, "Tip"] = e_p_tip
                            st.session_state.prog_df.loc[selected_prog_idx, "Clinica"] = e_p_clinica
                            st.session_state.prog_df.loc[selected_prog_idx, "Zile_Alerta"] = e_p_alerta
                            st.session_state.prog_df.loc[selected_prog_idx, "Efectuat"] = "Da" if "Da" in e_p_efectuat else "Nu"
                            st.session_state.prog_df.loc[selected_prog_idx, "Observatii"] = clean_obs(e_p_obs)
                            save_all_files()
                            st.success("Programare actualizata cu succes!")
                            trigger_rerun()
                            
                        if btn_del:
                            st.session_state.prog_df = st.session_state.prog_df.drop(selected_prog_idx).reset_index(drop=True)
                            save_all_files()
                            st.success("Programare stersa!")
                            trigger_rerun()

        with col_p3:
            with st.container(border=True):
                st.markdown("#### 📨 Trimitere & Test iCloud")
                destinatar_auto = st.text_input("Email Destinatar", value=st.session_state.settings.get("email_sender", ""))
                
                if st.button("🚀 Trimite Alerte Automat Acum", type="primary"):
                    if not destinatar_auto:
                        st.error("Completeaza adresa de email.")
                    else:
                        save_all_files()
                        trimis_ok = 0
                        azi = datetime.now().date()
                        mesaj_final = "🔔 ALERTE AUTOMATE PROGRAMARI MEDICALE - HEALTHTRACK PRO\n\n"
                        
                        for _, row in st.session_state.prog_df.iterrows():
                            if str(row.get("Efectuat", "Nu")) == "Da":
                                continue
                            try:
                                p_date = datetime.strptime(str(row["Data"]), "%Y-%m-%d").date()
                                zile_ramase = (p_date - azi).days
                                zile_alerta_list = [int(x.strip()) for x in str(row["Zile_Alerta"]).split(",") if x.strip().isdigit()]
                                
                                if zile_ramase in zile_alerta_list or zile_ramase == 0:
                                    mesaj_final += f"- {row['Tip']} la {row['Clinica']} pe data de {row['Data']} ora {row.get('Ora', '')} (Au ramas {zile_ramase} zile!)\n"
                                    trimis_ok += 1
                            except:
                                pass
                        
                        if trimis_ok > 0:
                            succes, rez = trimite_email_cu_multiple_atasamente(destinatar_auto, "🔔 Notificare Programare Medicala", mesaj_final, {
                                "date_medicale.csv": DATA_FILE,
                                "medicamente.csv": MEDS_FILE,
                                "programari_medicale.csv": PROG_FILE
                            })
                            if succes:
                                st.success("Notificarile automate au fost trimise prin iCloud impreuna cu fisierele!")
                            else:
                                st.error(rez)
                        else:
                            st.info("Nicio programare activa nu necesita alerta astazi.")

# ----------------- TAB: RAPORT PDF -----------------
with tab_dict["📄 Raport PDF"]:
    st.markdown("### 📄 Generare Raport Medical PDF")
    st.write("Poti genera si descarca un raport PDF complet cu istoricul medical curent.")
    
    if st.button("📥 Genereaza Raport PDF", type="primary"):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        styles = getSampleStyleSheet()
        story = []
        
        title_style = ParagraphStyle('ReportTitle', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#38bdf8'), alignment=1, spaceAfter=15)
        normal_style = ParagraphStyle('ReportNormal', parent=styles['Normal'], fontSize=10, textColor=colors.HexColor('#333333'))
        
        story.append(Paragraph("Raport Medical - HealthTrack Pro", title_style))
        story.append(Paragraph(f"Generat la: {datetime.now().strftime('%d.%m.%Y %H:%M')} | Utilizator: {st.session_state.user}", normal_style))
        story.append(Spacer(1, 15))
        
        if not view_df.empty:
            story.append(Paragraph("<b>Ultimele inregistrari din jurnal:</b>", normal_style))
            story.append(Spacer(1, 8))
            
            table_data = [["Data", "Moment", "Glicemie", "Sistolica", "Diastolica", "Puls", "Observatii"]]
            for _, r in view_df.tail(20).iterrows():
                d_fmt = parse_flexible_date(r[date_col]).strftime('%d.%m.%Y') if pd.notna(r[date_col]) else ""
                table_data.append([
                    d_fmt,
                    str(r.get(moment_col, "")),
                    str(r.get(col_glic, "")) if float(r.get(col_glic, 0) or 0) > 0 else "-",
                    str(r.get(col_sis, "")) if float(r.get(col_sis, 0) or 0) > 0 else "-",
                    str(r.get(col_dia, "")) if float(r.get(col_dia, 0) or 0) > 0 else "-",
                    str(r.get(col_puls, "")) if float(r.get(col_puls, 0) or 0) > 0 else "-",
                    str(r.get(col_obs, ""))
                ])
            
            t = Table(table_data, colWidths=[65, 95, 55, 50, 50, 40, 180])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e222d')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,0), 6),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dddddd')),
            ]))
            story.append(t)
        else:
            story.append(Paragraph("Nu exista date pentru perioada selectata.", normal_style))
            
        doc.build(story)
        pdf_data = buffer.getvalue()
        
        st.download_button(
            label="💾 Descarca Fisierul PDF",
            data=pdf_data,
            file_name=f"Raport_Medical_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime="application/pdf"
        )

# ----------------- TAB: SETARI & ADMIN -----------------
with tab_dict["⚙️ Setări"]:
    st.markdown("### ⚙️ Setari Generale, Test Conexiune iCloud & Gestiune Utilizatori")
    
    if is_admin:
        col_u1, col_u2 = st.columns(2)
        with col_u1:
            with st.container(border=True):
                st.markdown("#### ➕ Adauga Utilizator Nou")
                with st.form("form_new_user"):
                    new_u_name = st.text_input("Nume Utilizator Nou")
                    new_u_pass = st.text_input("Parola", type="password")
                    new_u_role = st.selectbox("Rol", ["Membru", "Doctor", "Administrator"])
                    if st.form_submit_button("Creeaza Cont", type="primary"):
                        if new_u_name and new_u_pass:
                            if new_u_name in st.session_state.users:
                                st.error("Utilizatorul exista deja!")
                            else:
                                st.session_state.users[new_u_name] = {"pass": new_u_pass, "role": new_u_role}
                                st.success(f"Utilizatorul {new_u_name} a fost creat!")
                                trigger_rerun()
                        else:
                            st.warning("Completeaza numele si parola.")

        with col_u2:
            with st.container(border=True):
                st.markdown("#### 👥 Editeaza / Sterge Utilizator")
                user_list = list(st.session_state.users.keys())
                target_user = st.selectbox("Selecteaza utilizator", user_list, key="sel_user_manage")
                
                with st.form("form_manage_user"):
                    current_target_role = st.session_state.users[target_user].get("role", "Membru")
                    role_options = ["Membru", "Doctor", "Administrator"]
                    updated_role = st.selectbox("Schimba Rol", role_options, index=role_options.index(current_target_role))
                    updated_pass = st.text_input("Parola Noua (optional)", type="password", key="pass_edit_user")
                    
                    c_ub1, c_ub2 = st.columns(2)
                    with c_ub1:
                        btn_save_u = st.form_submit_button("💾 Salveaza Modificari", type="primary")
                    with c_ub2:
                        btn_del_u = st.form_submit_button("🗑️ Sterge Utilizator", type="secondary")
                        
                    if btn_save_u:
                        st.session_state.users[target_user]["role"] = updated_role
                        if updated_pass:
                            st.session_state.users[target_user]["pass"] = updated_pass
                        st.success(f"Detaliile pentru {target_user} au fost actualizate!")
                        trigger_rerun()
                        
                    if btn_del_u:
                        if target_user == "Alex" and len(st.session_state.users) <= 1:
                            st.error("Nu poti sterge administratorul principal daca este singurul cont!")
                        else:
                            del st.session_state.users[target_user]
                            st.success(f"Utilizatorul {target_user} a fost sters cu succes!")
                            trigger_rerun()

        st.markdown("<br>", unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown("#### 🍎 Gestiune Elemente Mese & Indice Glicemic")
            fc_cat = st.selectbox("Selecteaza Categoria", list(st.session_state.food_categories.keys()))
            
            c_f1, c_f2 = st.columns(2)
            with c_f1:
                new_food_item = st.text_input("Adauga ingredient nou")
                if st.button("➕ Adauga in Categorie"):
                    if new_food_item and new_food_item.strip():
                        item_clean = remove_diacritics(new_food_item).strip().lower()
                        existing_all = [remove_diacritics(str(x)).lower() for x in st.session_state.food_categories[fc_cat] if pd.notna(x)]
                        if item_clean in existing_all:
                            st.warning(f"⚠️ Ingredientul '{item_clean}' exista deja in aceasta categorie!")
                        else:
                            st.session_state.food_categories[fc_cat].append(item_clean)
                            save_custom_foods()
                            st.success(f"Ingredientul '{item_clean}' a fost adaugat cu succes!")
                            trigger_rerun()
            with c_f2:
                all_items_flat = sorted(list(set([str(x) for x in st.session_state.food_categories[fc_cat] if pd.notna(x)])))
                if all_items_flat:
                    del_food_item = st.selectbox("Selecteaza ingredient existent de sters", all_items_flat, key="del_food_select")
                    if st.button("🗑️ Sterge Ingredientul Selectat"):
                        st.session_state.food_categories[fc_cat].remove(del_food_item)
                        save_custom_foods()
                        st.success(f"Ingredientul '{del_food_item}' a fost sters!")
                        trigger_rerun()
                else:
                    st.info("Niciun element in categorie.")

    st.markdown("---")
    col_set1, col_set2 = st.columns(2)
    with col_set1:
        st.markdown("#### ✉️ Configurare Server iCloud Mail & Test Alerte (Salvare Permanenta)")
        
        entered_sender = st.text_input("Adresa ta de iCloud (expeditor)", value=st.session_state.settings.get("email_sender", ""))
        entered_password = st.text_input("Parola specifica de aplicatie iCloud (App-Specific Password)", type="password", value=st.session_state.settings.get("email_password", ""))
        
        if st.button("💾 Salveaza Datele Email Permanent", type="primary"):
            st.session_state.settings["email_sender"] = entered_sender
            st.session_state.settings["email_password"] = entered_password
            save_persisted_settings(st.session_state.settings)
            st.success("✅ Datele de email au fost salvate permanent pe disc!")

        st.markdown("<small>💡 *Nota: Nu folosi parola ta principala Apple ID. Genereaza o App-Specific Password din portalul tau Apple ID.*</small>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("#### 🔍 Verificare Integritate Jurnal (Zile Lipsa)")
        check_start_mode = st.radio("Perioada de verificare:", ["De la prima inregistrare (12.09)", "De la 1 ale lunii curente"], horizontal=True, key="chk_mode_radio")
        
        if st.button("🚀 Verifica Jurnalul Acum", type="primary"):
            if os.path.exists(DATA_FILE):
                df_chk = pd.read_csv(DATA_FILE)
                df_chk["Data_dt"] = parse_flexible_date(df_chk["Data" if "Data" in df_chk.columns else "Data"])
                df_chk = df_chk.dropna(subset=["Data_dt"])
                if not df_chk.empty:
                    min_d = df_chk["Data_dt"].dt.date.min() if "12.09" in check_start_mode else date(date.today().year, date.today().month, 1)
                    azi = datetime.now().date()
                    zile_goale = []
                    curr = min_d
                    while curr < azi:
                        df_zi = df_chk[df_chk["Data_dt"].dt.date == curr]
                        zi_ok = False
                        for _, r in df_zi.iterrows():
                            g = float(r.get("Glicemie", 0) or 0)
                            s = float(r.get("Sistolica" if "Sistolica" in df_chk.columns else "Sistolica", 0) or 0)
                            d = float(r.get("Diastolica" if "Diastolica" in df_chk.columns else "Diastolica", 0) or 0)
                            p = float(r.get("Puls", 0) or 0)
                            o = clean_obs(r.get("Observatii" if "Observatii" in df_chk.columns else "Observatii", ""))
                            if g > 0 or s > 0 or d > 0 or p > 0 or o:
                                zi_ok = True
                                break
                        if not zi_ok:
                            zile_goale.append(curr.strftime("%d.%m.%Y"))
                        curr += timedelta(days=1)
                    
                    if zile_goale:
                        st.warning(f"S-au gasit {len(zile_goale} zile fara date:")
                        for z in zile_goale[-10:]:
                            st.write(f"- {z}")
                    else:
                        st.success("Jurnalul este complet! Nu s-au gasit zile goale in perioada selectata.")
            else:
                st.info("Fisierul de date nu exista inca.")

    with col_set2:
        st.markdown("#### 🎯 Setari Tinte Medicale")
        t_g_min = st.number_input("Tinta Glicemie Minima (Inainte masa)", value=st.session_state.settings.get("target_glic_min", 70))
        t_g_max = st.number_input("Tinta Glicemie Maxima (Inainte masa)", value=st.session_state.settings.get("target_glic_max", 120))
        t_gp_min = st.number_input("Tinta Glicemie Minima (Dupa masa)", value=st.session_state.settings.get("target_glic_post_min", 70))
        t_gp_max = st.number_input("Tinta Glicemie Maxima (Dupa masa)", value=st.session_state.settings.get("target_glic_post_max", 160))
        t_sis = st.number_input("Tinta Tensiune Sistolica Maxima", value=st.session_state.settings.get("target_ta_sis", 120))
        t_dia = st.number_input("Tinta Tensiune Diastolica Maxima", value=st.session_state.settings.get("target_ta_dia", 80))
        
        if st.button("💾 Salveaza Tintele Medicale", type="primary"):
            st.session_state.settings["target_glic_min"] = t_g_min
            st.session_state.settings["target_glic_max"] = t_g_max
            st.session_state.settings["target_glic_post_min"] = t_gp_min
            st.session_state.settings["target_glic_post_max"] = t_gp_max
            st.session_state.settings["target_ta_sis"] = t_sis
            st.session_state.settings["target_ta_dia"] = t_dia
            save_persisted_settings(st.session_state.settings)
            st.success("Tintele medicale au fost actualizate cu succes!")
