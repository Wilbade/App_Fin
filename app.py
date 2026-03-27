import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import google.generativeai as genai
from PIL import Image
import json
import plotly.express as px

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
    # Mantendo o 2.5 flash que você confirmou funcionar
    model = genai.GenerativeModel('gemini-1.5-flash') 
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
    # --- SEÇÃO DE RENDAS ---
    with st.expander("💵 Rendas e Entradas", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Wil**")
            sal_wil = st.number_input("Salário Fixo Wil", value=5500.0, step=100.0)
            extra_wil = st.number_input("Renda Extra Wil", value=0.0, step=50.0)
        with c2:
            st.markdown("**Ju**")
            sal_ju = st.number_input("Salário Fixo Ju", value=5500.0, step=100.0)
            extra_ju = st.number_input("Renda Extra Ju", value=0.0, step=50.0)
        
        renda_total_mes = sal_wil + extra_wil + sal_ju + extra_ju
        st.info(f"Renda Total Estimada: R$ {renda_total_mes:,.2f}")

    # --- BUSCA DE DADOS ---
    try:
        res = supabase.table("transacoes").select("*").execute()
        df = pd.DataFrame(res.data)
        
        if not df.empty:
            # Converter data para formato datetime do Python
            df['data'] = pd.to_datetime(df['data'])
            
            # Filtrar pelo mês e ano selecionados
            df_mes = df[(df['data'].dt.month == mes_num) & (df['data'].dt.year == ano)].copy()
            
            # Métricas principais
            total_gasto = df_mes["valor_planeado"].sum() if not df_mes.empty else 0.0
            saldo_final = renda_total_mes - total_gasto
            
            m1, m2, m3 = st.columns(3)
            m1.metric(f"Gasto em {mes_nome}", f"R$ {total_gasto:,.2f}")
            m2.metric("Saldo Restante", f"R$ {saldo_final:,.2f}", delta=f"{saldo_final:,.2f}")
            m3.metric("Total Acumulado (Geral)", f"R$ {df['valor_planeado'].sum():,.2f}")

            st.divider()

            if not df_mes.empty:
                st.subheader("📋 Detalhes das Transações")
                st.caption("💡 Você pode clicar em qualquer célula abaixo para editar o valor diretamente.")

                # Preparar o editor de dados
                df_editor = df_mes.sort_values(by="data", ascending=False)
                
                # Editor Interativo
                editado_df = st.data_editor(
                    df_editor,
                    column_order=("data", "user_id", "categoria", "subcategoria", "valor_planeado"),
                    column_config={
                        "data": st.column_config.DateColumn("Data"),
                        "user_id": st.column_config.SelectboxColumn("Quem?", options=["wil", "ju"]),
                        "categoria": st.column_config.TextColumn("Categoria"),
                        "subcategoria": st.column_config.TextColumn("Local/Item"),
                        "valor_planeado": st.column_config.NumberColumn("Valor (R$)", format="%.2f"),
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="editor_financeiro"
                )

                # Verificar se o usuário mudou algo
                if not editado_df.equals(df_editor):
                    if st.button("💾 Salvar Alterações"):
                        with st.spinner("Atualizando banco de dados..."):
                            for index, row in editado_df.iterrows():
                                # Pegamos o ID original para saber qual linha atualizar
                                id_transacao = row['id']
                                payload = {
                                    "user_id": row['user_id'],
                                    "categoria": row['categoria'],
                                    "subcategoria": row['subcategoria'],
                                    "valor_planeado": float(row['valor_planeado']),
                                    "data": row['data'].strftime('%Y-%m-%d') if hasattr(row['data'], 'strftime') else row['data']
                                }
                                supabase.table("transacoes").update(payload).eq("id", id_transacao).execute()
                            
                            st.success("Tudo atualizado!")
                            st.cache_resource.clear()
                            st.rerun()

                # --- GRÁFICOS ---
                st.divider()
                g1, g2 = st.columns(2)
                with g1:
                    fig_pizza = px.pie(df_mes, values='valor_planeado', names='categoria', 
                                     title="Divisão por Categoria", hole=0.4)
                    st.plotly_chart(fig_pizza, use_container_width=True)
                with g2:
                    resumo_quem = df_mes.groupby('user_id')['valor_planeado'].sum().reset_index()
                    fig_barra = px.bar(resumo_quem, x='user_id', y='valor_planeado', color='user_id',
                                     title="Gastos: Wil vs Ju", text_auto='.2f')
                    st.plotly_chart(fig_barra, use_container_width=True)
            else:
                st.info(f"Nenhum gasto encontrado para {mes_nome}/{ano}.")
                
    except Exception as e:
        st.error(f"Erro ao acessar Supabase: {e}")

with aba2:
    st.header("📸 Scanner Inteligente")
    user_scan = st.radio("Responsável pelo gasto:", ["wil", "ju"], horizontal=True)
    up = st.file_uploader("Subir foto do recibo", type=["jpg", "png", "jpeg"])
    
    if up:
        img = Image.open(up)
        st.image(img, width=280, caption="Recibo carregado")
        
        if st.button("🔍 1. Ler Recibo com IA"):
            with st.spinner("A IA está analisando os dados..."):
                try:
                    prompt = """Retorne um JSON estrito com: {"valor": 0.0, "local": "nome", "categoria": "Lazer", "data_recibo": "YYYY-MM-DD"}"""
                    response = model.generate_content([prompt, img])
                    # Limpeza de texto para evitar erro de JSON
                    res_text = response.text.replace('```json', '').replace('```', '').strip()
                    st.session_state['temp_dados'] = json.loads(res_text)
                except Exception as e:
                    st.error(f"Erro na IA: {e}")

        if 'temp_dados' in st.session_state:
            st.divider()
            st.subheader("📝 2. Validar e Editar")
            d = st.session_state['temp_dados']
            
            c_ed1, c_ed2 = st.columns(2)
            with c_ed1:
                ed_data = st.date_input("Data:", value=datetime.strptime(d.get('data_recibo', datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d"))
                ed_local = st.text_input("Local (Subcategoria):", value=d.get('local', ''))
            with c_ed2:
                ed_cat = st.text_input("Categoria:", value=d.get('categoria', 'Outros'))
                ed_val = st.number_input("Valor (R$):", value=float(d.get('valor', 0.0)), format="%.2f")

            if st.button("✅ 3. Salvar no Supabase"):
                payload = {
                    "user_id": user_scan,
                    "categoria": ed_cat,
                    "subcategoria": ed_local,
                    "valor_planeado": ed_val,
                    "data": ed_data.strftime("%Y-%m-%d")
                }
                supabase.table("transacoes").insert(payload).execute()
                st.success("Salvo com sucesso!")
                st.balloons()
                del st.session_state['temp_dados']
                st.cache_resource.clear()
                st.rerun()
