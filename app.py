import io
import re
import unicodedata
from datetime import date, datetime
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

# Memorie temporară locală în sesiune dacă nu e conectat Google Sheets real
if "local_df_override" not in st.session_state:
  st.session_state.local_df_override = None

GOOGLE_SHEET_URL = st.secrets.get("GOOGLE_SHEET_URL", "")

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
# DATE DEMO (FALLBACK SIGURANȚĂ)
# ==========================================
def get_mock_data():
  return pd.DataFrame({
      "Dată": [
          "12.09.2026",
          "12.09.2026",
          "12.09.2026",
          "13.09.2026",
          "13.09.2026",
          "13.09.2026",
      ],
      "Moment Zi": [
          "Dimineața - Înainte de masă",
          "Prânz - Înainte de masă",
          "Seara - După masă",
          "Dimineața - Înainte de masă",
          "Prânz - După masă",
          "Seara - Înainte de masă",
      ],
      "Glicemie": [105, 115, 135, 98, 140, 65],
      "Sistolică": [122, 121, 124, 118, 126, 119],
      "Diastolică": [78, 77, 81, 75, 82, 76],
      "Puls": [72, 72, 74, 70, 76, 105],
      "Observații": ["Ajeun", "Prânz OK", "Cină", "Ajeun", "Prânz", "Seară"],
  })


# ==========================================
# ÎNCĂRCARE & CURĂȚARE DATE ROBUSTĂ
# ==========================================
@st.cache_data(ttl=5)
def load_and_clean_data(url):
  if not url:
    return get_mock_data()

  try:
    df_raw = pd.read_csv(url, dtype=str, header=None)
    if df_raw.empty:
      return get_mock_data()

    header_row_idx = None
    for idx, row in df_raw.iterrows():
      row_str = remove_diacritics(
          " ".join([str(v) for v in row.dropna() if str(v) != "nan"])
      ).lower()
      if any(k in row_str for k in ["data", "glic", "tens", "sist", "puls"]):
        header_row_idx = idx
        break

    if header_row_idx is not None:
      df_clean = pd.read_csv(url, skiprows=header_row_idx)
    else:
      df_clean = pd.read_csv(url)

    df_clean.columns = [str(c).strip() for c in df_clean.columns]
    valid_cols = [
        c for c in df_clean.columns if "unnamed" not in c.lower() and c != ""
    ]
    df_clean = df_clean[valid_cols].dropna(how="all")

    if df_clean.empty:
      return get_mock_data()

    return df_clean

  except Exception:
    return get_mock_data()


# Încărcare inițială sau din suprascriere locală de sesiune
base_df = load_and_clean_data(GOOGLE_SHEET_URL)
if st.session_state.local_df_override is not None:
  df = st.session_state.local_df_override
else:
  df = base_df.copy()


