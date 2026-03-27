import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import google.generativeai as genai
from PIL import Image
import json
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Financeira Wil & Ju", layout="wide", page_icon="💰")

# --- CONEXÃO SUPABASE ---
@st.cache_resource
def init_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- CONFIGURAÇÃO GEMINI ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # Usando o modelo 1.5-flash por estabilidade de cota, mude para 2.5 se preferir
    model = genai.GenerativeModel('gemini-1.5-flash') 
except Exception as e:
    st.error(f"Erro ao carregar IA: {e}")

# --- FUNÇÕES DE APOIO ---
def salvar_transacao(payload):
    try:
        supabase.table("transacoes").insert(payload).execute()
        st.success("✅ Lançamento realizado com sucesso!")
        st.balloons()
        st.cache_resource.clear()
        st.rerun()
    except Exception as e:
        st.error(f"❌ Erro ao salvar: {e}")

# --- TÍTULO ---
st.title("💰 Gestão Financeira - Wil & Ju")

# --- 1. FILTROS DE PERÍODO (SEMPRE À VISTA) ---
# Colocamos no topo para facilitar a troca rápida de meses
c_f1, c_f2 = st.columns(2)
with c_f1:
    meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    mes_nome = st.selectbox("Selecione o Mês:", meses, index=datetime.now().month - 1)
    mes_num = meses.index(mes_nome) + 1
with c_f2:
    ano = st.number_input("Ano:", value=2026, step=1)

# --- 2. CONFIGURAÇÃO DE RENDAS (RECOLHIDO POR PADRÃO) ---
with st.expander("💵 Configurar Salários e Rendas Extras", expanded=False):
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.markdown("**Wil**")
        sal_wil = st.number_input("Salário Fixo (Wil)", value=5500.0)
        ext_wil = st.number_input("Renda Extra (Wil)", value=0.0)
    with col_r2:
        st.markdown("**Ju**")
        sal_ju = st.number_input("Salário Fixo (Ju)", value=5500.0)
        ext_ju = st.number_input("Renda Extra (Ju)", value=0.0)
    renda_total = sal_wil + ext_wil + sal_ju + ext_ju

st.divider()

# --- ABAS ---
aba1, aba2, aba3, aba4 = st.tabs(["📊 Dashboard", "➕ Novo Lançamento", "💳 Cartões de Crédito", "📝 Histórico Geral"])

# --- ABA 1: DASHBOARD ---
with aba1:
    try:
        res = supabase.table("transacoes").select("*").execute()
        df = pd.DataFrame(res.data)
        
        if not df.empty:
            df['data'] = pd.to_datetime(df['data'])
            df_mes = df[(df['data'].dt.month == mes_num) & (df['data'].dt.year == ano)].copy()
            
            # Garantir que as colunas novas existam no DF para não dar erro
            if 'meio_pagamento' not in df_mes.columns: df_mes['meio_pagamento'] = "Dinheiro/Débito"

            # Lógica Financeira
            gastos_imediatos = df_mes[df_mes['meio_pagamento'] != "Cartão de Crédito"]["valor_planeado"].sum()
            gastos_cartao = df_mes[df_mes['meio_pagamento'] == "Cartão de Crédito"]["valor_planeado"].sum()
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Renda Total", f"R$ {renda_total:,.2f}")
            m2.metric("Gastos (Dinheiro/Débito)", f"R$ {gastos_imediatos:,.2f}")
            m3.metric("Saldo Atual em Conta", f"R$ {(renda_total - gastos_imediatos):,.2f}")
            m4.metric("Fatura Cartão (A pagar)", f"R$ {gastos_cartao:,.2f}")

            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                fig_p = px.pie(df_mes, values='valor_planeado', names='categoria', hole=0.4, title="Gastos por Categoria")
                st.plotly_chart(fig_p, use_container_width=True)
            with c2:
                fig_b = px.bar(df_mes.groupby('meio_pagamento')['valor_planeado'].sum().reset_index(), 
                               x='meio_pagamento', y='valor_planeado', color='meio_pagamento', title="Débito vs Crédito")
                st.plotly_chart(fig_b, use_container_width=True)
    except Exception as e:
        st.info("Nenhum dado para exibir.")

