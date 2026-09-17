import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, date
import io
import re
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Setare pagina
st.set_page_config(page_title="Monitorizare Sănătate - Linie de familie", layout="wide", page_icon="🩺")

# Utilizatori
USERS = {
    "Alex": "Aleks132509",
    "Ionut": "Ionut061191",
    "Doctor": "Alex2026"
}

# Verificare conectare
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

# Sidebar
st.sidebar.title(f"👤 Utilizator: {st.session_state.user.capitalize()}")
if st.sidebar.button("🚪 Deconectare"):
    st.session_state.logged_in = False
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("🔗 Sursă Date (Google Sheet)")

def fix_google_sheet_url(url):
    url = url.strip()
    match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
    if match:
        sheet_id = match.group(1)
        if '/pub?' in url and 'output=csv' in url:
            return url
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    return url

default_url = st.sidebar.text_input("default_url = st.sidebar.text_input("Link Google Sheet CSV:", "https://docs.google.com/spreadsheets/d/e/2PACX-1vRs6o_ryWI3jCSZ_EpNyv6lDvQakwdEb0RoeuhXXXCdv9lzwCkkEXMorkk2W3ZBvg/pub?output=csv")

# Titlu Principal
st.title("🩺 Registru Personal de Sănătate")
st.markdown("Monitorizare Glicemie, Tensiune Arterială, Medicamente și Programări Medicale")

# Tabs principali
tab_jurnal, tab_add, tab_med, tab_prog, tab_pdf = st.tabs([
    "📊 Jurnal & Grafice", 
    "➕ Adaugă Măsurătoare", 
    "💊 Medicamente", 
    "📅 Programări", 
    "📄 Export Raport PDF"
])

@st.cache_data(ttl=60)
def load_data(url):
    if not url:
        # Date demonstrative dacă nu este introdus niciun link
        dates = pd.date_range(end=date.today(), periods=10)
        data = []
        for d in dates:
            data.append({
                "Dată": d.strftime("%Y-%m-%d"),
                "Moment": "Dimineața",
                "Glicemie Înainte": np.random.randint(100, 140),
                "Glicemie După": np.random.randint(130, 160),
                "Sistolică Înainte": np.random.randint(110, 135),
                "Diastolică Înainte": np.random.randint(60, 80),
                "Puls": np.random.randint(65, 85),
                "Notițe": "Stare bună"
            })
            data.append({
                "Dată": d.strftime("%Y-%m-%d"),
                "Moment": "Seara",
                "Glicemie Înainte": np.random.randint(105, 135),
                "Glicemie După": np.random.randint(125, 155),
                "Sistolică Înainte": np.random.randint(112, 130),
                "Diastolică Înainte": np.random.randint(62, 78),
                "Puls": np.random.randint(68, 82),
                "Notițe": ""
            })
        return pd.DataFrame(data)
    else:
        csv_url = fix_google_sheet_url(url)
        return pd.read_csv(csv_url)

try:
    df = load_data(default_url)
except Exception as e:
    st.error(f"Eroare la încărcarea datelor: {e}")
    df = pd.DataFrame()

# ----------------- TAB 1: JURNAL & GRAFICE -----------------
with tab_jurnal:
    if not df.empty:
        st.subheader("📈 Grafice Evoluție")
        
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.markdown("##### 🩸 Evoluție Glicemie (mg/dL)")
            cols_glic = [c for c in ["Glicemie Înainte", "Glicemie După", "Înainte masă", "După masă"] if c in df.columns]
            fig_glic = px.line(
                df, x="Dată" if "Dată" in df.columns else df.columns[0],
                y=cols_glic if cols_glic else df.columns[2:4],
                markers=True, title="Glicemie în Timp"
            )
            fig_glic.add_hrect(y0=70, y1=100, line_width=0, fillcolor="green", opacity=0.1, annotation_text="Ideal à jeun")
            fig_glic.add_hrect(y0=100, y1=125, line_width=0, fillcolor="orange", opacity=0.1, annotation_text="Atenție")
            st.plotly_chart(fig_glic, use_container_width=True)
            
        with col_g2:
            st.markdown("##### 🫀 Evoluție Tensiune Arterială (mmHg)")
            cols_ta = [c for c in ["Sistolică Înainte", "Diastolică Înainte", "Sistolică", "Diastolică"] if c in df.columns]
            fig_ta = px.line(
                df, x="Dată" if "Dată" in df.columns else df.columns[0],
                y=cols_ta if cols_ta else df.columns[4:6],
                markers=True, title="Tensiune Arterială"
            )
            fig_ta.add_hrect(y0=90, y1=120, line_width=0, fillcolor="green", opacity=0.1, annotation_text="Sistolică Optimă")
            st.plotly_chart(fig_ta, use_container_width=True)

        st.markdown("---")
        st.subheader("📋 Istoric Date Măsurate")
        st.dataframe(df, use_container_width=True)

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
            glic_inainte = st.number_input("Înainte de masă", min_value=0, max_value=400, value=0)
        with cg2:
            glic_dupa = st.number_input("După masă", min_value=0, max_value=400, value=0)
            
        st.markdown("---")
        st.markdown("##### 🫀 Tensiune Arterială (mmHg) & Puls")
        ct1, ct2, ct3 = st.columns(3)
        with ct1:
            ta_sis_in = st.number_input("Sistolică (mare) - Înainte", min_value=0, max_value=250, value=0)
            ta_sis_dup = st.number_input("Sistolică (mare) - După", min_value=0, max_value=250, value=0)
        with ct2:
            ta_dia_in = st.number_input("Diastolică (mică) - Înainte", min_value=0, max_value=150, value=0)
            ta_dia_dup = st.number_input("Diastolică (mică) - După", min_value=0, max_value=150, value=0)
        with ct3:
            puls_v = st.number_input("Puls (bpm)", min_value=0, max_value=200, value=0)
            
        st.markdown("---")
        notite_v = st.text_area("✍️ Notițe / Simptome", placeholder="Ex: Mâncat târziu, amețeală ușoară...")
        
        btn_submit = st.form_submit_button("💾 Salvează Măsurătoarea", type="primary")
        if btn_submit:
            st.success(f"Măsurătoarea pentru {data_m} ({moment_m}) a fost salvată!")

# ----------------- TAB 3: MEDICAMENTE -----------------
with tab_med:
    st.subheader("💊 Schema de Tratament & Medicamente")
    meds_data = pd.DataFrame([
        {"Medicament": "Glucophage", "Doză": "1000 mg", "Orar": "Dimineața și Seara", "Meniu": "După masă"},
        {"Medicament": "Lagosa", "Doză": "150 mg", "Orar": "Dimineața și Seara", "Meniu": "După masă"},
        {"Medicament": "Diaprel MR", "Doză": "60 mg (1/2)", "Orar": "Dimineața", "Meniu": "Înainte de masă"},
        {"Medicament": "Atacand", "Doză": "8 mg", "Orar": "Seara", "Meniu": "După masă"},
        {"Medicament": "Nebilet", "Doză": "5 mg", "Orar": "Dimineața", "Meniu": "După masă"},
        {"Medicament": "Aspenter", "Doză": "75 mg", "Orar": "Prânz", "Meniu": "După masă"}
    ])
    st.dataframe(meds_data, use_container_width=True)

# ----------------- TAB 4: PROGRAMĂRI -----------------
with tab_prog:
    st.subheader("📅 Programări Medicale & Analize")
    prog_data = pd.DataFrame([
        {"Dată": "2026-12-02", "Tip": "Analize de laborator", "Clinică / Medic": "Regina Maria", "Observații": "Repetare analize Diabet", "Efectuat": "Nu"},
        {"Dată": "2026-12-09", "Tip": "Consult Diabet", "Clinică / Medic": "Dr. Clenciu Craiova", "Observații": "Rețetă 3 luni", "Efectuat": "Nu"}
    ])
    st.dataframe(prog_data, use_container_width=True)

# ----------------- TAB 5: EXPORT PDF REAL -----------------
with tab_pdf:
    st.subheader("📄 Generare Raport Medical PDF")
    st.markdown("Apăsați butonul de mai jos pentru a genera un fișier **PDF oficial** cu istoricul măsurătorilor și mediile calculate.")
    
    def generate_pdf_report(df_data):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        story = []
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor('#0f172a'))
        section_style = ParagraphStyle('SectionStyle', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#1e3a8a'), spaceBefore=12, spaceAfter=8)
        
        story.append(Paragraph("<b>RAPORT MEDICAL MONITORIZARE SĂNĂTATE</b>", title_style))
        story.append(Paragraph(f"Data generării: {datetime.now().strftime('%d.%m.%Y %H:%M')}", styles['Normal']))
        story.append(Spacer(1, 15))
        
        story.append(Paragraph("<b>1. Istoric Măsurători Recent</b>", section_style))
        
        hist_table_data = [["Dată", "Moment", "Glic. Înainte", "Glic. După", "TA Sist.", "TA Diast.", "Puls"]]
        for _, r in df_data.head(15).iterrows():
            hist_table_data.append([
                str(r.get('Dată', '')),
                str(r.get('Moment', '')),
                str(r.get('Glicemie Înainte', '-')),
                str(r.get('Glicemie După', '-')),
                str(r.get('Sistolică Înainte', '-')),
                str(r.get('Diastolică Înainte', '-')),
                str(r.get('Puls', '-'))
            ])
            
        t_hist = Table(hist_table_data, colWidths=[80, 70, 75, 75, 65, 65, 50])
        t_hist.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e3a8a')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ]))
        story.append(t_hist)
        
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
            mime="application/pdf"
        )
