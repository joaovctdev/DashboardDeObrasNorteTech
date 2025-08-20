import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
import re
import json
import numpy as np
import datetime
from fpdf import FPDF
from io import BytesIO
import tempfile
import os
import googlemaps
from datetime import datetime, timedelta
import time

# REMOVA esta dupla configuração - deixe apenas UMA:
st.set_page_config(
    page_title="Dashboard de Obras",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS personalizado
st.markdown("""
<style>
    .metric-card {
        border: 1px solid white;
        border-radius: 10px;
        padding: 15px;
        background-color: #0e1117;
        text-align: center;
    }
    .metric-title {
        color: #ffffff;
        font-size: 1rem;
        margin-bottom: 5px;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: bold;
    }
    .stPlotlyChart {
        border: 1px solid white;
        border-radius: 10px;
        padding: 0px;
        margin: -4px;
    }
    /* Elimina TODOS os espaçamentos indesejados */
    .stVerticalBlock, .st-emotion-cache-159b5ki, .st-emotion-cache-1vo6xi6 {
        padding: 0 !important;
        margin: 0 !important;
        gap: 0 !important;
    }
    
    /* Reset radical no container do título */
    .st-emotion-cache-18tdrd9, .st-emotion-cache-arp25b {
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* Título ultra-compacto */
    h1.titulo {
        padding: 0 !important;
        margin: 0 !important;
        line-height: 1 !important;
    }
    
    /* Remove espaçamento do ícone de link */
    .st-emotion-cache-gi0tri, .st-emotion-cache-ubko3j {
        display: none !important;
    }
    
    /* Container principal sem espaços */
    .stApp > div {
        padding: 0 !important;
    }
</style>
""", unsafe_allow_html=True)

# Função para encontrar coluna por padrão de nome
def encontrar_coluna(df, padroes):
    for col in df.columns:
        for padrao in padroes:
            if re.search(padrao, str(col), re.IGNORECASE):
                return col
    return None

# Adicione esta função ANTES do seu main()
def compact_layout():
    import streamlit.components.v1 as components
    components.html("""
    <script>
        // Método JS para forçar compactação
        setTimeout(function(){
            const containers = parent.document.querySelectorAll('.block-container, .st-emotion-cache-1y4p8pa');
            containers.forEach(container => {
                container.style.paddingTop = '0.5rem';
                container.style.paddingBottom = '0.5rem';
            });
            
            const headers = parent.document.querySelectorAll('header');
            headers.forEach(header => {
                header.style.padding = '0';
                header.style.minHeight = '0';
            });
        }, 100);
    </script>
    """, height=0)

# Função para aplicar filtros
@st.cache_data
def aplicar_filtros(df, colunas, filtros):
    """Aplica todos os filtros ao dataframe"""
    df_filtrado = df.copy()
    
    # Filtros múltiplos
    if colunas['equipes'] and filtros['equipes']:
        df_filtrado = df_filtrado[df_filtrado[colunas['equipes']].isin(filtros['equipes'])]
    if colunas['supervisor'] and filtros['supervisores']:
        df_filtrado = df_filtrado[df_filtrado[colunas['supervisor']].isin(filtros['supervisores'])]
    if colunas['municipio'] and filtros['municipios']:
        df_filtrado = df_filtrado[df_filtrado[colunas['municipio']].isin(filtros['municipios'])]
    if colunas['mes'] and filtros['meses']:
        df_filtrado = df_filtrado[df_filtrado[colunas['mes']].isin(filtros['meses'])]
    
    # Filtros por pesquisa de texto
    if colunas['titulo'] and filtros['titulo_pesquisa']:
        df_filtrado = df_filtrado[
            df_filtrado[colunas['titulo']].str.contains(
                filtros['titulo_pesquisa'], case=False, na=False)
        ]
    if colunas['base_obra'] and filtros['base_pesquisa']:
        df_filtrado = df_filtrado[
            df_filtrado[colunas['base_obra']].str.contains(
                filtros['base_pesquisa'], case=False, na=False)
        ]
    
    return df_filtrado

# Carregar dados principais (Excel)
@st.cache_data(ttl=60)
def carregar_dados():
    try:
        # Primeiro tenta ler como .xlsx
        timestamp = os.path.getmtime("dados.xlsx")
        df = pd.read_excel("dados.xlsx", engine='openpyxl')
    except:
        try:
            # Se falhar, tenta como .xls
            df = pd.read_excel("dados.xls", engine='xlrd')
        except Exception as e:
            st.error(f"Erro ao ler o arquivo: {e}")
            st.error("Verifique:")
            st.error("1. O arquivo existe no diretório?")
            st.error("2. O arquivo não está corrompido?")
            st.error("3. O formato é .xlsx ou .xls válido?")
            return None
    
    # Converter colunas para tipos consistentes
    for col in df.columns:
        if df[col].dtype == 'object':
            try:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='ignore')
            except:
                pass
    return df

