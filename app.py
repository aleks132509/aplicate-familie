import streamlit as st
import pandas as pd

# Setări pagină
st.set_page_config(page_title="Aplicație Familie", page_icon="📊", layout="wide")

st.title("📊 Aplicație Familie - Jurnal")

# Funcție pentru încărcarea datelor din Google Sheets CSV
@st.cache_data(ttl=60)
def load_data(url):
    try:
        df = pd.read_csv(url)
        # Eliminare spații din numele coloanelor
        df.columns = df.columns.str.strip()
        
        # Identificare și formatare coloană de dată (dacă există)
        for col in df.columns:
            if 'data' in col.lower() or 'date' in col.lower():
                df[col] = pd.to_datetime(df[col], dayfirst=True, errors='coerce')
                df = df.dropna(subset=[col])
                df = df.sort_values(by=col, ascending=False)
                df[col] = df[col].dt.strftime('%d/%m/%Y')
        return df, None
    except Exception as e:
        return None, str(e)

# Sidebar - Configurare Conexiune
st.sidebar.header("⚙️ Setări Conexiune")

# Linkul tău predefinit Google Sheet CSV
DEFAULT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRs6o_ryWI3jCSZ_EpNyv6lDvQakwdEb0RoeuhXXXCdv9lzwCkkEXMorkk2W3ZBvg/pub?output=csv"

sheet_url = st.sidebar.text_input("Link Google Sheet CSV:", value=DEFAULT_URL)

if st.sidebar.button("🔄 Actualizează datele"):
    st.cache_data.clear()
    st.rerun()

# Afișare date
if sheet_url:
    df, error = load_data(sheet_url)
    
    if error:
        st.error("Nu s-au putut încărca datele. Verifică dacă link-ul este corect și publicat ca CSV.")
        st.caption(f"Detalii eroare: {error}")
    elif df is not None and not df.empty:
        st.success("✅ Datele din Google Sheets au fost încărcate cu succes!")
        
        # Afișare număr total de înregistrări
        st.metric(label="Total Înregistrări", value=len(df))
        
        # Afișare Tabel Date
        st.subheader("📋 Istoric Înregistrări (Jurnal)")
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("Tabelul încărcat este gol sau nu conține date valide.")
else:
    st.info("Introdu link-ul Google Sheets în bara din stânga.")
