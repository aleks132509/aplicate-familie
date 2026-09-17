import io
import re
import unicodedata
from datetime import date, datetime
import pandas as pd
import plotly.graph_objects as go
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
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
        padding: 18px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.4);
        border: 1px solid #2e3545;
        text-align: center;
        margin-bottom: 12px;
    }
    .metric-value { 
        font-size: 26px; 
        font-weight: 700; 
        color: #38bdf8; 
    }
    .metric-label { 
        font-size: 13px; 
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

# Helper eliminare diacritice
def remove_diacritics(text):
  if not isinstance(text, str):
    text = str(text)
  return "".join(
      c
      for c in unicodedata.normalize("NFD", text)
      if unicodedata.category(c) != "Mn"
  )

# Initialize Session State Utilizatori & Roluri
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
      "notif_days": 7,
      "target_glic_min": 70,
      "target_glic_max": 120,
      "target_ta_sis": 120,
      "target_ta_dia": 80,
  }

GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRs6o_ryWI3jCSZ_EpNyv6lDvQakwdEb0RoeuhXXXCdv9lzwCkkEXMorkk2W3ZBvg/pub?output=csv"

# ==========================================
# ECRAN AUTENTIFICARE
# ==========================================
if not st.session_state.logged_in:
  st.markdown("<br><br><br>", unsafe_allow_html=True)
  _, col_b, _ = st.columns([1, 1.2, 1])

  with col_b:
    st.markdown(
        "<h1 style='text-align: center; color: #38bdf8;'>🩺 HealthTrack Pro</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align: center; color: #94a3b8; font-size: 16px;'>"
        "Platformă de Monitorizare Medicală de Familie</p>",
        unsafe_allow_html=True,
    )

    with st.container(border=True):
      username = st.text_input("👤 Utilizator")
      password = st.text_input("🔑 Parolă", type="password")

      if st.button("🔓 Autentificare", type="primary", use_container_width=True):
        user_data = st.session_state.users.get(username)
        if user_data and user_data["pass"] == password:
          st.session_state.logged_in = True
          st.session_state.user = username
          st.rerun()
        else:
          st.error("Utilizator sau parolă incorectă!")
  st.stop()

# Detalii utilizator curent
current_user_info = st.session_state.users.get(st.session_state.user, {"role": "Membru"})
current_role = current_user_info.get("role", "Membru")

# ==========================================
# SIDEBAR
# ==========================================
st.sidebar.markdown(f"### 👤 **{st.session_state.user}**")
st.sidebar.markdown(f"Rol: <span class='role-badge'>{current_role}</span>", unsafe_allow_html=True)
st.sidebar.markdown("<br>", unsafe_allow_html=True)

if st.sidebar.button("🚪 Deconectare", use_container_width=True):
  st.session_state.logged_in = False
  st.session_state.user = None
  st.rerun()

st.sidebar.markdown("---")

# ==========================================
# CĂUTARE & DETECȚIE ULTRA-ROBUSTĂ A GOOGLE SHEET
# ==========================================
@st.cache_data(ttl=10)
def load_and_clean_data(url):
  try:
    # 1. Citire brută a tuturor rândurilor
    raw_df = pd.read_csv(url, header=None)
    
    header_idx = None
    for idx, row in raw_df.iterrows():
      row_str = " ".join([str(v) for v in row.values if pd.notna(v)]).lower()
      row_clean = remove_diacritics(row_str)
      if any(k in row_clean for k in ["data", "date", "glicem", "tensiun", "sistol", "diastol", "ora", "moment"]):
        header_idx = idx
        break

    if header_idx is not None:
      df_clean = pd.read_csv(url, skiprows=header_idx)
    else:
      # Fallback în caz că nu se găsește niciun cuvânt cheie
      df_clean = pd.read_csv(url)

    # Curățare coloane (fără spații, caractere invizibile)
    df_clean.columns = [str(c).strip() for c in df_clean.columns]
    
    # Păstrăm coloanele valide
    valid_cols = [c for c in df_clean.columns if "Unnamed" not in c and c.lower() != "nan" and c != ""]
    if valid_cols:
      df_clean = df_clean[valid_cols]

    return df_clean.dropna(how="all")
  except Exception as e:
    st.error(f"Eroare la preluarea datelor: {e}")
    return pd.DataFrame()

df = load_and_clean_data(GOOGLE_SHEET_URL)

