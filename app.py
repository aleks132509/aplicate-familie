import io
import re
from datetime import date, datetime
import numpy as np
import pandas as pd
import plotly.express as px
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import streamlit as st

# ==========================================
# CONFIGURARE UTILIZATORI ȘI PAROLE
# (Modifică utilizatorii și parolele aici)
# ==========================================
USERS = {"tata": "parola123", "mama": "parola456", "copil": "parola789"}

# ==========================================
# LINK GOOGLE SHEET (Ascuns din interfață)
# ==========================================
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRs6o_ryWI3jCSZ_EpNyv6lDvQakwdEb0RoeuhXXXCdv9lzwCkkEXMorkk2W3ZBvg/pub?output=csv"

# Setare pagină
st.set_page_config(
    page_title="Monitorizare Sănătate - Linie de familie",
    layout="wide",
    page_icon="🩺",
)

# Autentificare
if "logged_in" not in st.session_state:
  st.session_state.logged_in = False

if not st.session_state.logged_in:
  st.title("🔒 Autentificare Registru Sănătate")
  st.markdown("Introduceți numele de utilizator și parola setată pentru familie.")

  col1, col2 = st.columns([1, 2])
  with col1:
    username = st.text_input("Utilizator")
    password = st.text_input("Parolă", type="password")
    if st.button("🔑 Conectare", type="primary"):
      if USERS.get(username) == password:
        st.session_state.logged_in = True
        st.session_state.user = username
        st.rerun()
      else:
        st.error("Utilizator sau parolă incorectă!")
  st.stop()

# Sidebar (fără link-ul Google Sheet)
st.sidebar.title(f"👤 Utilizator: {st.session_state.user.capitalize()}")
if st.sidebar.button("🚪 Deconectare"):
  st.session_state.logged_in = False
  st.rerun()


# Funcție procesare URL Google Sheet
def fix_google_sheet_url(url):
  if not url:
    return url
  url = url.strip()
  if "output=csv" in url or "export?format=csv" in url:
    return url
  match = re.search(r"/d/([a-zA-Z0-9-_]+)", url)
  if match and match.group(1) != "e":
    sheet_id = match.group(1)
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
  return url


# Titlu Principal
st.title("🩺 Registru Personal de Sănătate")
st.markdown(
    "Monitorizare Glicemie, Tensiune Arterială, Medicamente și Programări"
    " Medicale"
)

# Tabs
tab_jurnal, tab_add, tab_med, tab_prog, tab_pdf = st.tabs([
    "📊 Jurnal & Grafice",
    "➕ Adaugă Măsurătoare",
    "💊 Medicamente",
    "📅 Programări",
    "📄 Export Raport PDF",
])


@st.cache_data(ttl=30)
def load_data(url):
  if not url:
    return pd.DataFrame()
  csv_url = fix_google_sheet_url(url)
  data = pd.read_csv(csv_url)
  # Curățare nume coloane
  data.columns = [str(c).strip() for c in data.columns]
  return data


try:
  df = load_data(GOOGLE_SHEET_URL)
except Exception as e:
  st.error(
      f"Eroare la conectarea cu Google Sheets: {e}. Verificați dacă link-ul este"
      " publicat ca CSV."
  )
  df = pd.DataFrame()

# ----------------- TAB 1: JURNAL & GRAFICE -----------------
with tab_jurnal:
  if not df.empty:
    st.subheader("📈 Grafice Evoluție")

    # Identificare flexibilă a coloanei de dată
    date_col = next(
        (c for c in df.columns if "dat" in c.lower() or "date" in c.lower()),
        df.columns[0],
    )

    col_g1, col_g2 = st.columns(2)

    with col_g1:
      st.markdown("##### 🩸 Evoluție Glicemie (mg/dL)")
      cols_glic = [c for c in df.columns if "glic" in c.lower()]
      if not cols_glic and len(df.columns) >= 4:
        cols_glic = df.columns[2:4].tolist()

      if cols_glic:
        fig_glic = px.line(
            df,
            x=date_col,
            y=cols_glic,
            markers=True,
            title="Glicemie în Timp",
        )
        fig_glic.add_hrect(
            y0=70,
            y1=100,
            line_width=0,
            fillcolor="green",
            opacity=0.1,
            annotation_text="Ideal à jeun",
        )
        fig_glic.add_hrect(
            y0=100,
            y1=125,
            line_width=0,
            fillcolor="orange",
            opacity=0.1,
            annotation_text="Atenție",
        )
        st.plotly_chart(fig_glic, use_container_width=True)
      else:
        st.info("Nu s-au găsit coloane specifice pentru glicemie.")

    with col_g2:
      st.markdown("##### 🫀 Evoluție Tensiune Arterială (mmHg)")
      cols_ta = [
          c
          for c in df.columns
          if "sist" in c.lower()
          or "diast" in c.lower()
          or "tens" in c.lower()
          or "ta" in c.lower()
      ]
      if not cols_ta and len(df.columns) >= 6:
        cols_ta = df.columns[4:6].tolist()

      if cols_ta:
        fig_ta = px.line(
            df,
            x=date_col,
            y=cols_ta,
            markers=True,
            title="Tensiune Arterială",
        )
        fig_ta.add_hrect(
            y0=90,
            y1=120,
            line_width=0,
            fillcolor="green",
            opacity=0.1,
            annotation_text="Sistolică Optimă",
        )
        st.plotly_chart(fig_ta, use_container_width=True)
      else:
        st.info("Nu s-au găsit coloane specifice pentru tensiune arterială.")

    st.markdown("---")
    st.subheader("📋 Istoric Date Măsurate")
    st.dataframe(df, use_container_width=True)
  else:
    st.warning(
        "Nu există date de afișat sau tabela Google Sheet este goală /"
        " inaccesibilă."
    )

