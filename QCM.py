import json, os, random
import streamlit as st

# ============ CONFIG ==================
st.set_page_config(page_title="QCM Trainer", layout="wide")

# ---------- helpers génériques ----------

def force_rerun():
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()


# ---------- FS helpers ----------

def get_modules():
    return [d for d in os.listdir() if os.path.isdir(d) and not d.startswith(".")]


def get_jsons(module):
    return [f for f in os.listdir(module) if f.endswith(".json")]


def load_qcm(module, lesson_file):
    with open(os.path.join(module, lesson_file), encoding="utf-8") as f:
        return json.load(f)


# ============ SESSION INIT =============

def init_state():
    defaults = dict(
        screen="menu",  # menu / lesson / mode / quiz
        selected_module=None,
        selected_lesson=None,
        qcm=None,
        order=[],
        idx=0,
        scores=[],
        answers={},  # conserve les cases cochées {idx: set(indices)}
        mode="Aléatoire",
        show=False,
        finished=False,
        show_review=False,
    )
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)


init_state()


# ============ QUIZ helpers =============

def reset_quiz():
    qcm = st.session_state.qcm
    total = len(qcm)
    st.session_state.order = (
        random.sample(range(total), total)
        if st.session_state.mode == "Aléatoire"
        else list(range(total))
    )
    st.session_state.idx = 0  # démarre directement
    st.session_state.scores = [None] * total
    st.session_state.answers = {}
    st.session_state.show = False
    st.session_state.finished = False
    st.session_state.show_review = False


# ------------------------------------------------------------
#                       SIDEBAR
# ------------------------------------------------------------
with st.sidebar:
    st.header("Navigation")
    if st.button("🏠  Menu principal"):
        st.session_state.screen = "menu"
        force_rerun()

    if st.session_state.selected_module:
        if st.button(f"📚  {st.session_state.selected_module}"):
            st.session_state.screen = "lesson"
            force_rerun()

    if st.session_state.selected_lesson:
        st.markdown(f"**Leçon :** {st.session_state.selected_lesson[:-5]}")

# ------------------------------------------------------------
#                   ENTÊTE + flèche retour
# ------------------------------------------------------------
col_back, col_title = st.columns([0.04, 0.96])
if st.session_state.screen in {"lesson", "mode", "quiz"}:
    if col_back.button("⬅", key="back_arrow_btn"):
        prev = {"lesson": "menu", "mode": "lesson", "quiz": "mode"}
        st.session_state.screen = prev[st.session_state.screen]
        force_rerun()
else:
    col_back.write(" ")

col_title.markdown("## 🎓 QCM Trainer")

# ------------------------------------------------------------
#                       ÉCRAN : MENU
# ------------------------------------------------------------
if st.session_state.screen == "menu":
    st.subheader("Choisis un module :")
    for mod in get_modules():
        if st.button(mod, key=f"mod_{mod}"):
            st.session_state.selected_module = mod
            st.session_state.screen = "lesson"
            force_rerun()

# ------------------------------------------------------------
#                       ÉCRAN : LEÇON
# ------------------------------------------------------------
elif st.session_state.screen == "lesson":
    st.subheader(f"Module : {st.session_state.selected_module}")
    st.write("Choisis une leçon :")
    for lesson_file in get_jsons(st.session_state.selected_module):
        nice = lesson_file[:-5]
        if st.button(nice, key=f"lesson_{lesson_file}"):
            st.session_state.selected_lesson = lesson_file
            st.session_state.qcm = load_qcm(st.session_state.selected_module, lesson_file)
            st.session_state.screen = "mode"
            force_rerun()

# ------------------------------------------------------------
#                       ÉCRAN : MODE
# ------------------------------------------------------------
elif st.session_state.screen == "mode":
    st.subheader(f"Leçon : {st.session_state.selected_lesson[:-5]}")
    st.radio("Mode des questions :", ("Aléatoire", "Ordre fixe"),
             index=0 if st.session_state.mode == "Aléatoire" else 1, key="mode")
    if st.button("▶️  Commencer le QCM"):
        reset_quiz()
        st.session_state.screen = "quiz"
        force_rerun()

# ------------------------------------------------------------
#                       ÉCRAN : QUIZ
# ------------------------------------------------------------
elif st.session_state.screen == "quiz":
    qcm = st.session_state.qcm
    total = len(qcm)

    def current_q():
        return qcm[st.session_state.order[st.session_state.idx]]

    def record_score():
        q = current_q()
        good = set(q["correct"])
        user = st.session_state.answers.get(st.session_state.idx, set())
        if user == good:
            sc = 1.0
        elif user - good:
            sc = 0.0
        else:
            sc = len(user & good) / len(good)
        st.session_state.scores[st.session_state.idx] = sc
        return sc

    def next_q():
        record_score()
        st.session_state.idx += 1
        st.session_state.show = False
        if st.session_state.idx >= total:
            st.session_state.finished = True

    def prev_q():
        if st.session_state.idx > 0:
            st.session_state.idx -= 1
            st.session_state.show = False

    # ----- fin
    if st.session_state.finished:
        final = sum(st.session_state.scores)
        st.markdown(f"## 🎉 Score final : **{final:.2f} / {total}**")
        wrong = [i for i, s in enumerate(st.session_state.scores) if s < 1]

        c1, c2, c3 = st.columns(3)
        with c1:
            if wrong and st.button("📝 Corrections"):
                st.session_state.show_review = not st.session_state.show_review
        with c2:
            if st.button("🔄 Retry"):
                reset_quiz(); force_rerun()
        with c3:
            if st.button("🏠 Menu"):
                st.session_state.screen = "menu"; force_rerun()

        if st.session_state.show_review and wrong:
            st.markdown("### ❌ Questions mal / partiellement répondues")
            for idx in wrong:
                q = qcm[st.session_state.order[idx]]
                st.write(f"**Q{idx+1}. {q['question']}**")
                for i, ch in enumerate(q['choices']):
                    prefix = "✅" if i in q['correct'] else "❌"
                    st.write(f"{prefix} {chr(65+i)}. {ch}")
                st.markdown("---")
        st.stop()

    # ----- affichage
    q = current_q()
    st.progress(st.session_state.idx / total)
    st.write(f"Question {st.session_state.idx + 1} / {total}")
    st.write(f"**{q['question']}**")

    # --- cases à cocher avec persistance manuelle ---
    selected = st.session_state.answers.get(st.session_state.idx, set())
    for i, txt in enumerate(q['choices']):
        checked = i in selected
        if st.checkbox(f"{chr(65+i)}. {txt}", value=checked, key=f"chk_{st.session_state.idx}_{i}"):
            selected.add(i)
        else:
            selected.discard(i)
    st.session_state.answers[st.session_state.idx] = selected

    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        if st.session_state.idx > 0 and st.button("Précédente"):
            prev_q(); force_rerun()
    with col2:
        if st.button("Vérifier"):
            st.session_state.show = True
    with col3:
        if st.button("Suivante"):
            next_q(); force_rerun()

    if st.session_state.show:
        sc = record_score()
        good = set(q['correct'])
        if sc == 1.0:
            st.success("✅ Correct !")
        elif sc == 0.0:
            st.error("❌ Incorrect !")
        else:
            st.warning("⚠️ Partiellement correct !")
        st.write("Bonne(s) réponse(s) : " + ", ".join(chr(65+i) for i in good))
        st.write(f"Note : **{sc:.2f} / 1**")
