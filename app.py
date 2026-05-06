import streamlit as st
import pandas as pd
import duckdb
import re
import time
from datetime import datetime

# ─────────────────────────────────────────────
# MOTHERDUCK
# ─────────────────────────────────────────────
def salvar_no_motherduck(form_id, cpf, setor, historico, tempos, tempo_total, pontuacao):
    try:
        token = st.secrets["motherduck_token"]
        con = duckdb.connect(f"md:?motherduck_token={token}")

        con.execute("""
            CREATE TABLE IF NOT EXISTS resultados_quiz (
                timestamp     TIMESTAMP,
                form_id       VARCHAR,
                cpf           VARCHAR,
                setor         VARCHAR,
                p1  VARCHAR, p2  VARCHAR, p3  VARCHAR, p4  VARCHAR, p5  VARCHAR,
                p6  VARCHAR, p7  VARCHAR, p8  VARCHAR, p9  VARCHAR, p10 VARCHAR,
                t1  DOUBLE,  t2  DOUBLE,  t3  DOUBLE,  t4  DOUBLE,  t5  DOUBLE,
                t6  DOUBLE,  t7  DOUBLE,  t8  DOUBLE,  t9  DOUBLE,  t10 DOUBLE,
                tempo_total   DOUBLE,
                pontuacao     INTEGER
            )
        """)

        timestamp = datetime.now()

        # Garante 10 posições para respostas e tempos
        h = historico + [""] * (10 - len(historico))
        t = tempos    + [0.0] * (10 - len(tempos))

        con.execute(
            """INSERT INTO resultados_quiz VALUES (
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?
            )""",
            [timestamp, form_id, cpf, setor,
             h[0], h[1], h[2], h[3], h[4], h[5], h[6], h[7], h[8], h[9],
             t[0], t[1], t[2], t[3], t[4], t[5], t[6], t[7], t[8], t[9],
             tempo_total, pontuacao]
        )
        con.close()
        return True
    except Exception as e:
        st.error("Erro na conexão com o banco de dados. Informe ao administrador.")
        return False


# ─────────────────────────────────────────────
# PONTUAÇÃO
# Acerto: 1.000 pts base + bônus de até 99 pts (referência: 30s)
# Erro:   0 pts
# Máximo: 10 × 1.099 = 10.990 pts
# Garantia matemática: 1 acerto a mais sempre vale mais do que
# qualquer combinação de bônus de velocidade (bônus total máx = 990 pts < 1.000 pts)
# ─────────────────────────────────────────────
TEMPO_REF  = 30    # segundos de referência por pergunta
BASE_ACERTO = 1000
BONUS_MAX   = 99

def calcular_pontos(acertou: bool, tempo_segundos: float) -> int:
    if not acertou:
        return 0
    bonus = max(0, round(BONUS_MAX * (TEMPO_REF - tempo_segundos) / TEMPO_REF))
    return BASE_ACERTO + bonus


# ─────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────
st.set_page_config(page_title="Check da Qualidade", page_icon="🛡️")

@st.cache_data
def load_questions():
    return pd.read_csv("perguntas.csv")

df_questions = load_questions()

# ─── Session State ───────────────────────────
if "passo" not in st.session_state:
    st.session_state.passo               = "setor"
    st.session_state.setor               = ""
    st.session_state.cpf                 = ""
    st.session_state.indice_pergunta     = 0
    st.session_state.acertos             = 0
    st.session_state.pontuacao           = 0
    st.session_state.historico_respostas = []
    st.session_state.tempos_respostas    = []   # tempo gasto em cada pergunta (s)
    st.session_state.tempo_inicio_quiz   = None # epoch do início do quiz
    st.session_state.tempo_inicio_perg   = None # epoch do início da pergunta atual
    st.session_state.respondido          = False
    st.session_state.dados_salvos        = False


# ─────────────────────────────────────────────
# PASSO 1 — SETOR
# ─────────────────────────────────────────────
if st.session_state.passo == "setor":
    st.title("🛡️ Check da Qualidade")
    st.subheader("Reforço Mensal de Segurança")

    setor = st.radio("Qual o seu setor?", ["Operação", "Administrativo", "Gestão"], index=None)
    if setor:
        st.session_state.setor = setor
        if st.button("Continuar ➡️"):
            st.session_state.passo = "cpf"
            st.rerun()


# ─────────────────────────────────────────────
# PASSO 2 — CPF
# ─────────────────────────────────────────────
elif st.session_state.passo == "cpf":
    st.title("🛡️ Check da Qualidade")
    st.subheader("Identificação")

    st.caption("Somente números. Pontos e traços são ignorados automaticamente.")
    cpf_raw = st.text_input("Digite o seu CPF", placeholder="Ex: 00000000000")

    # Sanitiza: mantém apenas dígitos
    cpf_limpo = re.sub(r"\D", "", cpf_raw)

    # Contador customizado — exibe só após começar a digitar
    if cpf_raw:
        st.caption(f"Dígitos digitados: {len(cpf_limpo)} / 11")

    # Botão sempre visível — validação acontece no clique, sem Enter intermediário
    if st.button("Iniciar Quiz 🚀"):
        if len(cpf_limpo) != 11:
            st.warning("O CPF deve ter exatamente 11 dígitos.")
        else:
            st.session_state.cpf = cpf_limpo
            st.session_state.tempo_inicio_quiz = time.time()
            st.session_state.tempo_inicio_perg = time.time()
            st.session_state.passo = "quiz"
            st.rerun()


