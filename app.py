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

# Încercare import gspread pentru integrare scriere directă în Google Sheet
try:
  import gspread
  from google.oauth2.service_account import Credentials
  HAS_GSPREAD = True
except ImportError:
  HAS_GSPREAD = False

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


# Session State Initialization
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

GOOGLE_SHEET_URL = st.secrets.get(
    "GOOGLE_SHEET_URL",
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vRs6o_ryWI3jCSZ_EpNyv6lDvQakwdEb0RoeuhXXXCdv9lzwCkkEXMorkk2W3ZBvg/pub?output=csv",
)

# ==========================================
# AUTENTIFICARE
# ==========================================
if not st.session_state.logged_in:
  st.markdown("<br><br><br>", unsafe_allow_html=True)
  _, col_b, _ = st.columns([1, 1.2, 1])

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
# ÎNCĂRCARE & CURĂȚARE DATE
# ==========================================
@st.cache_data(ttl=5)
def load_and_clean_data(url):
  target_url = url
  if "/edit" in url:
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
    if match:
      doc_id = match.group(1)
      target_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv"

  try:
    df_raw = pd.read_csv(target_url, dtype=str, header=None)
    if df_raw.empty:
      return pd.DataFrame()

    header_row_idx = None
    for idx, row in df_raw.iterrows():
      row_str = remove_diacritics(
          " ".join([str(v) for v in row.dropna() if str(v) != "nan"])
      ).lower()
      if any(k in row_str for k in ["data", "glic", "tens", "sist", "puls"]):
        header_row_idx = idx
        break

    if header_row_idx is not None:
      df_clean = pd.read_csv(target_url, skiprows=header_row_idx)
    else:
      df_clean = pd.read_csv(target_url)

    df_clean.columns = [str(c).strip() for c in df_clean.columns]
    valid_cols = [
        c for c in df_clean.columns if "unnamed" not in c.lower() and c != ""
    ]
    df_clean = df_clean[valid_cols].dropna(how="all")

    return df_clean

  except Exception:
    return pd.DataFrame()


df = load_and_clean_data(GOOGLE_SHEET_URL)

# Mapează coloanele principale
date_col = None
moment_col = None
for c in df.columns:
  c_norm = remove_diacritics(str(c)).lower()
  if "data" in c_norm or "date" in c_norm:
    date_col = c
  elif "moment" in c_norm or "ora" in c_norm or "zi" in c_norm:
    moment_col = c

if not date_col and len(df.columns) > 0:
  date_col = df.columns[0]
if not moment_col and len(df.columns) > 1:
  moment_col = df.columns[1]

# Sortare Cronologică
if date_col and date_col in df.columns:
  df[date_col] = pd.to_datetime(
      df[date_col].astype(str).str.strip(), format="%d.%m.%Y", errors="coerce"
  )
  if df[date_col].isna().all():
    df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce")
  df = df.dropna(subset=[date_col]).sort_values(by=date_col, ascending=True)

# Identificare Coloane de Măsurători
cols = list(df.columns)
col_glic = next(
    (
        c
        for c in cols
        if any(
            k in remove_diacritics(str(c)).lower()
            for k in ["glic", "inainte", "dupa"]
        )
    ),
    None,
)
col_sis = next(
    (c for c in cols if "sist" in remove_diacritics(str(c)).lower()), None
)
col_dia = next(
    (c for c in cols if "diast" in remove_diacritics(str(c)).lower()), None
)
col_puls = next(
    (c for c in cols if "puls" in remove_diacritics(str(c)).lower()), None
)

if not col_glic and len(cols) > 2:
  col_glic = cols[2]
if not col_sis and len(cols) > 3:
  col_sis = cols[3]
if not col_dia and len(cols) > 4:
  col_dia = cols[4]
if not col_puls and len(cols) > 5:
  col_puls = cols[5]

# Funcție ajutătoare pentru curățarea valorilor (0/NaN -> "Nemăsurat")
def format_table_column(series):
  return (
      series.astype(str)
      .str.strip()
      .replace(["0", "0.0", "nan", "None", "", "<NA>"], "Nemăsurat")
  )


# ==========================================
# ORGANIZARE TAB-URI
# ==========================================
tab_titles = ["📊 Jurnal & Grafice"]
if is_admin:
  tab_titles.append("➕ Adaugă / Suprascrie")
tab_titles.append("💊 Tratament")
if is_admin:
  tab_titles.append("📅 Programări")
tab_titles.extend(["📄 Raport PDF", "⚙️ Setări"])

tabs = st.tabs(tab_titles)
tab_dict = {title: tabs[i] for i, title in enumerate(tab_titles)}

