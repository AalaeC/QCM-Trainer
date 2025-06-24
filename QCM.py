import json, random, glob, os
import streamlit as st

# ================= CONFIG =================
st.set_page_config(page_title="QCM Trainer", layout="centered")
st.title("🎓 QCM Trainer")

# ----------- DISK HELPERS -----------------
BASE_DIR = os.getcwd()                          # racine du projet


def available_modules():
    """Sous‑dossiers contenant au moins un *.json*."""
    return sorted([d for d in os.listdir(BASE_DIR)
                   if os.path.isdir(d) and glob.glob(os.path.join(d, "*.json"))])


def available_sets(module: str):
    """Noms de fichiers json (sans extension) pour un module."""
    return sorted([os.path.splitext(os.path.basename(p))[0]
                   for p in glob.glob(os.path.join(module, "*.json"))])


def load_set(module: str, lesson: str):
    """Charge <module>/<lesson>.json et met à jour le state."""
    path = os.path.join(module, f"{lesson}.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        st.error(f"Fichier {path} introuvable !")
        st.stop()
    st.session_state.QCM     = data
    st.session_state.TOTAL   = len(data)
    st.session_state.module  = module
    st.session_state.lesson  = lesson

# ------------- STATE UTILS ---------------

def force_rerun():
    (st.rerun if hasattr(st, "rerun") else st.experimental_rerun)()


def reset_state():
    """Ré‑initialise ordre, index et scores en conservant set & mode."""
    mode  = st.session_state.get("mode", "Aléatoire")
    total = st.session_state.TOTAL
    st.session_state.order = random.sample(range(total), total) if mode == "Aléatoire" else list(range(total))
    st.session_state.idx         = -1
    st.session_state.scores      = [None]*total
    st.session_state.show        = False
    st.session_state.finished    = False
    st.session_state.show_review = False

# ------------- FIRST LOAD ---------------
if "module" not in st.session_state:
    m0 = available_modules()[0]
    l0 = available_sets(m0)[0]
    load_set(m0, l0)

if "mode" not in st.session_state:
    st.session_state.mode = "Aléatoire"
if "order" not in st.session_state:
    reset_state()

QCM   = st.session_state.QCM
TOTAL = st.session_state.TOTAL

# ------------- HELPERS ------------------

def current_q():
    return QCM[st.session_state.order[st.session_state.idx]]


def record_score():
    q    = current_q()
    good = set(q["correct"])
    user = {i for i in range(len(q["choices"])) if st.session_state.get(f"chk_{st.session_state.idx}_{i}")}
    score = 0.0 if user - good else len(user & good)/len(good)
    st.session_state.scores[st.session_state.idx] = score
    return score


def next_q():
    if 0 <= st.session_state.idx < TOTAL:
        record_score()
    st.session_state.idx += 1
    st.session_state.show = False
    if st.session_state.idx >= TOTAL:
        st.session_state.finished = True


def prev_q():
    if st.session_state.idx > 0:
        st.session_state.idx -= 1
        st.session_state.show = True

# ============ SIDEBAR NAV ============
st.sidebar.header("Navigation")

if st.sidebar.button("🏠 Menu principal"):
    reset_state(); st.session_state.idx = -1; force_rerun()

mods = available_modules()
mod_sel = st.sidebar.selectbox("Module", mods, index=mods.index(st.session_state.module))
sets = available_sets(mod_sel)
lesson_sel = st.sidebar.selectbox("Leçon", sets, index=sets.index(st.session_state.lesson) if mod_sel == st.session_state.module else 0)

if (mod_sel != st.session_state.module) or (lesson_sel != st.session_state.lesson):
    load_set(mod_sel, lesson_sel); reset_state(); st.session_state.idx = -1; force_rerun()

# ============ MAIN FLOW ============

# ---- FIN ----
if st.session_state.finished:
    final = sum(s for s in st.session_state.scores if s is not None)
    st.markdown(f"## 🎉 Score final : **{final:.2f} / {TOTAL}**")

    wrong = [i for i, s in enumerate(st.session_state.scores) if s is not None and s < 1]
    if wrong and st.button("Afficher corrections des erreurs"):
        st.session_state.show_review = not st.session_state.show_review

    if st.session_state.show_review and wrong:
        st.markdown("### ❌ Questions erronées")
        for idx in wrong:
            real = st.session_state.order[idx]
            q = QCM[real]
            st.write(f"**Q{real+1}. {q['question']}**")
            for j, ch in enumerate(q['choices']):
                pref = "✅" if j in q['correct'] else "❌"
                st.write(f"{pref} {chr(65+j)}. {ch}")
            st.markdown("---")

    if st.button("Réessayer"):
        reset_state(); force_rerun()
    st.stop()

# ---- MENU PRINCIPAL ----
if st.session_state.idx == -1:
    st.subheader("Menu principal")
    mode_choice = st.radio("Mode des questions :", ("Aléatoire", "Ordre fixe"),
                           index=0 if st.session_state.mode == "Aléatoire" else 1)
    if mode_choice != st.session_state.mode:
        st.session_state.mode = mode_choice; reset_state()
    if st.button("Commencer"):
        next_q(); force_rerun()
    st.stop()

# ---- QUESTION ----
q = current_q()
st.progress(st.session_state.idx / TOTAL)

st.write(f"Module **{st.session_state.module}** | Set **{st.session_state.lesson}** | Q {st.session_state.idx+1}/{TOTAL}")

st.write(f"**{q['question']}**")
for i, txt in enumerate(q['choices']):
    st.checkbox(f"{chr(65+i)}. {txt}", key=f"chk_{st.session_state.idx}_{i}")

c_prev, c_ver, c_next = st.columns([1,3,1])
with c_prev:
    if st.session_state.idx > 0 and st.button("Question précédente"):
        prev_q(); force_rerun()
with c_ver:
    if st.button("Vérifier"):
        st.session_state.show = True
with c_next:
    if st.button("Question suivante"):
        next_q(); force_rerun()

# ---- CORRECTION ----
if st.session_state.show:
    score = record_score()
    good  = set(q['correct'])

    if score == 1:
        st.success("✅ Correct !")
    elif score == 0:
        st.error("❌ Incorrect")
    else:
        st.warning("⚠️ Partiellement correct")

    if score < 1:
        st.write("Bonne(s) réponse(s) : " + ", ".join(chr(65+i) for i in good))
    st.write(f"Note : **{score:.2f} / 1**")