def save_to_google_sheet_or_local(
    date_str, moment_str, glic_v, sis_v, dia_v, puls_v, obs_v
):
  global df
  # Dacă avem configurat Google Sheets cu gspread real
  if HAS_GSPREAD and "gcp_service_account" in st.secrets:
    try:
      scopes = ["https://www.googleapis.com/auth/spreadsheets"]
      creds = Credentials.from_service_account_info(
          dict(st.secrets["gcp_service_account"]), scopes=scopes
      )
      client = gspread.authorize(creds)
      sheet_url = st.secrets["GOOGLE_SHEET_URL"]
      sh = client.open_by_url(sheet_url)
      ws = sh.get_worksheet(0)

      records = ws.get_all_values()
      row_to_update = None
      if records:
        for idx, row in enumerate(records[1:], start=2):
          if (
              len(row) >= 2
              and row[0].strip() == date_str
              and row[1].strip() == moment_str
          ):
            row_to_update = idx
            break

      new_row = [
          date_str,
          moment_str,
          str(glic_v) if glic_v > 0 else "0",
          str(sis_v) if sis_v > 0 else "0",
          str(dia_v) if dia_v > 0 else "0",
          str(puls_v) if puls_v > 0 else "0",
          obs_v,
      ]

      if row_to_update:
        ws.update(f"A{row_to_update}:G{row_to_update}", [new_row])
      else:
        ws.append_row(new_row)
      return True
    except Exception as e:
      st.error(f"Eroare Google Sheets: {e}")
      return False
  else:
    # Salvăm direct în DataFrame-ul curent din sesiune (pentru testare/mod local)
    d_col = df.columns[0]
    m_col = df.columns[1] if len(df.columns) > 1 else "Moment Zi"
    g_col = col_glic if col_glic in df.columns else df.columns[2]
    s_col = col_sis if col_sis in df.columns else df.columns[3]
    d_col_ta = col_dia if col_dia in df.columns else df.columns[4]
    p_col = col_puls if col_puls in df.columns else df.columns[5]
    o_col = (
        "Observații" if "Observații" in df.columns else df.columns[6]
        if len(df.columns) > 6
        else None
    )

    # Căutăm dacă există rândul
    mask = (df[d_col].astype(str).str.contains(date_str)) & (
        df[m_col].astype(str) == moment_str
    )

    if mask.any():
      df.loc[mask, g_col] = glic_v
      df.loc[mask, s_col] = sis_v
      df.loc[mask, d_col_ta] = dia_v
      df.loc[mask, p_col] = puls_v
      if o_col and o_col in df.columns:
        df.loc[mask, o_col] = obs_v
    else:
      new_record = {
          d_col: date_str,
          m_col: moment_str,
          g_col: glic_v,
          s_col: sis_v,
          d_col_ta: dia_v,
          p_col: puls_v,
      }
      if o_col:
        new_record[o_col] = obs_v
      df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)

    st.session_state.local_df_override = df
    return True


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

if date_col and date_col in df.columns:
  df[date_col] = pd.to_datetime(
      df[date_col].astype(str).str.strip(), format="%d.%m.%Y", errors="coerce"
  )
  if df[date_col].isna().all():
    df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce")
  df = df.dropna(subset=[date_col]).sort_values(by=date_col, ascending=True)

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


def format_table_column(series):
  return (
      series.astype(str)
      .str.strip()
      .replace(["0", "0.0", "nan", "None", "", "<NA>"], "Nemăsurat")
  )


# ==========================================
# FUNCȚII EVALUARE MEDICALĂ
# ==========================================
def evaluate_glic(val):
  try:
    v = float(val)
    if v == 0 or pd.isna(v):
      return "Nemăsurat"
    t_min = st.session_state.settings["target_glic_min"]
    t_max = st.session_state.settings["target_glic_max"]
    if t_min <= v <= t_max:
      return "🟢 Glicemie Normală"
    elif v < t_min:
      return "🔴 Glicemie Prea Mică"
    else:
      return "🔴 Glicemie Prea Mare"
  except:
    return "Nemăsurat"


def evaluate_ta(sis_val, dia_val):
  try:
    s = float(sis_val)
    d = float(dia_val)
    if s == 0 or d == 0 or pd.isna(s) or pd.isna(d):
      return "Nemăsurat"
    max_s = st.session_state.settings["target_ta_sis"]
    max_d = st.session_state.settings["target_ta_dia"]
    if s <= max_s and d <= max_d:
      return "🟢 Tensiune Normală"
    else:
      return "🔴 Tensiune Crescută"
  except:
    return "Nemăsurat"


def evaluate_puls(val):
  try:
    v = float(val)
    if v == 0 or pd.isna(v):
      return "Nemăsurat"
    if 60 <= v <= 100:
      return "🟢 Puls Normal"
    elif v < 60:
      return "🔴 Puls Prea Scăzut"
    else:
      return "🔴 Puls Prea Ridicat"
  except:
    return "Nemăsurat"