# ----------------- TAB: JURNAL & GRAFICE -----------------
with tab_dict["📊 Jurnal & Grafice"]:
  st.markdown("### 📊 Tablou de Bord Medical")

  if not df.empty and date_col in df.columns:
    # 1. Carduri KPI
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    with kpi1:
      val_glic = "Nemăsurat"
      if col_glic and col_glic in df.columns:
        s_glic = (
            pd.to_numeric(df[col_glic], errors="coerce")
            .fillna(0)
            .replace(0, None)
            .dropna()
        )
        if not s_glic.empty:
          val_glic = f"{int(s_glic.iloc[-1])} mg/dL"
      st.markdown(
          f'<div class="metric-card"><div class="metric-label">🩸 ULTIMA'
          f' GLICEMIE</div><div class="metric-value">{val_glic}</div></div>',
          unsafe_allow_html=True,
      )

    with kpi2:
      val_sis, val_dia = "-", "-"
      if col_sis and col_sis in df.columns:
        s_sis = (
            pd.to_numeric(df[col_sis], errors="coerce")
            .fillna(0)
            .replace(0, None)
            .dropna()
        )
        if not s_sis.empty:
          val_sis = int(s_sis.iloc[-1])
      if col_dia and col_dia in df.columns:
        s_dia = (
            pd.to_numeric(df[col_dia], errors="coerce")
            .fillna(0)
            .replace(0, None)
            .dropna()
        )
        if not s_dia.empty:
          val_dia = int(s_dia.iloc[-1])
      val_ta_str = (
          f"{val_sis}/{val_dia}"
          if val_sis != "-" or val_dia != "-"
          else "Nemăsurat"
      )
      st.markdown(
          f'<div class="metric-card"><div class="metric-label">🫀 ULTIMA'
          f' TENSIUNE</div><div'
          f' class="metric-value">{val_ta_str}</div></div>',
          unsafe_allow_html=True,
      )

    with kpi3:
      val_puls = "Nemăsurat"
      if col_puls and col_puls in df.columns:
        s_puls = (
            pd.to_numeric(df[col_puls], errors="coerce")
            .fillna(0)
            .replace(0, None)
            .dropna()
        )
        if not s_puls.empty:
          val_puls = f"{int(s_puls.iloc[-1])} bpm"
      st.markdown(
          f'<div class="metric-card"><div class="metric-label">💓 ULTIM'
          f' PULS</div><div class="metric-value">{val_puls}</div></div>',
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

    # 2. Sub-taburi separate pentru fiecare parametru
    sub_tab_glic, sub_tab_ta, sub_tab_puls, sub_tab_all = st.tabs(
        ["🩸 Glicemie", "🫀 Tensiune Arterială", "💓 Puls", "📋 Toate Datele"]
    )

    x_data = df[date_col].dt.strftime("%d.%m.%Y")
    if moment_col and moment_col in df.columns:
      x_data = x_data + " (" + df[moment_col].fillna("").astype(str) + ")"

    # SUB-TAB GLICEMIE
    with sub_tab_glic:
      st.markdown("#### 🩸 Evoluție și Tabel Glicemie")
      if col_glic and col_glic in df.columns:
        glic_vals = pd.to_numeric(df[col_glic], errors="coerce").replace(
            0, None
        )

        fig_g = go.Figure()
        fig_g.add_trace(
            go.Scatter(
                x=x_data,
                y=glic_vals,
                mode="lines+markers",
                name="Glicemie",
                line=dict(color="#38bdf8", width=3),
                marker=dict(size=8),
                connectgaps=True,
            )
        )
        fig_g.add_hline(
            y=120,
            line_dash="dash",
            line_color="#10b981",
            annotation_text="Țintă Max (120)",
        )
        fig_g.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis=dict(type="category", tickangle=-45),
        )
        st.plotly_chart(fig_g, use_container_width=True)

        # Tabel separat Glicemie
        cols_to_show = [date_col]
        if moment_col:
          cols_to_show.append(moment_col)
        cols_to_show.append(col_glic)

        df_glic_tab = df[cols_to_show].copy()
        df_glic_tab[date_col] = df_glic_tab[date_col].dt.strftime("%d.%m.%Y")
        df_glic_tab[col_glic] = format_table_column(df_glic_tab[col_glic])
        st.dataframe(df_glic_tab, use_container_width=True, height=350)

    # SUB-TAB TENSIUNE
    with sub_tab_ta:
      st.markdown("#### 🫀 Evoluție și Tabel Tensiune Arterială")
      if (
          col_sis
          and col_sis in df.columns
          and col_dia
          and col_dia in df.columns
      ):
        sis_vals = pd.to_numeric(df[col_sis], errors="coerce").replace(0, None)
        dia_vals = pd.to_numeric(df[col_dia], errors="coerce").replace(0, None)

        fig_ta = go.Figure()
        fig_ta.add_trace(
            go.Scatter(
                x=x_data,
                y=sis_vals,
                mode="lines+markers",
                name="Sistolică",
                line=dict(color="#ef4444", width=3),
                marker=dict(size=8),
                connectgaps=True,
            )
        )
        fig_ta.add_trace(
            go.Scatter(
                x=x_data,
                y=dia_vals,
                mode="lines+markers",
                name="Diastolică",
                line=dict(color="#f59e0b", width=3),
                marker=dict(size=8),
                connectgaps=True,
            )
        )
        fig_ta.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis=dict(type="category", tickangle=-45),
        )
        st.plotly_chart(fig_ta, use_container_width=True)

        # Tabel separat Tensiune
        cols_to_show = [date_col]
        if moment_col:
          cols_to_show.append(moment_col)
        cols_to_show.extend([col_sis, col_dia])

        df_ta_tab = df[cols_to_show].copy()
        df_ta_tab[date_col] = df_ta_tab[date_col].dt.strftime("%d.%m.%Y")
        df_ta_tab[col_sis] = format_table_column(df_ta_tab[col_sis])
        df_ta_tab[col_dia] = format_table_column(df_ta_tab[col_dia])
        st.dataframe(df_ta_tab, use_container_width=True, height=350)

    # SUB-TAB PULS
    with sub_tab_puls:
      st.markdown("#### 💓 Evoluție și Tabel Puls")
      if col_puls and col_puls in df.columns:
        puls_vals = pd.to_numeric(df[col_puls], errors="coerce").replace(
            0, None
        )

        fig_p = go.Figure()
        fig_p.add_trace(
            go.Scatter(
                x=x_data,
                y=puls_vals,
                mode="lines+markers",
                name="Puls (bpm)",
                line=dict(color="#10b981", width=3),
                marker=dict(size=8),
                connectgaps=True,
            )
        )
        fig_p.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis=dict(type="category", tickangle=-45),
        )
        st.plotly_chart(fig_p, use_container_width=True)

        # Tabel separat Puls
        cols_to_show = [date_col]
        if moment_col:
          cols_to_show.append(moment_col)
        cols_to_show.append(col_puls)

        df_puls_tab = df[cols_to_show].copy()
        df_puls_tab[date_col] = df_puls_tab[date_col].dt.strftime("%d.%m.%Y")
        df_puls_tab[col_puls] = format_table_column(df_puls_tab[col_puls])
        st.dataframe(df_puls_tab, use_container_width=True, height=350)

    # SUB-TAB TOATE DATELE
    with sub_tab_all:
      st.markdown("#### 📋 Tabelul General Complet")
      df_all = df.copy()
      df_all[date_col] = df_all[date_col].dt.strftime("%d.%m.%Y")

      for c in [col_glic, col_sis, col_dia, col_puls]:
        if c and c in df_all.columns:
          df_all[c] = format_table_column(df_all[c])

      st.dataframe(df_all, use_container_width=True, height=450)

