import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import google.generativeai as genai
from PIL import Image
import json
import plotly.express as px

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Gestão Wil & Ju Pro", layout="wide", page_icon="🚀")

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
    st.error(f"Erro na IA: {e}")

# --- BUSCA DE DADOS GLOBAL (Evita o erro NameError) ---
@st.cache_data(ttl=60) # Atualiza a cada 1 minuto ou ao limpar cache
def carregar_dados_globais():
    try:
        res_t = supabase.table("transacoes").select("*").execute()
        df_t = pd.DataFrame(res_t.data)
        if not df_t.empty:
            df_t['data'] = pd.to_datetime(df_t['data'])
    except:
        df_t = pd.DataFrame()
        
    try:
        res_m = supabase.table("metas").select("*").execute()
        df_m = pd.DataFrame(res_m.data)
    except:
        df_m = pd.DataFrame()
        
    return df_t, df_m

df, df_metas = carregar_dados_globais()

# --- FUNÇÕES DE AÇÃO ---
def salvar_transacoes(lista_payloads):
    try:
        supabase.table("transacoes").insert(lista_payloads).execute()
        st.success(f"✅ {len(lista_payloads)} lançamentos salvos!")
        st.cache_data.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- INTERFACE ---
st.title("🚀 Sistema Financeiro Wil & Ju")

# FILTROS DE TOPO
col_f1, col_f2 = st.columns(2)
with col_f1:
    meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    mes_nome = st.selectbox("Mês de Referência:", meses, index=datetime.now().month - 1)
    mes_num = meses.index(mes_nome) + 1
with col_f2:
    ano = st.number_input("Ano:", value=2025, step=1)

with st.expander("💵 Configurar Salários e Rendas Extras (Mês)", expanded=False):
    c_r1, c_r2 = st.columns(2)
    sal_wil = c_r1.number_input("Salário Wil", value=5500.0)
    ext_wil = c_r1.number_input("Extra Wil", value=0.0)
    sal_ju = c_r2.number_input("Salário Ju", value=5500.0)
    ext_ju = c_r2.number_input("Extra Ju", value=0.0)
    renda_total = sal_wil + ext_wil + sal_ju + ext_ju

st.divider()

aba1, aba2, aba3, aba4, aba5 = st.tabs(["📊 Dashboard", "➕ Lançar", "🎯 Metas", "💳 Cartões", "📝 Histórico"])

# --- ABA 1: DASHBOARD ---
with aba1:
    if not df.empty:
        df_mes = df[(df['data'].dt.month == mes_num) & (df['data'].dt.year == ano)].copy()
        
        # Métricas
        g_imediato = df_mes[df_mes['meio_pagamento'] != "Cartão de Crédito"]["valor_planeado"].sum()
        g_cartao = df_mes[df_mes['meio_pagamento'] == "Cartão de Crédito"]["valor_planeado"].sum()
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Renda Total", f"R$ {renda_total:,.2f}")
        m2.metric("Débito/Dinheiro", f"R$ {g_imediato:,.2f}")
        m3.metric("Saldo em Conta", f"R$ {(renda_total - g_imediato):,.2f}")
        m4.metric("Fatura Cartão", f"R$ {g_cartao:,.2f}")

        st.subheader("🎯 Progresso das Metas")
        if not df_metas.empty:
            for _, meta in df_metas.iterrows():
                gasto_cat = df_mes[df_mes['categoria'] == meta['categoria']]['valor_planeado'].sum()
                limite = meta['valor_limite']
                perc = min(gasto_cat / limite, 1.0) if limite > 0 else 0
                
                col_m1, col_m2 = st.columns([1, 4])
                col_m1.write(f"**{meta['categoria']}**")
                cor = "normal" if perc < 0.8 else "inverse" # Streamlit muda cor auto
                col_m2.progress(perc)
                col_m2.caption(f"R$ {gasto_cat:,.2f} de R$ {limite:,.2f}")
        else:
            st.info("Cadastre metas na aba 🎯")
    else:
        st.warning("Nenhum dado encontrado.")

