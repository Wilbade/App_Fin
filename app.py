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
    model = genai.GenerativeModel('gemini-1.5-flash') 
except Exception as e:
    st.error(f"Erro ao carregar IA: {e}")

# --- FUNÇÕES DE APOIO ---
def salvar_transacao(payload):
    try:
        supabase.table("transacoes").insert(payload).execute()
        st.success("Lançamento realizado com sucesso!")
        st.balloons()
        st.cache_resource.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- UI PRINCIPAL ---
st.title("💰 Gestão Financeira Inteligente - Wil & Ju")

# --- FILTRO GLOBAL ---
with st.sidebar:
    st.header("📅 Filtro de Período")
    meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    mes_nome = st.selectbox("Mês:", meses, index=datetime.now().month - 1)
    mes_num = meses.index(mes_nome) + 1
    ano = st.number_input("Ano:", value=2026, step=1)
    
    st.divider()
    st.markdown("### 💵 Configuração de Rendas")
    sal_wil = st.number_input("Salário Wil", value=5500.0)
    ext_wil = st.number_input("Extra Wil", value=0.0)
    sal_ju = st.number_input("Salário Ju", value=5500.0)
    ext_ju = st.number_input("Extra Ju", value=0.0)
    renda_total = sal_wil + ext_wil + sal_ju + ext_ju

aba1, aba2, aba3, aba4 = st.tabs(["📊 Dashboard", "➕ Novo Lançamento", "💳 Cartões de Crédito", "📝 Histórico Geral"])

# --- ABA 1: DASHBOARD ---
with aba1:
    try:
        res = supabase.table("transacoes").select("*").execute()
        df = pd.DataFrame(res.data)
        
        if not df.empty:
            df['data'] = pd.to_datetime(df['data'])
            df_mes = df[(df['data'].dt.month == mes_num) & (df['data'].dt.year == ano)].copy()
            
            # Cálculo Financeiro Analítico
            # Gastos no Débito/Dinheiro (saem do saldo agora)
            gastos_imediatos = df_mes[df_mes['meio_pagamento'] != "Cartão de Crédito"]["valor_planeado"].sum()
            # Gastos no Crédito (são dívidas futuras)
            gastos_cartao = df_mes[df_mes['meio_pagamento'] == "Cartão de Crédito"]["valor_planeado"].sum()
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Renda Total", f"R$ {renda_total:,.2f}")
            m2.metric("Gastos (Dinheiro/Débito)", f"R$ {gastos_imediatos:,.2f}")
            m3.metric("Saldo em Conta", f"R$ {(renda_total - gastos_imediatos):,.2f}", delta_color="normal")
            m4.metric("Fatura Cartões (A pagar)", f"R$ {gastos_cartao:,.2f}", delta="-")

            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Gastos por Categoria")
                fig_p = px.pie(df_mes, values='valor_planeado', names='categoria', hole=0.4)
                st.plotly_chart(fig_p, use_container_width=True)
            with c2:
                st.subheader("Fluxo de Caixa (Débito vs Crédito)")
                fig_b = px.bar(df_mes.groupby('meio_pagamento')['valor_planeado'].sum().reset_index(), 
                               x='meio_pagamento', y='valor_planeado', color='meio_pagamento')
                st.plotly_chart(fig_b, use_container_width=True)
    except: st.info("Adicione lançamentos para ver o dashboard.")