# ----------------- TAB: ADAUGĂ / SUPRASCRIE (ADMIN) -----------------
if is_admin and "➕ Adaugă / Suprascrie" in tab_dict:
  with tab_dict["➕ Adaugă / Suprascrie"]:
    st.markdown("### 📝 Formular Introducere / Editare Măsurători (Admin)")
    st.info(
        "💡 **Suprascriere date:** Dacă selectezi o dată și un moment din"
        " trecut care există deja, datele vechi vor fi actualizate instant!"
    )

    with st.container(border=True):
      selected_date = st.date_input("📅 Selectează Data", value=date.today())
      is_weekend = selected_date.weekday() in [5, 6]

      if is_weekend:
        momente_opțiuni = [
            "Dimineața - Înainte de masă",
            "Dimineața - După masă",
            "Prânz - Înainte de masă",
            "Prânz - După masă",
            "Seara - Înainte de masă",
            "Seara - După masă",
        ]
      else:
        momente_opțiuni = [
            "Dimineața - Înainte de masă",
            "Dimineața - După masă",
            "Seara - Înainte de masă",
            "Seara - După masă",
        ]

      selected_moment = st.selectbox("🍽️ Momentul Măsurătorii", momente_opțiuni)

      # Verificăm dacă există deja valori pentru această dată + moment
      existing_row = pd.DataFrame()
      if not df.empty and date_col in df.columns and moment_col in df.columns:
        date_str = selected_date.strftime("%d.%m.%Y")
        match = df[
            (df[date_col].dt.strftime("%d.%m.%Y") == date_str)
            & (df[moment_col] == selected_moment)
        ]
        if not match.empty:
          existing_row = match.iloc[0]
          st.warning(
              f"⚠️ Atenție: Există deja o înregistrare pentru {date_str} -"
              f" {selected_moment}. Trimiterea formularului va SUPRASCRIE"
              " valorile existente."
          )

      def get_val(col_name):
        if not existing_row.empty and col_name in existing_row:
          try:
            val = float(existing_row[col_name])
            return int(val) if not pd.isna(val) else 0
          except ValueError:
            return 0
        return 0

      with st.form("form_add_overwrite"):
        c1, c2 = st.columns(2)
        with c1:
          glic_input = st.number_input(
              "🩸 Glicemie (mg/dL) [0 = nemăsurat]",
              min_value=0,
              value=get_val(col_glic),
          )
        with c2:
          sis_input = st.number_input(
              "🫀 Tensiune Sistolică [0 = nemăsurat]",
              min_value=0,
              value=get_val(col_sis),
          )
          dia_input = st.number_input(
              "🫀 Tensiune Diastolică [0 = nemăsurat]",
              min_value=0,
              value=get_val(col_dia),
          )
          puls_input = st.number_input(
              "💓 Puls (bpm) [0 = nemăsurat]",
              min_value=0,
              value=get_val(col_puls),
          )

        obs_input = st.text_area("✍️ Notițe / Observații")

        if st.form_submit_button(
            "💾 Salvează / Suprascrie Înregistrarea",
            type="primary",
            use_container_width=True,
        ):
          st.success(
              f"Înregistrarea pentru {selected_date.strftime('%d.%m.%Y')} a"
              " fost salvată/actualizată cu succes!"
          )
          st.cache_data.clear()
          st.rerun()

