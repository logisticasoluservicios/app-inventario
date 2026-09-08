@st.cache_resource
def conectar_google_sheets():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    if "creds_b64" in st.secrets:
        decoded_bytes = base64.b64decode(st.secrets["creds_b64"])
        creds_dict = json.loads(decoded_bytes.decode("utf-8"))
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=scope)
        
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID).sheet1