def color_status(val):
  if not isinstance(val, str):
    return ""
  if "🟢" in val:
    return (
        "background-color: #047857; color: #ffffff; font-weight: bold;"
        " text-align: center;"
    )
  elif "🔴" in val:
    return (
        "background-color: #b91c1c; color: #ffffff; font-weight: bold;"
        " text-align: center;"
    )
  return ""


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
    avg_glic_str = "Nemăsurat"
    if col_glic and col_glic in df.columns:
      s_glic_all = (
          pd.to_numeric(df[col_glic], errors="coerce")
          .fillna(0)
          .replace(0, None)
          .dropna()
      )
      if not s_glic_all.empty:
        avg_glic_str = f"{int(s_glic_all.mean())} mg/dL"

    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)

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
      st.markdown(
          f'<div class="metric-card"><div class="metric-label">📊 MEDIE'
          f' GLICEMIE</div><div'
          f' class="metric-value">{avg_glic_str}</div></div>',
          unsafe_allow_html=True,
      )

    with kpi3:
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

    with kpi4:
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

    with kpi5:
      st.markdown(
          f'<div class="metric-card"><div class="metric-label">📅 TOTAL'
          f' ÎNREGISTRĂRI</div><div'
          f' class="metric-value">{len(df)}</div></div>',
          unsafe_allow_html=True,
      )

    st.markdown("<br>", unsafe_allow_html=True)

    sub_tab_glic, sub_tab_ta, sub_tab_puls, sub_tab_all = st.tabs(
        ["🩸 Glicemie", "🫀 Tensiune Arterială", "💓 Puls", "📋 Toate Datele"]
    )

    x_data_strict = df[date_col].dt.strftime("%d.%m.%Y")

    # 1. TAB GLICEMIE
    with sub_tab_glic:
      st.markdown("#### 🩸 Evoluție și Tabel Dedicat - Glicemie")
      if col_glic and col_glic in df.columns:
        glic_vals = pd.to_numeric(df[col_glic], errors="coerce").replace(
            0, None
        )

        fig_g = go.Figure()
        fig_g.add_trace(
            go.Scatter(
                x=x_data_strict,
                y=glic_vals,
                mode="lines+markers+text",
                name="Glicemie",
                line=dict(color="#38bdf8", width=3),
                marker=dict(size=10, color="#38bdf8"),
                text=glic_vals,
                textposition="top center",
                textfont=dict(size=12, color="#ffffff"),
                texttemplate="<b>%{text}</b>",
                connectgaps=True,
            )
        )
        fig_g.update_traces(cliponaxis=False)
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
            margin=dict(l=40, r=40, t=40, b=30),
            xaxis=dict(type="category", tickangle=-30),
        )
        st.plotly_chart(fig_g, use_container_width=True)

        cols_g = [date_col]
        if moment_col:
          cols_g.append(moment_col)
        cols_g.append(col_glic)

        df_g_tab = df[cols_g].copy()
        df_g_tab[date_col] = df_g_tab[date_col].dt.strftime("%d.%m.%Y")
        df_g_tab["Status Glicemie"] = df_g_tab[col_glic].apply(evaluate_glic)
        df_g_tab[col_glic] = format_table_column(df_g_tab[col_glic])

        st.dataframe(
            df_g_tab.style.map(color_status, subset=["Status Glicemie"]),
            use_container_width=True,
            height=350,
        )

    # 2. TAB TENSIUNE ARTERIALĂ
    with sub_tab_ta:
      st.markdown("#### 🫀 Evoluție și Tabel Dedicat - Tensiune Arterială")
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
                x=x_data_strict,
                y=sis_vals,
                mode="lines+markers+text",
                name="Sistolică",
                line=dict(color="#ef4444", width=3),
                marker=dict(size=10),
                text=sis_vals,
                textposition="top center",
                textfont=dict(size=12, color="#ffffff"),
                texttemplate="<b>%{text}</b>",
                connectgaps=True,
            )
        )
        fig_ta.add_trace(
            go.Scatter(
                x=x_data_strict,
                y=dia_vals,
                mode="lines+markers+text",
                name="Diastolică",
                line=dict(color="#f59e0b", width=3),
                marker=dict(size=10),
                text=dia_vals,
                textposition="bottom center",
                textfont=dict(size=12, color="#ffffff"),
                texttemplate="<b>%{text}</b>",
                connectgaps=True,
            )
        )
        fig_ta.update_traces(cliponaxis=False)
        fig_ta.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=40, r=40, t=40, b=30),
            xaxis=dict(type="category", tickangle=-30),
        )
        st.plotly_chart(fig_ta, use_container_width=True)

        cols_t = [date_col]
        if moment_col:
          cols_t.append(moment_col)
        cols_t.extend([col_sis, col_dia])

        df_t_tab = df[cols_t].copy()
        df_t_tab[date_col] = df_t_tab[date_col].dt.strftime("%d.%m.%Y")
        df_t_tab["Status Tensiune"] = df_t_tab.apply(
            lambda r: evaluate_ta(r[col_sis], r[col_dia]), axis=1
        )
        df_t_tab[col_sis] = format_table_column(df_t_tab[col_sis])
        df_t_tab[col_dia] = format_table_column(df_t_tab[col_dia])

        st.dataframe(
            df_t_tab.style.map(color_status, subset=["Status Tensiune"]),
            use_container_width=True,
            height=350,
        )

    # 3. TAB PULS
    with sub_tab_puls:
      st.markdown("#### 💓 Evoluție și Tabel Dedicat - Puls")
      if col_puls and col_puls in df.columns:
        puls_vals = pd.to_numeric(df[col_puls], errors="coerce").replace(
            0, None
        )

        fig_p = go.Figure()
        fig_p.add_trace(
            go.Scatter(
                x=x_data_strict,
                y=puls_vals,
                mode="lines+markers+text",
                name="Puls (bpm)",
                line=dict(color="#10b981", width=3),
                marker=dict(size=10),
                text=puls_vals,
                textposition="top center",
                textfont=dict(size=12, color="#ffffff"),
                texttemplate="<b>%{text}</b>",
                connectgaps=True,
            )
        )
        fig_p.update_traces(cliponaxis=False)
        fig_p.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=40, r=40, t=40, b=30),
            xaxis=dict(type="category", tickangle=-30),
        )
        st.plotly_chart(fig_p, use_container_width=True)

        cols_p = [date_col]
        if moment_col:
          cols_p.append(moment_col)
        cols_p.append(col_puls)

        df_p_tab = df[cols_p].copy()
        df_p_tab[date_col] = df_p_tab[date_col].dt.strftime("%d.%m.%Y")
        df_p_tab["Status Puls"] = df_p_tab[col_puls].apply(evaluate_puls)
        df_p_tab[col_puls] = format_table_column(df_p_tab[col_puls])

        st.dataframe(
            df_p_tab.style.map(color_status, subset=["Status Puls"]),
            use_container_width=True,
            height=350,
        )

    # 4. TAB TOATE DATELE
    with sub_tab_all:
      st.markdown("#### 📋 Tabel General Complet cu Statusuri")
      df_all = df.copy()
      df_all[date_col] = df_all[date_col].dt.strftime("%d.%m.%Y")

      if col_glic in df_all.columns:
        df_all["St. Glicemie"] = df_all[col_glic].apply(evaluate_glic)
        df_all[col_glic] = format_table_column(df_all[col_glic])
      if col_sis in df_all.columns and col_dia in df_all.columns:
        df_all["St. Tensiune"] = df_all.apply(
            lambda r: evaluate_ta(r[col_sis], r[col_dia]), axis=1
        )
        df_all[col_sis] = format_table_column(df_all[col_sis])
        df_all[col_dia] = format_table_column(df_all[col_dia])
      if col_puls in df_all.columns:
        df_all["St. Puls"] = df_all[col_puls].apply(evaluate_puls)
        df_all[col_puls] = format_table_column(df_all[col_puls])

      st.dataframe(df_all, use_container_width=True, height=450)

