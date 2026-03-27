import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import google.generativeai as genai
from PIL import Image
import json

# Configuração da página
st.set_page_config(page_title="Gestão Wil & Ju 2026", layout="wide", page_icon="💰")

# Conexão Supabase
@st.cache_resource
def init_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# Configuração Gemini - Melhorada para evitar falhas
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # Usando gemini-1.5-flash que é mais rápido e ideal para recibos
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"Erro ao carregar IA: {e}")

st.title("💰 Gestão Financeira Mensal - 2026")

# --- SELEÇÃO DE MÊS E ANO (FILTRO GLOBAL) ---
col_m1, col_m2 = st.columns(2)
with col_m1:
    meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
             "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    # Pega o mês atual como padrão
    mes_padrao = datetime.now().month - 1
    mes_nome = st.selectbox("Selecione o Mês:", meses, index=mes_padrao)
    mes_num = meses.index(mes_nome) + 1
with col_m2:
    # Atualizado para 2026 como padrão
    ano = st.number_input("Ano:", value=2026, step=1)

# --- ABAS ---
aba1, aba2 = st.tabs(["📊 Visão Mensal", "📸 Escanear Recibo"])

with aba1:
    st.header(f"Resumo de {mes_nome} / {ano}")
    
    # --- ÁREA DE RENDAS ---
    with st.expander("💵 Rendas deste Mês (Fixa + Extra)", expanded=False):
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
    try:
        res = supabase.table("transacoes").select("*").execute()
        df = pd.DataFrame(res.data)

        if not df.empty:
            df['data'] = pd.to_datetime(df['data'])
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
                # Cor do delta: verde se positivo, vermelho se negativo
                m3.metric("Sobrou no Mês", f"R$ {sobra:,.2f}", delta=f"{sobra:,.2f}", delta_color="normal")

                st.divider()
                st.subheader(f"Detalhamento de Gastos: {mes_nome}")
                
                # Gráfico de Barras
                graf_data = df_mes.groupby(["categoria", "user_id"])["valor_planeado"].sum().unstack().fillna(0)
                st.bar_chart(graf_data)
                
                st.write("### Lista de Despesas do Mês")
                st.dataframe(df_mes[["data", "user_id", "categoria", "subcategoria", "valor_planeado"]], use_container_width=True)
            else:
                st.info(f"Não há despesas lançadas para {mes_nome} de {ano}.")
        else:
            st.warning("Banco de dados vazio. Comece a lançar despesas!")
    except Exception as e:
        st.error(f"Erro ao conectar com o banco de dados: {e}")

with aba2:
    st.header("👤 Novo Gasto com Foto")
    user = st.selectbox("Lançar para:", ["wil", "ju"])
    up = st.file_uploader("Suba a foto do recibo aqui", type=["jpg", "png", "jpeg"])
    
    if up:
        img = Image.open(up)
        st.image(img, width=300, caption="Recibo carregado")
        
        if st.button("Analisar Recibo com IA"):
            with st.spinner("A IA está lendo os dados..."):
                try:
                    # Prompt mais específico para evitar lixo no JSON
                    prompt = """
                    Analise este recibo e extraia APENAS um JSON puro (sem markdown ou blocos de código) com:
                    {
                        "categoria": "escolha uma entre (Alimentação, Moradia, Transporte, Lazer, Saúde, Outros)",
                        "valor": 0.0,
                        "descricao": "nome curto do local"
                    }
                    """
                    # Chamada corrigida
                    response = model.generate_content([prompt, img])
                    
                    # Limpeza simples caso a IA coloque blocos de código ```json
                    texto_limpo = response.text.replace('```json', '').replace('```', '').strip()
                    dados = json.loads(texto_limpo)
                    
                    st.success("Leitura concluída!")
                    st.json(dados)
                    
                    # Botão para salvar no Supabase após conferir
                    if st.button("Confirmar e Salvar no Banco"):
                        nova_transacao = {
                            "user_id": user,
                            "categoria": dados['categoria'],
                            "valor_planeado": dados['valor'],
                            "data": datetime.now().strftime("%Y-%m-%d"),
                            "subcategoria": dados.get('descricao', 'Importado via Foto')
                        }
                        supabase.table("transacoes").insert(nova_transacao).execute()
                        st.balloons()
                        st.success("Salvo com sucesso!")
                        
                except Exception as e:
                    st.error(f"Falha ao processar imagem. Erro: {e}")
                    st.info("Dica: Verifique se sua GEMINI_API_KEY está correta nos Secrets do Streamlit.")
