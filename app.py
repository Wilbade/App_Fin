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

# --- CONEXÃO SUPABASE ---
@st.cache_resource
def init_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- IA ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash') 
except Exception as e:
    st.error(f"Erro IA: {e}")

# --- BUSCA DE DADOS ---
def carregar_dados():
    try:
        res_t = supabase.table("transacoes").select("*").execute()
        df_t = pd.DataFrame(res_t.data)
        if not df_t.empty:
            df_t['data'] = pd.to_datetime(df_t['data'])
        
        res_m = supabase.table("metas").select("*").execute()
        df_m = pd.DataFrame(res_m.data)
        return df_t, df_m
    except:
        return pd.DataFrame(), pd.DataFrame()

# --- INTERFACE ---
st.title("🚀 Sistema Financeiro Wil & Ju")

# 1. FILTROS (TOPO)
c_f1, c_f2 = st.columns(2)
with c_f1:
    meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    mes_nome = st.selectbox("Mês de Referência:", meses, index=datetime.now().month - 1)
    mes_num = meses.index(mes_nome) + 1
with c_f2:
    ano = st.number_input("Ano:", value=2026, step=1)

# 2. RENDAS (RECOLHIDO)
with st.expander("💵 Configurar Salários e Rendas Extras (Mês)", expanded=False):
    c_r1, c_r2 = st.columns(2)
    s_wil = c_r1.number_input("Renda Wil (Salário + Extra)", value=5500.0)
    s_ju = c_r2.number_input("Renda Ju (Salário + Extra)", value=5500.0)
    renda_total = s_wil + s_ju

df, df_metas = carregar_dados()

st.divider()

aba1, aba2, aba3, aba4, aba5 = st.tabs(["📊 Dashboard", "➕ Lançar", "🎯 Metas", "💳 Cartões", "📝 Histórico"])

# --- ABA 1: DASHBOARD ---
with aba1:
    if not df.empty:
        df_mes = df[(df['data'].dt.month == mes_num) & (df['data'].dt.year == ano)].copy()
        if not df_mes.empty:
            g_fixo = df_mes[df_mes['meio_pagamento'] != "Cartão de Crédito"]['valor_planeado'].sum()
            g_cartao = df_mes[df_mes['meio_pagamento'] == "Cartão de Crédito"]['valor_planeado'].sum()
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Renda Total", f"R$ {renda_total:,.2f}")
            m2.metric("Débito/Dinheiro", f"R$ {g_fixo:,.2f}")
            m3.metric("Saldo em Conta", f"R$ {(renda_total - g_fixo):,.2f}")
            m4.metric("Fatura Cartão", f"R$ {g_cartao:,.2f}")

            st.subheader("🎯 Progresso das Metas")
            if not df_metas.empty:
                for _, meta in df_metas.iterrows():
                    gasto_cat = df_mes[df_mes['categoria'].str.upper() == meta['categoria'].upper()]['valor_planeado'].sum()
                    limite = meta['valor_limite']
                    progresso = min(gasto_cat / limite, 1.0) if limite > 0 else 0
                    c_t, c_b = st.columns([1, 4])
                    c_t.write(f"**{meta['categoria']}**")
                    c_b.progress(progresso)
                    c_b.caption(f"R$ {gasto_cat:,.2f} de R$ {limite:,.2f}")
            
            st.divider()
            fig = px.pie(df_mes, values='valor_planeado', names='categoria', hole=0.4, title="Divisão de Gastos")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning(f"Nenhum gasto encontrado para {mes_nome}/{ano}")

