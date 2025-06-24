import json, os, random
import streamlit as st

# ================= App‑wide helpers =================

def force_rerun():
    """Compatibility wrapper so the code works on every Streamlit version."""
    if hasattr(st, "rerun"):
        st.rerun()
    else:
        st.experimental_rerun()

# ---------- file system helpers ----------

def get_modules():
    """Return every *folder* inside the working directory (ignores dot‑folders)."""
    return [d for d in os.listdir() if os.path.isdir(d) and not d.startswith(".")]


def get_jsons(module: str):
    return [f for f in os.listdir(module) if f.endswith(".json")]


def load_qcm(module: str, lesson_file: str):
    with open(os.path.join(module, lesson_file), "r", encoding="utf-8") as f:
        return json.load(f)

# ================= Session‑state bootstrap =================

def init_state():
    state_defaults = {
        "screen": "menu",         # menu / lesson / mode / quiz
        "selected_module": None,
        "selected_lesson": None,
        "qcm": None,
        "order": [],
        "idx": -1,
        "scores": [],
        "mode": "Aléatoire",     # or "Ordre fixe"
        "show": False,
        "finished": False,
        "show_review": False,
    }
    for k, v in state_defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ================== quiz helpers =====================

def reset_quiz():
    qcm = st.session_state.qcm
    total = len(qcm)
    st.session_state.order = (
        random.sample(range(total), total)
        if st.session_state.mode == "Aléatoire"
        else list(range(total))
    )
    st.session_state.idx = -1
    st.session_state.scores = [None] * total
    st.session_state.show = False
    st.session_state.finished = False
    st.session_state.show_review = False


# ------------------------------------------------------------
#                       SIDEBAR / NAV
# ------------------------------------------------------------
with st.sidebar:
    st.header("Navigation")

    # Always available
    if st.button("🏠  Menu principal"):
        st.session_state.screen = "menu"
        force_rerun()

    # Clickable module name
    if st.session_state.selected_module:
        if st.button(f"📚  {st.session_state.selected_module}"):
            st.session_state.screen = "lesson"
            force_rerun()

    # Reminder of current lesson
    if st.session_state.selected_lesson:
        st.markdown(f"**Leçon :** {st.session_state.selected_lesson.replace('.json','')}")

# ------------------------------------------------------------
#                       HEADER with BACK ARROW
# ------------------------------------------------------------
header_col1, header_col2 = st.columns([0.05, 0.95])

# "←" is *only* shown if we can effectively go back one screen
show_back = st.session_state.screen in {"lesson", "mode", "quiz"}
if show_back:
    if header_col1.button("←", key="back_arrow_btn"):
        # simple stack‑less router
        prev = {
            "lesson": "menu",
            "mode": "lesson",
            "quiz": "mode",
        }
        st.session_state.screen = prev[st.session_state.screen]
        force_rerun()
else:
    header_col1.write(" ")  # placeholder to keep alignment

header_col2.markdown("## 🎓QCM Trainer")

# ------------------------------------------------------------
#                      SCREEN : MENU  (choose module)
# ------------------------------------------------------------
if st.session_state.screen == "menu":
    st.subheader("Choisis un module :")
    for mod in get_modules():
        if st.button(mod, key=f"mod_{mod}"):
            st.session_state.selected_module = mod
            st.session_state.selected_lesson = None
            st.session_state.screen = "lesson"
            force_rerun()

# ------------------------------------------------------------
#                      SCREEN : LESSON  (choose json)
# ------------------------------------------------------------
elif st.session_state.screen == "lesson":
    if not st.session_state.selected_module:
        st.warning("Aucun module sélectionné.")
        st.stop()

    st.subheader(f"Module : {st.session_state.selected_module}")
    st.write("Choisis une leçon :")

    for lesson_file in get_jsons(st.session_state.selected_module):
        nice_name = lesson_file.replace(".json", "")
        if st.button(nice_name, key=f"lesson_{lesson_file}"):
            st.session_state.selected_lesson = lesson_file
            st.session_state.qcm = load_qcm(st.session_state.selected_module, lesson_file)
            st.session_state.screen = "mode"
            force_rerun()

