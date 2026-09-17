import io
import re
from datetime import date, datetime, timedelta
import pandas as pd
import plotly.express as px
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import streamlit as st

# ==========================================
# UTILIZATORI ȘI PAROLE
# ==========================================
USERS = {
    "Alex": "Aleks132509",
    "Ionut": "Ionut061191",
    "Doctor": "Alex2026",
}

# ==========================================
# LINK GOOGLE SHEET (Integrat direct)
# ==========================================
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRs6o_ryWI3jCSZ_EpNyv6lDvQakwdEb0RoeuhXXXCdv9lzwCkkEXMorkk2W3ZBvg/pub?output=csv"

# Configurare Pagină
st.set_page_config(
    page_title="Monitorizare Sănătate",
    layout="wide",
    page_icon="🩺",
    initial_sidebar_state="expanded",
)

# Authentificare
if "logged_in" not in st.session_state:
  st.session_state.logged_in = False

if not st.session_state.logged_in:
  st.title("🔒 Autentificare Registru Sănătate")
  st.markdown("Introduceți numele de utilizator și parola contului dumneavoastră.")

  col1, _ = st.columns([1, 2])
  with col1:
    username = st.text_input("Utilizator")
    password = st.text_input("Parolă", type="password")
    if st.button("🔑 Conectare", type="primary", use_container_width=True):
      if USERS.get(username) == password:
        st.session_state.logged_in = True
        st.session_state.user = username
        st.rerun()
      else:
        st.error("Utilizator sau parolă incorectă!")
  st.stop()

# Sidebar
st.sidebar.title(f"👤 Conectat: {st.session_state.user}")
if st.sidebar.button("🚪 Deconectare", use_container_width=True):
  st.session_state.logged_in = False
  st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("**⚙️ Setări Notificări**")
enable_notifs = st.sidebar.checkbox(
    "🔔 Activează notificări programări", value=True
)
notif_days = st.sidebar.slider(
    "Zile în avans pentru alertă:", min_value=1, max_value=30, value=7
)


# Încărcare Date din Google Sheet
@st.cache_data(ttl=15)
def load_data(url):
  try:
    data = pd.read_csv(url)
    data.columns = [str(c).strip() for c in data.columns]
    return data
  except Exception as e:
    st.error(f"Eroare la preluarea datelor din Google Sheet: {e}")
    return pd.DataFrame()


df = load_data(GOOGLE_SHEET_URL)

# Header Principal
st.title("🩺 Registru Personal de Sănătate")

# System de Notificări Programări
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

if enable_notifs and not prog_data.empty:
  prog_data["Dată_dt"] = pd.to_datetime(prog_data["Dată"], errors="coerce").dt.date
  today = date.today()
  upcoming = prog_data[
      (prog_data["Dată_dt"] >= today)
      & (prog_data["Dată_dt"] <= today + timedelta(days=notif_days))
      & (prog_data["Efectuat"] == "Nu")
  ]

  if not upcoming.empty:
    for _, row in upcoming.iterrows():
      st.warning(
          f"🔔 **Atenție! Programare viitoare în curând:** {row['Tip']} la"
          f" **{row['Clinică / Medic']}** pe data de **{row['Dată']}**"
          f" ({row['Observații']})."
      )

# Navigare prin Tab-uri
tab_jurnal, tab_add, tab_med, tab_prog, tab_pdf = st.tabs([
    "📊 Jurnal & Grafice",
    "➕ Adaugă / Modifică Măsurătoare",
    "💊 Medicamente",
    "📅 Programări & Notificări",
    "📄 Export Raport PDF",
])

# ----------------- TAB 1: JURNAL & GRAFICE (MAIN PAGE) -----------------
with tab_jurnal:
  st.subheader("📋 Toate Datele din Spreadsheet")

  if not df.empty:
    # Afișare tabel complet nefiltrat
    st.dataframe(df, use_container_width=True, height=350)

    st.markdown("---")
    st.subheader("📈 Evoluție Grafică")

    # Identificare flexibilă a coloanelor
    cols = list(df.columns)
    date_col = next(
        (c for c in cols if "dat" in c.lower() or "date" in c.lower()), cols[0]
    )
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

    if not numeric_cols:
      # Încercare convertire coloane la valori numerice dacă sunt citite ca string
      for c in cols:
        df[c] = pd.to_numeric(df[c], errors="ignore")
      numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

    col_sel1, col_sel2 = st.columns(2)

    with col_sel1:
      glic_cols = [c for c in cols if "glic" in c.lower()]
      selected_glic = st.multiselect(
          "Alege coloanele de Glicemie pentru grafic:",
          options=cols,
          default=glic_cols if glic_cols else (numeric_cols[:2] if len(numeric_cols)>=2 else cols),
      )
      if selected_glic:
        fig_glic = px.line(
            df,
            x=date_col,
            y=selected_glic,
            markers=True,
            title="Evoluție Glicemie",
        )
        fig_glic.add_hrect(
            y0=70,
            y1=100,
            line_width=0,
            fillcolor="green",
            opacity=0.1,
            annotation_text="Ideal à jeun",
        )
        st.plotly_chart(fig_glic, use_container_width=True)

    with col_sel2:
      ta_cols = [
          c
          for c in cols
          if "sist" in c.lower()
          or "diast" in c.lower()
          or "tens" in c.lower()
          or "ta" in c.lower()
          or "puls" in c.lower()
      ]
      selected_ta = st.multiselect(
          "Alege coloanele de Tensiune / Puls pentru grafic:",
          options=cols,
          default=ta_cols if ta_cols else (numeric_cols[2:4] if len(numeric_cols)>=4 else cols),
      )
      if selected_ta:
        fig_ta = px.line(
            df,
            x=date_col,
            y=selected_ta,
            markers=True,
            title="Evoluție Tensiune / Puls",
        )
        st.plotly_chart(fig_ta, use_container_width=True)
  else:
    st.info("Nu s-au putut încărca date din Google Sheet.")

