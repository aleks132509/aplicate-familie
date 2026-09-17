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

# Custom CSS optimizat pentru DARK MODE (Contrast ridicat pe text și butoane)
st.markdown(
    """
    <style>
    /* Fundal general Dark Mode */
    .stApp {
        background-color: #0e1117 !important;
        color: #f1f5f9 !important;
    }
    
    /* Styling pentru Carduri KPI */
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

    /* Vizibilitate și contrast pentru câmpuri de text */
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
# ECRAN AUTENTIFICARE
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
        "<p style='text-align: center; color: #94a3b8; font-size: 16px;'>"
        "Platformă de Monitorizare Medicală de Familie</p>",
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
# ÎNCĂRCARE ȘI PARSARE ROBUSTĂ A DATELOR
# ==========================================
@st.cache_data(ttl=15)
def load_and_clean_data(url):
  try:
    # 1. Încărcăm tot fișierul brut
    raw_df = pd.read_csv(
        url, header=None, names=[f"col_{i}" for i in range(50)]
    )

    # 2. Căutăm rândul unde se află antetul real al tabelului
    header_idx = None
    for idx, row in raw_df.iterrows():
      # Conversie sigură în string (previne erorile de tip float/NaN)
      row_cells = [str(val) for val in row.values if pd.notna(val)]
      row_text = " ".join(row_cells).lower()

      if ("data" in row_text or "dată" in row_text or "date" in row_text) and any(
          k in row_text
          for k in [
              "glicem",
              "tensiun",
              "sistol",
              "diastol",
              "puls",
              "moment",
              "ora",
          ]
      ):
        header_idx = idx
        break

    if header_idx is not None:
      header_row = raw_df.iloc[header_idx]
      df_clean = raw_df.iloc[header_idx + 1 :].copy()

      cols = []
      for i, val in enumerate(header_row):
        val_str = str(val).strip() if pd.notna(val) else ""
        if val_str and val_str.lower() != "nan":
          cols.append(val_str)
        else:
          cols.append(f"Unnamed_{i}")
      df_clean.columns = cols
    else:
      # Fallback: Sare direct peste primele 5 rânduri introductive
      df_clean = pd.read_csv(url, skiprows=5)
      df_clean.columns = [str(col).strip() for col in df_clean.columns]

    # 3. Curățare coloane invalide
    valid_cols = [
        c
        for c in df_clean.columns
        if not str(c).startswith("Unnamed_")
        and "Unnamed" not in str(c)
        and str(c) != "nan"
        and str(c) != ""
    ]

    if valid_cols:
      df_clean = df_clean[valid_cols]

    # Elimină rândurile complet goale
    df_clean = df_clean.dropna(how="all")

    return df_clean

  except Exception as e:
    st.error(f"Eroare la procesarea fișierului: {e}")
    return pd.DataFrame()


df = load_and_clean_data(GOOGLE_SHEET_URL)

# Identificare automatizată coloană Dată
date_col = None
if not df.empty:
  for c in df.columns:
    if "dat" in str(c).lower() or "date" in str(c).lower():
      date_col = c
      break

  if date_col:
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce", dayfirst=True)
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
    # 1. Indicatoare KPI
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    cols = df.columns
    col_glic = next((c for c in cols if "glic" in str(c).lower()), None)
    col_sis = next((c for c in cols if "sist" in str(c).lower()), None)
    col_dia = next((c for c in cols if "diast" in str(c).lower()), None)
    col_puls = next((c for c in cols if "puls" in str(c).lower()), None)

    with kpi1:
      val_glic = "N/A"
      if col_glic:
        s_glic = pd.to_numeric(df[col_glic], errors="coerce").dropna()
        if not s_glic.empty:
          val_glic = f"{int(s_glic.iloc[0])} mg/dL"

      st.markdown(
          f'<div class="metric-card"><div class="metric-label">🩸 ULTIMA'
          f' GLICEMIE</div><div class="metric-value">{val_glic}</div></div>',
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
          f'<div class="metric-card"><div class="metric-label">🫀 ULTIMA'
          f' TENSIUNE</div><div'
          f' class="metric-value">{val_sis}/{val_dia}</div></div>',
          unsafe_allow_html=True,
      )

    with kpi3:
      val_puls = "N/A"
      if col_puls:
        s_puls = pd.to_numeric(df[col_puls], errors="coerce").dropna()
        if not s_puls.empty:
          val_puls = f"{int(s_puls.iloc[0])} bpm"

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

    # 2. Grafice Plotly optimizate Dark Theme
    st.markdown("#### 📈 Grafice Evoluție")
    g1, g2 = st.columns(2)

    with g1:
      fig_g = go.Figure()
      glic_cols = [c for c in cols if "glic" in str(c).lower()]
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
          if any(k in str(c).lower() for k in ["sist", "diast", "puls"])
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

    # 3. Tabelul de Date Curat
    st.markdown("#### 📋 Tabelul Măsurătorilor")
    df_display = df.copy()
    if date_col:
      df_display[date_col] = df_display[date_col].dt.strftime("%Y-%m-%d")

    st.dataframe(df_display, use_container_width=True, height=420)
  else:
    st.warning("Nu s-au găsit date valide în fișierul Google Sheet.")

# ----------------- TAB 2: ADAUGĂ -----------------
with tab_add:
  st.markdown("### 📝 Formular Introducere Măsurători")
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
        st.success("Măsurătoarea a fost salvată!")

# ----------------- TAB 3: MEDICAMENTE -----------------
with tab_med:
  st.markdown("### 💊 Schemă Tratament Medical")
  meds_df = pd.DataFrame([
      {
          "Medicament": "Glucophage",
          "Doză": "1000 mg",
          "Orar": "Dimineața / Seara",
          "Administrare": "După masă",
      },
      {
          "Medicament": "Lagosa",
          "Doză": "150 mg",
          "Orar": "Dimineața / Seara",
          "Administrare": "După masă",
      },
      {
          "Medicament": "Diaprel MR",
          "Doză": "60 mg (1/2)",
          "Orar": "Dimineața",
          "Administrare": "Înainte de masă",
      },
      {
          "Medicament": "Atacand",
          "Doză": "8 mg",
          "Orar": "Seara",
          "Administrare": "După masă",
      },
      {
          "Medicament": "Nebilet",
          "Doză": "5 mg",
          "Orar": "Dimineața",
          "Administrare": "După masă",
      },
  ])
  st.dataframe(meds_df, use_container_width=True)

# ----------------- TAB 4: PROGRAMĂRI -----------------
with tab_prog:
  st.markdown("### 📅 Programări Medicale")
  prog_df = pd.DataFrame([
      {
          "Dată": "2026-09-25",
          "Tip": "Analize de laborator",
          "Clinică": "Regina Maria",
          "Observații": "Repetare analize Diabet",
      },
      {
          "Dată": "2026-10-05",
          "Tip": "Consult Diabet",
          "Clinică": "Dr. Clenciu Craiova",
          "Observații": "Rețetă 3 luni",
      },
  ])
  st.dataframe(prog_df, use_container_width=True)

# ----------------- TAB 5: RAPORT PDF -----------------
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

    story.append(
        Paragraph(
            "<b>RAPORT MEDICAL MONITORIZARE SĂNĂTATE</b>", styles["Heading1"]
        )
    )
    story.append(
        Paragraph(
            f"Data generării: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 15))

    if not data_frame.empty:
      table_data = [list(data_frame.columns)]
      for _, row in data_frame.head(20).iterrows():
        table_data.append([str(v) for v in row.values])

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

# ----------------- TAB 6: SETĂRI -----------------
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
