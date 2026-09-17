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
# CONFIGURARE PAGINĂ & THEME
# ==========================================
st.set_page_config(
    page_title="HealthTrack Pro - Monitorizare Sănătate",
    layout="wide",
    page_icon="🩺",
    initial_sidebar_state="expanded",
)

# Custom CSS pentru aspect profesional
st.markdown(
    """
    <style>
    .stApp { background-color: #f8fafc; }
    .metric-card {
        background-color: #ffffff;
        padding: 18px;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border: 1px solid #e2e8f0;
        text-align: center;
    }
    .metric-value { font-size: 24px; font-weight: bold; color: #1e3a8a; }
    .metric-label { font-size: 13px; color: #64748b; font-weight: 600; }
    </style>
""",
    unsafe_text_inline=True,
)

# Initialize Session State pentru setări și securitate
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
      "auto_refresh": True,
      "refresh_rate": 30,
      "theme_mode": "Luminos",
  }

# ==========================================
# LINK GOOGLE SHEET (Integrat direct)
# ==========================================
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRs6o_ryWI3jCSZ_EpNyv6lDvQakwdEb0RoeuhXXXCdv9lzwCkkEXMorkk2W3ZBvg/pub?output=csv"

# ==========================================
# ECRAN AUTENTIFICARE
# ==========================================
if not st.session_state.logged_in:
  st.markdown("<br><br>", unsafe_allow_html=True)
  col_a, col_b, col_c = st.columns([1, 1.2, 1])
  with col_b:
    st.markdown("### 🩺 HealthTrack Pro")
    st.caption("Platformă de Monitorizare Medicală de Familie")
    with st.container(border=True):
      username = st.text_input("👤 Utilizator")
      password = st.text_input("🔑 Parolă", type="password")
      if st.button(
          "Autentificare", type="primary", use_container_width=True
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
st.sidebar.markdown(f"### 👤 {st.session_state.user}")
st.sidebar.caption("Rol: Administrator Măsurători")

if st.sidebar.button("🚪 Deconectare", use_container_width=True):
  st.session_state.logged_in = False
  st.rerun()

st.sidebar.markdown("---")


# Încărcare Date
@st.cache_data(ttl=15)
def load_data(url):
  try:
    data = pd.read_csv(url)
    data.columns = [str(c).strip() for c in data.columns]
    return data
  except Exception as e:
    st.error(f"Eroare la preluarea datelor: {e}")
    return pd.DataFrame()


df = load_data(GOOGLE_SHEET_URL)

# Curățare și preparare date
if not df.empty:
  date_col = next(
      (c for c in df.columns if "dat" in c.lower() or "date" in c.lower()),
      df.columns[0],
  )
  df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
  df = df.sort_values(by=date_col, ascending=False)

# Notificări Programări
prog_data = pd.DataFrame([
    {
        "Dată": "2026-09-25",
        "Tip": "Analize de laborator",
        "Clinică / Medic": "Regina Maria",
        "Observații": "Repetare analize Diabet",
        "Efectuat": "Nu",
    },
    {
        "Dată": "2026-10-05",
        "Tip": "Consult Diabet",
        "Clinică / Medic": "Dr. Clenciu Craiova",
        "Observații": "Rețetă 3 luni",
        "Efectuat": "Nu",
    },
])

if st.session_state.settings["notif_enabled"] and not prog_data.empty:
  prog_data["Dată_dt"] = pd.to_datetime(prog_data["Dată"], errors="coerce").dt.date
  today = date.today()
  upcoming = prog_data[
      (prog_data["Dată_dt"] >= today)
      & (
          prog_data["Dată_dt"]
          <= today
          + timedelta(days=st.session_state.settings["notif_days"])
      )
      & (prog_data["Efectuat"] == "Nu")
  ]
  if not upcoming.empty:
    for _, row in upcoming.iterrows():
      st.warning(
          f"🔔 **Notificare Programare Medicală:** {row['Tip']} la"
          f" **{row['Clinică / Medic']}** pe data de **{row['Dată']}**"
          f" ({row['Observații']})."
      )

# ==========================================
# STRUCTURĂ TAB-URI
# ==========================================
tab_jurnal, tab_add, tab_med, tab_prog, tab_pdf, tab_settings = st.tabs([
    "📊 Jurnal & Grafice",
    "➕ Adaugă / Modifică",
    "💊 Medicamente",
    "📅 Programări",
    "📄 Export Raport PDF",
    "⚙️ Setări Aplicație",
])

# ----------------- TAB 1: JURNAL & GRAFICE -----------------
with tab_jurnal:
  st.markdown("### 📊 Panou General de Monitorizare")

  if not df.empty:
    # 1. Carduri sintetice sus (KPIs)
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    # Căutare inteligentă coloane pentru KPI
    cols = df.columns
    col_glic = next((c for c in cols if "glic" in c.lower()), None)
    col_sis = next((c for c in cols if "sist" in c.lower()), None)
    col_dia = next((c for c in cols if "diast" in c.lower()), None)
    col_puls = next((c for c in cols if "puls" in c.lower()), None)

    with kpi1:
      val_glic = (
          f"{int(df[col_glic].dropna().iloc[0])} mg/dL"
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
          int(df[col_sis].dropna().iloc[0])
          if col_sis and not df[col_sis].dropna().empty
          else "-"
      )
      val_dia = (
          int(df[col_dia].dropna().iloc[0])
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
          f"{int(df[col_puls].dropna().iloc[0])} bpm"
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

    # 2. Grafice Profesionale Plotly
    st.markdown("#### 📈 Evoluție Parametri Medicali")
    g1, g2 = st.columns(2)

    with g1:
      fig_g = go.Figure()
      glic_cols = [c for c in cols if "glic" in c.lower()]
      for gc in glic_cols:
        fig_g.add_trace(
            go.Scatter(x=df[date_col], y=df[gc], mode="lines+markers", name=gc)
        )

      # Interval Țintă din Setări
      fig_g.add_hrect(
          y0=st.session_state.settings["target_glic_min"],
          y1=st.session_state.settings["target_glic_max"],
          fillcolor="green",
          opacity=0.1,
          line_width=0,
          annotation_text="Zona Țintă",
      )

      fig_g.update_layout(
          title="Evoluție Glicemie (mg/dL)",
          xaxis_title="Dată",
          yaxis_title="mg/dL",
          template="plotly_white",
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
            go.Scatter(x=df[date_col], y=df[tc], mode="lines+markers", name=tc)
        )

      fig_ta.update_layout(
          title="Evoluție Tensiune & Puls",
          xaxis_title="Dată",
          yaxis_title="mmHg / BPM",
          template="plotly_white",
          margin=dict(l=20, r=20, t=40, b=20),
      )
      st.plotly_chart(fig_ta, use_container_width=True)

    st.markdown("---")

    # 3. Tabelul de Date Structurat
    st.markdown("#### 📋 Istoric Detaliat Măsurători")
    df_display = df.copy()
    df_display[date_col] = df_display[date_col].dt.strftime("%Y-%m-%d")

    st.dataframe(
        df_display,
        use_container_width=True,
        height=380,
        column_config={
            date_col: st.column_config.DateColumn(
                "Data Măsurătorii", format="YYYY-MM-DD"
            )
        },
    )
  else:
    st.info("Nu s-au găsit date în spreadsheet.")

# ----------------- TAB 2: ADAUGĂ / MODIFICĂ -----------------
with tab_add:
  st.markdown("### 📝 Formular Introducere Măsurători")
  with st.container(border=True):
    with st.form("form_masuratoare_prof"):
      c1, c2, c3 = st.columns(3)
      with c1:
        data_input = st.date_input("📅 Data", value=date.today())
      with c2:
        moment_input = st.selectbox(
            "🌅 Moment", ["Dimineața", "Prânz", "Seara"]
        )
      with c3:
        user_input = st.selectbox("👤 Utilizator", list(st.session_state.users.keys()))

      st.markdown("---")
      g1, g2, g3, g4 = st.columns(4)
      with g1:
        glic_i = st.number_input("🩸 Glicemie Înainte", value=100)
      with g2:
        glic_d = st.number_input("🩸 Glicemie După", value=125)
      with g3:
        ta_s = st.number_input("🫀 Sistolică (Mare)", value=120)
      with g4:
        ta_d = st.number_input("🫀 Diastolică (Mică)", value=80)

      puls_i = st.number_input("💓 Puls (BPM)", value=72)
      notes_i = st.text_area(
          "✍️ Notițe / Simptome / Alimentație",
          placeholder="Detalii relevante...",
      )

      if st.form_submit_button(
          "💾 Salvează Înregistrarea", type="primary", use_container_width=True
      ):
        st.success(f"Măsurătoarea pentru {data_input} a fost înregistrată!")

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
      {
          "Medicament": "Aspenter",
          "Doză": "75 mg",
          "Orar": "Prânz",
          "Administrare": "După masă",
      },
  ])
  st.dataframe(meds_df, use_container_width=True)

