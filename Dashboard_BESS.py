import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium
import os

# ------------------- CONFIGURAÇÃO DA PÁGINA -------------------
st.set_page_config(
    page_title="DAL - BESS Dashboard",
    page_icon="⚡",
    layout="wide"
)

st.title("⚡ Dashboard DALS - Sistemas de Armazenamento (BESS)")
st.markdown("**Rio de Janeiro** — Análise completa com mapa interativo")

# ------------------- CARREGAR DADOS DO EXCEL -------------------
@st.cache_data
def load_excel_data():
    arquivo = "Levantamento_DAL_BESS.xlsx"
    
    if not os.path.exists(arquivo):
        st.error(f"❌ Arquivo '{arquivo}' não encontrado! Verifique se ele está na mesma pasta.")
        st.stop()
    
    df = pd.read_excel(arquivo, engine='openpyxl')
    
    # Padroniza nomes das colunas
    df.columns = df.columns.str.strip()
    
    # Remove colunas duplicadas (se houver)
    df = df.loc[:, ~df.columns.duplicated()].copy()
    
    # Mapeamento flexível de colunas
    rename_map = {}
    for col in df.columns:
        col_lower = col.lower()
        if 'nota' in col_lower and 'status' not in col_lower:
            rename_map[col] = 'Nota'
        elif 'status' in col_lower and 'nota' in col_lower:
            rename_map[col] = 'Status Nota'
        elif 'razão' in col_lower or 'razao' in col_lower:
            rename_map[col] = 'Razão Social'
        elif 'solicitação' in col_lower or 'solicitacao' in col_lower:
            rename_map[col] = 'Data Solicitação'
        elif 'entrega' in col_lower:
            rename_map[col] = 'Data Entrega'
        elif 'demanda' in col_lower and 'mw' in col_lower:
            rename_map[col] = 'Demanda MW'
        elif 'localização' in col_lower or 'localizacao' in col_lower or 'bairro' in col_lower:
            rename_map[col] = 'Localização'
        elif 'latitude' in col_lower:
            rename_map[col] = 'Latitude'
        elif 'longitude' in col_lower:
            rename_map[col] = 'Longitude'
    
    df = df.rename(columns=rename_map)
    
    # Converte Demanda MW para numérico
    if 'Demanda MW' in df.columns:
        df['Demanda MW'] = pd.to_numeric(df['Demanda MW'], errors='coerce')
    
    # Padroniza Status Nota
    if 'Status Nota' in df.columns:
        df['Status Nota'] = df['Status Nota'].str.upper().str.strip()
    
    # ------------------- CONVERSÃO DE COORDENADAS (SIMPLIFICADA) -------------------
    for col in ['Latitude', 'Longitude']:
        if col in df.columns:
            # Converte a coluna para string, substitui vírgula por ponto, e converte para float
            try:
                df[col] = df[col].astype(str).str.replace(',', '.').str.strip().astype(float)
            except Exception as e:
                st.warning(f"Erro ao converter a coluna '{col}': {e}. Verifique os valores.")
                df[col] = pd.to_numeric(df[col], errors='coerce')
    
    return df

df = load_excel_data()

# ------------------- SIDEBAR - FILTROS -------------------
st.sidebar.header("🔍 Filtros")

# Filtro de Status
status_list = df['Status Nota'].unique().tolist() if 'Status Nota' in df.columns else []
status_filter = st.sidebar.multiselect(
    "Status da Nota",
    options=status_list,
    default=status_list
)

# Filtro de busca
search_term = st.sidebar.text_input("🔎 Buscar por Razão Social", "")

# Aplicar filtros
df_filtered = df.copy()
if 'Status Nota' in df.columns and status_filter:
    df_filtered = df_filtered[df_filtered['Status Nota'].isin(status_filter)]
if search_term and 'Razão Social' in df.columns:
    df_filtered = df_filtered[df_filtered['Razão Social'].str.contains(search_term, case=False, na=False)]

if df_filtered.empty:
    st.warning("Nenhum dado encontrado com os filtros selecionados.")
    st.stop()

# ------------------- MÉTRICAS -------------------
col1, col2, col3, col4 = st.columns(4)

total_mw = df_filtered['Demanda MW'].sum() if 'Demanda MW' in df_filtered.columns else 0
total_projetos = len(df_filtered)
media_mw = df_filtered['Demanda MW'].mean() if 'Demanda MW' in df_filtered.columns else 0

if 'Status Nota' in df_filtered.columns:
    concluidos = df_filtered[df_filtered['Status Nota'] == 'CONCLUIDO'].shape[0]
    andamento = df_filtered[df_filtered['Status Nota'] == 'EM ANDAMENTO'].shape[0]
else:
    concluidos = andamento = 0

col1.metric("⚡ Demanda Total", f"{total_mw:.2f} MW")
col2.metric("📋 Total de Projetos", total_projetos)
col3.metric("📊 Média por Projeto", f"{media_mw:.2f} MW")
col4.metric("✅ Concluídos / 🟠 Em Andamento", f"{concluidos} / {andamento}")

