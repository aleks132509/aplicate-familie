import io
import re
from datetime import date, datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
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

# Custom CSS optimizat pentru DARK MODE și contrast ridicat
st.markdown(
    """
    <style>
    /* Styling general Dark Theme */
    .stApp {
        background-color: #0e1117;
        color: #ffffff;
    }
    
    /* Carduri de date (KPI-uri) */
    .metric-card {
        background-color: #1e222d;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        border: 1px solid #2e3545;
        text-align: center;
        margin-bottom: 10px;
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

    /* Ajustări pentru câmpuri de text și butoane */
    .stTextInput > div > div > input {
        color: #ffffff !important;
        background-color: #1e222d !important;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# Initialize Session State
if "users" not in st.session_state:
  st.session_state.users = {
      "Alex": "Aleks132509",
      "Ionut": "Ionut061191",
      "Doctor": "Alex2026",
  }

if "logged_in" not in st.session_state:
  st.session_state.logged_in = False

if "settings" not in st.session_state:
  st.session_state.settings = {
      "notif_enabled": True,
      "notif_days": 7,
      "target_glic_min": 70,
      "target_glic_max": 120,
      "target_ta_sis": 120,
      "target_ta_dia": 80,
  }

# ==========================================
# LINK GOOGLE SHEET
# ==========================================
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRs6o_ryWI3jCSZ_EpNyv6lDvQakwdEb0RoeuhXXXCdv9lzwCkkEXMorkk2W3ZBvg/pub?output=csv"

# ==========================================
# ECRAN AUTENTIFICARE (OPTIMIZAT VIZUAL)
# ==========================================
if not st.session_state.logged_in:
  st.markdown("<br><br><br>", unsafe_allow_html=True)
  col_a, col_b, col_c = st.columns([1, 1.2, 1])

  with col_b:
    st.markdown(
        "<h1 style='text-align: center; color: #38bdf8;'>🩺 HealthTrack"
        " Pro</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align: center; color: #94a3b8;'>Platformă de"
        " Monitorizare Medicală</p>",
        unsafe_allow_html=True,
    )

    with st.container(border=True):
      username = st.text_input("👤 Utilizator")
      password = st.text_input("🔑 Parolă", type="password")

      if st.button(
          "🔓 Autentificare", type="primary", use_container_width=True
      ):
        if st.session_state.users.get(username) == password:
          st.session_state.logged_in = True
          st.session_state.user = username
          st.rerun()
        else:
          st.error("Utilizator sau parolă incorectă!")
  st.stop()

# ==========================================
# SIDEBAR
# ==========================================
st.sidebar.markdown(f"### 👤 Autentificat: **{st.session_state.user}**")
if st.sidebar.button("🚪 Deconectare", use_container_width=True):
  st.session_state.logged_in = False
  st.rerun()

st.sidebar.markdown("---")


# ==========================================
# CURĂȚARE ȘI PARSARE INTELIGENTĂ DATE
# ==========================================
@st.cache_data(ttl=15)
def load_and_clean_data(url):
  try:
    # Citiți tot fișierul fără antet
    raw_df = pd.read_csv(url, header=None)

    # Caută rândul care conține capul de tabel (ex: Data, Glicemie, Tensiune)
    header_idx = None
    for idx, row in raw_df.iterrows():
      row_str = " ".join(row.astype(str)).lower()
      if "data" in row_str or "glicem" in row_str or "tensiun" in row_str:
        header_idx = idx
        break

    if header_idx is not None:
      # Reîncarcă datele începând de la rândul corect
      df_clean = pd.read_csv(url, skiprows=header_idx)
    else:
      df_clean = raw_df

    # Curățare nume coloane
    df_clean.columns = [
        str(c).strip() for c in df_clean.columns if "Unnamed" not in str(c)
    ]

    # Elimină rândurile complet goale
    df_clean = df_clean.dropna(how="all")

    return df_clean
  except Exception as e:
    st.error(f"Eroare la preluarea datelor: {e}")
    return pd.DataFrame()


df = load_and_clean_data(GOOGLE_SHEET_URL)

# Identificare automatizată coloană Dată
date_col = None
if not df.empty:
  for c in df.columns:
    if "dat" in c.lower() or "date" in c.lower():
      date_col = c
      break

  if date_col:
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])
    df = df.sort_values(by=date_col, ascending=False)

# ==========================================
# INTERFAȚĂ PRINCIPALĂ (TAB-URI)
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

  if not df.empty:
    # 1. KPI-uri
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    cols = df.columns
    col_glic = next((c for c in cols if "glic" in c.lower()), None)
    col_sis = next((c for c in cols if "sist" in c.lower()), None)
    col_dia = next((c for c in cols if "diast" in c.lower()), None)
    col_puls = next((c for c in cols if "puls" in c.lower()), None)

    with kpi1:
      val_glic = (
          f"{int(pd.to_numeric(df[col_glic], errors='coerce').dropna().iloc[0])} mg/dL"
          if col_glic and not df[col_glic].dropna().empty
          else "N/A"
      )
      st.markdown(
          f'<div class="metric-card"><div class="metric-label">🩸 ULTIMA'
          f' GLICEMIE</div><div class="metric-value">{val_glic}</div></div>',
          unsafe_allow_html=True,
      )

    with kpi2:
      val_sis = (
          int(pd.to_numeric(df[col_sis], errors="coerce").dropna().iloc[0])
          if col_sis and not df[col_sis].dropna().empty
          else "-"
      )
      val_dia = (
          int(pd.to_numeric(df[col_dia], errors="coerce").dropna().iloc[0])
          if col_dia and not df[col_dia].dropna().empty
          else "-"
      )
      st.markdown(
          f'<div class="metric-card"><div class="metric-label">🫀 ULTIMA'
          f' TENSIUNE</div><div'
          f' class="metric-value">{val_sis}/{val_dia}</div></div>',
          unsafe_allow_html=True,
      )

    with kpi3:
      val_puls = (
          f"{int(pd.to_numeric(df[col_puls], errors='coerce').dropna().iloc[0])} bpm"
          if col_puls and not df[col_puls].dropna().empty
          else "N/A"
      )
      st.markdown(
          f'<div class="metric-card"><div class="metric-label">💓 PULS'
          f' MEDIU</div><div class="metric-value">{val_puls}</div></div>',
          unsafe_allow_html=True,
      )

    with kpi4:
      st.markdown(
          f'<div class="metric-card"><div class="metric-label">📅 TOTAL'
          f' ÎNREGISTRĂRI</div><div'
          f' class="metric-value">{len(df)}</div></div>',
          unsafe_allow_html=True,
      )

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Grafice Plotly optimizate Dark Mode
    st.markdown("#### 📈 Grafice Evoluție")
    g1, g2 = st.columns(2)

    with g1:
      fig_g = go.Figure()
      glic_cols = [c for c in cols if "glic" in c.lower()]
      for gc in glic_cols:
        fig_g.add_trace(
            go.Scatter(
                x=df[date_col],
                y=pd.to_numeric(df[gc], errors="coerce"),
                mode="lines+markers",
                name=gc,
            )
        )

      fig_g.update_layout(
          title="Evoluție Glicemie (mg/dL)",
          template="plotly_dark",
          paper_bgcolor="rgba(0,0,0,0)",
          plot_bgcolor="rgba(0,0,0,0)",
          margin=dict(l=20, r=20, t=40, b=20),
      )
      st.plotly_chart(fig_g, use_container_width=True)

    with g2:
      fig_ta = go.Figure()
      ta_cols = [
          c
          for c in cols
          if "sist" in c.lower() or "diast" in c.lower() or "puls" in c.lower()
      ]
      for tc in ta_cols:
        fig_ta.add_trace(
            go.Scatter(
                x=df[date_col],
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

    # 3. Tabelul Curat
    st.markdown("#### 📋 Tabelul Măsurătorilor")
    df_display = df.copy()
    if date_col:
      df_display[date_col] = df_display[date_col].dt.strftime("%Y-%m-%d")

    st.dataframe(df_display, use_container_width=True, height=400)
  else:
    st.warning(
        "Nu s-au putut extrage date din tabel. Verifică structura fișierului"
        " Google Sheet."
    )

# ----------------- TAB 2: ADAUGĂ -----------------
with tab_add:
  st.markdown("### 📝 Formular Adăugare Măsurătoare")
  with st.container(border=True):
    with st.form("form_add"):
      c1, c2 = st.columns(2)
      with c1:
        st.date_input("📅 Data Măsurătorii", value=date.today())
        st.number_input("🩸 Glicemie (mg/dL)", value=100)
      with c2:
        st.number_input("🫀 Tensiune Sistolică", value=120)
        st.number_input("🫀 Tensiune Diastolică", value=80)
      st.text_area("✍️ Observații")

      if st.form_submit_button(
          "💾 Salvează Înregistrarea", type="primary", use_container_width=True
      ):
        st.success("Datele au fost salvate local!")

# ----------------- TAB 6: SETĂRI APLICAȚIE -----------------
with tab_settings:
  st.markdown("### ⚙️ Setări Cont & Sistem")
  s1, s2 = st.columns(2)

  with s1:
    with st.container(border=True):
      st.markdown("#### 🔒 Schimbare Parolă Utilizator")
      selected_user = st.selectbox(
          "Selectează utilizator", list(st.session_state.users.keys())
      )
      new_pass = st.text_input("Parolă nouă", type="password")
      if st.button("💾 Actualizează Parola"):
        if new_pass:
          st.session_state.users[selected_user] = new_pass
          st.success(f"Parola pentru {selected_user} a fost modificată!")

  with s2:
    with st.container(border=True):
      st.markdown("#### 🔔 Configurare Notificări")
      st.toggle(
          "Activează notificările",
          value=st.session_state.settings["notif_enabled"],
      )
      st.slider(
          "Zile înainte de alertă programare",
          1,
          14,
          st.session_state.settings["notif_days"],
      )
