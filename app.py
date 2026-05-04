
import streamlit as st
import pandas as pd
import duckdb
from datetime import datetime

# No topo do app.py, substitua a parte da conexão por esta:
def salvar_no_motherduck(form_id, setor, historico):
    try:
        # Busca o token diretamente dos segredos do Streamlit Cloud
        token = st.secrets["motherduck_token"]
        con = duckdb.connect(f"md:?motherduck_token={token}")
        
        con.execute("""
            CREATE TABLE IF NOT EXISTS resultados_quiz (
                timestamp TIMESTAMP,
                form_id VARCHAR,
                setor VARCHAR,
                p1 VARCHAR, p2 VARCHAR, p3 VARCHAR, p4 VARCHAR, p5 VARCHAR,
                p6 VARCHAR, p7 VARCHAR, p8 VARCHAR, p9 VARCHAR, p10 VARCHAR
            )
        """)
        
        timestamp = datetime.now()
        con.execute(f"INSERT INTO resultados_quiz VALUES ('{timestamp}', '{form_id}', '{setor}', " + 
                    ", ".join([f"'{res}'" for res in historico]) + ")")
        con.close()
        return True
    except Exception as e:
        st.error("Erro na conexão. Informe ao administrador.")
        return False

# Configuração visual do Streamlit
st.set_page_config(page_title="Dose de Qualidade", page_icon="🛡️")

@st.cache_data
def load_questions():
    return pd.read_csv("perguntas.csv")

df_questions = load_questions()

if 'passo' not in st.session_state:
    st.session_state.passo = "setor"
    st.session_state.setor = ""
    st.session_state.indice_pergunta = 0
    st.session_state.acertos = 0
    st.session_state.historico_respostas = []
    st.session_state.respondido = False
    st.session_state.dados_salvos = False

# --- PASSO 1: SETOR ---
if st.session_state.passo == "setor":
    st.title("🛡️ Pílula da Qualidade")
    st.subheader("Reforço Mensal de Segurança")
    setor = st.radio("Qual o seu setor?", ["Operação", "Administrativo", "Gestão"], index=None)
    if setor:
        st.session_state.setor = setor
        if st.button("Iniciar 🚀"):
            st.session_state.passo = "quiz"
            st.rerun()

# --- PASSO 2: QUIZ ---
elif st.session_state.passo == "quiz":
    idx = st.session_state.indice_pergunta
    total = len(df_questions)
    row = df_questions.iloc[idx]
    
    st.caption(f"ID: {row['form_id']} | Setor: {st.session_state.setor}")
    st.progress((idx + 1) / total)
    
    opcoes = [row['opcao_a'], row['opcao_b'], row['opcao_c'], row['opcao_d']]
    st.subheader(row['pergunta'])
    
    escolha = st.radio("Selecione a opção correta:", opcoes, index=None, key=f"p_{idx}", disabled=st.session_state.respondido)

    if escolha and not st.session_state.respondido:
        idx_escolha = opcoes.index(escolha)
        if idx_escolha == row['correta']:
            st.success(f"✅ **Correto!** \n\n {row['feedback_acerto']}")
            st.session_state.acertos += 1
            st.session_state.historico_respostas.append("Correto")
        else:
            st.error(f"❌ **Incorreto.** \n\n {row['feedback_erro']}")
            st.session_state.historico_respostas.append("Incorreto")
        st.session_state.respondido = True

    if st.session_state.respondido:
        texto_botao = "Finalizar e Salvar 🏁" if idx + 1 == total else "Próxima Pergunta ➡️"
        if st.button(texto_botao):
            if idx + 1 < total:
                st.session_state.indice_pergunta += 1
                st.session_state.respondido = False
                st.rerun()
            else:
                if not st.session_state.dados_salvos:
                    sucesso = salvar_no_motherduck(row['form_id'], st.session_state.setor, st.session_state.historico_respostas)
                    if sucesso: st.session_state.dados_salvos = True
                st.session_state.passo = "fim"
                st.rerun()

# --- PASSO 3: RESULTADO FINAL (DESEMPENHO) ---
elif st.session_state.passo == "fim":
    st.balloons()
    st.title("Dose Concluída! 🎊")
    
    # Cálculos
    total_perguntas = len(df_questions)
    acertos = st.session_state.acertos
    percentual = (acertos / total_perguntas) * 100
    
    st.markdown(f"### Parabéns pela participação, colaborador da **{st.session_state.setor}**!")
    st.write("Confira abaixo o seu desempenho técnico neste formulário:")

    # Layout de Métricas
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(label="Total de Questões", value=total_perguntas)
    
    with col2:
        st.metric(label="Quantidade de Acertos", value=acertos, delta=f"{acertos} acertos", delta_color="normal")
    
    with col3:
        # Define a cor da métrica baseado no desempenho (verde para >= 70%)
        cor_performance = "inverse" if percentual < 70 else "normal"
        st.metric(label="Aproveitamento (%)", value=f"{percentual:.0f}%", delta=None)

    # Mensagem de incentivo baseada no Score
    st.divider()
    if percentual >= 80:
        st.success("🎯 **Excelente desempenho!** Você demonstra um domínio avançado sobre as normas de segurança em Espaços Confinados.")
    elif percentual >= 50:
        st.warning("⚠️ **Bom trabalho!** Mas lembre-se: em ambientes críticos, o detalhe salva vidas. Que tal revisar os pontos que você errou?")
    else:
        st.error("🆘 **Atenção necessária.** Seu aproveitamento ficou abaixo do esperado para esta NR. Recomendamos uma leitura atenta do procedimento interno no Sólides antes da próxima operação.")

    st.info(f"Os dados deste quiz (ID: {df_questions['form_id'].iloc[0]}) foram salvos com sucesso na base de dados da Qualidade.")
    
    st.caption("Você já pode fechar esta aba do navegador.")