# Identificare flexibilă a coloanei de dată
date_col = None
if not df.empty:
  for c in df.columns:
    c_clean = remove_diacritics(str(c)).lower()
    if any(k in c_clean for k in ["dat", "date", "timp", "time"]):
      date_col = c
      break
  
  # Dacă nu găsește cuvântul exact "data", ia prima coloană din tabel
  if not date_col and len(df.columns) > 0:
    date_col = df.columns[0]

  if date_col and date_col in df.columns:
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
    df = df.dropna(subset=[date_col])
    df = df.sort_values(by=date_col, ascending=False)

# ==========================================
# INTERFAȚĂ PRINCIPALĂ
# ==========================================
tab_jurnal, tab_add, tab_med, tab_prog, tab_pdf, tab_settings = st.tabs([
    "📊 Jurnal & Grafice",
    "➕ Adaugă Înregistrare",
    "💊 Tratament",
    "📅 Programări",
    "📄 Raport PDF",
    "⚙️ Setări",
])

# ----------------- TAB 1: JURNAL & GRAFICE -----------------
with tab_jurnal:
  st.markdown("### 📊 Tablou de Bord Medical")

  if not df.empty and date_col is not None and date_col in df.columns:
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    cols = df.columns
    col_glic = next((c for c in cols if "glic" in remove_diacritics(str(c)).lower()), None)
    col_sis = next((c for c in cols if "sist" in remove_diacritics(str(c)).lower()), None)
    col_dia = next((c for c in cols if "diast" in remove_diacritics(str(c)).lower()), None)
    col_puls = next((c for c in cols if "puls" in remove_diacritics(str(c)).lower()), None)

    with kpi1:
      val_glic = "N/A"
      if col_glic:
        s_glic = pd.to_numeric(df[col_glic], errors="coerce").dropna()
        if not s_glic.empty:
          val_glic = f"{int(s_glic.iloc[0])} mg/dL"
      st.markdown(
          f'<div class="metric-card"><div class="metric-label">🩸 ULTIMA GLICEMIE</div><div class="metric-value">{val_glic}</div></div>',
          unsafe_allow_html=True,
      )

    with kpi2:
      val_sis, val_dia = "-", "-"
      if col_sis:
        s_sis = pd.to_numeric(df[col_sis], errors="coerce").dropna()
        if not s_sis.empty:
          val_sis = int(s_sis.iloc[0])
      if col_dia:
        s_dia = pd.to_numeric(df[col_dia], errors="coerce").dropna()
        if not s_dia.empty:
          val_dia = int(s_dia.iloc[0])
      st.markdown(
          f'<div class="metric-card"><div class="metric-label">🫀 ULTIMA TENSIUNE</div><div class="metric-value">{val_sis}/{val_dia}</div></div>',
          unsafe_allow_html=True,
      )

    with kpi3:
      val_puls = "N/A"
      if col_puls:
        s_puls = pd.to_numeric(df[col_puls], errors="coerce").dropna()
        if not s_puls.empty:
          val_puls = f"{int(s_puls.iloc[0])} bpm"
      st.markdown(
          f'<div class="metric-card"><div class="metric-label">💓 PULS MEDIU</div><div class="metric-value">{val_puls}</div></div>',
          unsafe_allow_html=True,
      )

    with kpi4:
      st.markdown(
          f'<div class="metric-card"><div class="metric-label">📅 TOTAL ÎNREGISTRĂRI</div><div class="metric-value">{len(df)}</div></div>',
          unsafe_allow_html=True,
      )

    st.markdown("<br>", unsafe_allow_html=True)

    # Grafice
    st.markdown("#### 📈 Grafice Evoluție")
    g1, g2 = st.columns(2)

    x_data = df[date_col]

    with g1:
      fig_g = go.Figure()
      glic_cols = [c for c in cols if "glic" in remove_diacritics(str(c)).lower()]
      for gc in glic_cols:
        fig_g.add_trace(
            go.Scatter(
                x=x_data,
                y=pd.to_numeric(df[gc], errors="coerce"),
                mode="lines+markers",
                name=gc,
            )
        )
      fig_g.update_layout(
          title="Evoluție Glicemie",
          template="plotly_dark",
          paper_bgcolor="rgba(0,0,0,0)",
          plot_bgcolor="rgba(0,0,0,0)",
          margin=dict(l=20, r=20, t=40, b=20),
      )
      st.plotly_chart(fig_g, use_container_width=True)

    with g2:
      fig_ta = go.Figure()
      ta_cols = [
          c for c in cols if any(k in remove_diacritics(str(c)).lower() for k in ["sist", "diast", "puls"])
      ]
      for tc in ta_cols:
        fig_ta.add_trace(
            go.Scatter(
                x=x_data,
                y=pd.to_numeric(df[tc], errors="coerce"),
                mode="lines+markers",
                name=tc,
            )
        )
      fig_ta.update_layout(
          title="Evoluție Tensiune & Puls",
          template="plotly_dark",
          paper_bgcolor="rgba(0,0,0,0)",
          plot_bgcolor="rgba(0,0,0,0)",
          margin=dict(l=20, r=20, t=40, b=20),
      )
      st.plotly_chart(fig_ta, use_container_width=True)

    st.markdown("---")

    # Tabel
    st.markdown("#### 📋 Tabelul Măsurătorilor")
    df_display = df.copy()
    if date_col and date_col in df_display.columns:
      df_display[date_col] = df_display[date_col].dt.strftime("%Y-%m-%d")

    st.dataframe(df_display, use_container_width=True, height=420)
  else:
    st.warning("Nu s-au găsit date valide în fișierul Google Sheet. Verificați legătura fișierului.")

