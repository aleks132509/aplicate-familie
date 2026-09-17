import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# Configurare Pagină
st.set_page_config(
    page_title="Jurnal Familie",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Stiluri CSS personalizate pentru un aspect modern
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .stButton>button {
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# Gestionare stare de autentificare / conectare
if "logged_in" not in st.session_state:
    st.session_state.logged_in = True

# Functie de incarcare date din Google Sheets
@st.cache_data(ttl=60)
def load_data(url):
    try:
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        
        # Căutare și formatare coloană de dată
        date_col = None
        for col in df.columns:
            if 'data' in col.lower() or 'date' in col.lower():
                date_col = col
                break
        
        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
            df = df.dropna(subset=[date_col])
            df = df.sort_values(by=date_col, ascending=False)
            df['Data_Formata'] = df[date_col].dt.strftime('%d/%m/%Y')
            
        return df, date_col, None
    except Exception as e:
        return None, None, str(e)

# --- SIDEBAR (Meniul din stânga) ---
with st.sidebar:
    st.title("🏠 Panou Familie")
    st.caption("Conectat ca: **Membru Familie**")
    
    st.markdown("---")
    
    # URL-ul tău Google Sheets CSV
    DEFAULT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRs6o_ryWI3jCSZ_EpNyv6lDvQakwdEb0RoeuhXXXCdv9lzwCkkEXMorkk2W3ZBvg/pub?output=csv"
    sheet_url = st.text_input("Link Google Sheet CSV:", value=DEFAULT_URL)
    
    st.markdown("---")
    
    col_ref, col_disc = st.columns(2)
    with col_ref:
        if st.button("🔄 Reload", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
    with col_disc:
        if st.button("🔴 Deconectare", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()

# Verification stare deconectare
if not st.session_state.logged_in:
    st.warning("Te-ai deconectat cu succes.")
    if st.button("🔑 Reconectează-te"):
        st.session_state.logged_in = True
        st.rerun()
    st.stop()

# --- CORPUL PRINCIPAL AL APLICAȚIEI ---
st.markdown('<div class="main-header">📊 Jurnal & Activitate Familie</div>', unsafe_allow_html=True)

if sheet_url:
    df, date_col, error = load_data(sheet_url)
    
    if error:
        st.error("⚠️ Nu s-au putut prelua datele din Google Sheets.")
        st.info("Verifică dacă fișierul este publicat pe web în format CSV (File > Share > Publish to web > CSV).")
    elif df is not None and not df.empty:
        
        # Row 1: KPI Metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="Total Înregistrări", value=len(df))
        with col2:
            if date_col and not df[date_col].empty:
                ultima_data = df[date_col].max().strftime('%d/%m/%Y')
                st.metric(label="Ultima Înregistrare", value=ultima_data)
            else:
                st.metric(label="Status", value="Activ")
        with col3:
            numar_coloane = len(df.columns) - (1 if 'Data_Formata' in df.columns else 0)
            st.metric(label="Câmpuri Monitorizate", value=numar_coloane)
            
        st.markdown("---")
        
        # Tabs pentru organizarea vizuală
        tab1, tab2 = st.tabs(["📋 Jurnal Date", "📈 Grafice & Statistici"])
        
        with tab1:
            st.subheader("Istoric Complet Înregistrări")
            
            # Filtru de căutare
            search_query = st.text_input("🔍 Caută în jurnal:", "")
            
            df_display = df.copy()
            if 'Data_Formata' in df_display.columns and date_col:
                # Pune data formatată pe prima poziție
                cols = ['Data_Formata'] + [c for c in df_display.columns if c not in ['Data_Formata', date_col]]
                df_display = df_display[cols]
                df_display = df_display.rename(columns={'Data_Formata': 'Data'})
            
            if search_query:
                df_display = df_display[df_display.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]
                
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
        with tab2:
            st.subheader("Evoluție & Distribuție")
            if date_col and len(df) > 1:
                df_counts = df.groupby(df[date_col].dt.date).size().reset_index(name='Număr Înregistrări')
                fig = px.line(
                    df_counts, 
                    x=date_col, 
                    y='Număr Înregistrări', 
                    title="Activitate în Timp",
                    markers=True,
                    color_discrete_sequence=['#2563EB']
                )
                fig.update_layout(xaxis_title="Data", yaxis_title="Număr Intrări")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Sunt necesare cel puțin două înregistrări cu dată validă pentru generarea graficului.")
    else:
        st.warning("Tabelul din Google Sheets este gol sau nu conține date.")
