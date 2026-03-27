import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import google.generativeai as genai
from PIL import Image
import json
import plotly.express as px # Biblioteca para gráficos bonitos

# Configuração da página
st.set_page_config(page_title="Gestão Wil & Ju", layout="wide", page_icon="💰")

# --- CONEXÃO SUPABASE ---
@st.cache_resource
def init_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- CONFIGURAÇÃO GEMINI ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # Voltando para a versão que você confirmou que funciona
    model = genai.GenerativeModel('gemini-2.0-flash') # Tente 2.0 ou 2.5 conforme sua conta permitir
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
    ano = st.number_input("Ano:", value=2025, step=1) # Ajustado para 2025 como padrão

aba1, aba2 = st.tabs(["📊 Painel Histórico", "📸 Escanear Recibo"])

with aba1:
    # --- RENDAS FIXAS ---
    with st.expander("💵 Rendas do Mês", expanded=False):
        c1, c2 = st.columns(2)
        f_wil = c1.number_input("Salário Wil", value=5500.0)
        f_ju = c2.number_input("Salário Ju", value=5500.0)
        renda_total_mes = f_wil + f_ju

    try:
        # Puxando dados do Supabase
        res = supabase.table("transacoes").select("*").execute()
        df = pd.DataFrame(res.data)
        
        if not df.empty:
            df['data'] = pd.to_datetime(df['data'])
            # Filtro do mês e ano selecionado
            df_mes = df[(df['data'].dt.month == mes_num) & (df['data'].dt.year == ano)]
            
            # --- MÉTRICAS ---
            total_gasto_mes = df_mes["valor_planeado"].sum() if not df_mes.empty else 0
            
            m1, m2, m3 = st.columns(3)
            m1.metric(f"Gasto {mes_nome}", f"R$ {total_gasto_mes:,.2f}")
            m2.metric("Saldo", f"R$ {(renda_total_mes - total_gasto_mes):,.2f}", delta_color="normal")
            m3.metric("Acumulado Geral", f"R$ {df['valor_planeado'].sum():,.2f}")

            st.divider()

            if not df_mes.empty:
                # --- ÁREA DE GRÁFICOS ---
                g1, g2 = st.columns(2)
                
                with g1:
                    st.subheader("Gastos por Categoria")
                    fig_cat = px.pie(df_mes, names='categoria', values='valor_planeado', hole=0.4)
                    st.plotly_chart(fig_cat, use_container_width=True)
                
                with g2:
                    st.subheader("Quem gastou mais?")
                    fig_user = px.bar(df_mes.groupby('user_id')['valor_planeado'].sum().reset_index(), 
                                     x='user_id', y='valor_planeado', color='user_id')
                    st.plotly_chart(fig_user, use_container_width=True)

                st.subheader("📋 Detalhes das Transações")
                df_exibir = df_mes.copy().sort_values(by="data", ascending=False)
                df_exibir['data'] = df_exibir['data'].dt.strftime('%d/%m/%Y')
                st.dataframe(df_exibir[["data", "user_id", "categoria", "subcategoria", "valor_planeado"]], use_container_width=True)
            else:
                st.info(f"Nenhum dado encontrado para {mes_nome} de {ano}")
                
    except Exception as e: 
        st.error(f"Erro ao carregar banco: {e}")

with aba2:
    st.header("📸 Scanner com Edição")
    user_scan = st.radio("Responsável:", ["wil", "ju"], horizontal=True)
    up = st.file_uploader("Foto do recibo", type=["jpg", "png", "jpeg"])
    
    if up:
        img = Image.open(up)
        st.image(img, width=250)
        
        if st.button("1. Analisar com IA"):
            with st.spinner("IA lendo..."):
                try:
                    prompt = """Retorne APENAS um JSON: {"valor": 0.0, "local": "nome loja", "categoria": "Lazer", "data_recibo": "YYYY-MM-DD"}"""
                    response = model.generate_content([prompt, img])
                    # Limpeza de possíveis markdown na resposta da IA
                    texto_limpo = response.text.replace('```json', '').replace('```', '').strip()
                    st.session_state['temp_dados'] = json.loads(texto_limpo)
                except Exception as e:
                    st.error(f"Erro ao processar imagem: {e}")

        if 'temp_dados' in st.session_state:
            st.divider()
            st.subheader("2. Confira e Edite os dados:")
            dados = st.session_state['temp_dados']
            
            ed_data = st.date_input("Data do Recibo:", value=datetime.strptime(dados.get('data_recibo', datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d"))
            ed_local = st.text_input("Subcategoria (Local/Item):", value=dados.get('local', ''))
            ed_cat = st.selectbox("Categoria:", ["Alimentação", "Lazer", "Transporte", "Casa", "Saúde", "Outros"], index=5)
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
                st.rerun() # Atualiza a tela para mostrar os novos dados no gráfico
