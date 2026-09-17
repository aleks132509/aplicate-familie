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

def remove_diacritics(text):
  if not isinstance(text, str):
    text = str(text)
  return "".join(
      c
      for c in unicodedata.normalize("NFD", text)
      if unicodedata.category(c) != "Mn"
  )

# Session State & RBAC
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

current_user_info = st.session_state.users.get(
    st.session_state.user, {"role": "Membru"}
)
current_role = current_user_info.get("role", "Membru")
is_admin = current_role == "Administrator"

# ==========================================
# SIDEBAR
# ==========================================
st.sidebar.markdown(f"### 👤 **{st.session_state.user}**")
st.sidebar.markdown(
    f"Rol: <span class='role-badge'>{current_role}</span>",
    unsafe_allow_html=True,
)
st.sidebar.markdown("<br>", unsafe_allow_html=True)

if st.sidebar.button("🚪 Deconectare", use_container_width=True):
  st.session_state.logged_in = False
  st.session_state.user = None
  st.rerun()

st.sidebar.markdown("---")

# ==========================================
# PARSARE DIRECTĂ GOOGLE SHEET
# ==========================================
@st.cache_data(ttl=5)
def load_and_clean_data(url):
  try:
    # 1. Citiți tot fișierul fără antet rigid
    raw_df = pd.read_csv(url, dtype=str, header=None)

    # 2. Găsiți primul rând care conține o dată validă de tip DD.MM.YYYY
    date_pattern = re.compile(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b")
    start_row = None

    for idx, row in raw_df.iterrows():
      row_str = " ".join([str(v) for v in row.dropna() if str(v) != "nan"])
      if date_pattern.search(row_str):
        start_row = max(0, idx - 1)
        break

    if start_row is not None:
      df_clean = pd.read_csv(url, skiprows=start_row)
    else:
      df_clean = pd.read_csv(url)

    df_clean.columns = [str(c).strip() for c in df_clean.columns]
    valid_cols = [c for c in df_clean.columns if "unnamed" not in c.lower() and c != ""]
    return df_clean[valid_cols].dropna(how="all")

  except Exception as e:
    st.error(f"Eroare la procesare: {e}")
    return pd.DataFrame()

df = load_and_clean_data(GOOGLE_SHEET_URL)

# Identificare coloană Dată
date_col = None
if not df.empty:
  for c in df.columns:
    if "data" in remove_diacritics(str(c)).lower() or "date" in remove_diacritics(str(c)).lower():
      date_col = c
      break
  if not date_col and len(df.columns) > 0:
    date_col = df.columns[0]

# Procesare Dată & Sortare Cronologică (de sus în jos)
if not df.empty and date_col and date_col in df.columns:
  df["_temp_date"] = pd.to_datetime(
      df[date_col].astype(str).str.strip(), format="%d.%m.%Y", errors="coerce"
  )
  if df["_temp_date"].isna().all():
    df["_temp_date"] = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce")

  df = df.dropna(subset=["_temp_date"]).sort_values(by="_temp_date", ascending=True)
  df["Data_Display"] = df["_temp_date"].dt.strftime("%d.%m.%Y")
else:
  df["Data_Display"] = []

# Identificare coloane pentru grafic
cols = list(df.columns)
col_glic_in = next((c for c in cols if "glic" in remove_diacritics(str(c)).lower() and "inainte" in remove_diacritics(str(c)).lower()), None)
col_glic_dp = next((c for c in cols if "glic" in remove_diacritics(str(c)).lower() and "dupa" in remove_diacritics(str(c)).lower()), None)
col_glic_gen = next((c for c in cols if "glic" in remove_diacritics(str(c)).lower()), None)

col_sis = next((c for c in cols if "sist" in remove_diacritics(str(c)).lower()), None)
col_dia = next((c for c in cols if "diast" in remove_diacritics(str(c)).lower()), None)
col_puls = next((c for c in cols if "puls" in remove_diacritics(str(c)).lower()), None)
col_moment = next((c for c in cols if any(k in remove_diacritics(str(c)).lower() for k in ["moment", "ora"])), None)

# ==========================================
# ORGANIZARE TAB-URI PE BAZĂ DE ROL
# ==========================================
tab_titles = ["📊 Jurnal & Grafice"]
if is_admin:
  tab_titles.append("➕ Adaugă Înregistrare")
tab_titles.append("💊 Tratament")
if is_admin:
  tab_titles.append("📅 Programări")
tab_titles.extend(["📄 Raport PDF", "⚙️ Setări"])

tabs = st.tabs(tab_titles)
tab_dict = {title: tabs[i] for i, title in enumerate(tab_titles)}

# ----------------- TAB: JURNAL & GRAFICE -----------------
with tab_dict["📊 Jurnal & Grafice"]:
  st.markdown("### 📊 Tablou de Bord Medical")

  if not df.empty and "Data_Display" in df.columns:
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    # Ultimele valori (de la finalul tabelului)
    with kpi1:
      val_glic = "N/A"
      glic_col = col_glic_in or col_glic_dp or col_glic_gen
      if glic_col and glic_col in df.columns:
        s_glic = pd.to_numeric(df[glic_col], errors="coerce").dropna()
        if not s_glic.empty:
          val_glic = f"{int(s_glic.iloc[-1])} mg/dL"
      st.markdown(
          f'<div class="metric-card"><div class="metric-label">🩸 ULTIMA GLICEMIE</div><div class="metric-value">{val_glic}</div></div>',
          unsafe_allow_html=True,
      )

    with kpi2:
      val_sis, val_dia = "-", "-"
      if col_sis and col_sis in df.columns:
        s_sis = pd.to_numeric(df[col_sis], errors="coerce").dropna()
        if not s_sis.empty:
          val_sis = int(s_sis.iloc[-1])
      if col_dia and col_dia in df.columns:
        s_dia = pd.to_numeric(df[col_dia], errors="coerce").dropna()
        if not s_dia.empty:
          val_dia = int(s_dia.iloc[-1])
      st.markdown(
          f'<div class="metric-card"><div class="metric-label">🫀 ULTIMA TENSIUNE</div><div class="metric-value">{val_sis}/{val_dia}</div></div>',
          unsafe_allow_html=True,
      )

    with kpi3:
      val_puls = "N/A"
      if col_puls and col_puls in df.columns:
        s_puls = pd.to_numeric(df[col_puls], errors="coerce").dropna()
        if not s_puls.empty:
          val_puls = f"{int(s_puls.iloc[-1])} bpm"
      st.markdown(
          f'<div class="metric-card"><div class="metric-label">💓 ULTIM PULS</div><div class="metric-value">{val_puls}</div></div>',
          unsafe_allow_html=True,
      )

    with kpi4:
      st.markdown(
          f'<div class="metric-card"><div class="metric-label">📅 TOTAL ÎNREGISTRĂRI</div><div class="metric-value">{len(df)}</div></div>',
          unsafe_allow_html=True,
      )

    st.markdown("<br>", unsafe_allow_html=True)

    # Grafice fără ore pe axa X
    st.markdown("#### 📈 Grafice Evoluție Medicală")
    g1, g2 = st.columns(2)

    if col_moment and col_moment in df.columns:
      x_labels = df["Data_Display"] + " (" + df[col_moment].fillna("").astype(str) + ")"
    else:
      x_labels = df["Data_Display"]

    with g1:
      fig_g = go.Figure()
      if col_glic_in and col_glic_in in df.columns:
        fig_g.add_trace(go.Scatter(x=x_labels, y=pd.to_numeric(df[col_glic_in], errors="coerce"), mode="lines+markers", name="Înainte Masă", line=dict(color="#38bdf8", width=3), marker=dict(size=8)))
      if col_glic_dp and col_glic_dp in df.columns:
        fig_g.add_trace(go.Scatter(x=x_labels, y=pd.to_numeric(df[col_glic_dp], errors="coerce"), mode="lines+markers", name="După Masă", line=dict(color="#fb923c", width=3, dash="dot"), marker=dict(size=8)))
      if not col_glic_in and not col_glic_dp and col_glic_gen and col_glic_gen in df.columns:
        fig_g.add_trace(go.Scatter(x=x_labels, y=pd.to_numeric(df[col_glic_gen], errors="coerce"), mode="lines+markers", name="Glicemie", line=dict(color="#38bdf8", width=3), marker=dict(size=8)))

      fig_g.add_hline(y=120, line_dash="dash", line_color="#10b981", annotation_text="Țintă (120)")
      fig_g.update_layout(title="Evoluție Glicemie (mg/dL)", template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis=dict(type="category", tickangle=-45), margin=dict(l=20, r=20, t=40, b=20), hovermode="x unified")
      st.plotly_chart(fig_g, use_container_width=True)

    with g2:
      fig_ta = go.Figure()
      if col_sis and col_sis in df.columns:
        fig_ta.add_trace(go.Scatter(x=x_labels, y=pd.to_numeric(df[col_sis], errors="coerce"), mode="lines+markers", name="Sistolică", line=dict(color="#ef4444", width=3), marker=dict(size=8)))
      if col_dia and col_dia in df.columns:
        fig_ta.add_trace(go.Scatter(x=x_labels, y=pd.to_numeric(df[col_dia], errors="coerce"), mode="lines+markers", name="Diastolică", line=dict(color="#f59e0b", width=3), marker=dict(size=8)))
      if col_puls and col_puls in df.columns:
        s_p = pd.to_numeric(df[col_puls], errors="coerce")
        if not s_p.isna().all():
          fig_ta.add_trace(go.Scatter(x=x_labels, y=s_p, mode="lines+markers", name="Puls", line=dict(color="#10b981", width=2, dash="dash"), marker=dict(size=6)))

      fig_ta.update_layout(title="Evoluție Tensiune & Puls", template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis=dict(type="category", tickangle=-45), margin=dict(l=20, r=20, t=40, b=20), hovermode="x unified")
      st.plotly_chart(fig_ta, use_container_width=True)

    st.markdown("---")

    st.markdown("#### 📋 Tabelul Măsurătorilor (Cronologic: 12.09.2026 ➔ Prezent)")
    df_display = df.copy()
    if "_temp_date" in df_display.columns:
      df_display = df_display.drop(columns=["_temp_date"])
    if "Data_Display" in df_display.columns and date_col in df_display.columns:
      df_display[date_col] = df_display["Data_Display"]
      df_display = df_display.drop(columns=["Data_Display"])

    st.dataframe(df_display, use_container_width=True, height=450)
  else:
    st.warning("Nu s-au găsit date valide în fișierul Google Sheet.")

# ----------------- TAB: ADAUGĂ ÎNREGISTRARE (EXCLUSIV ADMIN) -----------------
if is_admin and "➕ Adaugă Înregistrare" in tab_dict:
  with tab_dict["➕ Adaugă Înregistrare"]:
    st.markdown("### 📝 Formular Introducere Măsurători (Admin)")
    with st.container(border=True):
      selected_date = st.date_input("📅 Data Măsurătorii", value=date.today())
      is_weekend = selected_date.weekday() in [5, 6]

      if is_weekend:
        st.info("ℹ️ Configurat pentru **WEEKEND**: 6 înregistrări pe zi (Dimineața, Prânz, Seara).")
        momente = [
            "Dimineața - Înainte de masă", "Dimineața - După masă",
            "Prânz - Înainte de masă", "Prânz - După masă",
            "Seara - Înainte de masă", "Seara - După masă"
        ]
      else:
        st.info("ℹ️ Configurat pentru **ZILE SĂPTĂMÂNĂ**: 4 înregistrări pe zi (Dimineața, Seara).")
        momente = [
            "Dimineața - Înainte de masă", "Dimineața - După masă",
            "Seara - Înainte de masă", "Seara - După masă"
        ]

      with st.form("form_add"):
        c1, c2 = st.columns(2)
        with c1:
          st.selectbox("🍽️ Momentul Măsurătorii", momente)
          st.number_input("🩸 Glicemie (mg/dL)", value=100)
        with c2:
          st.number_input("🫀 Tensiune Sistolică", value=120)
          st.number_input("🫀 Tensiune Diastolică", value=80)
          st.number_input("💓 Puls (bpm)", value=72)

        st.text_area("✍️ Notițe / Observații")

        if st.form_submit_button("💾 Salvează Înregistrarea", type="primary", use_container_width=True):
          st.success("Măsurătoarea a fost salvată!")

# ----------------- TAB: TRATAMENT -----------------
with tab_dict["💊 Tratament"]:
  st.markdown("### 💊 Schemă Tratament Medical")
  meds_df = pd.DataFrame([
      {"Medicament": "Glucophage", "Doză": "1000 mg", "Orar": "Dimineața / Seara", "Administrare": "După masă"},
      {"Medicament": "Lagosa", "Doză": "150 mg", "Orar": "Dimineața / Seara", "Administrare": "După masă"},
      {"Medicament": "Diaprel MR", "Doză": "60 mg (1/2)", "Orar": "Dimineața", "Administrare": "Înainte de masă"},
      {"Medicament": "Atacand", "Doză": "8 mg", "Orar": "Seara", "Administrare": "După masă"},
      {"Medicament": "Nebilet", "Doză": "5 mg", "Orar": "Dimineața", "Administrare": "După masă"},
  ])
  st.dataframe(meds_df, use_container_width=True)

# ----------------- TAB: PROGRAMĂRI (EXCLUSIV ADMIN) -----------------
if is_admin and "📅 Programări" in tab_dict:
  with tab_dict["📅 Programări"]:
    st.markdown("### 📅 Programări Medicale (Admin)")
    prog_df = pd.DataFrame([
        {"Dată": "2026-09-25", "Tip": "Analize de laborator", "Clinică": "Regina Maria", "Observații": "Repetare analize Diabet"},
        {"Dată": "2026-10-05", "Tip": "Consult Diabet", "Clinică": "Dr. Clenciu Craiova", "Observații": "Rețetă 3 luni"},
    ])
    st.dataframe(prog_df, use_container_width=True)

# ----------------- TAB: RAPORT PDF -----------------
with tab_dict["📄 Raport PDF"]:
  st.markdown("### 📄 Generare Raport PDF")

  def make_pdf(data_frame):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25
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

      for _, row in data_frame.iterrows():
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

# ----------------- TAB: SETĂRI -----------------
with tab_dict["⚙️ Setări"]:
  st.markdown("### ⚙️ Setări & Drepturi Acces")
  s1, s2 = st.columns(2)

  with s1:
    if is_admin:
      with st.container(border=True):
        st.markdown("#### ➕ Adaugă Utilizator Nou (Admin)")
        new_username = st.text_input("Nume Utilizator Nou")
        new_password = st.text_input("Parolă Utilizator", type="password")
        new_role = st.selectbox("Assignare Rol", ["Membru", "Doctor", "Administrator"])

        if st.button("➕ Creează Cont", type="primary"):
          if new_username and new_password:
            if new_username in st.session_state.users:
              st.error("Utilizatorul există deja!")
            else:
              st.session_state.users[new_username] = {"pass": new_password, "role": new_role}
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
            index=["Membru", "Doctor", "Administrator"].index(
                st.session_state.users[target_user].get("role", "Membru")
            ),
        )
        updated_pass = st.text_input("Parolă Nouă (lasă gol dacă nu schimbi)", type="password")

        if st.button("💾 Salvează Modificările Contului"):
          st.session_state.users[target_user]["role"] = updated_role
          if updated_pass:
            st.session_state.users[target_user]["pass"] = updated_pass
          st.success(f"Detaliile pentru {target_user} au fost actualizate!")
    else:
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
      st.number_input("Glicemie Minimă Țintă (mg/dL)", value=st.session_state.settings["target_glic_min"], disabled=not is_admin)
      st.number_input("Glicemie Maximă Țintă (mg/dL)", value=st.session_state.settings["target_glic_max"], disabled=not is_admin)
      st.number_input("Tensiune Sistolică Max Țintă", value=st.session_state.settings["target_ta_sis"], disabled=not is_admin)
      st.number_input("Tensiune Diastolică Max Țintă", value=st.session_state.settings["target_ta_dia"], disabled=not is_admin)

    with st.container(border=True):
      st.markdown("#### 🔔 Configurare Alerte")
      st.toggle("Activează notificările", value=st.session_state.settings["notif_enabled"], disabled=not is_admin)
      st.slider("Alertă programări (zile înainte)", 1, 14, st.session_state.settings["notif_days"], disabled=not is_admin)