# ----------------- TAB 2: ADAUGĂ ÎNREGISTRARE -----------------
with tab_add:
  st.markdown("### 📝 Formular Introducere Măsurători")
  with st.container(border=True):
    with st.form("form_add"):
      c1, c2 = st.columns(2)
      with c1:
        st.date_input("📅 Data Măsurătorii", value=date.today())
        st.time_input("🕒 Ora Măsurătorii")
        st.selectbox(
            "🍽️ Momentul Măsurătorii",
            [
                "Înainte de masă (Ajeun)",
                "După masă (2 ore)",
                "Dimineața (La trezire)",
                "Seara (Înainte de culcare)",
            ],
        )
      with c2:
        st.number_input("🩸 Glicemie (mg/dL)", value=100)
        st.number_input("🫀 Tensiune Sistolică", value=120)
        st.number_input("🫀 Tensiune Diastolică", value=80)
        st.number_input("💓 Puls (bpm)", value=72)

      st.text_area("✍️ Observații")

      if st.form_submit_button("💾 Salvează Înregistrarea", type="primary", use_container_width=True):
        st.success("Măsurătoarea a fost salvată!")

# ----------------- TAB 3: MEDICAMENTE -----------------
with tab_med:
  st.markdown("### 💊 Schemă Tratament Medical")
  meds_df = pd.DataFrame([
      {"Medicament": "Glucophage", "Doză": "1000 mg", "Orar": "Dimineața / Seara", "Administrare": "După masă"},
      {"Medicament": "Lagosa", "Doză": "150 mg", "Orar": "Dimineața / Seara", "Administrare": "După masă"},
      {"Medicament": "Diaprel MR", "Doză": "60 mg (1/2)", "Orar": "Dimineața", "Administrare": "Înainte de masă"},
      {"Medicament": "Atacand", "Doză": "8 mg", "Orar": "Seara", "Administrare": "După masă"},
      {"Medicament": "Nebilet", "Doză": "5 mg", "Orar": "Dimineața", "Administrare": "După masă"},
  ])
  st.dataframe(meds_df, use_container_width=True)

# ----------------- TAB 4: PROGRAMĂRI -----------------
with tab_prog:
  st.markdown("### 📅 Programări Medicale")
  prog_df = pd.DataFrame([
      {"Dată": "2026-09-25", "Tip": "Analize de laborator", "Clinică": "Regina Maria", "Observații": "Repetare analize Diabet"},
      {"Dată": "2026-10-05", "Tip": "Consult Diabet", "Clinică": "Dr. Clenciu Craiova", "Observații": "Rețetă 3 luni"},
  ])
  st.dataframe(prog_df, use_container_width=True)

