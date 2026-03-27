import streamlit as st
import pandas as pd
import json
from supabase import create_client, Client
import google.generativeai as genai
from PIL import Image

# Configuração da página
st.set_page_config(page_title="Finanças Wil e Ju", layout="wide")

if "gastos_reais" not in st.session_state:
    st.session_state.gastos_reais = []

# Conexão com o Supabase (usando segredos que vamos configurar depois)
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception as e:
    st.error(f"Erro ao conectar no Banco: {e}")

# Configuração do Gemini
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"Erro ao conectar no Gemini: {e}")

st.title("💸 Planejado vs Real - Wil & Ju")

usuario = st.selectbox("Quem está usando?", ["wil", "ju"])

st.header("📸 Escanear Recibo")
uploaded_file = st.file_uploader("Tire uma foto do recibo", type=["jpg", "png", "jpeg"])

if uploaded_file:
    img = Image.open(uploaded_file)
    st.image(img, caption="Recibo", width=300)
    
    if st.button("Analisar com IA"):
        with st.spinner("Lendo nota..."):
            prompt = "Analise este recibo. Extraia a CATEGORIA e o VALOR TOTAL. Responda apenas JSON, ex: {'categoria': 'HABITAÇÃO', 'valor': 150.50}"
            response = model.generate_content([prompt, img])
            try:
                txt = response.text.replace('```json', '').replace('```', '').strip()
                dados = json.loads(txt)
                dados["user_id"] = usuario
                st.session_state.gastos_reais.append(dados)
                st.success(f"Capturado: {dados['categoria']} - R$ {dados['valor']}")
            except:
                st.error("Erro na leitura.")

st.divider()
st.header(f"📊 Resumo: {usuario.upper()}")

try:
    res = supabase.table("transacoes").select("*").eq("user_id", usuario).execute()
    df_plan = pd.DataFrame(res.data)
    if not df_plan.empty:
        plan_agrupado = df_plan.groupby("categoria")["valor_planeado"].sum().reset_index()
        st.bar_chart(plan_agrupado.set_index("categoria"))
    else:
        st.info("Sem dados planejados no banco.")
except:
    st.warning("Conectando ao banco de dados...")