# --- ABA 2: NOVO LANÇAMENTO (MANUAL OU IA) ---
with aba2:
    col_l1, col_l2 = st.columns([1, 1.2])
    
    with col_l1:
        st.subheader("✍️ Lançamento Manual")
        with st.form("form_manual"):
            m_user = st.radio("Quem?", ["wil", "ju"], horizontal=True)
            m_data = st.date_input("Data:", value=datetime.now())
            m_cat = st.selectbox("Categoria:", ["Alimentação", "Habitação", "Saúde", "Veículos", "Lazer", "Dependentes", "Outros"])
            m_sub = st.text_input("Subcategoria/Local:", placeholder="Ex: Mercado X, Farmácia Y")
            m_val = st.number_input("Valor (R$):", min_value=0.0, format="%.2f")
            m_tipo = st.selectbox("Meio de Pagamento:", ["Dinheiro/Débito", "Cartão de Crédito"])
            m_card = st.text_input("Nome do Cartão (se houver):", placeholder="Ex: Nubank, Visa")
            
            if st.form_submit_button("Salvar Lançamento Manual"):
                salvar_transacao({
                    "user_id": m_user, "data": str(m_data), "categoria": m_cat,
                    "subcategoria": m_sub, "valor_planeado": m_val,
                    "meio_pagamento": m_tipo, "cartao_nome": m_card
                })

    with col_l2:
        st.subheader("📸 Scanner Inteligente (IA)")
        up = st.file_uploader("Subir foto do recibo", type=["jpg", "png", "jpeg"])
        if up:
            img = Image.open(up)
            st.image(img, width=200)
            if st.button("Analisar Recibo"):
                with st.spinner("IA lendo dados..."):
                    prompt = """Retorne um JSON: {"valor": 0.0, "local": "nome", "categoria": "Lazer", "data": "YYYY-MM-DD", "meio_pagamento": "Cartão de Crédito ou Dinheiro/Débito"} 
                    Dica: se no recibo aparecer 'Visa', 'Master', 'Final XXXX' ou 'Crédito', coloque 'Cartão de Crédito'."""
                    response = model.generate_content([prompt, img])
                    st.session_state['temp_ia'] = json.loads(response.text.replace('```json', '').replace('```', '').strip())
        
        if 'temp_ia' in st.session_state:
            d = st.session_state['temp_ia']
            st.markdown("### Revise os dados da IA")
            ed_user = st.radio("Responsável:", ["wil", "ju"], key="ia_user", horizontal=True)
            ed_val = st.number_input("Valor:", value=float(d.get('valor', 0.0)), key="ia_val")
            ed_tipo = st.selectbox("Meio:", ["Dinheiro/Débito", "Cartão de Crédito"], 
                                  index=0 if d.get('meio_pagamento') != "Cartão de Crédito" else 1)
            
            if st.button("Confirmar Lançamento IA"):
                salvar_transacao({
                    "user_id": ed_user, "data": d.get('data'), "categoria": d.get('categoria'),
                    "subcategoria": d.get('local'), "valor_planeado": ed_val,
                    "meio_pagamento": ed_tipo
                })
                del st.session_state['temp_ia']

# --- ABA 3: CARTÕES DE CRÉDITO ---
with aba3:
    st.header("💳 Controle de Faturas")
    if not df.empty:
        df_cards = df_mes[df_mes['meio_pagamento'] == "Cartão de Crédito"]
        if not df_cards.empty:
            total_fatura = df_cards['valor_planeado'].sum()
            st.warning(f"Total acumulado em cartões para {mes_nome}: **R$ {total_fatura:,.2f}**")
            
            # Gastos por cartão
            fig_cards = px.bar(df_cards.groupby('cartao_nome')['valor_planeado'].sum().reset_index(),
                               x='cartao_nome', y='valor_planeado', title="Gastos por Cartão")
            st.plotly_chart(fig_cards)
            
            st.dataframe(df_cards[["data", "cartao_nome", "subcategoria", "valor_planeado"]], use_container_width=True)
        else:
            st.info("Nenhum gasto no cartão este mês.")

# --- ABA 4: HISTÓRICO E EDIÇÃO ---
with aba4:
    st.header("📝 Edição de Lançamentos")
    if not df.empty:
        df_edit = df_mes.sort_values(by="data", ascending=False)
        
        # O Editor de Dados permite deletar e editar tudo
        editado = st.data_editor(
            df_edit,
            column_order=("data", "user_id", "categoria", "subcategoria", "valor_planeado", "meio_pagamento", "cartao_nome"),
            hide_index=True,
            use_container_width=True,
            key="global_editor"
        )
        
        if st.button("Salvar Alterações do Histórico"):
            for index, row in editado.iterrows():
                payload = {
                    "user_id": row['user_id'], "categoria": row['categoria'],
                    "subcategoria": row['subcategoria'], "valor_planeado": float(row['valor_planeado']),
                    "data": row['data'].strftime('%Y-%m-%d'), "meio_pagamento": row['meio_pagamento'],
                    "cartao_nome": row['cartao_nome']
                }
                supabase.table("transacoes").update(payload).eq("id", row['id']).execute()
            st.success("Dados atualizados!")
            st.rerun()