# ------------------------------------------------------------
#                      SCREEN : MODE  (random / fixed)
# ------------------------------------------------------------
elif st.session_state.screen == "mode":
    if not st.session_state.qcm:
        st.warning("Aucune leçon chargée.")
        st.stop()

    st.subheader(f"Leçon : {st.session_state.selected_lesson.replace('.json','')}")
    st.radio("Mode des questions :", ("Aléatoire", "Ordre fixe"),
             index=0 if st.session_state.mode == "Aléatoire" else 1,
             key="mode")

    if st.button("▶️ Commencer le QCM"):
        reset_quiz()
        st.session_state.screen = "quiz"
        force_rerun()

# ------------------------------------------------------------
#                      SCREEN : QUIZ
# ------------------------------------------------------------
elif st.session_state.screen == "quiz":
    qcm = st.session_state.qcm
    total = len(qcm)

    def current_q():
        return qcm[st.session_state.order[st.session_state.idx]]

    def record_score():
        q = current_q()
        good = set(q["correct"])
        user = {i for i in range(len(q["choices"])) if st.session_state.get(f"chk_{st.session_state.idx}_{i}", False)}
        if user == good:
            score = 1.0
        elif user - good:
            score = 0.0
        else:
            score = len(user & good) / len(good)
        st.session_state.scores[st.session_state.idx] = score
        return score

    def next_q():
        if 0 <= st.session_state.idx < total:
            record_score()
        st.session_state.idx += 1
        st.session_state.show = False
        if st.session_state.idx >= total:
            st.session_state.finished = True

    def prev_q():
        if st.session_state.idx > 0:
            st.session_state.idx -= 1
            st.session_state.show = True

    # ---- End of quiz
    if st.session_state.finished:
        final = sum(s for s in st.session_state.scores if s is not None)
        st.markdown(f"## 🎉 Score final : **{final:.2f} / {total}**")

        wrong_idx = [i for i, s in enumerate(st.session_state.scores) if s is not None and s < 1]

        cols_end = st.columns(3)
        with cols_end[0]:
            if wrong_idx and st.button("📝 Corrections"):
                st.session_state.show_review = not st.session_state.show_review
        with cols_end[1]:
            if st.button("🔄 Retry"):
                reset_quiz(); force_rerun()
        with cols_end[2]:
            if st.button("🏠 Menu"):
                st.session_state.screen = "menu"; force_rerun()

        if st.session_state.show_review and wrong_idx:
            st.markdown("### ❌ Questions mal / partiellement répondues")
            for idx in wrong_idx:
                q = qcm[st.session_state.order[idx]]
                st.write(f"**Q{idx+1}. {q['question']}**")
                for i, ch in enumerate(q['choices']):
                    prefix = "✅" if i in q['correct'] else "❌"
                    st.write(f"{prefix} {chr(65+i)}. {ch}")
                st.markdown("---")
        st.stop()

    # ---- Before start (idx == -1)
    if st.session_state.idx == -1:
        if st.button("Commencer"):
            next_q(); force_rerun()
        st.stop()

    # ---- Question view
    q = current_q()
    st.progress(st.session_state.idx / total)
    st.write(f"Question {st.session_state.idx + 1} / {total}")
    st.write(f"**{q['question']}**")

    for i, txt in enumerate(q['choices']):
        st.checkbox(f"{chr(65+i)}. {txt}", key=f"chk_{st.session_state.idx}_{i}")

    col_prev, col_verif, col_next = st.columns([1, 3, 1])
    with col_prev:
        if st.session_state.idx > 0 and st.button("Précédente"):
            prev_q(); force_rerun()
    with col_verif:
        if st.button("Vérifier"):
            st.session_state.show = True
    with col_next:
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
        st.write("Bonne(s) réponse(s) : " + ", ".join(chr(65+i) for i in good))
        st.write(f"Note : **{sc:.2f} / 1**")