# ----------------- TAB 2: FORMULAR DE ADAUGARE -----------------
with tab_add:
  st.subheader("📝 Completează o Măsurătoare Nouă")
  with st.form("form_masuratoare"):
    c_d1, c_d2 = st.columns(2)
    with c_d1:
      data_m = st.date_input("📅 Data măsurătorii", value=date.today())
    with c_d2:
      moment_m = st.selectbox("🌅 / 🌆 Momentul zilei", ["Dimineața", "Seara"])

    st.markdown("---")
    st.markdown("##### 🩸 Glicemie (mg/dL)")
    cg1, cg2 = st.columns(2)
    with cg1:
      glic_inainte = st.number_input(
          "Înainte de masă", min_value=0, max_value=400, value=0
      )
    with cg2:
      glic_dupa = st.number_input(
          "După masă", min_value=0, max_value=400, value=0
      )

    st.markdown("---")
    st.markdown("##### 🫀 Tensiune Arterială (mmHg) & Puls")
    ct1, ct2, ct3 = st.columns(3)
    with ct1:
      ta_sis_in = st.number_input(
          "Sistolică (mare) - Înainte", min_value=0, max_value=250, value=0
      )
      ta_sis_dup = st.number_input(
          "Sistolică (mare) - După", min_value=0, max_value=250, value=0
      )
    with ct2:
      ta_dia_in = st.number_input(
          "Diastolică (mică) - Înainte", min_value=0, max_value=150, value=0
      )
      ta_dia_dup = st.number_input(
          "Diastolică (mică) - După", min_value=0, max_value=150, value=0
      )
    with ct3:
      puls_v = st.number_input("Puls (bpm)", min_value=0, max_value=200, value=0)

    st.markdown("---")
    notite_v = st.text_area(
        "✍️ Notițe / Simptome",
        placeholder="Ex: Mâncat târziu, amețeală ușoară...",
    )

    btn_submit = st.form_submit_button(
        "💾 Salvează Măsurătoarea", type="primary"
    )
    if btn_submit:
      st.success(f"Măsurătoarea pentru {data_m} ({moment_m}) a fost salvată!")

# ----------------- TAB 3: MEDICAMENTE -----------------
with tab_med:
  st.subheader("💊 Schema de Tratament & Medicamente")
  meds_data = pd.DataFrame([
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
  st.dataframe(meds_data, use_container_width=True)

# ----------------- TAB 4: PROGRAMĂRI -----------------
with tab_prog:
  st.subheader("📅 Programări Medicale & Analize")
  prog_data = pd.DataFrame([
      {
          "Dată": "2026-12-02",
          "Tip": "Analize de laborator",
          "Clinică / Medic": "Regina Maria",
          "Observații": "Repetare analize Diabet",
          "Efectuat": "Nu",
      },
      {
          "Dată": "2026-12-09",
          "Tip": "Consult Diabet",
          "Clinică / Medic": "Dr. Clenciu Craiova",
          "Observații": "Rețetă 3 luni",
          "Efectuat": "Nu",
      },
  ])
  st.dataframe(prog_data, use_container_width=True)

# ----------------- TAB 5: EXPORT PDF REAL -----------------
with tab_pdf:
  st.subheader("📄 Generare Raport Medical PDF")
  st.markdown(
      "Apăsați butonul de mai jos pentru a genera un fișier **PDF oficial** cu"
      " istoricul măsurătorilor."
  )

  def generate_pdf_report(df_data):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
    )
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.HexColor("#0f172a"),
    )
    section_style = ParagraphStyle(
        "SectionStyle",
        parent=styles["Heading2"],
        fontSize=12,
        textColor=colors.HexColor("#1e3a8a"),
        spaceBefore=12,
        spaceAfter=8,
    )

    story.append(
        Paragraph("<b>RAPORT MEDICAL MONITORIZARE SĂNĂTATE</b>", title_style)
    )
    story.append(
        Paragraph(
            f"Data generării: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 15))

    story.append(
        Paragraph("<b>1. Istoric Măsurători Recent</b>", section_style)
    )

    if not df_data.empty:
      headers = list(df_data.columns[:7])
      hist_table_data = [headers]

      for _, r in df_data.head(15).iterrows():
        row_vals = [str(r.get(c, "-")) for c in headers]
        hist_table_data.append(row_vals)

      t_hist = Table(hist_table_data)
      t_hist.setStyle(
          TableStyle([
              ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
              ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
              ("ALIGN", (0, 0), (-1, -1), "CENTER"),
              ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
              ("FONTSIZE", (0, 0), (-1, -1), 8),
              ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
          ])
      )
      story.append(t_hist)
    else:
      story.append(
          Paragraph("Nu există date disponibile.", styles["Normal"])
      )

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

  if st.button("🚀 Generează Fișier PDF", type="primary"):
    pdf_bytes = generate_pdf_report(df)
    st.success("✅ Fișierul PDF a fost creat cu succes!")
    st.download_button(
        label="📥 Descarcă Raportul PDF",
        data=pdf_bytes,
        file_name=f"Raport_Sanatate_{date.today().strftime('%Y_%m_%d')}.pdf",
        mime="application/pdf",
    )
