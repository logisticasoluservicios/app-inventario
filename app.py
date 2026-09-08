import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import io

# Configuración inicial y optimización de CSS para móviles
st.set_page_config(
    page_title="Toma de Inventario",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS inyectado para reducir espacios y mejorar la experiencia en celulares
st.markdown("""
    <style>
        /* Reducir el padding general en pantallas pequeñas */
        .block-container {
            padding-top: 1.5rem !important;
            padding-bottom: 2rem !important;
            padding-left: 0.8rem !important;
            padding-right: 0.8rem !important;
        }
        /* Hacer botones e inputs más prominentes y táctiles */
        .stButton>button {
            width: 100%;
            border-radius: 8px;
            height: 3em;
            font-weight: bold;
        }
        /* Ajustar métricas en móviles */
        [data-testid="stMetricValue"] {
            font-size: 1.5rem !important;
        }
    </style>
""", unsafe_allow_html=True)

SPREADSHEET_ID = "1WmytTvrx1_3C-a2UQln7grajwFvGNy0Mxl4y3MmPdZ0"

@st.cache_resource
def conectar_google_sheets():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    if "gcp_service_account" not in st.secrets:
        st.error("No se encontraron las credenciales en 'Secrets' de Streamlit Cloud.")
        st.stop()

    creds_dict = dict(st.secrets["gcp_service_account"])

    if "private_key" in creds_dict:
        creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

    creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID).sheet1

sheet = conectar_google_sheets()

st.title("📦 Toma de Inventario")

raw_data = sheet.get_all_values()

if raw_data and len(raw_data) > 1:
    headers = [h.strip().upper() for h in raw_data[0]]
    df = pd.DataFrame(raw_data[1:], columns=headers)

    def get_col_letter(col_name, default_letter):
        if col_name in headers:
            col_idx = headers.index(col_name)
            return chr(65 + col_idx)
        return default_letter

    letra_inv = get_col_letter("CANTIDAD INVENTARIADA", "D")
    letra_dif = get_col_letter("DIFERENCIA", "E")
    letra_obs = get_col_letter("OBSERVACIONES", "F")

    df["CODIGO"] = df["CODIGO"].astype(str).str.strip().str.upper()
    df["ITEM"] = df["ITEM"].astype(str).str.strip().str.upper()
    
    for col in ["CANTIDAD SISTEMA", "CANTIDAD INVENTARIADA", "DIFERENCIA"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # Registro rápido desplegable en la parte superior para fácil acceso en móvil
    with st.expander("📝 **REGISTRAR O EDITAR CONTEO**", expanded=True):
        opciones_productos = df.apply(lambda row: f"{row['CODIGO']} - {row['ITEM']}", axis=1).tolist()
        
        producto_seleccionado = st.selectbox(
            "Buscar Producto:",
            options=opciones_productos,
            index=0
        )
        
        if producto_seleccionado:
            codigo_sel = producto_seleccionado.split(" - ")[0]
            fila_index = int(df[df["CODIGO"] == codigo_sel].index[0])
            num_fila_sheets = fila_index + 2
            
            item_nombre = df.loc[fila_index, "ITEM"]
            cant_sis = int(df.loc[fila_index, "CANTIDAD SISTEMA"])
            cant_inv_actual = int(df.loc[fila_index, "CANTIDAD INVENTARIADA"])
            obs_actual = str(df.loc[fila_index, "OBSERVACIONES"]) if "OBSERVACIONES" in df.columns else ""
            
            # Resumen visual tipo métrica táctil
            m1, m2 = st.columns(2)
            m1.metric("Stock Sistema", cant_sis)
            m2.metric("Conteo Actual", cant_inv_actual)
            
            c1, c2 = st.columns([1, 1])
            with c1:
                nueva_cantidad = st.number_input("Cantidad", min_value=1, step=1, value=1)
            with c2:
                modo_registro = st.radio("Acción:", ["Sumar", "Reemplazar"], horizontal=True)
                
            observacion_input = st.text_input("Observación (opcional):", value="")
            
            if st.button("💾 Guardar Conteo", type="primary"):
                if modo_registro == "Sumar":
                    total_inventariado = cant_inv_actual + int(nueva_cantidad)
                else:
                    total_inventariado = int(nueva_cantidad)
                
                diferencia_calculada = total_inventariado - cant_sis
                obs_final = observacion_input.strip() if observacion_input.strip() else obs_actual
                
                sheet.update(range_name=f"{letra_inv}{num_fila_sheets}", values=[[int(total_inventariado)]])
                sheet.update(range_name=f"{letra_dif}{num_fila_sheets}", values=[[int(diferencia_calculada)]])
                sheet.update(range_name=f"{letra_obs}{num_fila_sheets}", values=[[str(obs_final)]])
                
                st.success(f"¡Guardado! Nuevo total: {total_inventariado}")
                st.cache_data.clear()
                st.rerun()

    st.markdown("---")
    
    # Sección de consulta y filtros
    st.subheader("📊 Tabla de Control")
    
    opcion_filtro = st.selectbox(
        "Filtrar lista:",
        options=["Mostrar Todos", "Solo con Diferencias (≠ 0)", "Sin Diferencias (= 0)", "Pendientes (Cant. Inv = 0)"]
    )
        
    busqueda_tabla = st.text_input("Filtrar por texto:").strip().upper()

    df_vista = df.copy()

    if opcion_filtro == "Solo con Diferencias (≠ 0)":
        df_vista = df_vista[df_vista["DIFERENCIA"] != 0]
    elif opcion_filtro == "Sin Diferencias (= 0)":
        df_vista = df_vista[df_vista["DIFERENCIA"] == 0]
    elif opcion_filtro == "Pendientes (Cant. Inv = 0)":
        df_vista = df_vista[df_vista["CANTIDAD INVENTARIADA"] == 0]

    if busqueda_tabla:
        df_vista = df_vista[
            df_vista["CODIGO"].str.contains(busqueda_tabla) |
            df_vista["ITEM"].str.contains(busqueda_tabla)
        ]

    st.caption(f"Mostrando **{len(df_vista)}** de **{len(df)}** ítems.")
    st.dataframe(df_vista, use_container_width=True, hide_index=True)

    # Generar la descarga de Excel dinámicamente con los datos más recientes
    def convertir_df_a_excel(dataframe):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            dataframe.to_excel(writer, index=False, sheet_name='Inventario')
        return output.getvalue()

    excel_data = convertir_df_a_excel(df)

    st.download_button(
        label="📥 Descargar Reporte en Excel",
        data=excel_data,
        file_name="Inventario_Actualizado.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        key="btn_descarga_excel"
    )

else:
    st.warning("No se encontraron registros en Google Sheets.")
