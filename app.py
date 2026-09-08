import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import io

st.set_page_config(page_title="Toma de Inventario", layout="wide")

# Conexión a Google Sheets
SPREADSHEET_ID = "1WmytTvrx1_3C-a2UQln7grajwFvGNy0Mxl4y3MmPdZ0"

@st.cache_resource
def conectar_google_sheets():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # Intentar leer credenciales desde Streamlit Secrets (Nube)
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    else:
        # Modo local
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID).sheet1

sheet = conectar_google_sheets()

st.title("📦 Toma de Inventario en Tiempo Real")

# Obtener registros raw
raw_data = sheet.get_all_values()

if raw_data and len(raw_data) > 1:
    headers = [h.strip().upper() for h in raw_data[0]]
    df = pd.DataFrame(raw_data[1:], columns=headers)

    # Identificar letras de columna (A1 Notation)
    def get_col_letter(col_name, default_letter):
        if col_name in headers:
            col_idx = headers.index(col_name)
            return chr(65 + col_idx)
        return default_letter

    letra_inv = get_col_letter("CANTIDAD INVENTARIADA", "D")
    letra_dif = get_col_letter("DIFERENCIA", "E")
    letra_obs = get_col_letter("OBSERVACIONES", "F")

    # Limpieza de tipos de datos
    df["CODIGO"] = df["CODIGO"].astype(str).str.strip().str.upper()
    df["ITEM"] = df["ITEM"].astype(str).str.strip().str.upper()
    
    for col in ["CANTIDAD SISTEMA", "CANTIDAD INVENTARIADA", "DIFERENCIA"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # Panel lateral de búsqueda e ingreso
    with st.sidebar:
        st.header("🔍 Buscar y Registrar")
        
        opciones_productos = df.apply(lambda row: f"{row['CODIGO']} - {row['ITEM']}", axis=1).tolist()
        
        producto_seleccionado = st.selectbox(
            "Selecciona o busca un producto:",
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
            
            st.markdown("---")
            st.markdown(f"**Ítem:** {item_nombre}")
            st.markdown(f"**Stock Sistema:** `{cant_sis}`")
            st.markdown(f"**Conteo Acumulado Actual:** `{cant_inv_actual}`")
            st.markdown("---")
            
            nueva_cantidad = st.number_input("Cantidad Encontrada en Físico", min_value=1, step=1, value=1)
            observacion_input = st.text_input("Observaciones (opcional)", value="")
            
            modo_registro = st.radio("Acción:", ["Sumar al conteo existente", "Reemplazar conteo total"])
            
            if st.button("Guardar Inventario", type="primary"):
                if modo_registro == "Sumar al conteo existente":
                    total_inventariado = cant_inv_actual + int(nueva_cantidad)
                else:
                    total_inventariado = int(nueva_cantidad)
                
                diferencia_calculada = total_inventariado - cant_sis
                obs_final = observacion_input.strip() if observacion_input.strip() else obs_actual
                
                sheet.update(range_name=f"{letra_inv}{num_fila_sheets}", values=[[int(total_inventariado)]])
                sheet.update(range_name=f"{letra_dif}{num_fila_sheets}", values=[[int(diferencia_calculada)]])
                sheet.update(range_name=f"{letra_obs}{num_fila_sheets}", values=[[str(obs_final)]])
                
                st.success(f"¡Actualizado {item_nombre}! Nuevo Total: {total_inventariado}")
                st.cache_data.clear()
                st.rerun()

    # Pantalla principal
    col_titulo, col_descarga = st.columns([3, 1])
    
    with col_titulo:
        st.subheader("📊 Estado de Inventario")
    
    # Generar descarga en Excel (.xlsx) limpio
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Inventario')
    
    with col_descarga:
        st.download_button(
            label="📥 Descargar Excel",
            data=buffer.getvalue(),
            file_name="Inventario_Actualizado.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="secondary"
        )

    # Filtros de vista
    col_filtro_estado, col_filtro_texto = st.columns([1, 2])
    
    with col_filtro_estado:
        opcion_filtro = st.selectbox(
            "Filtrar por Estado:",
            options=["Mostrar Todos", "Solo con Diferencias (≠ 0)", "Sin Diferencias (= 0)", "Pendientes de Contar (Cant. Inv = 0)"]
        )
        
    with col_filtro_texto:
        busqueda_tabla = st.text_input("Filtrar por Código o Descripción:").strip().upper()

    # Aplicar lógica de filtrado
    df_vista = df.copy()

    if opcion_filtro == "Solo con Diferencias (≠ 0)":
        df_vista = df_vista[df_vista["DIFERENCIA"] != 0]
    elif opcion_filtro == "Sin Diferencias (= 0)":
        df_vista = df_vista[df_vista["DIFERENCIA"] == 0]
    elif opcion_filtro == "Pendientes de Contar (Cant. Inv = 0)":
        df_vista = df_vista[df_vista["CANTIDAD INVENTARIADA"] == 0]

    if busqueda_tabla:
        df_vista = df_vista[
            df_vista["CODIGO"].str.contains(busqueda_tabla) |
            df_vista["ITEM"].str.contains(busqueda_tabla)
        ]

    st.caption(f"Mostrando **{len(df_vista)}** de **{len(df)}** ítems totales.")
    st.dataframe(df_vista, use_container_width=True)

else:
    st.warning("No se encontraron registros en Google Sheets.")
