import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import google.generativeai as genai
from PIL import Image
import json

# Configuração da página
st.set_page_config(page_title="Gestão Financeira Histórica", layout="wide", page_icon="💰")

# --- CONEXÃO SUPABASE ---
@st.cache_resource
def init_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- CONFIGURAÇÃO GEMINI 2.5 ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-2.5-flash')
except Exception as e:
    st.error(f"Erro ao carregar IA: {e}")

st.title("💰 Sistema de Gestão Financeira Wil & Ju")

# --- SELEÇÃO DE MÊS E ANO (FILTRO GLOBAL) ---
# Este filtro define onde os dados serão visualizados e ONDE serão salvos
col_m1, col_m2 = st.columns(2)
with col_m1:
    meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    mes_nome = st.selectbox("Selecione o Mês para Visualizar/Lançar:", meses, index=datetime.now().month - 1)
    mes_num = meses.index(mes_nome) + 1
with col_m2:
    ano = st.number_input("Ano:", value=2026, step=1)

# --- ABAS ---
aba1, aba2 = st.tabs(["📊 Painel de Controle", "📸 Escanear Recibo"])

with aba1:
    # --- ÁREA DE RENDAS (Fixas Sugeridas) ---
    with st.expander("💵 Configuração de Renda do Mês", expanded=True):
        st.info("Os valores abaixo são sugeridos com base na sua planilha, mas você pode alterá-los.")
        c1, c2 = st.columns(2)
        with c1:
            f_wil = st.number_input("Salário Wil (Fixo)", value=5500.0)
            e_wil = st.number_input("Extra Wil", value=0.0)
        with c2:
            f_ju = st.number_input("Salário Ju (Fixo)", value=5500.0)
            e_ju = st.number_input("Extra Ju", value=0.0)
        
        renda_total_mes = f_wil + e_wil + f_ju + e_ju

    # --- PROCESSAMENTO DE DADOS ---
    try:
        res = supabase.table("transacoes").select("*").execute()
        df = pd.DataFrame(res.data)

        if not df.empty:
            df['data'] = pd.to_datetime(df['data'])
            
            # 1. Filtro do Mês Selecionado
            df_mes = df[(df['data'].dt.month == mes_num) & (df['data'].dt.year == ano)]
            
            # 2. Acumulado Histórico (Desde 2014 até o infinito)
            # Soma todas as despesas já registradas no banco
            total_historico_despesas = df["valor_planeado"].sum()
            
            # 3. Cálculos do Mês Selecionado
            total_gastos_mes = df_mes["valor_planeado"].sum()
            sobra_mes = renda_total_mes - total_gastos_mes

            # --- CARTOES DE MÉTRICA ---
            st.divider()
            m1, m2, m3, m4 = st.columns(4)
            m1.metric(f"Renda {mes_nome}", f"R$ {renda_total_mes:,.2f}")
            m2.metric(f"Gastos {mes_nome}", f"R$ {total_gastos_mes:,.2f}")
            m3.metric("Saldo do Mês", f"R$ {sobra_mes:,.2f}", delta=f"{sobra_mes:,.2f}")
            m4.metric("TOTAL GASTO HISTÓRICO", f"R$ {total_historico_despesas:,.2f}", help="Soma de todos os lançamentos desde 2014")

            st.divider()
            
            if not df_mes.empty:
                st.subheader(f"Listagem de Gastos: {mes_nome} / {ano}")
                st.dataframe(df_mes[["data", "user_id", "categoria", "subcategoria", "valor_planeado"]], use_container_width=True)
                
                # Gráfico de Categorias
                st.write("### Gastos por Categoria")
                graf_data = df_mes.groupby("categoria")["valor_planeado"].sum()
                st.bar_chart(graf_data)
            else:
                st.info(f"Nenhum lançamento encontrado para {mes_nome} de {ano}.")
        else:
            st.warning("O Banco de dados está vazio. Comece a importar seus dados de 2014!")

    except Exception as e:
        st.error(f"Erro ao conectar com o banco: {e}")

with aba2:
    st.header("📸 Scanner de Recibos")
    user_scan = st.radio("Registrar para:", ["wil", "ju"], horizontal=True)
    up = st.file_uploader("Arraste a foto do recibo", type=["jpg", "png", "jpeg"])
    
    if up:
        img = Image.open(up)
        st.image(img, width=300)
        
        if st.button("Analisar Recibo"):
            with st.spinner("O Gemini 2.5 está lendo a nota..."):
                try:
                    prompt = "Extraia valor e local. Retorne JSON: {'categoria': '', 'valor': 0.0, 'local': ''}"
                    response = model.generate_content([prompt, img])
                    res_text = response.text.replace('```json', '').replace('```', '').strip()
                    st.session_state['dados_scan'] = json.loads(res_text)
                    st.success("Leitura concluída!")
                    st.json(st.session_state['dados_scan'])
                except Exception as e:
                    st.error(f"Erro na IA: {e}")

        if 'dados_scan' in st.session_state:
            if st.button("Confirmar e Salvar no Banco"):
                dados = st.session_state['dados_scan']
                # A data é salva no mês/ano que você escolheu no seletor do topo!
                data_para_banco = f"{ano}-{mes_num:02d}-01"
                
                payload = {
                    "user_id": user_scan,
                    "categoria": dados.get('categoria', 'Outros'),
                    "valor_planeado": float(dados.get('valor', 0)),
                    "subcategoria": dados.get('local', 'Scanner'),
                    "data": data_para_banco
                }
                
                supabase.table("transacoes").insert(payload).execute()
                st.success(f"Lançamento salvo com sucesso em {mes_nome}/{ano}!")
                del st.session_state['dados_scan']
                st.cache_resource.clear()
