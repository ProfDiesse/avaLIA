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
# 1. CONFIGURAÇÕES E ESTÉTICA (CSS MOBILE)
# ========================================================
st.set_page_config(page_title="Gerador e Corretor Pro", layout="wide", page_icon="📝")

st.markdown("""
    <style>
    .stButton > button { width: 100%; border-radius: 10px; height: 3em; font-weight: bold; }
    .metric-card { background-color: #ffffff; padding: 15px; border-radius: 15px; border: 1px solid #e0e0e0; margin-bottom: 10px; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# Inicialização de variáveis de estado
if "texto_prova" not in st.session_state: st.session_state.texto_prova = ""
if "lista_notas" not in st.session_state: st.session_state.lista_notas = []

# ========================================================
# 2. MOTOR DE IA E SEGURANÇA
# ========================================================
CHAVE_API = "AIzaSyA1BIuyW5T36uXfSPspx4iSZUiRlxIw6oQ" # COLOQUE SUA CHAVE AQUI
genai.configure(api_key=CHAVE_API)

def selecionar_modelo_disponivel():
    try:
        modelos = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        prioridades = ['models/gemini-1.5-flash-latest', 'models/gemini-1.5-flash', 'models/gemini-pro']
        for p in prioridades:
            if p in modelos: return genai.GenerativeModel(model_name=p)
        return genai.GenerativeModel(model_name=modelos[0])
    except Exception as e:
        st.error(f"Erro de API: {str(e)}")
        st.stop()

# ========================================================
# 3. FUNÇÕES DE SUPORTE (PDF, QR, LIMPEZA)
# ========================================================
def limpar_texto_fpdf(texto):
    if not texto: return ""
    subs = {"“": '"', "”": '"', "‘": "'", "’": "'", "—": "-", "–": "-", "…": "...", "•": "*"}
    for original, novo in subs.items(): texto = texto.replace(original, novo)
    return texto.encode('latin-1', 'replace').decode('latin-1')

def buscar_imagem(nome_base):
    for ext in ['.png', '.jpg', '.jpeg']:
        caminho = nome_base + ext
        if os.path.exists(caminho): return caminho
    return None

def gerar_qr_code_file(link):
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=1)
        qr.add_data(link); qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white")
        caminho = "temp_qr.png"
        img_qr.save(caminho)
        return caminho
    except: return None

def gerar_perguntas_ia(texto_consolidado, tipo_prova):
    try:
        model = selecionar_modelo_disponivel()
        instrucoes = {
            "Prova Mista": "3 múltipla escolha (A-D), 3 lacunas e 4 dissertativas.",
            "Prova de Lacuna": "10 questões de completar lacunas.",
            "Prova Dissertativa": "8 questões dissertativas. Escreva (DISSERTATIVA) ao final.",
            "Prova Objetiva": "10 questões de múltipla escolha (A-D)."
        }
        prompt = f"""Aja como professor. Material: {texto_consolidado[:15000]}
        Tarefa: {instrucoes.get(tipo_prova)}
        Regras: Numere 01 a 10. Sem negritos. Fim das abertas com (DISSERTATIVA). 
        No final, escreva 'GABARITO_OFICIAL' e liste as respostas."""
        response = model.generate_content(prompt)
        return response.text
    except Exception as e: return f"ERRO IA: {str(e)}"

def corrigir_prova_por_foto(foto_frente, foto_verso, gabarito_oficial):
    try:
        model = selecionar_modelo_disponivel()
        img_frente = PIL.Image.open(foto_frente)
        prompt = [
            f"GABARITO OFICIAL: {gabarito_oficial}. Analise a prova e responda EXATAMENTE neste formato:",
            "NOTA: [0-10]", "ACERTOS: [X de 10]", "FEEDBACK: [resumo]", img_frente
        ]
        if foto_verso: prompt.append(PIL.Image.open(foto_verso))
        response = model.generate_content(prompt)
        return response.text
    except Exception as e: return f"Erro: {str(e)}"

def criar_pdf(escola, materia, prof, conteudo, link_qr, img_extra=None, tipo_prova=""):
    try:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        logo, bandeira = buscar_imagem("logoCivico"), buscar_imagem("BandeiraEscola")
        if logo: pdf.image(logo, 10, 8, 22)
        if bandeira: pdf.image(bandeira, 175, 8, 22)
        
        if link_qr:
            arq_qr = gerar_qr_code_file(link_qr)
            if arq_qr: pdf.image(arq_qr, 150 if bandeira else 175, 8, 18)

        pdf.set_y(10); pdf.set_font("Arial", 'B', 12); pdf.set_left_margin(35)
        pdf.multi_cell(0, 7, limpar_texto_fpdf(escola.upper()), align='C')
        
        pdf.set_left_margin(10); pdf.ln(10); pdf.set_font("Arial", '', 10)
        pdf.cell(140, 7, f"Aluno(a): {'_'*45}", ln=0)
        pdf.cell(0, 7, f"Data: {'_/'*2}____", ln=1)
        pdf.cell(140, 7, limpar_texto_fpdf(f"Componente: {materia}"), ln=0)
        pdf.cell(0, 7, "Nota: ________", ln=1)
        pdf.cell(0, 7, limpar_texto_fpdf(f"Professor(a): {prof}"), ln=1)
        pdf.line(10, pdf.get_y()+2, 200, pdf.get_y()+2); pdf.ln(8)

        if img_extra:
            with open("temp_extra.png", "wb") as f: f.write(img_extra.getbuffer())
            pdf.image("temp_extra.png", x=60, w=90); pdf.ln(5)

        partes = conteudo.split('GABARITO_OFICIAL')
        questoes = partes[0]
        
        pdf.set_font("Arial", '', 11)
        for linha in questoes.split('\n'):
            txt = linha.strip()
            if not txt: continue
            pdf.multi_cell(0, 7, limpar_texto_fpdf(txt))
            if "(DISSERTATIVA)" in txt.upper():
                pdf.ln(2)
                for _ in range(3):
                    if pdf.get_y() > 275: pdf.add_page()
                    pdf.line(10, pdf.get_y()+6, 200, pdf.get_y()+6); pdf.ln(8)
            pdf.ln(1)

        if tipo_prova != "Prova Dissertativa":
            if pdf.get_y() > 240: pdf.add_page()
            pdf.set_font("Arial", 'B', 9); pdf.cell(0, 6, "CARTÃO-RESPOSTA", ln=True)
            pdf.set_font("Arial", '', 8)
            for i in range(1, 11):
                pdf.cell(8, 6, f"{i:02}:", 0, 0)
                for l in ['A', 'B', 'C', 'D']: pdf.cell(7, 6, l, 1, 0, 'C')
                pdf.cell(5, 6, "", 0, 0)
                if i == 5: pdf.ln(8)

        return pdf.output(dest='S').encode('latin-1')
    except Exception as e: return None

# ========================================================
# 4. INTERFACE
# ========================================================
with st.sidebar:
    st.header("⚙️ Configurações")
    escola = st.text_input("Escola:", "CECM DOURADINA")
    prof = st.text_input("Professor:", "Diésse Ricardo da Silva")
    mat = st.text_input("Matéria:", "Educação Digital")
    link = st.text_input("Link QR:", "https://suaescola.com")
    tipo = st.selectbox("Modelo:", ["Prova Mista", "Prova de Lacuna", "Prova Dissertativa", "Prova Objetiva"])
    img_extra = st.file_uploader("🖼️ Imagem Extra", type=["png", "jpg"])

tab1, tab2 = st.tabs(["📝 Elaboração", "📸 Correção"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        arquivos = st.file_uploader("Upload PDFs", type="pdf", accept_multiple_files=True)
        if arquivos and st.button("🤖 Gerar Prova"):
            texto_full = ""
            for arq in arquivos:
                leitor = PdfReader(arq)
                texto_full += "".join([p.extract_text() for p in leitor.pages if p.extract_text()])
            st.session_state.texto_prova = gerar_perguntas_ia(texto_full, tipo)
    with col2:
        if st.session_state.texto_prova:
            st.session_state.texto_prova = st.text_area("Edite:", value=st.session_state.texto_prova, height=300)
            if st.button("📄 Baixar PDF"):
                res = criar_pdf(escola, mat, prof, st.session_state.texto_prova, link, img_extra, tipo)
                if res: st.download_button("📥 Download", res, f"{mat}.pdf")

with tab2:
    if st.session_state.texto_prova:
        nome_aluno = st.text_input("Nome do Aluno:")
        foto = st.camera_input("Foto da Prova")
        if foto and st.button("🚀 Corrigir"):
            res = corrigir_prova_por_foto(foto, None, st.session_state.texto_prova)
            nota_match = re.search(r"NOTA:\s*([\d,.]+)", res)
            nota_final = nota_match.group(1) if nota_match else "Erro"
            st.session_state.lista_notas.append({"Aluno": nome_aluno or "Anônimo", "Nota": nota_final, "Hora": pd.Timestamp.now().strftime("%H:%M")})
            st.markdown(res)

        if st.session_state.lista_notas:
            st.divider(); st.subheader("📊 Notas da Turma")
            df = pd.DataFrame(st.session_state.lista_notas)
            st.table(df)
            st.download_button("📥 Baixar Planilha", df.to_csv(index=False).encode('utf-8'), "notas.csv")
            if st.button("🗑️ Limpar"): st.session_state.lista_notas = []; st.rerun()
    else: st.warning("Gere a prova na Aba 1 primeiro.")
