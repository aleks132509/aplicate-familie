import streamlit as st
import pandas as pd

# 1. Configurare utilizatori (Nume utilizator: Parolă)
USERS = {
    "tata": "parola123",
    "mama": "parola456",
    "copil": "parola789"
}

st.set_page_config(page_title="Aplicație Familie", layout="wide")

# Verificare Autentificare
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔒 Autentificare Familie")
    username = st.text_input("Utilizator")
    password = st.text_input("Parolă", type="password")
    
    if st.button("Conectare"):
        if USERS.get(username) == password:
            st.session_state.logged_in = True
            st.session_state.user = username
            st.rerun()
        else:
            st.error("Utilizator sau parolă incorectă!")
else:
    st.sidebar.write(f"Conectat ca: **{st.session_state.user}**")
    if st.sidebar.button("Deconectare"):
        st.session_state.logged_in = False
        st.rerun()

    st.title("📋 Gestiune Date & Export PDF")

    # Introdu link-ul public către fișierul tău (Google Sheet / CSV)
    # Înlocuiește link-ul de mai jos cu link-ul tău dacă folosești Google Sheets
    sheet_url = st.text_input("Link fișier / Google Sheet CSV:", "")

    if sheet_url:
        try:
            df = pd.read_csv(sheet_url)
            st.subheader("📊 Date Curente")
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.error("Nu s-a putut încărca fișierul. Verifică link-ul.")
            df = pd.DataFrame()
    else:
        st.info("Introdu link-ul fișierului de date mai sus.")
        df = pd.DataFrame()

    # Formular Adăugare Date
    st.subheader("➕ Adaugă Date Noi")
    with st.form("form_adaugare"):
        col1 = st.text_input("Nume / Descriere")
        col2 = st.number_input("Suma / Valoare", min_value=0.0)
        col3 = st.date_input("Data")
        
        submitted = st.form_submit_button("Adaugă")
        if submitted:
            st.success("Date introduse cu succes!")

    # Export PDF
    st.subheader("📄 Export PDF")
    if not df.empty:
        # Generare HTML simplu pentru print
        html_code = df.to_html(classes="table", index=False)
        st.download_button(
            label="📥 Descarcă Tabelul ca fișier (HTML/PDF)",
            data=f"<html><head><style>table {{width:100%; border-collapse:collapse;}} th,td {{border:1px solid black; padding:8px;}}</style></head><body><h1>Raport Familie</h1>{html_code}</body></html>",
            file_name="raport.html",
            mime="text/html"
        )