# --- ABA 2: NOVO LANÇAMENTO ---
with aba2:
    tipo_input = st.radio("Escolha o método:", ["✍️ Manual", "📸 Scanner IA"], horizontal=True)
    
    if tipo_input == "✍️ Manual":
        with st.form("form_manual", clear_on_submit=True):
            c_m1, c_m2 = st.columns(2)
            with c_m1:
                m_user = st.radio("Quem gastou?", ["wil", "ju"], horizontal=True)
                m_data = st.date_input("Data do Gasto:", value=datetime.now())
                m_cat = st.selectbox("Categoria:", ["Habitação", "Alimentação", "Transporte", "Saúde", "Lazer", "Educação", "Outros"])
                m_sub = st.text_input("Local/Item:", placeholder="Ex: Mercado Central")
            with c_m2:
                m_val = st.number_input("Valor (R$):", min_value=0.0, format="%.2f")
                m_tipo = st.selectbox("Meio de Pagamento:", ["Dinheiro/Débito", "Cartão de Crédito"])
                m_card = st.text_input("Nome do Cartão:", placeholder="Ex: Nubank, Inter")
            
            if st.form_submit_button("🚀 Salvar Gasto"):
                salvar_transacao({
                    "user_id": m_user, "data": str(m_data), "categoria": m_cat,
                    "subcategoria": m_sub, "valor_planeado": m_val,
                    "meio_pagamento": m_tipo, "cartao_nome": m_card
                })

    else:
        up = st.file_uploader("Subir foto do recibo", type=["jpg", "png", "jpeg"])
        if up:
            img = Image.open(up)
            st.image(img, width=250)
            if st.button("🔍 Analisar Recibo agora"):
                with st.spinner("IA lendo dados e identificando pagamento..."):
                    prompt = """Analise o recibo e retorne um JSON:
                    {"valor": 0.0, "local": "nome", "categoria": "Outros", "data": "YYYY-MM-DD", 
                     "meio_pagamento": "Cartão de Crédito ou Dinheiro/Débito", "cartao_nome": "nome do banco"}
                    Dica: Se houver 'Visa', 'Master', 'Crédito' ou 'Final XXXX', defina como 'Cartão de Crédito'."""
                    response = model.generate_content([prompt, img])
                    res_json = response.text.replace('```json', '').replace('```', '').strip()
                    st.session_state['ia_data'] = json.loads(res_json)
        
        if 'ia_data' in st.session_state:
            d = st.session_state['ia_data']
            st.markdown("---")
            st.subheader("Verifique os dados lidos:")
            c_ia1, c_ia2 = st.columns(2)
            with c_ia1:
                ia_user = st.radio("Responsável:", ["wil", "ju"], horizontal=True)
                ia_val = st.number_input("Valor:", value=float(d.get('valor', 0.0)))
                ia_tipo = st.selectbox("Meio:", ["Dinheiro/Débito", "Cartão de Crédito"], 
                                      index=1 if d.get('meio_pagamento') == "Cartão de Crédito" else 0)
            with c_ia2:
                ia_data = st.date_input("Data:", value=datetime.strptime(d.get('data', datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d"))
                ia_sub = st.text_input("Local:", value=d.get('local', ''))
                ia_card = st.text_input("Cartão:", value=d.get('cartao_nome', ''))
            
            if st.button("✅ Confirmar e Salvar IA"):
                salvar_transacao({
                    "user_id": ia_user, "data": str(ia_data), "categoria": d.get('categoria'),
                    "subcategoria": ia_sub, "valor_planeado": ia_val,
                    "meio_pagamento": ia_tipo, "cartao_nome": ia_card
                })
                del st.session_state['ia_data']

# --- ABA 3: CARTÕES ---
with aba3:
    st.header("💳 Controle de Faturas")
    if not df.empty:
        df_mes = df[(df['data'].dt.month == mes_num) & (df['data'].dt.year == ano)].copy()
        df_cards = df_mes[df_mes['meio_pagamento'] == "Cartão de Crédito"]
        
        if not df_cards.empty:
            total_f = df_cards['valor_planeado'].sum()
            st.error(f"Total da fatura de {mes_nome}: **R$ {total_f:,.2f}**")
            
            fig_c = px.bar(df_cards.groupby('cartao_nome')['valor_planeado'].sum().reset_index(),
                           x='cartao_nome', y='valor_planeado', color='cartao_nome', title="Gastos por Cartão")
            st.plotly_chart(fig_c, use_container_width=True)
            
            st.dataframe(df_cards[["data", "cartao_nome", "subcategoria", "valor_planeado"]], hide_index=True)
        else:
            st.info("Nenhum gasto no crédito este mês.")

# --- ABA 4: HISTÓRICO ---
with aba4:
    st.header("📝 Histórico e Edição")
    if not df.empty:
        # Pega os dados do mês selecionado para editar
        df_edit = df[(df['data'].dt.month == mes_num) & (df['data'].dt.year == ano)].copy()
        df_edit = df_edit.sort_values(by="data", ascending=False)
        
        editado = st.data_editor(
            df_edit,
            column_order=("data", "user_id", "categoria", "subcategoria", "valor_planeado", "meio_pagamento", "cartao_nome"),
            column_config={
                "meio_pagamento": st.column_config.SelectboxColumn("Meio", options=["Dinheiro/Débito", "Cartão de Crédito"]),
                "user_id": st.column_config.SelectboxColumn("Quem", options=["wil", "ju"]),
            },
            hide_index=True,
            use_container_width=True
        )
        
        if st.button("💾 Salvar todas as edições"):
            with st.spinner("Atualizando..."):
                for _, row in editado.iterrows():
                    p = {
                        "user_id": row['user_id'], "categoria": row['categoria'], "subcategoria": row['subcategoria'],
                        "valor_planeado": float(row['valor_planeado']), "data": row['data'].strftime('%Y-%m-%d'),
                        "meio_pagamento": row['meio_pagamento'], "cartao_nome": row['cartao_nome']
                    }
                    supabase.table("transacoes").update(p).eq("id", row['id']).execute()
                st.success("Banco de dados atualizado!")
                st.rerun()