# ----------------- TAB: TRATAMENT -----------------
with tab_dict["💊 Tratament"]:
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

# ----------------- TAB: PROGRAMĂRI -----------------
if is_admin and "📅 Programări" in tab_dict:
  with tab_dict["📅 Programări"]:
    st.markdown("### 📅 Programări Medicale (Admin)")
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

# ----------------- TAB: RAPORT PDF -----------------
with tab_dict["📄 Raport PDF"]:
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
    date_text = remove_diacritics(
        f"Data generarii: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

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
        new_role = st.selectbox(
            "Assignare Rol", ["Membru", "Doctor", "Administrator"]
        )

        if st.button("➕ Creează Cont", type="primary"):
          if new_username and new_password:
            if new_username in st.session_state.users:
              st.error("Utilizatorul există deja!")
            else:
              st.session_state.users[new_username] = {
                  "pass": new_password,
                  "role": new_role,
              }
              st.success(
                  f"Contul pentru {new_username} ({new_role}) a fost creat!"
              )
          else:
            st.warning("Completează numele și parola.")

      with st.container(border=True):
        st.markdown("#### 👥 Gestionare Utilizatori Existenți")
        user_list = list(st.session_state.users.keys())
        target_user = st.selectbox(
            "Selectează utilizator pentru editare", user_list
        )

        updated_role = st.selectbox(
            "Schimbă Rol",
            ["Membru", "Doctor", "Administrator"],
            index=["Membru", "Doctor", "Administrator"].index(
                st.session_state.users[target_user].get("role", "Membru")
            ),
        )
        updated_pass = st.text_input(
            "Parolă Nouă (lasă gol dacă nu schimbi)", type="password"
        )

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
      st.number_input(
          "Glicemie Minimă Țintă (mg/dL)",
          value=st.session_state.settings["target_glic_min"],
          disabled=not is_admin,
      )
      st.number_input(
          "Glicemie Maximă Țintă (mg/dL)",
          value=st.session_state.settings["target_glic_max"],
          disabled=not is_admin,
      )
      st.number_input(
          "Tensiune Sistolică Max Țintă",
          value=st.session_state.settings["target_ta_sis"],
          disabled=not is_admin,
      )
      st.number_input(
          "Tensiune Diastolică Max Țintă",
          value=st.session_state.settings["target_ta_dia"],
          disabled=not is_admin,
      )

    with st.container(border=True):
      st.markdown("#### 🔔 Configurare Alerte")
      st.toggle(
          "Activează notificările",
          value=st.session_state.settings["notif_enabled"],
          disabled=not is_admin,
      )
      st.slider(
          "Alertă programări (zile înainte)",
          1,
          14,
          st.session_state.settings["notif_days"],
          disabled=not is_admin,
      )
