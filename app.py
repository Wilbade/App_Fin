import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import google.generativeai as genai
from PIL import Image
import json

# Configuração da página
st.set_page_config(page_title="Gestão Wil & Ju", layout="wide", page_icon="💰")

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

st.title("💰 Sistema Financeiro - Wil & Ju")

# --- FILTRO GLOBAL ---
col_m1, col_m2 = st.columns(2)
with col_m1:
    meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    mes_nome = st.selectbox("Mês para Visualizar:", meses, index=datetime.now().month - 1)
    mes_num = meses.index(mes_nome) + 1
with col_m2:
    ano = st.number_input("Ano:", value=2026, step=1)

aba1, aba2 = st.tabs(["📊 Painel Histórico", "📸 Escanear Recibo"])

with aba1:
    # --- RENDAS FIXAS ---
    with st.expander("💵 Rendas do Mês", expanded=False):
        c1, c2 = st.columns(2)
        f_wil = c1.number_input("Salário Wil", value=5500.0)
        f_ju = c2.number_input("Salário Ju", value=5500.0)
        renda_total_mes = f_wil + f_ju

    try:
        res = supabase.table("transacoes").select("*").execute()
        df = pd.DataFrame(res.data)
        if not df.empty:
            df['data'] = pd.to_datetime(df['data'])
            df_mes = df[(df['data'].dt.month == mes_num) & (df['data'].dt.year == ano)]
            total_gasto_mes = df_mes["valor_planeado"].sum()
            
            m1, m2, m3 = st.columns(3)
            m1.metric(f"Gasto {mes_nome}", f"R$ {total_gasto_mes:,.2f}")
            m2.metric("Saldo", f"R$ {(renda_total_mes - total_gasto_mes):,.2f}")
            m3.metric("Acumulado Geral", f"R$ {df['valor_planeado'].sum():,.2f}")

            st.divider()
            if not df_mes.empty:
                df_exibir = df_mes.copy().sort_values(by="data")
                df_exibir['data'] = df_exibir['data'].dt.strftime('%d/%m/%Y')
                st.dataframe(df_exibir[["data", "user_id", "categoria", "subcategoria", "valor_planeado"]], use_container_width=True)
    except: st.warning("Erro ao carregar banco.")

with aba2:
    st.header("📸 Scanner com Edição")
    user_scan = st.radio("Responsável:", ["wil", "ju"], horizontal=True)
    up = st.file_uploader("Foto do recibo", type=["jpg", "png", "jpeg"])
    
    if up:
        img = Image.open(up)
        st.image(img, width=250)
        
        if st.button("1. Analisar com IA"):
            with st.spinner("IA lendo..."):
                prompt = """Retorne APENAS um JSON: {"valor": 0.0, "local": "nome loja", "categoria": "Lazer", "data_recibo": "YYYY-MM-DD"}"""
                response = model.generate_content([prompt, img])
                st.session_state['temp_dados'] = json.loads(response.text.replace('```json', '').replace('```', '').strip())

        # --- CAMPOS DE EDIÇÃO (O que tu pediste) ---
        if 'temp_dados' in st.session_state:
            st.divider()
            st.subheader("2. Confira e Edite os dados:")
            dados = st.session_state['temp_dados']
            
            # Criamos campos de entrada com os dados que a IA leu
            ed_data = st.date_input("Data do Recibo:", value=datetime.strptime(dados.get('data_recibo', f"{ano}-{mes_num:02d}-01"), "%Y-%m-%d"))
            ed_local = st.text_input("Subcategoria (Local/Item):", value=dados.get('local', ''))
            ed_cat = st.text_input("Categoria:", value=dados.get('categoria', 'Outros'))
            ed_val = st.number_input("Valor (R$):", value=float(dados.get('valor', 0.0)))

            if st.button("3. Confirmar e Salvar no Supabase"):
                payload = {
                    "user_id": user_scan,
                    "categoria": ed_cat,
                    "valor_planeado": ed_val,
                    "subcategoria": ed_local,
                    "data": ed_data.strftime("%Y-%m-%d")
                }
                supabase.table("transacoes").insert(payload).execute()
                st.success("Salvo com sucesso!")
                st.balloons()
                del st.session_state['temp_dados']
                st.cache_resource.clear()