# Carregar dados JSON com tratamento robusto
@st.cache_data(ttl=60)
def carregar_json():
    try:
        # Verificar se arquivo existe
        if not os.path.exists("bd.json"):
            st.warning("Arquivo bd.json não encontrado. Criando arquivo vazio...")
            with open('bd.json', 'w', encoding='utf-8') as f:
                json.dump([], f, indent=4, ensure_ascii=False)
            return pd.DataFrame()
        
        # Verificar se arquivo está vazio
        if os.path.getsize("bd.json") == 0:
            st.warning("Arquivo bd.json está vazio.")
            return pd.DataFrame()
        
        # Ler e processar o arquivo
        with open('bd.json', 'r', encoding='utf-8') as f:
            conteudo = f.read().strip()
            
            if not conteudo:
                return pd.DataFrame()
            
            # Carregar JSON
            dados = json.loads(conteudo)
            
            # Converter objeto único para array
            if isinstance(dados, dict):
                dados = [dados]
            
            # Processar dados para DataFrame
            df = pd.DataFrame(dados)
            
            # Converter tipos de dados
            if 'DATA' in df.columns:
                df['DATA'] = pd.to_datetime(df['DATA'], format='%d/%m/%Y', errors='coerce')
            
            # Converter colunas numéricas
            colunas_numericas = ['LOCAÇÃO', 'CAV PREV', 'CAVA REAL', 'POSTE PREV', 'POSTE REAL', 'TOTAL POSTE']
            for col in colunas_numericas:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Substituir NaN por valores apropriados
            df = df.fillna({
                'LOCAÇÃO': 0,
                'CAV PREV': 0,
                'CAVA REAL': 0,
                'POSTE PREV': 0,
                'POSTE REAL': 0,
                'TOTAL POSTE': 0,
                'JUSTIFICATIVA': ''
            })
            
            return df
            
    except json.JSONDecodeError as e:
        st.error(f"❌ Erro na formatação do JSON: {e}")
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"❌ Erro inesperado ao carregar JSON: {e}")
        return pd.DataFrame()

# FUNÇÃO CALCULAR RENDIMENTO DEFINIDA FORA DO MAIN
def calcular_rendimento(row, col_json):
    try:
        # Obter nomes reais das colunas
        col_atividade = col_json['atividade']
        col_justificativa = col_json['justificativa']
        
        # Obter valores
        atividade = str(row.get(col_atividade, '')).upper().strip()
        justificativa = str(row.get(col_justificativa, '')).upper().strip()
        
        # Debug (descomente para ver)
        # print(f"DEBUG: Atividade='{atividade}', Justificativa='{justificativa}'")
        
        # Termos que automaticamente dão 100%
        termos_100 = [
            'ENERGIZAÇÃO', 'ENERGIZACAO', 'ENERGIZADA', 'ENERGIZADO',
            'DESLIGAMENTO', 'DESLIGADA', 'DESLIGADO', 
            'LIGAMENTO', 'LIGADA', 'LIGADO', 'LIGAÇÃO',
            'IMPLANTAÇÃO', 'IMPLANTACAO', 'IMPLANTADA', 'IMPLANTADO',
            'ESCAVAÇÃO', 'ESCAVACAO', 'ESCAVADA', 'ESCAVADO',
            'LANÇAMENTO', 'LANCAMENTO', 'LANÇADA', 'LANCADA',
            'LOCAÇÃO', 'LOCACAO', 'LOCADA', 'LOCADO',
            'POSTE', 'POSTES', 'CAVA', 'CAVAS',
            'CONCLUSÃO', 'CONCLUSAO', 'CONCLUIDO', 'CONCLUÍDO'
        ]
        
        # Verificar se qualquer termo está presente
        texto_completo = f"{atividade} {justificativa}"
        for termo in termos_100:
            if termo in texto_completo:
                return 100.0
        
        # Verificação direta
        if atividade and justificativa and atividade in justificativa:
            return 100.0
        
        return 0.0
        
    except Exception as e:
        print(f"Erro ao calcular rendimento: {e}")
        return 0.0

