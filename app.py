import os
from datetime import date, datetime
import pandas as pd
import plotly.graph_objects as st_go
import streamlit as st

# Importuri ReportLab pentru PDF
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# --- CONFIGURARE PAGINĂ ---
st.set_page_config(
    page_title="HealthTrack Pro",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- STILIZARE CSS ---
st.markdown("""
    <style>
    .metric-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .metric-label {
        font-size: 13px;
        color: #94a3b8;
        font-weight: 600;
        margin-bottom: 5px;
    }
    .metric-value {
        font-size: 22px;
        color: #f8fafc;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# --- FIȘIERE PERSISTENTE ---
HEALTH_FILE = "health_data.csv"
MEDS_FILE = "meds_data.csv"
APPT_FILE = "appointments_data.csv"
APPLE_WATCH_FILE = "apple_watch_data.csv"

# --- FUNCȚII AUXILIARE ---
def parse_flexible_date(series):
    return pd.to_datetime(series, format="%d.%m.%Y", errors="coerce").fillna(
        pd.to_datetime(series, format="%Y-%m-%d", errors="coerce")
    )

def clean_obs(text):
    if not text:
        return ""
    return str(text).replace(";", ",").replace("\n", " ").strip()

def trigger_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

# --- INIȚIALIZARE DATE ---
def get_initial_health():
    if os.path.exists(HEALTH_FILE):
        try:
            df = pd.read_csv(HEALTH_FILE)
            if not df.empty: return df
        except: pass
    df_init = pd.DataFrame([{
        "Dată": "20.09.2026", "Tensiune_Sistolica": 120, "Tensiune_Diastolica": 80,
        "Puls": 72, "Glicemie": 95, "Greutate": 75.0, "Observații": "Stare generală bună"
    }])
    df_init.to_csv(HEALTH_FILE, index=False)
    return df_init

def get_initial_meds():
    if os.path.exists(MEDS_FILE):
        try:
            df = pd.read_csv(MEDS_FILE)
            if not df.empty: return df
        except: pass
    df_init = pd.DataFrame([{
        "Medicament": "Vitamina C", "Doza": "1000mg", "Frecvență": "1 pe zi", "Ora": "08:00", "Status": "Activ"
    }])
    df_init.to_csv(MEDS_FILE, index=False)
    return df_init

def get_initial_appointments():
    if os.path.exists(APPT_FILE):
        try:
            df = pd.read_csv(APPT_FILE)
            if not df.empty: return df
        except: pass
    df_init = pd.DataFrame([{
        "Data": "28.09.2026", "Ora": "10:00", "Medic": "Dr. Ionescu", "Specialitate": "Cardiologie", "Locație": "Clinica MedSan"
    }])
    df_init.to_csv(APPT_FILE, index=False)
    return df_init

def get_initial_apple_watch():
    if os.path.exists(APPLE_WATCH_FILE):
        try:
            df = pd.read_csv(APPLE_WATCH_FILE)
            if not df.empty: return df
        except: pass
    df_init = pd.DataFrame([{
        "Dată": "20.09.2026", "Puls_Min": 58, "Puls_Max": 115, "PulsMediu": 74,
        "Oxigen_Sange": 98, "Apnee_Detectata": "Fără semne", "Pasi": 8420, "Observații": "Somn odihnitor"
    }])
    df_init.to_csv(APPLE_WATCH_FILE, index=False)
    return df_init

if "health_df" not in st.session_state: st.session_state.health_df = get_initial_health()
if "meds_df" not in st.session_state: st.session_state.meds_df = get_initial_meds()
if "appt_df" not in st.session_state: st.session_state.appt_df = get_initial_appointments()
if "apple_watch_df" not in st.session_state: st.session_state.apple_watch_df = get_initial_apple_watch()

# --- SIDEBAR & AUTENTIFICARE ---
st.sidebar.title("🩺 HealthTrack Pro")
auth_mode = st.sidebar.selectbox("Mod utilizare", ["Pacient", "Administrator / Medic"])
is_admin = (auth_mode == "Administrator / Medic")

if is_admin:
    st.sidebar.success("Mod Administrator activ (Acces complet)")
else:
    st.sidebar.info("Mod Vizualizare / Pacient")

st.sidebar.markdown("---")
st.sidebar.markdown("### 📌 Navigare rapidă")

# --- CONSTRUIRE TAB-URI ---
tab_titles = ["📊 Jurnal & Grafice"]
if is_admin: tab_titles.append("➕ Adaugă / Suprascrie")
tab_titles.append("💊 Tratament")
if is_admin: tab_titles.append("📅 Programări")
tab_titles.extend(["⌚ Apple Watch", "📄 Raport PDF", "⚙️ Setări"])

tabs = st.tabs(tab_titles)
tab_dict = {title: tabs[i] for i, title in enumerate(tab_titles)}

# ----------------- TAB: JURNAL & GRAFICE -----------------
with tab_dict["📊 Jurnal & Grafice"]:
    st.markdown("### 📊 Istoric Măsurători Biometrice")
    df = st.session_state.health_df.copy()
    if not df.empty:
        df["Dată_dt"] = parse_flexible_date(df["Dată"])
        df = df.sort_values(by="Dată_dt", ascending=False).drop(columns=["Dată_dt"])
        
        latest = df.iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">❤️ TENSIUNE (ULTIMĂ)</div><div class="metric-value">{int(latest.get("Tensiune_Sistolica", 0))}/{int(latest.get("Tensiune_Diastolica", 0))}</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">💓 PULS</div><div class="metric-value">{int(latest.get("Puls", 0))} bpm</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="metric-card"><div class="metric-label">🩸 GLICEMIE</div><div class="metric-value">{int(latest.get("Glicemie", 0))} mg/dl</div></div>', unsafe_allow_html=True)
        with c4:
            st.markdown(f'<div class="metric-card"><div class="metric-label">⚖️ GREUTATE</div><div class="metric-value">{float(latest.get("Greutate", 0))} kg</div></div>', unsafe_allow_html=True)
            
        st.markdown("<br>", unsafe_allow_html=True)
        st.dataframe(df, use_container_width=True, hide_index=True)

# ----------------- TAB: ADAUGĂ / SUPRASCRIE -----------------
if is_admin and "➕ Adaugă / Suprascrie" in tab_dict:
    with tab_dict["➕ Adaugă / Suprascrie"]:
        st.markdown("### ➕ Adăugare sau Actualizare Înregistrare")
        with st.form("form_add_health"):
            f_date = st.date_input("Data Măsurătorii", value=date.today())
            col_a, col_b = st.columns(2)
            with col_a:
                sys = st.number_input("Tensiune Sistolică (mmHg)", 70, 250, 120)
                puls = st.number_input("Puls (bpm)", 40, 200, 72)
                greutate = st.number_input("Greutate (kg)", 30.0, 250.0, 75.0, step=0.1)
            with col_b:
                dia = st.number_input("Tensiune Diastolică (mmHg)", 40, 150, 80)
                glic = st.number_input("Glicemie (mg/dl)", 50, 400, 95)
            obs = st.text_input("Observații")
            
            if st.form_submit_button("💾 Salvează Datele", type="primary"):
                d_str = f_date.strftime("%d.%m.%Y")
                new_entry = {
                    "Dată": d_str, "Tensiune_Sistolica": sys, "Tensiune_Diastolica": dia,
                    "Puls": puls, "Glicemie": glic, "Greutate": greutate, "Observații": clean_obs(obs)
                }
                cur_df = st.session_state.health_df
                cur_df = cur_df[cur_df["Dată"] != d_str]
                st.session_state.health_df = pd.concat([cur_df, pd.DataFrame([new_entry])], ignore_index=True)
                st.session_state.health_df.to_csv(HEALTH_FILE, index=False)
                st.success("Înregistrarea a fost salvată!")
                trigger_rerun()

# ----------------- TAB: TRATAMENT -----------------
with tab_dict["💊 Tratament"]:
    st.markdown("### 💊 Schema de Tratament Curentă")
    st.dataframe(st.session_state.meds_df, use_container_width=True, hide_index=True)
    if is_admin:
        with st.form("form_meds"):
            m_nume = st.text_input("Nume Medicament")
            m_doza = st.text_input("Doza (ex: 50mg)")
            m_frec = st.text_input("Frecvență")
            m_ora = st.text_input("Ora administrării")
            if st.form_submit_button("Adaugă Medicament"):
                new_m = pd.DataFrame([{"Medicament": m_nume, "Doza": m_doza, "Frecvență": m_frec, "Ora": m_ora, "Status": "Activ"}])
                st.session_state.meds_df = pd.concat([st.session_state.meds_df, new_m], ignore_index=True)
                st.session_state.meds_df.to_csv(MEDS_FILE, index=False)
                st.success("Medicament adăugat!")
                trigger_rerun()

# ----------------- TAB: PROGRAMĂRI -----------------
if is_admin and "📅 Programări" in tab_dict:
    with tab_dict["📅 Programări"]:
        st.markdown("### 📅 Programări Medicale Viitoare")
        st.dataframe(st.session_state.appt_df, use_container_width=True, hide_index=True)

# ----------------- TAB: APPLE WATCH -----------------
with tab_dict["⌚ Apple Watch"]:
    st.markdown("### ⌚ Monitorizare & Telemetrie Apple Watch")
    st.caption("Date zilnice preluate automat sau introduse manual privind pulsul (min/max/mediu), saturația oxigenului, apneea în somn și pașii.")

    aw_df = st.session_state.apple_watch_df.copy()
    if not aw_df.empty:
        aw_df["Dată_dt"] = parse_flexible_date(aw_df["Dată"])
        aw_df = aw_df.sort_values(by="Dată_dt", ascending=False).drop(columns=["Dată_dt"])

        latest_aw = aw_df.iloc[0]
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">💓 PULS MEDIU</div><div class="metric-value">{int(latest_aw.get("PulsMediu", 0))} bpm</div></div>', unsafe_allow_html=True)
        with k2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">🩸 OXIGEN (SpO2)</div><div class="metric-value">{int(latest_aw.get("Oxigen_Sange", 0))}%</div></div>', unsafe_allow_html=True)
        with k3:
            st.markdown(f'<div class="metric-card"><div class="metric-label">🌙 APNEE / SOMN</div><div class="metric-value" style="font-size:15px;">{latest_aw.get("Apnee_Detectata", "-")}</div></div>', unsafe_allow_html=True)
        with k4:
            st.markdown(f'<div class="metric-card"><div class="metric-label">🚶‍♂️ PAȘI ZILNICI</div><div class="metric-value">{int(latest_aw.get("Pasi", 0)):,}</div></div>', unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        
        # Grafic interactiv Puls
        fig_aw = st_go.Figure()
        fig_aw.add_trace(st_go.Scatter(x=aw_df["Dată"], y=aw_df["Puls_Max"], mode="lines+markers", name="Puls Maxim", line=dict(color="#ef4444")))
        fig_aw.add_trace(st_go.Scatter(x=aw_df["Dată"], y=aw_df["PulsMediu"], mode="lines+markers", name="Puls Mediu", line=dict(color="#38bdf8")))
        fig_aw.add_trace(st_go.Scatter(x=aw_df["Dată"], y=aw_df["Puls_Min"], mode="lines+markers", name="Puls Minim", line=dict(color="#10b981")))
        fig_aw.update_layout(template="plotly_dark", title="Evoluție Puls Zilnic (Min / Mediu / Max)", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_aw, use_container_width=True)

        st.markdown("#### 📋 Istoric Detaliat Apple Watch")
        st.dataframe(aw_df, use_container_width=True, hide_index=True)

    if is_admin:
        st.markdown("---")
        st.markdown("#### ➕ Adaugă / Actualizează Valori Apple Watch")
        with st.form("form_apple_watch"):
            aw_date = st.date_input("Data Măsurătorii", value=date.today(), key="aw_date_in")
            c_aw1, c_aw2, c_aw3 = st.columns(3)
            with c_aw1:
                p_min = st.number_input("Puls Minim (bpm)", 30, 150, 60)
                p_max = st.number_input("Puls Maxim (bpm)", 50, 220, 120)
            with c_aw2:
                p_med = st.number_input("Puls Mediu (bpm)", 40, 180, 75)
                spo2 = st.number_input("Oxigen Sânge - SpO2 (%)", 70, 100, 98)
            with c_aw3:
                pasi = st.number_input("Număr Pași", 0, 100000, 7500)
                apnee_st = st.selectbox("Status Apnee / Respirație", ["Fără semne", "Risc scăzut", "Risc moderat/ridicat"])
            
            obs_aw = st.text_input("Observații Apple Watch")

            if st.form_submit_button("💾 Salvează Datele Apple Watch", type="primary"):
                date_str = aw_date.strftime("%d.%m.%Y")
                new_row = {
                    "Dată": date_str, "Puls_Min": p_min, "Puls_Max": p_max,
                    "PulsMediu": p_med, "Oxigen_Sange": spo2, "Apnee_Detectata": apnee_st,
                    "Pasi": pasi, "Observații": clean_obs(obs_aw)
                }
                df_cur = st.session_state.apple_watch_df
                df_cur = df_cur[df_cur["Dată"] != date_str]
                st.session_state.apple_watch_df = pd.concat([df_cur, pd.DataFrame([new_row])], ignore_index=True)
                st.session_state.apple_watch_df.to_csv(APPLE_WATCH_FILE, index=False)
                st.success("Datele Apple Watch au fost salvate!")
                trigger_rerun()

# ----------------- TAB: RAPORT PDF -----------------
with tab_dict["📄 Raport PDF"]:
    st.markdown("### 📄 Generare Raport Medical PDF")
    st.caption("Descarcă un raport complet incluzând biometria clasică și datele Apple Watch pentru medicul curant.")

    if st.button("🖨️ Generează Fișierul PDF", type="primary"):
        pdf_filename = "Raport_Medical_HealthTrack.pdf"
        doc = SimpleDocTemplate(pdf_filename, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        styles = getSampleStyleSheet()
        story = []

        # Titlu raport
        story.append(Paragraph("<b>Raport Medical Consolidat - HealthTrack Pro</b>", styles["Title"]))
        story.append(Spacer(1, 10))
        story.append(Paragraph(f"Generat la data: {datetime.now().strftime('%d.%m.%Y %H:%M')}", styles["Normal"]))
        story.append(Spacer(1, 15))

        # Tabel Biometrie Principală
        story.append(Paragraph("<b>Istoric Biometric Principal</b>", styles["Heading2"]))
        df_bio = st.session_state.health_df
        if not df_bio.empty:
            bio_data = [["Data", "Tensiune", "Puls", "Glicemie", "Greutate", "Observații"]]
            for _, r in df_bio.tail(10).iterrows():
                bio_data.append([
                    str(r.get("Dată", "")),
                    f"{int(r.get('Tensiune_Sistolica',0))}/{int(r.get('Tensiune_Diastolica',0))}",
                    str(r.get("Puls", "")),
                    str(r.get("Glicemie", "")),
                    str(r.get("Greutate", "")),
                    str(r.get("Observații", ""))
                ])
            t_bio = Table(bio_data, colWidths=[65, 75, 50, 60, 60, 190])
            t_bio.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0284c7")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
            ]))
            story.append(t_bio)
        
        story.append(Spacer(1, 15))

        # Tabel Apple Watch în PDF
        if os.path.exists(APPLE_WATCH_FILE):
            try:
                df_aw_pdf = pd.read_csv(APPLE_WATCH_FILE)
                if not df_aw_pdf.empty:
                    story.append(Paragraph("<b>Telemetrie Apple Watch (Puls, SpO2, Apnee & Pași)</b>", styles["Heading2"]))
                    aw_table_data = [["Data", "Puls Min/Med/Max", "SpO2", "Apnee", "Pași", "Observații"]]
                    for _, r in df_aw_pdf.tail(7).iterrows():
                        aw_table_data.append([
                            str(r.get("Dată", "")),
                            f"{r.get('Puls_Min', '')} / {r.get('PulsMediu', '')} / {r.get('Puls_Max', '')}",
                            f"{r.get('Oxigen_Sange', '')}%",
                            str(r.get("Apnee_Detectata", "")),
                            f"{int(r.get('Pasi', 0)):,}".replace(",", "."),
                            str(r.get("Observații", ""))
                        ])
                    t_aw = Table(aw_table_data, colWidths=[65, 100, 50, 85, 60, 140])
                    t_aw.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0284c7")),
                        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0,0), (-1,-1), 7.5),
                        ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
                    ]))
                    story.append(t_aw)
            except Exception as e:
                print(f"Erore adăugare Apple Watch în PDF: {e}")

        doc.build(story)
        st.success("Raportul PDF a fost generat cu succes!")
        
        with open(pdf_filename, "rb") as f:
            st.download_button(
                label="📥 Descarcă Raportul PDF",
                data=f,
                file_name="Raport_Medical_HealthTrack.pdf",
                mime="application/pdf"
            )

# ----------------- TAB: SETĂRI -----------------
with tab_dict["⚙️ Setări"]:
    st.markdown("### ⚙️ Setări Aplicație")
    st.write("Aplicație configurată pentru monitorizare sănătate și Apple Watch.")
    if st.button("🔄 Resetează toate datele la valorile implicite"):
        for f in [HEALTH_FILE, MEDS_FILE, APPT_FILE, APPLE_WATCH_FILE]:
            if os.path.exists(f): os.remove(f)
        st.success("Datele au fost resetate!")
        trigger_rerun()
