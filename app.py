@st.cache_resource
def conectar_google_sheets():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    if "gcp_service_account" not in st.secrets:
        st.error("No se encontraron las credenciales en 'Secrets' de Streamlit Cloud.")
        st.stop()

    # Convertir el objeto de secretos a diccionario
    creds_dict = dict(st.secrets["gcp_service_account"])

    # Reemplazar la representación textual de \n por el caracter de salto de línea
    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID).sheet1
