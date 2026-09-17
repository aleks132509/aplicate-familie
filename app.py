@st.cache_data(ttl=10)
def load_and_clean_data(url):
  try:
    # Citim fișierul fără să presupunem un singur rând de antet
    df_raw = pd.read_csv(url, header=None)

    # Identificăm rândul exact unde apare "Dată" sau "Dată" în prima coloană
    header_row_idx = None
    for idx, row in df_raw.iterrows():
      first_cell = remove_diacritics(str(row.iloc[0])).lower().strip()
      if "data" in first_cell or "date" in first_cell:
        header_row_idx = idx
        break

    if header_row_idx is not None:
      # Citim datele începând direct de la rândul cu antetele reale (Dată, Moment, etc.)
      df_clean = pd.read_csv(url, skiprows=header_row_idx)
    else:
      df_clean = pd.read_csv(url)

    # Curățăm numele coloanelor de spații și diacritice
    df_clean.columns = [str(c).strip() for c in df_clean.columns]

    # Eliminăm coloanele vide / Unnamed
    valid_cols = [
        c
        for c in df_clean.columns
        if "Unnamed" not in c and c.lower() != "nan" and c != ""
    ]
    df_clean = df_clean[valid_cols]

    return df_clean.dropna(how="all")
  except Exception as e:
    st.error(f"Eroare la citirea datelor din Google Sheets: {e}")
    return pd.DataFrame()


# Incarcare date
df = load_and_clean_data(GOOGLE_SHEET_URL)

# Identificare sigura a coloanei de Dată
date_col = None
if not df.empty:
  for c in df.columns:
    c_norm = remove_diacritics(str(c)).lower()
    if "data" in c_norm or "date" in c_norm:
      date_col = c
      break

  if not date_col and len(df.columns) > 0:
    date_col = df.columns[0]

  if date_col and date_col in df.columns:
    # Formatul din imagine este DD.MM.YYYY (ex: 12.09.2026)
    df[date_col] = pd.to_datetime(
        df[date_col].astype(str).str.strip(), format="%d.%m.%Y", errors="coerce"
    )

    # Daca formatul punctat esueaza, încercam parsare generala
    if df[date_col].isna().all():
      df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce")

    # Eliminam randurile goale
    df = df.dropna(subset=[date_col])
    df = df.sort_values(by=date_col, ascending=False)
