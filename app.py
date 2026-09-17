@st.cache_data(ttl=10)
def load_and_clean_data(url):
  try:
    # 1. Citim fișierul brut
    df_raw = pd.read_csv(url, header=None)

    # 2. Căutăm rândul unde apare 'Dată' în prima coloană
    data_row_idx = None
    for idx, row in df_raw.iterrows():
      val = remove_diacritics(str(row.iloc[0])).lower().strip()
      if "data" in val or "date" in val:
        data_row_idx = idx
        break

    if data_row_idx is not None:
      # Preluăm rândul superior (dacă există) și rândul curent pentru a construi nume unice de coloane
      if data_row_idx > 0:
        top_header = (
            df_raw.iloc[data_row_idx - 1].fillna("").astype(str).str.strip()
        )
      else:
        top_header = pd.Series([""] * len(df_raw.columns))

      sub_header = df_raw.iloc[data_row_idx].fillna("").astype(str).str.strip()

      # Construim numele de coloane combinate (ex: "GLICEMIE - Înainte masă")
      combined_cols = []
      current_main = ""
      for top, sub in zip(top_header, sub_header):
        if top != "" and "unnamed" not in top.lower():
          current_main = top
        name = f"{current_main} {sub}".strip() if current_main else sub
        combined_cols.append(name if name else "Necunoscut")

      # Citim datele propriu-zise sărind rândurile de antet
      df_clean = pd.read_csv(url, skiprows=data_row_idx + 1, header=None)
      df_clean.columns = combined_cols[: len(df_clean.columns)]
    else:
      # Fallback în cazul în care nu se identifică antetul
      df_clean = pd.read_csv(url)

    # Curățăm coloanele goale
    df_clean = df_clean.dropna(how="all")
    valid_cols = [
        c
        for c in df_clean.columns
        if "Unnamed" not in str(c) and str(c).strip() != ""
    ]
    return df_clean[valid_cols]

  except Exception as e:
    st.error(f"Eroare la procesarea fișierului: {e}")
    return pd.DataFrame()


# Încarcă datele
df = load_and_clean_data(GOOGLE_SHEET_URL)

# Detectare și conversie dată (format DD.MM.YYYY)
date_col = None
if not df.empty:
  for c in df.columns:
    if "data" in remove_diacritics(str(c)).lower():
      date_col = c
      break

  if not date_col and len(df.columns) > 0:
    date_col = df.columns[0]

  if date_col:
    df[date_col] = pd.to_datetime(
        df[date_col].astype(str).str.strip(), format="%d.%m.%Y", errors="coerce"
    )
    # Păstrăm doar rândurile cu date valide (de pe 12.09.2026 până în prezent)
    df = df.dropna(subset=[date_col])
    df = df.sort_values(by=date_col, ascending=False)