# ─────────────────────────────────────────────
# PASSO 3 — QUIZ
# ─────────────────────────────────────────────
elif st.session_state.passo == "quiz":
    idx   = st.session_state.indice_pergunta
    total = len(df_questions)
    row   = df_questions.iloc[idx]

    st.caption(f"ID: {row['form_id']} | Setor: {st.session_state.setor}")
    st.progress((idx + 1) / total)

    opcoes = [row["opcao_a"], row["opcao_b"], row["opcao_c"], row["opcao_d"]]
    st.subheader(row["pergunta"])

    escolha = st.radio(
        "Selecione a opção correta:",
        opcoes,
        index=None,
        key=f"p_{idx}",
        disabled=st.session_state.respondido
    )

    if escolha and not st.session_state.respondido:
        # Calcula tempo gasto nesta pergunta
        tempo_perg = round(time.time() - st.session_state.tempo_inicio_perg, 2)
        st.session_state.tempos_respostas.append(tempo_perg)

        idx_escolha = opcoes.index(escolha)
        acertou     = idx_escolha == row["correta"]
        pts         = calcular_pontos(acertou, tempo_perg)
        st.session_state.pontuacao += pts

        if acertou:
            st.success(f"✅ **Correto!** (+{pts} pts)\n\n{row['feedback_acerto']}")
            st.session_state.acertos += 1
            st.session_state.historico_respostas.append("Correto")
        else:
            st.error(f"❌ **Incorreto.** (+0 pts)\n\n{row['feedback_erro']}")
            st.session_state.historico_respostas.append("Incorreto")

        st.session_state.respondido = True

    if st.session_state.respondido:
        texto_botao = "Finalizar e Salvar 🏁" if idx + 1 == total else "Próxima Pergunta ➡️"
        if st.button(texto_botao):
            if idx + 1 < total:
                st.session_state.indice_pergunta += 1
                st.session_state.respondido       = False
                st.session_state.tempo_inicio_perg = time.time()
                st.rerun()
            else:
                tempo_total = round(time.time() - st.session_state.tempo_inicio_quiz, 2)
                if not st.session_state.dados_salvos:
                    sucesso = salvar_no_motherduck(
                        form_id     = row["form_id"],
                        cpf         = st.session_state.cpf,
                        setor       = st.session_state.setor,
                        historico   = st.session_state.historico_respostas,
                        tempos      = st.session_state.tempos_respostas,
                        tempo_total = tempo_total,
                        pontuacao   = st.session_state.pontuacao
                    )
                    if sucesso:
                        st.session_state.dados_salvos   = True
                        st.session_state.tempo_total_fim = tempo_total
                st.session_state.passo = "fim"
                st.rerun()


# ─────────────────────────────────────────────
# PASSO 4 — RESULTADO FINAL
# ─────────────────────────────────────────────
elif st.session_state.passo == "fim":
    st.balloons()
    st.title("Dose Concluída! 🎊")

    total_perguntas = len(df_questions)
    acertos         = st.session_state.acertos
    percentual      = (acertos / total_perguntas) * 100
    pontuacao       = st.session_state.pontuacao
    pontuacao_max   = total_perguntas * (BASE_ACERTO + BONUS_MAX)
    tempo_total     = getattr(st.session_state, "tempo_total_fim", 0)

    # Formata tempo total em mm:ss
    minutos  = int(tempo_total // 60)
    segundos = int(tempo_total % 60)
    tempo_str = f"{minutos}m {segundos:02d}s"

    st.markdown(f"### Parabéns pela participação, colaborador da **{st.session_state.setor}**!")
    st.write("Confira abaixo o seu desempenho neste formulário:")

    # ── Métricas ──────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total de Questões", total_perguntas)
    with col2:
        st.metric("Acertos", acertos)
    with col3:
        st.metric("Aproveitamento", f"{percentual:.0f}%")
    with col4:
        st.metric("Pontuação", f"{pontuacao:,}".replace(",", "."))

    st.caption(f"⏱️ Tempo total de resposta: **{tempo_str}** | Pontuação máxima possível: {pontuacao_max:,}".replace(",", "."))

    # ── Mensagem de incentivo ─────────────────
    st.divider()
    if percentual >= 80:
        st.success("🎯 **Excelente desempenho!** Você demonstra domínio avançado sobre o tema. Continue sendo referência em segurança!")
    elif percentual >= 50:
        st.warning("⚠️ **Bom trabalho!** Mas lembre-se: em ambientes críticos, o detalhe salva vidas. Que tal revisar os pontos que você errou?")
    else:
        st.error("🆘 **Atenção necessária.** Seu aproveitamento ficou abaixo do esperado. Recomendamos uma leitura atenta do procedimento interno no Sólides antes da próxima operação.")

    st.info(f"Os dados deste quiz (ID: {df_questions['form_id'].iloc[0]}) foram salvos com sucesso na base de dados da Qualidade.")
    st.caption("Você já pode fechar esta aba do navegador.")
