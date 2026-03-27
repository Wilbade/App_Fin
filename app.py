import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import google.generativeai as genai
from PIL import Image
import json

# Configuração da página
st.set_page_config(page_title="Gestão Wil & Ju", layout="wide")

# Conexão Supabase
@st.cache_resource
def init_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# Configuração Gemini
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except:
    st.error("Erro ao carregar IA")

st.title("💰 Gestão Financeira Mensal")

# --- SELEÇÃO DE MÊS E ANO (FILTRO GLOBAL) ---
col_m1, col_m2 = st.columns(2)
with col_m1:
    meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    mes_nome = st.selectbox("Selecione o Mês:", meses, index=datetime.now().month - 1)
    mes_num = meses.index(mes_nome) + 1
with col_m2:
    ano = st.number_input("Ano:", value=2025, step=1)

# --- ABAS ---
aba1, aba2 = st.tabs(["📊 Visão Mensal", "📸 Escanear Recibo"])

with aba1:
    st.header(f"Resumo de {mes_nome} / {ano}")
    
    # --- ÁREA DE RENDAS ---
    with st.expander("💵 Rendas deste Mês (Fixa + Extra)", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Wil")
            f_wil = st.number_input("Salário (Wil)", value=0.0, key="fw")
            e_wil = st.number_input("Extra (Wil)", value=0.0, key="ew")
        with c2:
            st.subheader("Ju")
            f_ju = st.number_input("Salário (Ju)", value=0.0, key="fj")
            e_ju = st.number_input("Extra (Ju)", value=0.0, key="ej")
        renda_mes = f_wil + e_wil + f_ju + e_ju

    # --- BUSCA E FILTRO DE DADOS ---
    res = supabase.table("transacoes").select("*").execute()
    df = pd.DataFrame(res.data)

    if not df.empty:
        # Converte a coluna data para formato de data real do Python
        df['data'] = pd.to_datetime(df['data'])
        
        # FILTRO MÁGICO: Filtra apenas o mês e ano selecionados
        df_mes = df[(df['data'].dt.month == mes_num) & (df['data'].dt.year == ano)]
        
        if not df_mes.empty:
            gasto_wil = df_mes[df_mes["user_id"] == "wil"]["valor_planeado"].sum()
            gasto_ju = df_mes[df_mes["user_id"] == "ju"]["valor_planeado"].sum()
            total_gastos = gasto_wil + gasto_ju
            sobra = renda_mes - total_gastos

            # --- CARTOES ---
            st.divider()
            m1, m2, m3 = st.columns(3)
            m1.metric("Renda Total", f"R$ {renda_mes:,.2f}")
            m2.metric("Total Despesas", f"R$ {total_gastos:,.2f}")
            m3.metric("Sobrou no Mês", f"R$ {sobra:,.2f}", delta=f"{sobra:,.2f}")

            st.divider()
            st.subheader(f"Detalhamento de Gastos: {mes_nome}")
            graf_data = df_mes.groupby(["categoria", "user_id"])["valor_planeado"].sum().unstack().fillna(0)
            st.bar_chart(graf_data)
            
            st.write("### Lista de Despesas do Mês")
            st.dataframe(df_mes[["data", "user_id", "categoria", "subcategoria", "valor_planeado"]], use_container_width=True)
        else:
            st.info(f"Não há despesas lançadas para {mes_nome} de {ano}.")
    else:
        st.warning("Banco de dados vazio.")

with aba2:
    st.header("👤 Novo Gasto com Foto")
    user = st.selectbox("Lançar para:", ["wil", "ju"])
    up = st.file_uploader("Foto do recibo", type=["jpg", "png", "jpeg"])
    if up:
        img = Image.open(up)
        st.image(img, width=250)
        if st.button("Analisar Recibo"):
            with st.spinner("IA lendo..."):
                prompt = "Extraia categoria e valor total deste recibo em JSON: {'categoria': '', 'valor': 0.0}"
                response = model.generate_content([prompt, img])
                st.write("Resultado da IA:", response.text)
