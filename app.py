import streamlit as st
import pandas as pd
import json
from supabase import create_client, Client
import google.generativeai as genai
from PIL import Image

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

st.title("💰 Gestão Financeira Family")

# --- ABAS ---
aba1, aba2 = st.tabs(["📊 Visão Geral da Casa", "📸 Lançar Recibos (IA)"])

with aba1:
    st.header("Resumo de Rendas e Gastos")
    
    # --- ÁREA DE RENDAS (MALEÁVEL) ---
    with st.expander("💵 Configurar Rendas deste Mês", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Wil")
            fixa_wil = st.number_input("Salário Fixo (Wil)", value=0.0, step=100.0)
            extra_wil = st.number_input("Renda Extra (Wil)", value=0.0, step=50.0)
        with col2:
            st.subheader("Ju")
            fixa_ju = st.number_input("Salário Fixo (Ju)", value=0.0, step=100.0)
            extra_ju = st.number_input("Renda Extra (Ju)", value=0.0, step=50.0)
        
        renda_total = fixa_wil + extra_wil + fixa_ju + extra_ju
    
    # --- BUSCA DADOS NO SUPABASE ---
    res = supabase.table("transacoes").select("*").execute()
    df = pd.DataFrame(res.data)
    
    if not df.empty:
        gasto_wil = df[df["user_id"] == "wil"]["valor_planeado"].sum()
        gasto_ju = df[df["user_id"] == "ju"]["valor_planeado"].sum()
        total_gastos = gasto_wil + gasto_ju
        saldo_final = renda_total - total_gastos

        # --- CARTOES DE RESULTADO ---
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Renda Total", f"R$ {renda_total:,.2f}")
        c2.metric("Total Gastos", f"R$ {total_gastos:,.2f}", delta=f"-{total_gastos:,.2f}", delta_color="inverse")
        c3.metric("Saldo Sobrando", f"R$ {saldo_final:,.2f}", delta=f"{saldo_final:,.2f}")
        c4.write("✅ Dados atualizados do Supabase")

        st.divider()
        st.subheader("Gráfico Comparativo por Categoria")
        # Prepara dados para o gráfico comparando Wil e Ju por categoria
        graf_data = df.groupby(["categoria", "user_id"])["valor_planeado"].sum().unstack().fillna(0)
        st.bar_chart(graf_data)
    else:
        st.warning("Ainda não existem transações no banco de dados.")

with aba2:
    st.header("👤 Área do Usuário & Recibos")
    usuario = st.selectbox("Quem está lançando?", ["wil", "ju"])
    
    uploaded_file = st.file_uploader("Subir foto do recibo", type=["jpg", "png", "jpeg"])
    if uploaded_file:
        img = Image.open(uploaded_file)
        st.image(img, width=250)
        if st.button("Escanear com IA"):
            with st.spinner("IA analisando..."):
                prompt = "Extraia categoria e valor total deste recibo em JSON: {'categoria': '', 'valor': 0.0}"
                response = model.generate_content([prompt, img])
                st.write(response.text) # Mostra o resultado da leitura
