import streamlit as st
from PyPDF2 import PdfReader
from fpdf import FPDF
import google.generativeai as genai
import qrcode
import os
import PIL.Image
import pandas as pd
import re

# ========================================================
# CONFIGURAÇÃO DA PÁGINA
# ========================================================
st.markdown("""
<style>

/* FORÇA TEXTO VISÍVEL */
input, textarea {
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
    background-color: #ffffff !important;
}

/* WRAPPER DO STREAMLIT */
div[data-baseweb="input"] input {
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
    background-color: #ffffff !important;
}

div[data-baseweb="textarea"] textarea {
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
    background-color: #ffffff !important;
}

/* PLACEHOLDER */
input::placeholder, textarea::placeholder {
    color: #6b7280 !important;
}

/* REMOVE TRANSPARÊNCIAS BUGADAS */
.stTextInput input, .stTextArea textarea {
    opacity: 1 !important;
}

/* CURSOR (às vezes some também) */
input, textarea {
    caret-color: #000000 !important;
}

</style>
""", unsafe_allow_html=True)

# ========================================================
# CABEÇALHO
# ========================================================
st.markdown("""
<h1 style='text-align: center;'>🧠 Gerador & Corretor Inteligente</h1>
<p style='text-align: center; color: #94a3b8;'>
Automatize provas com IA de forma profissional
</p>
""", unsafe_allow_html=True)

# ========================================================
# ESTADO
# ========================================================
if "texto_prova" not in st.session_state:
    st.session_state.texto_prova = ""

if "lista_notas" not in st.session_state:
    st.session_state.lista_notas = []

# ========================================================
# API SEGURA
# ========================================================
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])

def selecionar_modelo():
    modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    return genai.GenerativeModel(modelos[0])

# ========================================================
# FUNÇÕES
# ========================================================
def gerar_perguntas(texto, tipo):
    model = selecionar_modelo()

    prompt = f"""
    Gere uma prova com base no texto:
    {texto[:10000]}

    Tipo: {tipo}

    Gere também o GABARITO ao final.
    """

    with st.spinner("🧠 Gerando prova..."):
        return model.generate_content(prompt).text


def corrigir(foto, gabarito):
    model = selecionar_modelo()
    img = PIL.Image.open(foto)

    prompt = [
        f"GABARITO: {gabarito}",
        "Corrija e retorne:",
        "NOTA: 0-10",
        "ACERTOS:",
        "FEEDBACK:",
        img
    ]

    return model.generate_content(prompt).text


def criar_pdf(conteudo):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    for linha in conteudo.split("\n"):
        pdf.multi_cell(0, 8, linha)

    return pdf.output(dest="S").encode("latin-1")

# ========================================================
# SIDEBAR
# ========================================================
with st.sidebar:
    st.title("⚙️ Configurações")

    escola = st.text_input("Escola", "Minha Escola")
    prof = st.text_input("Professor", "Professor X")
    mat = st.text_input("Matéria", "Matemática")

    tipo = st.selectbox("Tipo de Prova", [
        "Mista", "Objetiva", "Dissertativa"
    ])

# ========================================================
# ABAS
# ========================================================
tab1, tab2 = st.tabs(["📝 Criar Prova", "📸 Corrigir"])

# ========================================================
# CRIAR PROVA
# ========================================================
with tab1:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.markdown("### 📁 Upload de Material")

        arquivos = st.file_uploader("PDFs", type="pdf", accept_multiple_files=True)

        if st.button("✨ Gerar Prova Inteligente"):
            if arquivos:
                texto = ""
                for arq in arquivos:
                    reader = PdfReader(arq)
                    for p in reader.pages:
                        if p.extract_text():
                            texto += p.extract_text()

                st.session_state.texto_prova = gerar_perguntas(texto, tipo)
            else:
                st.warning("Envie PDFs")

        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        if st.session_state.texto_prova:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.markdown("### ✏️ Editor")

            st.session_state.texto_prova = st.text_area(
                "Edite a prova",
                st.session_state.texto_prova,
                height=400
            )

            if st.button("📄 Gerar Documento Oficial"):
                pdf = criar_pdf(st.session_state.texto_prova)

                st.download_button(
                    "📥 Baixar PDF",
                    pdf,
                    "prova.pdf"
                )

            st.markdown("</div>", unsafe_allow_html=True)

# ========================================================
# CORRIGIR
# ========================================================
with tab2:
    col1, col2 = st.columns(2)

    with col1:
        nome = st.text_input("Nome do aluno")
        foto = st.camera_input("Foto da prova")

    with col2:
        if foto:
            if st.button("🚀 Corrigir com IA"):
                resultado = corrigir(foto, st.session_state.texto_prova)

                st.markdown("### Resultado")
                st.info(resultado)

                st.session_state.lista_notas.append({
                    "Aluno": nome,
                    "Resultado": resultado
                })

    if st.session_state.lista_notas:
        st.markdown("### 📊 Desempenho da Turma")

        df = pd.DataFrame(st.session_state.lista_notas)
        st.dataframe(df, use_container_width=True, height=300)

        st.download_button(
            "📥 Exportar CSV",
            df.to_csv(index=False),
            "notas.csv"
        )