# ------------------- GRÁFICO 1: Demanda por Status -------------------
st.subheader("📊 Demanda Total por Status")
if 'Status Nota' in df_filtered.columns and 'Demanda MW' in df_filtered.columns:
    demanda_status = df_filtered.groupby('Status Nota')['Demanda MW'].sum().reset_index()
    fig1 = px.bar(
        demanda_status,
        x='Status Nota',
        y='Demanda MW',
        color='Status Nota',
        color_discrete_map={'CONCLUIDO': '#2ecc71', 'EM ANDAMENTO': '#f39c12'},
        text_auto='.2f',
        title="Soma da Demanda (MW) por Status"
    )
    fig1.update_traces(textposition='outside')
    st.plotly_chart(fig1, use_container_width=True)

# ------------------- GRÁFICO 2: Quantidade vs Demanda -------------------
st.subheader("📈 Quantidade de Solicitações vs Demanda Total")
if 'Status Nota' in df_filtered.columns and 'Demanda MW' in df_filtered.columns:
    stats = df_filtered.groupby('Status Nota').agg(
        Quantidade=('Nota', 'count') if 'Nota' in df_filtered.columns else ('Status Nota', 'count'),
        Demanda=('Demanda MW', 'sum')
    ).reset_index()
    
    stats_melted = stats.melt(
        id_vars='Status Nota',
        value_vars=['Quantidade', 'Demanda'],
        var_name='Métrica',
        value_name='Valor'
    )
    fig2 = px.bar(
        stats_melted,
        x='Status Nota',
        y='Valor',
        color='Métrica',
        barmode='group',
        color_discrete_map={'Quantidade': '#3498db', 'Demanda': '#e74c3c'},
        text_auto=True,
        title="Comparação: Quantidade vs Demanda (MW)"
    )
    fig2.update_traces(textposition='outside')
    st.plotly_chart(fig2, use_container_width=True)

# ------------------- MAPA DO RIO DE JANEIRO -------------------
st.subheader("🗺️ Mapa com Potência Somada por Localização")

# Verifica se temos coordenadas
tem_coords = all(col in df_filtered.columns for col in ['Latitude', 'Longitude'])

if not tem_coords:
    st.warning("⚠️ Colunas 'Latitude' e 'Longitude' não encontradas. Adicione essas colunas no seu Excel para exibir o mapa.")
else:
    # Remove linhas sem coordenadas
    df_map = df_filtered.dropna(subset=['Latitude', 'Longitude']).copy()
    
    if df_map.empty:
        st.warning("Nenhuma coordenada válida encontrada.")
    else:
        # Agrupa por Localização (se existir) ou por coordenadas (fallback)
        if 'Localização' not in df_map.columns:
            df_map['Localização'] = df_map.apply(
                lambda row: f"{row['Latitude']:.4f}, {row['Longitude']:.4f}", axis=1
            )
        
        df_grouped = df_map.groupby('Localização', as_index=False).agg(
            Demanda_Total=('Demanda MW', 'sum'),
            Latitude=('Latitude', 'first'),
            Longitude=('Longitude', 'first'),
            Status_List=('Status Nota', lambda x: list(x)) if 'Status Nota' in df_map.columns else (lambda x: ['N/A'])
        )
        
        if df_grouped.empty:
            st.warning("Nenhum dado disponível para o mapa.")
        else:
            # Centro aproximado do Rio
            map_center = [-22.9068, -43.1729]
            m = folium.Map(location=map_center, zoom_start=9, tiles="OpenStreetMap")
            
            max_demanda = df_grouped['Demanda_Total'].max()
            
            for _, row in df_grouped.iterrows():
                local = row['Localização']
                demanda = row['Demanda_Total']
                lat = row['Latitude']
                lon = row['Longitude']
                status_list = row['Status_List'] if isinstance(row['Status_List'], list) else []
                
                qtd_concluido = sum(1 for s in status_list if s == 'CONCLUIDO')
                qtd_andamento = sum(1 for s in status_list if s == 'EM ANDAMENTO')
                
                if qtd_concluido > 0 and qtd_andamento == 0:
                    cor = '#2ecc71'  # verde
                elif qtd_andamento > 0 and qtd_concluido == 0:
                    cor = '#f39c12'  # laranja
                else:
                    cor = '#3498db'  # azul (misto ou sem status)
                
                radius = (demanda / max_demanda) * 32 + 8
                
                popup_text = f"""
                <b>{local}</b><br>
                Demanda Total: <b>{demanda:.0f} MW</b><br>
                Projetos: {len(status_list)}<br>
                ✅ Concluídos: {qtd_concluido}<br>
                🟠 Em Andamento: {qtd_andamento}
                """
                
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=radius,
                    popup=folium.Popup(popup_text, max_width=250),
                    color='black',
                    weight=1,
                    fill=True,
                    fill_color=cor,
                    fill_opacity=0.8
                ).add_to(m)
            
            st_folium(m, width=700, height=500, returned_objects=[])

# ------------------- TABELA DE DADOS -------------------
with st.expander("📋 Visualizar Dados Completos (Filtrados)"):
    st.dataframe(df_filtered, use_container_width=True)

st.markdown("---")
st.caption("Dashboard desenvolvido com ❤️ usando Streamlit, Plotly e Folium.")