import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import google.generativeai as genai
from PIL import Image
import json
import plotly.express as px

# --- CONFIGURAÇÃO ---
st.set_page_config(page_title="Gestão Wil & Ju Pro", layout="wide", page_icon="🚀")

@st.cache_resource
def init_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash') 
except Exception as e:
    st.error(f"Erro IA: {e}")

# --- FUNÇÕES ---
def salvar_varios(lista_payloads):
    try:
        supabase.table("transacoes").insert(lista_payloads).execute()
        st.success(f"✅ {len(lista_payloads)} itens lançados com sucesso!")
        st.cache_resource.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- UI ---
st.title("🚀 Sistema Financeiro Inteligente")

# FILTROS NO TOPO
c_f1, c_f2 = st.columns(2)
with c_f1:
    meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    mes_nome = st.selectbox("Mês de Referência:", meses, index=datetime.now().month - 1)
    mes_num = meses.index(mes_nome) + 1
with c_f2:
    ano = st.number_input("Ano:", value=2026, step=1)

with st.expander("💵 Configurar Salários e Rendas Extras (Mês)", expanded=False):
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        sal_wil = st.number_input("Salário Wil", value=5500.0)
        ext_wil = st.number_input("Extra Wil", value=0.0)
    with col_r2:
        sal_ju = st.number_input("Salário Ju", value=5500.0)
        ext_ju = st.number_input("Extra Ju", value=0.0)
    renda_total = sal_wil + ext_wil + sal_ju + ext_ju

aba1, aba2, aba3, aba4, aba5 = st.tabs(["📊 Dashboard", "➕ Lançar", "🎯 Metas", "💳 Cartões", "📝 Histórico"])

# --- ABA 1: DASHBOARD COM METAS ---
with aba1:
    try:
        # Puxar Transações
        res = supabase.table("transacoes").select("*").execute()
        df = pd.DataFrame(res.data)
        # Puxar Metas
        res_metas = supabase.table("metas").select("*").execute()
        df_metas = pd.DataFrame(res_metas.data)

        if not df.empty:
            df['data'] = pd.to_datetime(df['data'])
            df_mes = df[(df['data'].dt.month == mes_num) & (df['data'].dt.year == ano)].copy()
            
            gastos_imediatos = df_mes[df_mes['meio_pagamento'] != "Cartão de Crédito"]["valor_planeado"].sum()
            gastos_cartao = df_mes[df_mes['meio_pagamento'] == "Cartão de Crédito"]["valor_planeado"].sum()
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Renda Total", f"R$ {renda_total:,.2f}")
            m2.metric("Débito/Dinheiro", f"R$ {gastos_imediatos:,.2f}")
            m3.metric("Saldo em Conta", f"R$ {(renda_total - gastos_imediatos):,.2f}")
            m4.metric("Fatura Cartão", f"R$ {gastos_cartao:,.2f}")

            st.divider()
            
            # --- SEÇÃO DE METAS (BARRAS DE PROGRESSO) ---
            st.subheader("🎯 Acompanhamento de Metas")
            if not df_metas.empty:
                for _, meta in df_metas.iterrows():
                    gasto_cat = df_mes[df_mes['categoria'] == meta['categoria']]['valor_planeado'].sum()
                    progresso = gasto_cat / meta['valor_limite'] if meta['valor_limite'] > 0 else 0
                    
                    col_meta1, col_meta2 = st.columns([1, 3])
                    col_meta1.write(f"**{meta['categoria']}**")
                    
                    cor_barra = "green" if progresso < 0.8 else "orange" if progresso < 1 else "red"
                    col_meta2.progress(min(progresso, 1.0))
                    col_meta2.caption(f"Gasto: R$ {gasto_cat:,.2f} de R$ {meta['valor_limite']:,.2f} ({progresso*100:.1f}%)")
            else:
                st.info("Configure suas metas na aba '🎯 Metas'.")
    except: st.info("Sem dados.")

# --- ABA 2: LANÇAR (MANUAL / RECIBO / FATURA INTEIRA) ---
with aba2:
    tipo_lanca = st.segmented_control("Método:", ["Manual", "Recibo Único", "Fatura Completa (PDF/Print)"])
    
    if tipo_lanca == "Manual":
        with st.form("manual"):
            c1, c2 = st.columns(2)
            u = c1.radio("Quem?", ["wil", "ju"], horizontal=True)
            d = c1.date_input("Data:")
            cat = c1.selectbox("Categoria:", df_metas['categoria'].unique() if not df_metas.empty else ["Lazer", "Alimentação", "Saúde"])
            sub = c2.text_input("Local/Item:")
            val = c2.number_input("Valor:", format="%.2f")
            meio = c2.selectbox("Meio:", ["Dinheiro/Débito", "Cartão de Crédito"])
            if st.form_submit_button("Salvar"):
                salvar_varios([{"user_id":u, "data":str(d), "categoria":cat, "subcategoria":sub, "valor_planeado":val, "meio_pagamento":meio}])

    elif tipo_lanca == "Fatura Completa (PDF/Print)":
        st.info("Tire um print da fatura do banco ou suba o PDF. A IA vai extrair todas as linhas.")
        up_fatura = st.file_uploader("Fatura", type=["jpg", "png", "pdf"])
        if up_fatura and st.button("Explodir Fatura (IA)"):
            with st.spinner("Lendo fatura inteira..."):
                img = Image.open(up_fatura)
                prompt = "Analise esta fatura e retorne uma LISTA JSON: [{\"data\": \"YYYY-MM-DD\", \"local\": \"nome\", \"valor\": 0.0, \"categoria\": \"Lazer\"}]"
                response = model.generate_content([prompt, img])
                lista_gastos = json.loads(response.text.replace('```json', '').replace('```', '').strip())
                st.session_state['fatura_ia'] = lista_gastos

        if 'fatura_ia' in st.session_state:
            df_preview = pd.DataFrame(st.session_state['fatura_ia'])
            st.table(df_preview)
            if st.button("Confirmar Importação de Tudo"):
                payloads = []
                for item in st.session_state['fatura_ia']:
                    payloads.append({
                        "user_id": "wil", # Padronizar ou pedir pra escolher
                        "data": item['data'],
                        "categoria": item['categoria'],
                        "subcategoria": item['local'],
                        "valor_planeado": item['valor'],
                        "meio_pagamento": "Cartão de Crédito"
                    })
                salvar_varios(payloads)
                del st.session_state['fatura_ia']

# --- ABA 3: CONFIGURAR METAS ---
with aba3:
    st.header("🎯 Definir Limites de Gastos")
    with st.form("nova_meta"):
        c_m1, c_m2 = st.columns(2)
        m_cat = c_m1.text_input("Nome da Categoria (Ex: Alimentação)")
        m_lim = c_m2.number_input("Limite Mensal (R$)", value=1000.0)
        if st.form_submit_button("Salvar Meta"):
            supabase.table("metas").insert({"categoria": m_cat, "valor_limite": m_lim}).execute()
            st.success("Meta salva!")
            st.rerun()
    
    if not df_metas.empty:
        st.subheader("Metas Atuais")
        st.dataframe(df_metas[["categoria", "valor_limite"]], use_container_width=True)

# (Abas de Cartões e Histórico continuam com a mesma lógica anterior...)