# --- ABA 2: LANÇAR ---
with aba2:
    metodo = st.radio("Método:", ["Manual", "Scanner Recibo", "Explodir Fatura (PDF/Print)"], horizontal=True)
    
    if metodo == "Manual":
        with st.form("f_manual"):
            c1, c2 = st.columns(2)
            u = c1.radio("Quem?", ["wil", "ju"], horizontal=True)
            d = c1.date_input("Data:")
            # Usa as categorias das metas para facilitar
            lista_cats = df_metas['categoria'].tolist() if not df_metas.empty else ["Alimentação", "Lazer", "Habitação"]
            cat = c1.selectbox("Categoria:", lista_cats)
            sub = c2.text_input("Local/Item:")
            val = c2.number_input("Valor:", format="%.2f")
            meio = c2.selectbox("Meio:", ["Dinheiro/Débito", "Cartão de Crédito"])
            if st.form_submit_button("Salvar"):
                salvar_transacoes([{"user_id":u, "data":str(d), "categoria":cat, "subcategoria":sub, "valor_planeado":val, "meio_pagamento":meio}])

    elif metodo == "Scanner Recibo":
        up = st.file_uploader("Foto do Recibo", type=["jpg", "png", "jpeg"])
        if up:
            img = Image.open(up)
            st.image(img, width=250)
            if st.button("Analisar Recibo"):
                with st.spinner("IA lendo..."):
                    prompt = "Retorne JSON: {\"valor\": 0.0, \"local\": \"\", \"categoria\": \"\", \"data\": \"YYYY-MM-DD\", \"meio\": \"Cartão de Crédito ou Dinheiro/Débito\"}"
                    resp = model.generate_content([prompt, img])
                    st.session_state['ia_recibo'] = json.loads(resp.text.replace('```json', '').replace('```', '').strip())
        
        if 'ia_recibo' in st.session_state:
            res = st.session_state['ia_recibo']
            st.json(res)
            if st.button("Confirmar e Salvar"):
                salvar_transacoes([{"user_id":"wil", "data":res['data'], "categoria":res['categoria'], "subcategoria":res['local'], "valor_planeado":res['valor'], "meio_pagamento":res['meio']}])
                del st.session_state['ia_recibo']

    elif metodo == "Explodir Fatura (PDF/Print)":
        up_fat = st.file_uploader("Upload da Fatura", type=["jpg", "png", "jpeg"])
        if up_fat:
            img_fat = Image.open(up_fat)
            st.image(img_fat, width=400)
            if st.button("Explodir Fatura agora"):
                with st.spinner("IA extraindo todas as linhas..."):
                    prompt = "Analise esta fatura e extraia TODOS os gastos em uma LISTA JSON: [{\"data\": \"2025-MM-DD\", \"local\": \"nome\", \"valor\": 0.0, \"categoria\": \"Alimentação\"}]. Não ignore nada."
                    resp = model.generate_content([prompt, img_fat])
                    st.session_state['ia_fatura'] = json.loads(resp.text.replace('```json', '').replace('```', '').strip())

        if 'ia_fatura' in st.session_state:
            st.write("### Itens detectados:")
            df_fat = pd.DataFrame(st.session_state['ia_fatura'])
            st.dataframe(df_fat)
            if st.button("🚀 Lançar tudo no Supabase"):
                payloads = []
                for _, row in df_fat.iterrows():
                    payloads.append({
                        "user_id": "wil", # Ajuste conforme necessário
                        "data": row['data'],
                        "categoria": row['categoria'],
                        "subcategoria": row['local'],
                        "valor_planeado": row['valor'],
                        "meio_pagamento": "Cartão de Crédito"
                    })
                salvar_transacoes(payloads)
                del st.session_state['ia_fatura']

# --- ABA 3: METAS ---
with aba3:
    st.header("🎯 Definir Metas Mensais")
    with st.form("f_metas"):
        c1, c2 = st.columns(2)
        m_cat = c1.text_input("Nome da Categoria (Ex: iFood, Mercado, Gasolina)")
        m_val = c2.number_input("Limite Mensal (R$):", value=500.0)
        if st.form_submit_button("Salvar Meta"):
            supabase.table("metas").insert({"categoria": m_cat, "valor_limite": m_val}).execute()
            st.cache_data.clear()
            st.rerun()
    
    if not df_metas.empty:
        st.dataframe(df_metas[["categoria", "valor_limite"]], use_container_width=True)
        if st.button("Limpar todas as metas"):
             supabase.table("metas").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
             st.cache_data.clear()
             st.rerun()

# --- ABA 4 E 5: CARTÕES E HISTÓRICO (Resumido) ---
with aba4:
    if not df.empty:
        df_cartao = df[(df['data'].dt.month == mes_num) & (df['meio_pagamento'] == "Cartão de Crédito")]
        st.write(f"Total Cartão: R$ {df_cartao['valor_planeado'].sum():,.2f}")
        st.dataframe(df_cartao[["data", "subcategoria", "valor_planeado", "cartao_nome"]], hide_index=True)

with aba5:
    if not df.empty:
        st.subheader("Edição Geral")
        # Filtrar o mês para não sobrecarregar o editor
        df_edit = df[(df['data'].dt.month == mes_num)].sort_values(by="data", ascending=False)
        editado = st.data_editor(df_edit, use_container_width=True, hide_index=True)
        if st.button("Salvar Alterações"):
            for _, row in editado.iterrows():
                p = {"user_id": row['user_id'], "categoria": row['categoria'], "subcategoria": row['subcategoria'], "valor_planeado": float(row['valor_planeado']), "data": str(row['data'].date()), "meio_pagamento": row['meio_pagamento']}
                supabase.table("transacoes").update(p).eq("id", row['id']).execute()
            st.cache_data.clear()
            st.rerun()
