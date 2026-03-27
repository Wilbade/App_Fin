import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import google.generativeai as genai
from PIL import Image
import json
import re

# Configuração da página
st.set_page_config(page_title="Gestão Wil & Ju", layout="wide", page_icon="💰")

# --- CONEXÃO SUPABASE ---
@st.cache_resource
def init_supabase() -> Client:
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as e:
        st.error(f"Erro ao conectar ao Supabase: {e}")
        return None

supabase = init_supabase()

# --- CONFIGURAÇÃO GEMINI ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # Corrigido para gemini-1.5-flash (versão estável atual)
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"Erro ao carregar IA: {e}")

# --- FUNÇÕES AUXILIARES ---
def extrair_json(texto):
    """Extrai o JSON de dentro de possíveis marcações de markdown da IA"""
    try:
        # Busca conteúdo entre chaves { }
        match = re.search(r"\{.*\}", texto, re.DOTALL)
        if match:
            return json.loads(match.group())
        return json.loads(texto)
    except:
        return None

# --- UI ---
st.title("💰 Sistema Financeiro - Wil & Ju")

# --- FILTRO GLOBAL ---
col_m1, col_m2 = st.columns(2)
with col_m1:
    meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    mes_nome = st.selectbox("Mês para Visualizar:", meses, index=datetime.now().month - 1)
    mes_num = meses.index(mes_nome) + 1
with col_m2:
    ano = st.number_input("Ano:", value=datetime.now().year, step=1)

aba1, aba2 = st.tabs(["📊 Painel Histórico", "📸 Escanear Recibo"])

with aba1:
    # --- RENDAS FIXAS ---
    with st.expander("💵 Configuração de Rendas", expanded=False):
        c1, c2 = st.columns(2)
        f_wil = c1.number_input("Salário Wil", value=5500.0, step=100.0)
        f_ju = c2.number_input("Salário Ju", value=5500.0, step=100.0)
        renda_total_mes = f_wil + f_ju

    # --- BUSCA DE DADOS ---
    try:
        # Filtro direto no banco (Performance)
        data_inicio = f"{ano}-{mes_num:02d}-01"
        # Simplificando a busca: pegamos tudo do mês/ano filtrado
        res = supabase.table("transacoes").select("*").execute()
        
        if res.data:
            df_geral = pd.DataFrame(res.data)
            df_geral['data'] = pd.to_datetime(df_geral['data'])
            
            # Filtro Pandas para o dashboard mensal
            df_mes = df_geral[(df_geral['data'].dt.month == mes_num) & (df_geral['data'].dt.year == ano)]
            
            total_gasto_mes = df_mes["valor_planeado"].sum() if not df_mes.empty else 0.0
            
            m1, m2, m3 = st.columns(3)
            m1.metric(f"Gasto {mes_nome}", f"R$ {total_gasto_mes:,.2f}")
            m2.metric("Saldo Restante", f"R$ {(renda_total_mes - total_gasto_mes):,.2f}")
            m3.metric("Total Histórico", f"R$ {df_geral['valor_planeado'].sum():,.2f}")

            st.divider()
            if not df_mes.empty:
                df_exibir = df_mes.copy().sort_values(by="data", ascending=False)
                df_exibir['data'] = df_exibir['data'].dt.strftime('%d/%m/%Y')
                st.dataframe(
                    df_exibir[["data", "user_id", "categoria", "subcategoria", "valor_planeado"]], 
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info(f"Nenhum registro encontrado para {mes_nome}/{ano}")
    except Exception as e:
        st.error(f"Erro ao carregar banco: {e}")

with aba2:
    st.header("📸 Scanner de Recibos")
    user_scan = st.radio("Responsável pelo gasto:", ["wil", "ju"], horizontal=True)
    up = st.file_uploader("Upload do Recibo (Imagem)", type=["jpg", "png", "jpeg"])
    
    if up:
        img = Image.open(up)
        st.image(img, caption="Recibo carregado", width=300)
        
        if st.button("🚀 Analisar com Inteligência Artificial"):
            with st.spinner("IA processando a imagem..."):
                prompt = """
                Analise este recibo e extraia os dados.
                Retorne APENAS um JSON no formato:
                {"valor": 0.0, "local": "nome da loja", "categoria": "Alimentação/Lazer/Transporte/etc", "data_recibo": "YYYY-MM-DD"}
                Se não encontrar a data, use a data de hoje.
                """
                try:
                    response = model.generate_content([prompt, img])
                    dados_ia = extrair_json(response.text)
                    
                    if dados_ia:
                        st.session_state['temp_dados'] = dados_ia
                        st.success("Análise concluída!")
                    else:
                        st.error("A IA não conseguiu formatar os dados corretamente. Tente novamente.")
                except Exception as e:
                    st.error(f"Erro na IA: {e}")

        # --- CAMPOS DE EDIÇÃO ---
        if 'temp_dados' in st.session_state:
            st.divider()
            st.subheader("📝 Validar Dados")
            dados = st.session_state['temp_dados']
            
            # Lista de categorias padrão para manter organização
            lista_cats = ["Alimentação", "Lazer", "Saúde", "Transporte", "Casa", "Educação", "Outros"]
            cat_index = lista_cats.index(dados.get('categoria')) if dados.get('categoria') in lista_cats else 6

            c_ed1, c_ed2 = st.columns(2)
            with c_ed1:
                ed_data = st.date_input("Data do Recibo:", value=pd.to_datetime(dados.get('data_recibo', datetime.now())).date())
                ed_local = st.text_input("Local/Item (Subcategoria):", value=dados.get('local', ''))
            with c_ed2:
                ed_cat = st.selectbox("Categoria:", options=lista_cats, index=cat_index)
                ed_val = st.number_input("Valor (R$):", value=float(dados.get('valor', 0.0)), format="%.2f")

            if st.button("💾 Salvar no Banco de Dados"):
                with st.spinner("Salvando..."):
                    payload = {
                        "user_id": user_scan,
                        "categoria": ed_cat,
                        "valor_planeado": ed_val,
                        "subcategoria": ed_local,
                        "data": ed_data.strftime("%Y-%m-%d")
                    }
                    try:
                        supabase.table("transacoes").insert(payload).execute()
                        st.success("Transação salva com sucesso!")
                        st.balloons()
                        
                        # Limpa cache e reinicia para atualizar a tabela
                        del st.session_state['temp_dados']
                        st.cache_resource.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