# Seção de Produtividade de Carreteiros
def carreteiros_section():
    st.header("🚛 Cálculo de Produtividade de Carreteiros (TESTE)")
    
    if 'resultados_carreteiros' not in st.session_state:
        st.session_state.resultados_carreteiros = None
    
    df = carregar_dados()
    if df is None:
        st.error("Não foi possível carregar os dados principais")
        return
    
    coluna_base = encontrar_coluna(df, ['B DA OBRA', 'BASE DA OBRA', 'BASE_OBRA', 'BASE'])
    coluna_postes = encontrar_coluna(df, ['POSTES PREVISTOS', 'PREVISTOS', 'PLANEJADOS'])
    coluna_lat = encontrar_coluna(df, ['LATITUDE', 'LAT'])
    coluna_lon = encontrar_coluna(df, ['LONGITUDE', 'LONG', 'LON'])
    
    col1, col2 = st.columns(2)
    
    with col1:
        capacidade_carreteiro = st.number_input("Capacidade do carreteiro (quantidade de postes)", min_value=1, value=20, key='capacidade')
        
        TEMPO_CARGA_POR_POSTE = 4
        TEMPO_DESCARGA_POR_POSTE = 5
        
        tempo_carga = capacidade_carreteiro * TEMPO_CARGA_POR_POSTE
        tempo_descarga = capacidade_carreteiro * TEMPO_DESCARGA_POR_POSTE
        
        st.info(f"Tempo médio de carga: {tempo_carga} minutos (para {capacidade_carreteiro} postes)")
        st.info(f"Tempo médio de descarga: {tempo_descarga} minutos (para {capacidade_carreteiro} postes)")
        
        velocidade_media = st.number_input("Velocidade média (km/h)", min_value=1, value=60, key='velocidade')
        
    with col2:
        st.subheader("🔍 Seleção da Obra")
        
        origem = (-11.3039, -41.8567)  # Coordenadas de Irecê-BA
        
        if coluna_base:
            obras_disponiveis = df[coluna_base].dropna().unique()
            nome_obra = st.selectbox("Selecione a obra (B da obra)", options=obras_disponiveis, key='obra')
            
            if coluna_postes and nome_obra:
                postes_obra = df[df[coluna_base] == nome_obra][coluna_postes].sum()
                postes_necessarios = st.number_input(
                    "Postes necessários na obra", 
                    min_value=1, 
                    value=int(postes_obra) if not pd.isna(postes_obra) else 100,
                    key='postes_necessarios'
                )
            else:
                postes_necessarios = st.number_input("Postes necessários na obra", min_value=1, value=100, key='postes_necessarios')
        else:
            st.warning("Coluna 'B DA OBRA' não encontrada na planilha")
            nome_obra = None
            postes_necessarios = st.number_input("Postes necessários na obra", min_value=1, value=100, key='postes_necessarios')
        
        distancia_ida_volta = st.number_input("Distância ida e volta (km) - opcional para cálculo automático", min_value=0, value=0, key='distancia')
    
    google_api_key = "AIzaSyAhfh4DPlxWxlN3r61PRXfcoQD8SHQ3iCs"
    
    if st.button("Calcular Produtividade", key='calcular'):
        if distancia_ida_volta == 0 and (not nome_obra or not coluna_lat or not coluna_lon):
            st.warning("Para cálculo automático de distância, é necessário:")
            st.warning("- Selecionar uma obra válida")
            st.warning("- Ter colunas de Latitude e Longitude na planilha")
            return
            
        try:
            obra_info = df[df[coluna_base] == nome_obra].iloc[0]
            
            try:
                lat = float(obra_info[coluna_lat])
                lon = float(obra_info[coluna_lon])
                destino = (lat, lon)
            except (ValueError, TypeError) as e:
                st.error(f"Coordenadas inválidas para a obra selecionada: {obra_info[coluna_lat]}, {obra_info[coluna_lon]}")
                return
                
            if distancia_ida_volta == 0:
                gmaps = googlemaps.Client(key=google_api_key)
                
                now = datetime.now()
                directions_result = gmaps.directions(origem, destino, mode="driving", departure_time=now)
                
                if directions_result:
                    distancia_metros = directions_result[0]['legs'][0]['distance']['value']
                    tempo_segundos = directions_result[0]['legs'][0]['duration']['value']
                    
                    distancia_ida_volta = (distancia_metros * 2) / 1000
                    tempo_viagem = (tempo_segundos * 2) / 60
                    
                    st.success(f"Distância calculada: {distancia_ida_volta:.2f} km (ida e volta)")
                    st.success(f"Tempo de viagem estimado: {tempo_viagem:.2f} minutos (ida e volta)")
            
            if distancia_ida_volta > 0:
                tempo_total_viagem = (distancia_ida_volta / velocidade_media) * 60
                viagens_necessarias = np.ceil(postes_necessarios / capacidade_carreteiro)
                
                tempo_total_carga = tempo_carga * viagens_necessarias
                tempo_total_descarga = tempo_descarga * viagens_necessarias
                tempo_total_carga_descarga = tempo_total_carga + tempo_total_descarga
                
                tempo_total_transporte = tempo_total_viagem * viagens_necessarias
                tempo_total = tempo_total_carga_descarga + tempo_total_transporte
                
                st.session_state.resultados_carreteiros = {
                    "Viagens necessárias": int(viagens_necessarias),
                    "Tempo total de carga (min)": f"{tempo_total_carga:.1f}",
                    "Tempo total de descarga (min)": f"{tempo_total_descarga:.1f}",
                    "Tempo total de transporte (min)": f"{tempo_total_transporte:.1f}",
                    "Tempo total estimado (min)": f"{tempo_total:.1f}",
                    "Tempo total estimado (horas)": f"{tempo_total/60:.1f}",
                    "Produtividade (postes/hora)": f"{(postes_necessarios/(tempo_total/60)):.2f}",
                    "mapa_data": {
                        "origem": origem,
                        "destino": destino,
                        "nome_obra": nome_obra.strip()
                    }
                }
                
        except Exception as e:
            st.error(f"Erro ao calcular produtividade: {str(e)}")
    
    if st.session_state.resultados_carreteiros:
        st.subheader("📊 Resultados de Produtividade")
        resultados_df = pd.DataFrame.from_dict(
            {k: v for k, v in st.session_state.resultados_carreteiros.items() if k != "mapa_data"}, 
            orient='index', 
            columns=['Valor']
        )
        st.table(resultados_df)