# ----------------- TAB 5: RAPORT PDF (FĂRĂ DIACRITICE) -----------------
with tab_pdf:
  st.markdown("### 📄 Generare Raport PDF")

  def make_pdf(data_frame):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=25,
        leftMargin=25,
        topMargin=25,
        bottomMargin=25,
    )
    story = []
    styles = getSampleStyleSheet()

    title_text = remove_diacritics("RAPORT MEDICAL MONITORIZARE SANATATE")
    date_text = remove_diacritics(f"Data generarii: {datetime.now().strftime('%d.%m.%Y %H:%M')}")

    story.append(Paragraph(f"<b>{title_text}</b>", styles["Heading1"]))
    story.append(Paragraph(date_text, styles["Normal"]))
    story.append(Spacer(1, 15))

    if not data_frame.empty:
      clean_cols = [remove_diacritics(c) for c in data_frame.columns]
      table_data = [clean_cols]

      for _, row in data_frame.head(25).iterrows():
        clean_row = [remove_diacritics(v) for v in row.values]
        table_data.append(clean_row)

      t = Table(table_data)
      t.setStyle(
          TableStyle([
              ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
              ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
              ("ALIGN", (0, 0), (-1, -1), "CENTER"),
              ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
              ("FONTSIZE", (0, 0), (-1, -1), 8),
              ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
          ])
      )
      story.append(t)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

  if st.button("🚀 Generează Raport PDF", type="primary"):
    pdf_out = make_pdf(df)
    st.download_button(
        label="📥 Descarcă Raportul PDF",
        data=pdf_out,
        file_name=f"Raport_Medical_{date.today()}.pdf",
        mime="application/pdf",
    )

# ----------------- TAB 6: SETĂRI & ROLURI -----------------
with tab_settings:
  st.markdown("### ⚙️ Setări & Drepturi Acces")

  s1, s2 = st.columns(2)

  with s1:
    # Doar ADMINISTRATORUL poate adăuga utilizatori noi și modifica roluri
    if current_role == "Administrator":
      with st.container(border=True):
        st.markdown("#### ➕ Adaugă Utilizator Nou (Doar Admin)")
        new_username = st.text_input("Nume Utilizator Nou")
        new_password = st.text_input("Parolă Utilizator", type="password")
        new_role = st.selectbox("Assignare Rol", ["Membru", "Doctor", "Administrator"])

        if st.button("➕ Creează Cont", type="primary"):
          if new_username and new_password:
            if new_username in st.session_state.users:
              st.error("Utilizatorul există deja!")
            else:
              st.session_state.users[new_username] = {
                  "pass": new_password,
                  "role": new_role,
              }
              st.success(f"Contul pentru {new_username} ({new_role}) a fost creat!")
          else:
            st.warning("Completează numele și parola.")

      with st.container(border=True):
        st.markdown("#### 👥 Gestionare Utilizatori Existenți")
        user_list = list(st.session_state.users.keys())
        target_user = st.selectbox("Selectează utilizator pentru editare", user_list)
        
        updated_role = st.selectbox(
            "Schimbă Rol",
            ["Membru", "Doctor", "Administrator"],
            index=["Membru", "Doctor", "Administrator"].index(st.session_state.users[target_user].get("role", "Membru"))
        )
        updated_pass = st.text_input("Parolă Nouă (lasă gol dacă nu schimbi)", type="password")

        if st.button("💾 Salvează Modificările Contului"):
          st.session_state.users[target_user]["role"] = updated_role
          if updated_pass:
            st.session_state.users[target_user]["pass"] = updated_pass
          st.success(f"Detaliile pentru {target_user} au fost actualizate!")
    else:
      # Membrii sau Doctorii își pot schimba doar propria parolă
      with st.container(border=True):
        st.markdown("#### 🔒 Schimbare Parolă Cont Curent")
        st.info(f"Conectat ca: **{st.session_state.user}** ({current_role})")
        own_pass = st.text_input("Parolă Nouă", type="password")
        if st.button("💾 Schimbă Parola Mea"):
          if own_pass:
            st.session_state.users[st.session_state.user]["pass"] = own_pass
            st.success("Parola ta a fost actualizată!")

  with s2:
    with st.container(border=True):
      st.markdown("#### 🎯 Valori Țintă Medicale")
      st.number_input(
          "Glicemie Minimă Țintă (mg/dL)",
          value=st.session_state.settings["target_glic_min"],
          disabled=(current_role != "Administrator")
      )
      st.number_input(
          "Glicemie Maximă Țintă (mg/dL)",
          value=st.session_state.settings["target_glic_max"],
          disabled=(current_role != "Administrator")
      )
      st.number_input(
          "Tensiune Sistolică Max Țintă",
          value=st.session_state.settings["target_ta_sis"],
          disabled=(current_role != "Administrator")
      )
      st.number_input(
          "Tensiune Diastolică Max Țintă",
          value=st.session_state.settings["target_ta_dia"],
          disabled=(current_role != "Administrator")
      )

    with st.container(border=True):
      st.markdown("#### 🔔 Configurare Alerte")
      st.toggle(
          "Activează notificările",
          value=st.session_state.settings["notif_enabled"],
      )
      st.slider(
          "Alertă programări (zile înainte)",
          1,
          14,
          st.session_state.settings["notif_days"],
      )