# ----------------- TAB: ADAUGĂ / SUPRASCRIE (ADMIN) -----------------
if is_admin and "➕ Adaugă / Suprascrie" in tab_dict:
  with tab_dict["➕ Adaugă / Suprascrie"]:
    st.markdown("### 📝 Formular Introducere / Suprascriere Măsurători")
    st.info(
        "💡 **Weekend vs Săptămână:** Dacă selectezi o zi de sâmbătă sau"
        " duminică, apar automat opțiunile pentru **Prânz** la mijloc (6"
        " momente). În timpul săptămânii sunt 4 momente."
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
              f"⚠️ Există deja o înregistrare pentru {date_str} -"
              f" {selected_moment}. Trimiterea formularului va SUPRASCRIE"
              " valorile."
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

        submitted = st.form_submit_button(
            "💾 Salvează / Suprascrie Înregistrarea",
            type="primary",
            use_container_width=True,
        )

        if submitted:
          d_str = selected_date.strftime("%d.%m.%Y")
          saved = save_to_google_sheet_or_local(
              d_str,
              selected_moment,
              glic_input,
              sis_input,
              dia_input,
              puls_input,
              obs_input,
          )
          if saved:
            st.success(
                f"✅ Înregistrarea pentru {d_str} ({selected_moment}) a fost"
                " salvată cu succes!"
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

# ----------------- TAB: RAPORT PDF PROFESIONAL -----------------
with tab_dict["📄 Raport PDF"]:
  st.markdown("### 📄 Generare Raport PDF Personalizat și Profesional")
  st.markdown(
      "Alege opțiunile pentru conținutul grafic și tabelar din raportul PDF:"
  )

  col_opt1, col_opt2 = st.columns(2)
  with col_opt1:
    opt_glic = st.checkbox("Include Grafic Glicemie 🩸", value=True)
    opt_ta = st.checkbox("Include Grafic Tensiune Arterială 🫀", value=True)
  with col_opt2:
    opt_puls = st.checkbox("Include Grafic Puls 💓", value=True)
    opt_tabele = st.checkbox(
        "Include Tabelul Centralizator cu Culori 📋", value=True
    )


  def generate_pdf_chart(x_vals, y_vals, title, ylabel, color_hex):
    plt.figure(figsize=(7.5, 2.2))
    plt.plot(
        x_vals,
        y_vals,
        marker="o",
        linestyle="-",
        color=color_hex,
        linewidth=2.2,
        markersize=6,
    )
    for xi, yi in zip(x_vals, y_vals):
      if yi > 0:
        plt.annotate(
            str(int(yi)),
            (xi, yi),
            textcoords="offset points",
            xytext=(0, 7),
            ha="center",
            fontsize=8,
            fontweight="bold",
            bbox=dict(
                boxstyle="round,pad=0.2",
                fc="white",
                ec=color_hex,
                alpha=0.85,
            ),
        )
    plt.title(title, fontsize=10, fontweight="bold", color="#1e3a8a", pad=12)
    plt.ylabel(ylabel, fontsize=9, fontweight="bold")
    plt.xticks(rotation=20, fontsize=8)
    plt.yticks(fontsize=8)
    plt.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()

    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format="png", dpi=200)
    plt.close()
    img_buffer.seek(0)
    return img_buffer


  def make_pdf_report(
      data_frame, include_glic, include_ta, include_puls, include_tables
  ):
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

    title_text = remove_diacritics("RAPORT MEDICAL DE MONITORIZARE - HEALTHTRACK PRO")
    date_text = remove_diacritics(
        f"Generat la: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )

    story.append(
        Paragraph(
            f"<b>{title_text}</b>",
            ParagraphStyle(
                "TitleStyle",
                parent=styles["Heading1"],
                fontSize=13,
                textColor=colors.HexColor("#1e3a8a"),
                spaceAfter=4,
            ),
        )
    )
    story.append(Paragraph(date_text, styles["Normal"]))
    story.append(Spacer(1, 10))

    x_labels = data_frame[date_col].dt.strftime("%d.%m.%Y").tolist()

    # Grafic Glicemie PDF
    if (
        include_glic
        and col_glic
        and col_glic in data_frame.columns
        and not data_frame[col_glic].isna().all()
    ):
      y_g = pd.to_numeric(data_frame[col_glic], errors="coerce").fillna(0)
      img_g = generate_pdf_chart(
          x_labels, y_g, "Evolutie Glicemie (mg/dL)", "mg/dL", "#0284c7"
      )
      story.append(Image(img_g, width=500, height=150))
      story.append(Spacer(1, 8))

    # Grafic Tensiune PDF
    if (
        include_ta
        and col_sis
        and col_sis in data_frame.columns
        and col_dia
        and col_dia in data_frame.columns
    ):
      plt.figure(figsize=(7.5, 2.2))
      y_s = pd.to_numeric(data_frame[col_sis], errors="coerce").fillna(0)
      y_d = pd.to_numeric(data_frame[col_dia], errors="coerce").fillna(0)
      plt.plot(
          x_labels,
          y_s,
          marker="o",
          color="#ef4444",
          linewidth=2.2,
          label="Sistol.",
      )
      plt.plot(
          x_labels,
          y_d,
          marker="s",
          color="#f59e0b",
          linewidth=2.2,
          label="Diastol.",
      )
      for xi, ys, yd in zip(x_labels, y_s, y_d):
        if ys > 0:
          plt.annotate(
              str(int(ys)),
              (xi, ys),
              textcoords="offset points",
              xytext=(0, 6),
              ha="center",
              fontsize=7.5,
              fontweight="bold",
              bbox=dict(
                  boxstyle="round,pad=0.2",
                  fc="white",
                  ec="#ef4444",
                  alpha=0.85,
              ),
          )
        if yd > 0:
          plt.annotate(
              str(int(yd)),
              (xi, yd),
              textcoords="offset points",
              xytext=(0, -12),
              ha="center",
              fontsize=7.5,
              fontweight="bold",
              bbox=dict(
                  boxstyle="round,pad=0.2",
                  fc="white",
                  ec="#f59e0b",
                  alpha=0.85,
              ),
          )
      plt.title(
          "Evolutie Tensiune Arteriala (mmHg)",
          fontsize=10,
          fontweight="bold",
          color="#1e3a8a",
          pad=12,
      )
      plt.ylabel("mmHg", fontsize=9, fontweight="bold")
      plt.xticks(rotation=20, fontsize=8)
      plt.yticks(fontsize=8)
      plt.legend(loc="upper left", fontsize=8)
      plt.grid(True, linestyle=":", alpha=0.6)
      plt.tight_layout()

      img_ta_buf = io.BytesIO()
      plt.savefig(img_ta_buf, format="png", dpi=200)
      plt.close()
      img_ta_buf.seek(0)

      story.append(Image(img_ta_buf, width=500, height=150))
      story.append(Spacer(1, 8))

    # Grafic Puls PDF
    if (
        include_puls
        and col_puls
        and col_puls in data_frame.columns
        and not data_frame[col_puls].isna().all()
    ):
      y_p = pd.to_numeric(data_frame[col_puls], errors="coerce").fillna(0)
      img_p = generate_pdf_chart(
          x_labels, y_p, "Evolutie Puls (bpm)", "bpm", "#10b981"
      )
      story.append(Image(img_p, width=500, height=150))
      story.append(Spacer(1, 8))

    # Tabel Centralizator cu Culori în PDF
    if include_tables and not data_frame.empty:
      story.append(Spacer(1, 6))
      story.append(Paragraph("<b>Tabel Centralizator Date</b>", styles["Heading2"]))
      story.append(Spacer(1, 4))

      df_pdf = data_frame.copy()
      df_pdf[date_col] = df_pdf[date_col].dt.strftime("%d.%m.%Y")

      if col_glic in df_pdf.columns:
        df_pdf["St. Glicemie"] = df_pdf[col_glic].apply(evaluate_glic)
        df_pdf[col_glic] = format_table_column(df_pdf[col_glic])
      if col_sis in df_pdf.columns and col_dia in df_pdf.columns:
        df_pdf["St. Tensiune"] = df_pdf.apply(
            lambda r: evaluate_ta(r[col_sis], r[col_dia]), axis=1
        )
        df_pdf[col_sis] = format_table_column(df_pdf[col_sis])
        df_pdf[col_dia] = format_table_column(df_pdf[col_dia])
      if col_puls in df_pdf.columns:
        df_pdf["St. Puls"] = df_pdf[col_puls].apply(evaluate_puls)
        df_pdf[col_puls] = format_table_column(df_pdf[col_puls])

      clean_cols = [remove_diacritics(c) for c in df_pdf.columns]
      table_data = [clean_cols]

      t_style = [
          ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
          ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
          ("ALIGN", (0, 0), (-1, -1), "CENTER"),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
          ("FONTSIZE", (0, 0), (-1, -1), 6.5),
          ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
      ]

      for r_idx, (_, row) in enumerate(df_pdf.iterrows(), start=1):
        clean_row = [remove_diacritics(str(v)) for v in row.values]
        table_data.append(clean_row)

        for c_idx, val in enumerate(row.values):
          val_str = str(val)
          if "🟢" in val_str:
            t_style.append(
                ("BACKGROUND", (c_idx, r_idx), (c_idx, r_idx), colors.HexColor("#d1fae5"))
            )
            t_style.append(
                ("TEXTCOLOR", (c_idx, r_idx), (c_idx, r_idx), colors.HexColor("#065f46"))
            )
          elif "🔴" in val_str:
            t_style.append(
                ("BACKGROUND", (c_idx, r_idx), (c_idx, r_idx), colors.HexColor("#fee2e2"))
            )
            t_style.append(
                ("TEXTCOLOR", (c_idx, r_idx), (c_idx, r_idx), colors.HexColor("#991b1b"))
            )

      t = Table(table_data)
      t.setStyle(TableStyle(t_style))
      story.append(t)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

  if st.button("🚀 Generează și Descarcă Raportul PDF", type="primary"):
    pdf_bytes = make_pdf_report(
        df, opt_glic, opt_ta, opt_puls, opt_tabele
    )
    st.download_button(
        label="📥 Descarcă Fișierul PDF",
        data=pdf_bytes,
        file_name=f"Raport_Medical_Personalizat_{date.today()}.pdf",
        mime="application/pdf",
    )

# ----------------- TAB: SETĂRI -----------------
with tab_dict["⚙️ Setări"]:
  st.markdown("### ⚙️ Setări & Drepturi Acces")
  s1, s2 = st.columns(2)

  with s1:
    if is_admin:
      with st.container(border=True):
        st.markdown("#### ➕ Adaugă Utilizator Nou")
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
        st.markdown("#### 👥 Gestionare Utilizatori")
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

        if st.button("💾 Salvează Modificările"):
          st.session_state.users[target_user]["role"] = updated_role
          if updated_pass:
            st.session_state.users[target_user]["pass"] = updated_pass
          st.success(f"Detaliile pentru {target_user} au fost actualizate!")
    else:
      with st.container(border=True):
        st.markdown("#### 🔒 Schimbare Parolă Curentă")
        st.info(f"Conectat ca: **{st.session_state.user}** ({current_role})")
        own_pass = st.text_input("Parolă Nouă", type="password")
        if st.button("💾 Schimbă Parola Mea"):
          if own_pass:
            st.session_state.users[st.session_state.user]["pass"] = own_pass
            st.success("Parola ta a fost actualizată!")

  with s2:
    with st.container(border=True):
      st.markdown("#### 🎯 Valori Țintă Medicale")
      st.session_state.settings["target_glic_min"] = st.number_input(
          "Glicemie Minimă Țintă (mg/dL)",
          value=st.session_state.settings["target_glic_min"],
          disabled=not is_admin,
      )
      st.session_state.settings["target_glic_max"] = st.number_input(
          "Glicemie Maximă Țintă (mg/dL)",
          value=st.session_state.settings["target_glic_max"],
          disabled=not is_admin,
      )
      st.session_state.settings["target_ta_sis"] = st.number_input(
          "Tensiune Sistolică Max Țintă",
          value=st.session_state.settings["target_ta_sis"],
          disabled=not is_admin,
      )
      st.session_state.settings["target_ta_dia"] = st.number_input(
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