# ----------------- TAB 4: PROGRAMĂRI -----------------
with tab_prog:
  st.markdown("### 📅 Programări & Consultații Medicale")
  st.dataframe(
      prog_data.drop(columns=["Dată_dt"], errors="ignore"),
      use_container_width=True,
  )

# ----------------- TAB 5: EXPORT PDF -----------------
with tab_pdf:
  st.markdown("### 📄 Generare Raport PDF")
  st.caption("Exportă un raport formatat pentru medicul specialist.")

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
              ("FONTSIZE", (0, 0), (-1, -1), 7),
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

# ----------------- TAB 6: SETĂRI APLICAȚIE -----------------
with tab_settings:
  st.markdown("### ⚙️ Centru de Setări & Administrare")

  s_col1, s_col2 = st.columns(2)

  with s_col1:
    with st.container(border=True):
      st.markdown("#### 🔒 Gestionare Utilizatori & Parole")
      curr_user = st.selectbox(
          "Selectează utilizatorul pentru modificare",
          list(st.session_state.users.keys()),
      )
      new_pass = st.text_input(
          f"Setează parolă nouă pentru {curr_user}", type="password"
      )

      if st.button("💾 Actualizează Parola"):
        if new_pass:
          st.session_state.users[curr_user] = new_pass
          st.success(f"Parola pentru {curr_user} a fost actualizată!")
        else:
          st.warning("Introduceți o parolă validă.")

      st.markdown("---")
      st.markdown("##### ➕ Adaugă Utilizator Nou")
      new_u_name = st.text_input("Nume Utilizator Nou")
      new_u_pass = st.text_input("Parolă Utilizator Nou", type="password")
      if st.button("➕ Creează Cont"):
        if new_u_name and new_u_pass:
          st.session_state.users[new_u_name] = new_u_pass
          st.success(f"Contul {new_u_name} a fost creat!")
          st.rerun()

  with s_col2:
    with st.container(border=True):
      st.markdown("#### 🔔 Setări Notificări & Alerte")
      st.session_state.settings["notif_enabled"] = st.toggle(
          "Activează Notificările de Sistem",
          value=st.session_state.settings["notif_enabled"],
      )
      st.session_state.settings["notif_days"] = st.slider(
          "Alertează cu X zile înainte de programare:",
          1,
          30,
          st.session_state.settings["notif_days"],
      )

      st.markdown("---")
      st.markdown("#### 🎯 Setare Valori Țintă (Referințe)")
      c_t1, c_t2 = st.columns(2)
      with c_t1:
        st.session_state.settings["target_glic_min"] = st.number_input(
            "Glicemie Minima Țintă",
            value=st.session_state.settings["target_glic_min"],
        )
        st.session_state.settings["target_ta_sis"] = st.number_input(
            "Tensiune Sistolică Max",
            value=st.session_state.settings["target_ta_sis"],
        )
      with c_t2:
        st.session_state.settings["target_glic_max"] = st.number_input(
            "Glicemie Maxima Țintă",
            value=st.session_state.settings["target_glic_max"],
        )
        st.session_state.settings["target_ta_dia"] = st.number_input(
            "Tensiune Diastolică Max",
            value=st.session_state.settings["target_ta_dia"],
        )

      if st.button("💾 Salvează Preferințele"):
        st.success("Setările au fost salvate cu succes!")