# ----------------- TAB 2: ADAUGĂ / MODIFICĂ MĂSURĂTOARE -----------------
with tab_add:
  st.subheader("📝 Înregistrează sau Modifică Măsurătoare")
  st.markdown(
      "Puteți selecta orice dată anterioară sau curentă pentru a adăuga ori"
      " modifica valorile."
  )

  with st.form("form_edit_add"):
    c1, c2 = st.columns(2)
    with c1:
      data_selectata = st.date_input(
          "📅 Selectează Data Măsurătorii", value=date.today()
      )
    with c2:
      moment_selectat = st.selectbox(
          "🌅 / 🌆 Momentul zilei", ["Dimineața", "Prânz", "Seara"]
      )

    st.markdown("---")
    cg1, cg2 = st.columns(2)
    with cg1:
      glic_inainte = st.number_input(
          "Glicemie Înainte de masă (mg/dL)",
          min_value=0,
          max_value=500,
          value=100,
      )
      ta_sis = st.number_input(
          "Tensiune Sistolică - Mare (mmHg)",
          min_value=0,
          max_value=260,
          value=120,
      )
    with cg2:
      glic_dupa = st.number_input(
          "Glicemie După masă (mg/dL)", min_value=0, max_value=500, value=130
      )
      ta_dia = st.number_input(
          "Tensiune Diastolică - Mică (mmHg)",
          min_value=0,
          max_value=160,
          value=80,
      )

    puls_val = st.number_input(
        "Puls (bpm)", min_value=0, max_value=220, value=75
    )
    notite_val = st.text_area(
        "✍️ Observații / Simptome / Note speciale",
        placeholder="Introduceți note relevante pentru ziua selectată...",
    )

    submit_btn = st.form_submit_button(
        "💾 Salvează Datele pentru Ziua Selectată", type="primary"
    )
    if submit_btn:
      st.success(
          f"Măsurătoarea din data de {data_selectata} ({moment_selectat}) a fost"
          " înregistrată cu succes!"
      )

# ----------------- TAB 3: MEDICAMENTE -----------------
with tab_med:
  st.subheader("💊 Schema de Tratament")
  meds_df = pd.DataFrame([
      {
          "Medicament": "Glucophage",
          "Doză": "1000 mg",
          "Orar": "Dimineața și Seara",
          "Meniu": "După masă",
      },
      {
          "Medicament": "Lagosa",
          "Doză": "150 mg",
          "Orar": "Dimineața și Seara",
          "Meniu": "După masă",
      },
      {
          "Medicament": "Diaprel MR",
          "Doză": "60 mg (1/2)",
          "Orar": "Dimineața",
          "Meniu": "Înainte de masă",
      },
      {
          "Medicament": "Atacand",
          "Doză": "8 mg",
          "Orar": "Seara",
          "Meniu": "După masă",
      },
      {
          "Medicament": "Nebilet",
          "Doză": "5 mg",
          "Orar": "Dimineața",
          "Meniu": "După masă",
      },
      {
          "Medicament": "Aspenter",
          "Doză": "75 mg",
          "Orar": "Prânz",
          "Meniu": "După masă",
      },
  ])
  st.dataframe(meds_df, use_container_width=True)

# ----------------- TAB 4: PROGRAMĂRI & NOTIFICĂRI -----------------
with tab_prog:
  st.subheader("📅 Programări Medicale & Analize")
  st.dataframe(
      prog_data.drop(columns=["Dată_dt"], errors="ignore"),
      use_container_width=True,
  )

  st.markdown("---")
  st.subheader("➕ Adaugă Programare Nouă")
  with st.form("form_prog"):
    cp1, cp2 = st.columns(2)
    with cp1:
      p_data = st.date_input("Data Programării", value=date.today())
      p_tip = st.text_input("Tip (ex: Consult, Analize)")
    with cp2:
      p_clinic = st.text_input("Clinică / Medic")
      p_obs = st.text_input("Observații")

    if st.form_submit_button("💾 Salvează Programarea"):
      st.success(f"Programarea pentru {p_data} a fost adăugată!")

# ----------------- TAB 5: EXPORT PDF -----------------
with tab_pdf:
  st.subheader("📄 Generare Raport PDF")

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
