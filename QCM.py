import json, os, random, streamlit as st

# ============ CONFIGURATION ============
st.set_page_config(page_title="QCM Trainer", layout="wide")
st.title("🎓 QCM Trainer")

# -------- UTILS FICHIERS ---------------
def list_modules() -> list[str]:
    return [d for d in os.listdir() if os.path.isdir(d) and not d.startswith(".")]

def list_jsons(module: str) -> list[str]:
    return [f for f in os.listdir(module) if f.endswith(".json")]

def load_qcm(module: str, lesson: str) -> list[dict]:
    with open(f"{module}/{lesson}", encoding="utf-8") as f:
        return json.load(f)

def force_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:                     # Streamlit < 1.25
        st.experimental_rerun()

# -------- ÉTAT DE SESSION --------------
if "screen" not in st.session_state:
    st.session_state.update(
        screen          = "menu",   # menu | lesson | mode | quiz
        module          = None,
        lesson          = None,
        qcm             = None,
        mode            = "Aléatoire",
        order           = [],
        idx             = -1,
        scores          = [],
        show            = False,
        finished        = False,
        show_review     = False,
    )

# -------- FONCTIONS QUIZ ---------------
def reset_quiz():
    qcm   = st.session_state.qcm
    total = len(qcm)
    st.session_state.order = (
        random.sample(range(total), total)
        if st.session_state.mode == "Aléatoire"
        else list(range(total))
    )
    st.session_state.idx      = -1
    st.session_state.scores   = [None]*total
    st.session_state.finished = False
    st.session_state.show     = False
    st.session_state.show_review = False

def current_q():
    return st.session_state.qcm[st.session_state.order[st.session_state.idx]]

def note_courante() -> float:
    q     = current_q()
    good  = set(q["correct"])
    user  = {i for i in range(len(q["choices"]))
             if st.session_state.get(f"chk_{st.session_state.idx}_{i}", False)}
    if user == good:
        return 1.0
    if user - good:
        return 0.0
    return len(user & good) / len(good)

# -------- BARRE LATÉRALE ---------------
with st.sidebar:
    st.header("Navigation")
    st.markdown("**Module** : "
                f"{st.session_state.module or '*—*'}  \n"
                "**Leçon** : "
                f"{(st.session_state.lesson or '*—*').replace('.json','')}")
    if st.button("🏠 Menu principal"):
        st.session_state.screen = "menu"
        st.session_state.module = st.session_state.lesson = None
        force_rerun()

# ======== ÉCRANS PRINCIPAUX ============

# ---------- 1) MENU MODULES ------------
if st.session_state.screen == "menu":
    st.subheader("Choisis un module")
    for mod in list_modules():
        if st.button(mod):
            st.session_state.module  = mod
            st.session_state.screen  = "lesson"
            force_rerun()
    st.stop()

# ----- 2) MENU LEÇONS DU MODULE -------
if st.session_state.screen == "lesson":
    st.subheader(f"Module : {st.session_state.module}")
    if st.button("← Retour"):
        st.session_state.screen = "menu"; force_rerun()
    st.markdown("### Sélectionne une leçon")
    for js in list_jsons(st.session_state.module):
        label = js.replace(".json","")
        if st.button(label):
            st.session_state.lesson = js
            st.session_state.qcm    = load_qcm(st.session_state.module, js)
            st.session_state.screen = "mode"
            force_rerun()
    st.stop()

# ---------- 3) CHOIX ALÉA / FIXE -------
if st.session_state.screen == "mode":
    st.subheader(f"Leçon : {st.session_state.lesson.replace('.json','')}")
    if st.button("← Retour"):
        st.session_state.screen = "lesson"; force_rerun()
    st.radio("Mode des questions :", ("Aléatoire", "Ordre fixe"),
             key="mode",
             index=0 if st.session_state.mode == "Aléatoire" else 1)
    if st.button("🚀 Commencer le QCM"):
        reset_quiz()
        st.session_state.screen = "quiz"
        force_rerun()
    st.stop()

# --------------- 4) QUIZ ---------------
if st.session_state.screen == "quiz":
    qcm   = st.session_state.qcm
    total = len(qcm)

    def next_q():
        if 0 <= st.session_state.idx < total:
            st.session_state.scores[st.session_state.idx] = note_courante()
        st.session_state.idx += 1
        st.session_state.show = False
        if st.session_state.idx >= total:
            st.session_state.finished = True

    def prev_q():
        if st.session_state.idx > 0:
            st.session_state.idx -= 1
            st.session_state.show = True

    # -------- FIN DU QCM --------
    if st.session_state.finished:
        total_score = sum(st.session_state.scores)
        st.success(f"### Score final : **{total_score:.2f} / {total}**")

        wrong = [i for i,s in enumerate(st.session_state.scores) if s < 1]
        if wrong and st.button("Afficher corrections des erreurs"):
            st.session_state.show_review = not st.session_state.show_review
        if st.session_state.show_review:
            st.markdown("#### Questions incorrectes / partielles")
            for i in wrong:
                q = qcm[ st.session_state.order[i] ]
                st.write(f"**Q{i+1}. {q['question']}**")
                for j,c in enumerate(q["choices"]):
                    p = "✅" if j in q["correct"] else "❌"
                    st.write(f"{p} {chr(65+j)}. {c}")
                st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Recommencer ce QCM"):
                reset_quiz(); st.session_state.screen="quiz"; force_rerun()
        with col2:
            if st.button("🏠 Retour menu"):
                st.session_state.screen="menu"; st.session_state.module=None; st.session_state.lesson=None
                force_rerun()
        st.stop()

    # -------- AVANT 1ʳᵉ QUESTION -------
    if st.session_state.idx == -1:
        if st.button("Commencer"):
            next_q(); force_rerun()
        st.stop()

    # -------- AFFICHAGE QUESTION --------
    q = current_q()
    st.progress(st.session_state.idx / total)
    st.write(f"**Question {st.session_state.idx+1}/{total}**")
    st.write(f"**{q['question']}**")

    for i, ch in enumerate(q["choices"]):
        st.checkbox(f"{chr(65+i)}. {ch}", key=f"chk_{st.session_state.idx}_{i}")

    col1, col2, col3 = st.columns([1,2,1])
    with col1:
        if st.session_state.idx>0 and st.button("← Précédente"):
            prev_q(); force_rerun()
    with col2:
        if st.button("Vérifier"):
            st.session_state.show = True
    with col3:
        if st.button("Suivante →"):
            next_q(); force_rerun()

    # -------- ZONE CORRECTION ----------
    if st.session_state.show:
        score = note_courante()
        good  = set(q["correct"])
        if score == 1:
            st.success("✅ Correct")
        elif score == 0:
            st.error("❌ Incorrect")
        else:
            st.warning("⚠️ Partiellement correct")
        st.write("Bonne(s) réponse(s) : " + ", ".join(chr(65+i) for i in good))
        st.write(f"Note : **{score:.2f} / 1**")