# Interface principal
def main():
    compact_layout()
    
    if st.button("🔄 Recarregar Dados Manualmente"):
        st.cache_data.clear()
        st.rerun()
    
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("<h1 style='margin:16px;padding:12px'>📈 Dashboard de Progresso de Obras </h1>", unsafe_allow_html=True)
    with col2:
        st.image("WhatsApp_Image_2025-03-13_at_13.58.59__2_-removebg-preview.png", width=100)

    st.markdown("<hr style='margin:0.5rem 0'>", unsafe_allow_html=True)
    
    # Carregar dados
    df = carregar_dados()
    if df is None:
        st.error("Não foi possível carregar os dados principais")
        st.stop()

    df_json = carregar_json()
    
    # Definir colunas
    colunas = {
        'equipes': encontrar_coluna(df, ['EQUIPE', 'ENCARREGADO', 'ENCARREGADOS']),
        'postes_previstos': encontrar_coluna(df, ['POSTES PREVISTOS', 'PREVISTOS', 'PLANEJADOS']),
        'postes_implantados': encontrar_coluna(df, ['POSTES IMPLANTADOS', 'IMPLANTADOS', 'EXECUTADOS']),
        'cavas': encontrar_coluna(df, ['CAVAS REALIZADAS', 'CAVAS', 'CAVAS EXECUTADAS', 'SCOPOS REALIZADOS']),
        'mes': encontrar_coluna(df, ['MÊS', 'MES', 'PERÍODO']),
        'latitude': encontrar_coluna(df, ['LATITUDE', 'LAT']),
        'longitude': encontrar_coluna(df, ['LONGITUDE', 'LONG', 'LON']),
        'situacao': encontrar_coluna(df, ['SITUAÇÃO', 'STATUS', 'SITUACAO']),
        'base_obra': encontrar_coluna(df, ['B DA OBRA', 'BASE DA OBRA', 'BASE_OBRA', 'BASE']),
        'titulo': encontrar_coluna(df, ['TÍTULO', 'TITULO', 'NOME', 'PROJETO']),
        'municipio': encontrar_coluna(df, ['MUNICÍPIO', 'MUNICIPIO', 'CIDADE', 'LOCALIDADE']),
        'supervisor': encontrar_coluna(df, ['SUPERVISOR', 'RESPONSAVEL', 'ENCARREGADO'])
    }

    # Filtros
    st.sidebar.header("🔍 Filtros Avançados")

    # Inicializar variáveis de filtro
    equipes_selecionadas = []
    supervisores_selecionados = []
    municipios_selecionados = []
    meses_selecionados = []
    titulo_pesquisa = ""
    base_pesquisa = ""

    # Filtros múltiplos
    with st.sidebar.expander("Filtros Múltiplos", expanded=True):
        if colunas.get('equipes'):
            equipes_disponiveis = df[colunas['equipes']].dropna().unique().tolist()
            equipes_selecionadas = st.multiselect(
                "Selecione as Equipes",
                options=equipes_disponiveis,
                default=equipes_disponiveis
            )
        
        if colunas.get('supervisor'):
            supervisores_disponiveis = df[colunas['supervisor']].dropna().unique().tolist()
            supervisores_selecionados = st.multiselect(
                "Selecione os Supervisores",
                options=supervisores_disponiveis,
                default=supervisores_disponiveis
            )
        
        if colunas.get('municipio'):
            municipios_disponiveis = df[colunas['municipio']].dropna().unique().tolist()
            municipios_selecionados = st.multiselect(
                "Selecione os Municípios",
                options=municipios_disponiveis,
                default=municipios_disponiveis
            )
        
        if colunas.get('mes'):
            meses_disponiveis = df[colunas['mes']].dropna().unique().tolist()
            meses_selecionados = st.multiselect(
                "Selecione os Meses",
                options=meses_disponiveis,
                default=meses_disponiveis
            )

    with st.sidebar.expander("Pesquisar", expanded=True):
        if colunas.get('titulo'):
            titulo_pesquisa = st.text_input("Pesquisar por Título:")
        
        if colunas.get('base_obra'):
            base_pesquisa = st.text_input("Pesquisar por Base da Obra:")

    filtros = {
        'equipes': equipes_selecionadas,
        'supervisores': supervisores_selecionados,
        'municipios': municipios_selecionados,
        'meses': meses_selecionados,
        'titulo_pesquisa': titulo_pesquisa,
        'base_pesquisa': base_pesquisa
    }

    df_filtrado = aplicar_filtros(df, colunas, filtros)

    # Cards de métricas
    st.subheader("Resumo Geral")
    cols = st.columns(4)

    total_previsto = df_filtrado[colunas['postes_previstos']].sum() if colunas['postes_previstos'] else 0
    total_implantado = df_filtrado[colunas['postes_implantados']].sum() if colunas['postes_implantados'] else 0
    total_cavas = df_filtrado[colunas['cavas']].sum() if colunas['cavas'] else 0
    porcentagem = (total_implantado / total_previsto) * 100 if total_previsto > 0 else 0

    with cols[0]:
        st.markdown('''
        <div class="metric-card">
            <div class="metric-title">Total Previsto</div>
            <div class="metric-value">''' + f"{int(total_previsto)}" + '''</div>
        </div>
        ''', unsafe_allow_html=True)

    with cols[1]:
        st.markdown('''
        <div class="metric-card">
            <div class="metric-title">Total Implantado</div>
            <div class="metric-value">''' + f"{int(total_implantado)}" + '''</div>
        </div>
        ''', unsafe_allow_html=True)

    with cols[2]:
        st.markdown('''
        <div class="metric-card">
            <div class="metric-title">Total de Cavas</div>
            <div class="metric-value">''' + f"{int(total_cavas)}" + '''</div>
        </div>
        ''', unsafe_allow_html=True)

    with cols[3]:
        st.markdown('''
        <div class="metric-card">
            <div class="metric-title">Percentual</div>
            <div class="metric-value">''' + f"{porcentagem:.1f}%" + '''</div>
        </div>
        ''', unsafe_allow_html=True)

    # Gráficos
    col_graficos1, col_graficos2 = st.columns([3, 1])

    with col_graficos1:
        if colunas['equipes'] and colunas['postes_previstos'] and colunas['postes_implantados']:
            st.subheader("Progresso Consolidado por Equipe")
            
            agregações = {
                colunas['postes_previstos']: 'sum',
                colunas['postes_implantados']: 'sum'
            }
            
            if colunas['cavas']:
                agregações[colunas['cavas']] = 'sum'
            
            df_agrupado = df_filtrado.groupby(colunas['equipes']).agg(agregações).reset_index()

            df_melted = df_agrupado.melt(
                id_vars=[colunas['equipes']], 
                value_vars=list(agregações.keys()),
                var_name='Métrica', 
                value_name='Quantidade'
            )

            color_map = {
                colunas['postes_previstos']: "#1522D6",
                colunas['postes_implantados']: "#FFD000",
                colunas['cavas']: "#FFFFFF" if colunas['cavas'] else None
            }
            color_map = {k: v for k, v in color_map.items() if v is not None}

            fig = px.bar(
                df_melted,
                x=colunas['equipes'],
                y='Quantidade',
                color='Métrica',
                barmode='group',
                color_discrete_map=color_map,
                height=500,
                text='Quantidade'
            )
            
            fig.update_traces(
                marker_line_width=1,
                marker_line_color='white',
                textposition='outside',
                textfont_size=12,
                textfont_color='white',
                textangle=0,
                cliponaxis=False
            )
            
            fig.update_layout(
                xaxis_title='Equipes',
                yaxis_title='Quantidade',
                legend_title='Métrica',
                margin=dict(l=0, r=0, b=0, t=50, pad=20),
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                uniformtext_minsize=8,
                uniformtext_mode='hide',
                xaxis={'categoryorder':'total descending'},
                yaxis={'range': [0, df_melted['Quantidade'].max() * 1.2]},
                shapes=[{
                    'type': 'rect',
                    'xref': 'paper',
                    'yref': 'paper',
                    'x0': 0,
                    'y0': 0,
                    'x1': 1,
                    'y1': 1,
                    'line': {
                        'color': 'white',
                        'width': 1,
                    },
                }]
            )
            
            st.plotly_chart(fig, use_container_width=True)

    with col_graficos2:
        st.subheader("Percentual de Implantação")
        
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=porcentagem,
            number={'suffix': '%', 'font': {'size': 40}},
            domain={'x': [0, 1], 'y': [0, 1]},
            gauge={
                'axis': {'range': [0, 100], 'tickvals': [0, 50, 100], 'ticktext': ['0%', '50%', '100%']},
                'bar': {'color': "#FFFFFF"},
                'steps': [
                    {'range': [0, 50], 'color': "#eb4836"},
                    {'range': [50, 75], 'color': "#eb8736"},
                    {'range': [75, 100], 'color': "#07a302"}],
                'threshold': {
                    'line': {'color': "black", 'width': 4},
                    'thickness': 0.75,
                    'value': porcentagem}
            }
        ))
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    # Mapa Interativo
    if all([colunas['latitude'], colunas['longitude'], colunas['situacao']]):
        st.subheader("Mapa de Obras - Região de Irecê")
        
        lat_irece = -11.3022176
        lon_irece = -41.8476563
        
        df_mapa = df_filtrado.dropna(subset=[colunas['latitude'], colunas['longitude']]).copy()
        
        df_mapa[colunas['latitude']] = pd.to_numeric(df_mapa[colunas['latitude']], errors='coerce')
        df_mapa[colunas['longitude']] = pd.to_numeric(df_mapa[colunas['longitude']], errors='coerce')
        df_mapa = df_mapa.dropna(subset=[colunas['latitude'], colunas['longitude']])
        
        df_mapa = df_mapa[
            (df_mapa[colunas['latitude']] >= -33.5) & (df_mapa[colunas['latitude']] <= 5.5) &
            (df_mapa[colunas['longitude']] >= -74.0) & (df_mapa[colunas['longitude']] <= -34.0)
        ]
        
        if not df_mapa.empty:
            mapa = folium.Map(
                location=[lat_irece, lon_irece],
                zoom_start=7.5,
                tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
                attr='Google Maps'
            )
            
            marker_cluster = MarkerCluster().add_to(mapa)
            
            for _, row in df_mapa.iterrows():
                try:
                    lat = float(row[colunas['latitude']])
                    lon = float(row[colunas['longitude']])
                    
                    if not np.isnan(lat) and not np.isnan(lon):
                        situacao = str(row[colunas['situacao']]).upper()
                        cor = 'green' if 'ENERGIZADA' in situacao else 'red'
                        
                        tooltip_text = f"""
                        <div style="font-family: Arial; font-size: 12px">
                            <b>Base da Obra:</b> {row[colunas['base_obra']] if colunas['base_obra'] and pd.notna(row[colunas['base_obra']]) else 'N/A'}<br>
                            <b>Município:</b> {row[colunas['municipio']] if colunas['municipio'] and pd.notna(row[colunas['municipio']]) else 'N/A'}<br>
                            <b>Postes Previstos:</b> {row[colunas['postes_previstos']] if 'postes_previstos' in colunas and pd.notna(row[colunas['postes_previstos']]) else 'N/A'}<br>
                            <b>Postes Implantados:</b> {row[colunas['postes_implantados']] if 'postes_implantados' in colunas and pd.notna(row[colunas['postes_implantados']]) else 'N/A'}<br>
                            <b>Cavas Realizadas:</b> {row[colunas['cavas']] if 'cavas' in colunas and pd.notna(row[colunas['cavas']]) else 'N/A'}<br>
                            <hr style="margin: 5px 0;">
                            <b>Situação:</b> {row[colunas['situacao']] if colunas['situacao'] and pd.notna(row[colunas['situacao']]) else 'N/A'}
                        </div>
                        """
                        
                        folium.Marker(
                            location=[lat, lon],
                            popup=tooltip_text,
                            icon=folium.Icon(color=cor, icon='bolt' if cor == 'green' else 'exclamation-triangle'),
                            tooltip=folium.Tooltip(tooltip_text, sticky=True)
                        ).add_to(marker_cluster)
                except:
                    continue
            
            st_folium(mapa, width=1955, height=600, returned_objects=[])
        else:
            st.warning("Nenhuma coordenada válida encontrada para exibir o mapa após a filtragem")
    else:
        st.warning("Dados de mapa não disponíveis (necessárias colunas LATITUDE, LONGITUDE e SITUAÇÃO)")

    # RELATÓRIO DE RENDIMENTO DIÁRIO
    if df_json is not None and not df_json.empty:
        st.subheader("📊 Relatório de Rendimento Diário")
        
        col_json_config = {
            'data': encontrar_coluna(df_json, ['DATA', 'DIA']),
            'supervisor': encontrar_coluna(df_json, ['SUPERVISOR', 'RESPONSAVEL']),
            'encarregado': encontrar_coluna(df_json, ['ENCARREGADO', 'LIDER']),
            'projeto': encontrar_coluna(df_json, ['PROJETO', 'CODIGO']),
            'titulo': encontrar_coluna(df_json, ['TITULO', 'NOME', 'OBRA']),
            'municipio': encontrar_coluna(df_json, ['MUNICÍPIO', 'MUNICIPIO', 'CIDADE']),
            'atividade': encontrar_coluna(df_json, ['ATIVIDADE PROGRAMADA', 'ATIVIDADE']),
            'locacao': encontrar_coluna(df_json, ['LOCAÇÃO', 'LOC']),
            'cava_prev': encontrar_coluna(df_json, ['CAV PREV', 'CAVA PREVISTA']),
            'cava_real': encontrar_coluna(df_json, ['CAVA REAL', 'CAVA EXECUTADA']),
            'poste_prev': encontrar_coluna(df_json, ['POSTE PREV', 'POSTE PREVISTO']),
            'poste_real': encontrar_coluna(df_json, ['POSTE REAL', 'POSTE EXECUTADO']),
            'total_poste': encontrar_coluna(df_json, ['TOTAL POSTE', 'TOTAL_POSTES']),
            'justificativa': encontrar_coluna(df_json, ['JUSTIFICATIVA', 'OBS']),
            'equipes': encontrar_coluna(df_json, ['ENCARREGADO', 'ENCARREGADOS']),
            'base_obra': encontrar_coluna(df_json, ['BASE DA OBRA', 'BASE_OBRA']),
            'mes': encontrar_coluna(df_json, ['MÊS', 'MES', 'PERIODO'])
        }
        
        # Aplicar os filtros principais
        df_json_filtrado = aplicar_filtros(df_json, col_json_config, filtros)
        
        # Filtro de período específico para o relatório diário
        if col_json_config['data']:
            # Converter coluna de data para datetime
            df_json_filtrado[col_json_config['data']] = pd.to_datetime(df_json_filtrado[col_json_config['data']], dayfirst=True, errors='coerce')
            
            # Remover linhas com datas inválidas
            df_json_filtrado = df_json_filtrado.dropna(subset=[col_json_config['data']])
            
            # Definir opções de período
            opcoes_periodo = {
                "Hoje": 1,
                "Ontem": 2,
                "Anteontem": 3,
                "Ultimos 4 dias": 4,
                "Últimos 7 dias": 7,
                "Últimos 14 dias": 14,
                "Este mês": 30,
                "Todos os registros": 0
            }
            
            # Criar seletor de período
            periodo_selecionado = st.selectbox(
                "Selecione o período para o relatório diário:",
                options=list(opcoes_periodo.keys()),
                index=0  # Padrão: "Hoje"
            )
            
            # Aplicar filtro de data conforme seleção
            hoje = datetime.now().date()
            
            if periodo_selecionado != "Todos os registros":
                dias = opcoes_periodo[periodo_selecionado]
                
                if periodo_selecionado == "Este mês":
                    # Filtrar para o mês atual
                    df_json_filtrado = df_json_filtrado[
                        (df_json_filtrado[col_json_config['data']].dt.month == hoje.month) &
                        (df_json_filtrado[col_json_config['data']].dt.year == hoje.year)
                    ]
                else:
                    # Filtrar pelos últimos X dias
                    data_inicial = hoje - timedelta(days=dias-1)
                    df_json_filtrado = df_json_filtrado[
                        (df_json_filtrado[col_json_config['data']].dt.date >= data_inicial)
                    ]
        
        if None in [col_json_config['atividade'], col_json_config['total_poste']]:
            st.error("Colunas essenciais não encontradas no JSON")
        else:
            colunas_relatorio = [
                col_json_config['data'], col_json_config['supervisor'], col_json_config['encarregado'],
                col_json_config['projeto'], col_json_config['titulo'], col_json_config['municipio'],
                col_json_config['atividade'], col_json_config['total_poste']
            ]
            
            for col in ['locacao', 'cava_prev', 'cava_real', 'poste_prev', 'poste_real', 'justificativa']:
                if col_json_config.get(col):
                    colunas_relatorio.append(col_json_config[col])
            
            df_relatorio = df_json_filtrado[colunas_relatorio].copy()
            
            if col_json_config['data']:
                try:
                    df_relatorio[col_json_config['data']] = pd.to_datetime(df_relatorio[col_json_config['data']], dayfirst=True)
                except:
                    pass
            
            for col in ['locacao', 'cava_prev', 'cava_real', 'poste_prev', 'poste_real', 'total_poste']:
                if col_json_config.get(col):
                    df_relatorio[col_json_config[col]] = pd.to_numeric(df_relatorio[col_json_config[col]], errors='coerce').fillna(0).astype(int)
            
            # AGORA CHAMA A FUNÇÃO CORRETA passando col_json_config
            df_relatorio['RENDIMENTO %'] = df_relatorio.apply(
                lambda row: calcular_rendimento(row, col_json_config), 
                axis=1
            ).round(1)
            
            df_relatorio = df_relatorio.sort_values(col_json_config['data'], ascending=False)
            
            def colorir_linhas(row):
                rendimento = row.get('RENDIMENTO %', 0)
                return ['background-color: #F22C2F'] * len(row) if rendimento < 50 else [''] * len(row)

            styled_df = df_relatorio.style.apply(colorir_linhas, axis=1)
            styled_df = styled_df.set_properties(**{
                'text-align': 'center',
                'font-size': '12px'
            }).set_table_styles([{
                'selector': 'th',
                'props': [('background-color', '#2c3e50'), ('color', 'white')]
            }])

            st.dataframe(
                styled_df,
                height=600,
                use_container_width=True,
                column_config={
                    col_json_config['data']: st.column_config.DateColumn("DATA", format="DD/MM/YYYY"),
                    "RENDIMENTO %": st.column_config.ProgressColumn(
                        "RENDIMENTO %",
                        format="%.1f%%",
                        min_value=0,
                        max_value=100,
                        help="Percentual de rendimento da atividade"
                    )
                },
                hide_index=True
            )
    else:
        st.warning("Nenhum dado disponível no relatório diário (bd.json)")
    
    # Seção de carreteiros
    carreteiros_section()

if __name__ == "__main__":
    main()