# --- ABA 2: LANÇAR ---
with aba2:
    tipo = st.radio("Método de Lançamento:", ["✍️ Manual", "📸 Recibo Único", "📄 Fatura Completa"], horizontal=True)
    
    if tipo == "✍️ Manual":
        with st.form("f_manual", clear_on_submit=True):
            c1, c2 = st.columns(2)
            u = c1.radio("Quem?", ["wil", "ju"], horizontal=True)
            d = c1.date_input("Data:", value=datetime.now())
            opcoes_cat = df_metas['categoria'].unique() if not df_metas.empty else ["OUTROS"]
            cat = c1.selectbox("Categoria:", opcoes_cat)
            sub = c2.text_input("Local/Item:")
            val = c2.number_input("Valor:", format="%.2f")
            meio = c2.selectbox("Meio de Pagamento:", ["Dinheiro/Débito", "Cartão de Crédito"])
            if st.form_submit_button("🚀 Salvar Gasto"):
                p = {"user_id":u, "data":str(d), "categoria":cat.upper(), "subcategoria":sub, "valor_planeado":val, "meio_pagamento":meio}
                supabase.table("transacoes").insert(p).execute()
                st.success("Salvo!")
                st.rerun()

    elif tipo == "📸 Recibo Único":
        up = st.file_uploader("Subir foto do recibo", type=["jpg", "png", "jpeg"], key="up_unico")
        if up:
            img = Image.open(up)
            st.image(img, width=250)
            if st.button("🔍 Analisar com IA"):
                with st.spinner("IA lendo..."):
                    prompt = "Retorne JSON: {\"valor\": 0.0, \"local\": \"\", \"categoria\": \"\", \"data\": \"YYYY-MM-DD\", \"meio\": \"Cartão de Crédito\"}"
                    resp = model.generate_content([prompt, img])
                    st.session_state['res_ia'] = json.loads(resp.text.replace('```json', '').replace('```', '').strip())
        
        if 'res_ia' in st.session_state:
            r = st.session_state['res_ia']
            st.info(f"Dados detectados: {r['local']} - R$ {r['valor']}")
            if st.button("✅ Confirmar Lançamento"):
                p = {"user_id":"wil", "data":r['data'], "categoria":r['categoria'].upper(), "subcategoria":r['local'], "valor_planeado":r['valor'], "meio_pagamento":r['meio']}
                supabase.table("transacoes").insert(p).execute()
                del st.session_state['res_ia']
                st.rerun()

    elif tipo == "📄 Fatura Completa":
        st.subheader("Explodir Fatura do Mês")
        up_fat = st.file_uploader("Upload do Print da Fatura", type=["jpg", "png", "jpeg"], key="up_fatura")
        if up_fat:
            img_fat = Image.open(up_fat)
            st.image(img_fat, width=400)
            if st.button("💥 Extrair Todos os Gastos"):
                with st.spinner("A IA está processando cada linha da fatura..."):
                    prompt = "Analise esta fatura e extraia TODOS os gastos em uma LISTA JSON: [{\"data\": \"2026-MM-DD\", \"local\": \"\", \"valor\": 0.0, \"categoria\": \"\"}]. Mantenha a data em 2026."
                    resp = model.generate_content([prompt, img_fat])
                    st.session_state['lista_fatura'] = json.loads(resp.text.replace('```json', '').replace('```', '').strip())

        if 'lista_fatura' in st.session_state:
            df_fat = pd.DataFrame(st.session_state['lista_fatura'])
            st.write("### Itens detectados para importação:")
            st.dataframe(df_fat, use_container_width=True)
            if st.button("🚀 Lançar TUDO no Supabase"):
                payloads = []
                for _, row in df_fat.iterrows():
                    payloads.append({
                        "user_id": "wil",
                        "data": row['data'],
                        "categoria": row['categoria'].upper(),
                        "subcategoria": row['local'],
                        "valor_planeado": row['valor'],
                        "meio_pagamento": "Cartão de Crédito"
                    })
                supabase.table("transacoes").insert(payloads).execute()
                st.success(f"{len(payloads)} itens importados!")
                del st.session_state['lista_fatura']
                st.rerun()

# --- ABA 3: METAS ---
with aba3:
    st.header("🎯 Suas Metas Mensais")
    with st.form("f_metas"):
        c1, c2 = st.columns(2)
        m_cat = c1.text_input("Nome da Categoria (Ex: Alimentação)")
        m_val = c2.number_input("Limite Mensal (R$):")
        if st.form_submit_button("Atualizar Meta"):
            supabase.table("metas").upsert({"categoria": m_cat.upper(), "valor_limite": m_val}, on_conflict="categoria").execute()
            st.rerun()
    if not df_metas.empty:
        st.dataframe(df_metas[["categoria", "valor_limite"]], hide_index=True, use_container_width=True)

# --- ABA 4: CARTÕES ---
with aba4:
    if not df.empty:
        df_mes = df[(df['data'].dt.month == mes_num) & (df['data'].dt.year == ano)].copy()
        df_c = df_mes[df_mes['meio_pagamento'] == "Cartão de Crédito"]
        if not df_c.empty:
            st.error(f"Total Fatura {mes_nome}: R$ {df_c['valor_planeado'].sum():,.2f}")
            st.dataframe(df_c[["data", "subcategoria", "valor_planeado"]], hide_index=True, use_container_width=True)
        else:
            st.info("Nada no crédito este mês.")

# --- ABA 5: HISTÓRICO ---
with aba5:
    st.subheader("📝 Edição Profissional")
    if not df.empty:
        df_edit = df[(df['data'].dt.month == mes_num) & (df['data'].dt.year == ano)].copy()
        if not df_edit.empty:
            df_edit = df_edit.sort_values(by="data", ascending=False)
            editado = st.data_editor(
                df_edit,
                column_order=("data", "user_id", "categoria", "subcategoria", "valor_planeado", "meio_pagamento"),
                column_config={
                    "data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                    "user_id": st.column_config.SelectboxColumn("Responsável", options=["wil", "ju"]),
                    "valor_planeado": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                    "meio_pagamento": st.column_config.SelectboxColumn("Meio", options=["Dinheiro/Débito", "Cartão de Crédito"]),
                },
                hide_index=True,
                use_container_width=True
            )
            
            if st.button("💾 Salvar Alterações"):
                for _, row in editado.iterrows():
                    p = {
                        "user_id": row['user_id'],
                        "categoria": row['categoria'].upper(),
                        "subcategoria": row['subcategoria'],
                        "valor_planeado": float(row['valor_planeado']),
                        "data": str(row['data'].date()),
                        "meio_pagamento": row['meio_pagamento']
                    }
                    supabase.table("transacoes").update(p).eq("id", row['id']).execute()
                st.success("Alterações salvas!")
                st.rerun()
        else:
            st.warning("Sem dados para este período.")
