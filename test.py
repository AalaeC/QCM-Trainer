"""
Improved QCM Trainer application.

This Streamlit application builds on top of the original QCM Trainer by adding
several quality of life improvements and new features:

* **Modern navigation** – a sidebar menu lets you jump between the Quiz,
  Add Question and Stats sections.  Rather than a linear flow through
  menu/lesson/mode/quiz screens the app uses simple select boxes to choose
  modules, lessons and exam size.

* **Exam timer** – when enabled the exam page shows a countdown and
  automatically finishes the test when time is up.  You can pick any
  duration from 1–120 minutes.  The remaining time is recomputed on every
  interaction and displayed at the top of the question page.

* **Persistent statistics** – after finishing an exam your results are
  aggregated into a persistent JSON file (`stats.json`) so you can track
  progress across sessions.  The Stats page displays your attempts per
  lesson or exam along with average scores.

* **Question authoring** – a dedicated page lets you add questions to
  existing lessons or create entirely new modules and lessons.  The simple
  form captures the question text, four answer choices and the correct
  answers (multi‑select).  Questions are saved in the same JSON format as
  the rest of the app with proper UTF‑8 encoding.

* **Exam customization** – you can choose the number of questions for
  exam‑simulations (20/40 or any number up to the pool size) and whether to
  present them in random or fixed order.

* **Detailed results** – at the end of each quiz the app displays your
  score, a breakdown of each question’s result (✅ correct, ⚠️ partiel,
  ❌ incorrect) and the correct answers for review.  A retry button lets
  you take the same quiz again with a fresh order.

This file is fully self‑contained and can be run directly with

```bash
streamlit run improved_qcm_app.py
```

It assumes that the directory structure used by the original QCM Trainer
(`Biochimie/`, `Hématologie/` etc.) is present in the working directory and
contains lesson files with `.json` extension following the schema:

```json
{
  "question": "...",
  "choices": ["...", "...", "...", "..."],
  "correct": [0, 2]
}
```

Copyright © 2025
"""

import json
import os
import random
import time
from datetime import datetime
from typing import Dict, List, Optional

import streamlit as st


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

STATS_FILE = "stats.json"


def load_stats() -> Dict[str, Dict[str, float]]:
    """Load persistent statistics from the stats file if it exists.

    Returns a dictionary mapping unique quiz identifiers (e.g. module/lesson or
    module/Exam-20) to an aggregate of attempts, correct answers and total
    questions.  If the file does not exist an empty dict is returned.
    """
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            return {k: v for k, v in data.items() if isinstance(v, dict)}
        except Exception:
            # If the file is corrupted return empty stats
            return {}
    return {}


def save_stats(stats: Dict[str, Dict[str, float]]) -> None:
    """Persist the statistics dictionary to disk.

    The file is written with UTF‑8 encoding and pretty printed for easier
    inspection.  Any exception while writing the file is silently ignored.
    """
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# -----------------------------------------------------------------------------
# Helpers for loading and saving QCM data
# -----------------------------------------------------------------------------

def get_modules() -> List[str]:
    """Return the list of visible module directories in the current working dir.

    Any directory starting with a dot (hidden folders) is ignored.  The
    returned list is sorted for a stable display order.
    """
    mods = [d for d in os.listdir() if os.path.isdir(d) and not d.startswith(".")]
    mods.sort()
    return mods


def get_jsons(module: str) -> List[str]:
    """Return the list of JSON lesson files inside a module directory.

    Only files ending with `.json` are returned.  The list is sorted.
    """
    try:
        files = [f for f in os.listdir(module) if f.endswith(".json")]
        files.sort()
        return files
    except FileNotFoundError:
        return []


def load_qcm(path: str) -> List[Dict]:
    """Load a QCM JSON file and return its list of questions.

    Each question is a dictionary with keys `question`, `choices` and
    `correct`.  If the file cannot be read an empty list is returned.
    """
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_qcm(path: str, data: List[Dict]) -> None:
    """Save a list of questions to a QCM JSON file.

    The JSON is written with UTF‑8 encoding and pretty printed.  If the
    directory does not exist it is created.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_exam(module: str, target: int) -> List[Dict]:
    """Build a composite exam from all lessons within a module.

    When multiple lessons exist, a quota is computed proportional to the size
    of each lesson's question bank with a minimum and maximum per lesson.  The
    quotas are adjusted so that the total number of questions equals the
    target.  Questions are randomly sampled from each lesson and then
    shuffled.
    """
    lessons = get_jsons(module)
    banks: Dict[str, List[Dict]] = {lf: load_qcm(os.path.join(module, lf)) for lf in lessons}

    # If there is only one lesson just slice up to the target
    if len(banks) == 1:
        bank = next(iter(banks.values()))
        random.shuffle(bank)
        return bank[:min(target, len(bank))]

    # Determine quotas per lesson
    min_q, max_q = (1, 5) if target <= 20 else (2, 10)
    sizes = {lf: len(b) for lf, b in banks.items()}
    total_size = sum(sizes.values())
    quotas = {lf: max(min_q, min(max_q, round(sizes[lf] / total_size * target))) for lf in lessons}

    # Adjust quotas to hit target exactly
    while sum(quotas.values()) < target:
        for lf in quotas:
            if quotas[lf] < min(max_q, sizes[lf]):
                quotas[lf] += 1
                if sum(quotas.values()) == target:
                    break
    while sum(quotas.values()) > target:
        for lf in quotas:
            if quotas[lf] > min_q:
                quotas[lf] -= 1
                if sum(quotas.values()) == target:
                    break

    exam: List[Dict] = []
    for lf, n in quotas.items():
        exam.extend(random.sample(banks[lf], n))
    random.shuffle(exam)
    return exam


# -----------------------------------------------------------------------------
# Quiz logic
# -----------------------------------------------------------------------------

def initialize_state() -> None:
    """Initialize the Streamlit session state with default values."""
    defaults = {
        "quiz_questions": [],  # list of questions currently loaded
        "question_order": [],  # randomised order of indices
        "current_index": 0,  # current question index in order
        "scores": [],  # list of float scores per question
        "answers": {},  # mapping from question index to selected answer indices
        "finished": False,  # whether the quiz has finished
        "show_review": False,  # whether to show review of wrong answers
        "module": None,  # currently selected module
        "lesson": None,  # currently selected lesson file (string) or None for exam
        "exam_size": None,  # number of questions in exam simulation
        "random_order": True,  # whether to randomise question order
        "timer_enabled": False,  # whether countdown is active
        "timer_duration": 20,  # duration in minutes
        "timer_end": None,  # end timestamp for countdown
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def reset_quiz() -> None:
    """Reset quiz-related state variables to start a new quiz."""
    total = len(st.session_state.quiz_questions)
    order = list(range(total))
    if st.session_state.random_order:
        random.shuffle(order)
    st.session_state.question_order = order
    st.session_state.current_index = 0
    st.session_state.scores = [None] * total
    st.session_state.answers = {}
    st.session_state.finished = False
    st.session_state.show_review = False
    # Reset timer end when starting new quiz
    if st.session_state.timer_enabled:
        st.session_state.timer_end = time.time() + st.session_state.timer_duration * 60
    else:
        st.session_state.timer_end = None


def record_score() -> None:
    """Record the score for the current question based on the user's answer."""
    q_index = st.session_state.question_order[st.session_state.current_index]
    question = st.session_state.quiz_questions[q_index]
    good = set(question.get("correct", []))
    user = st.session_state.answers.get(st.session_state.current_index, set())
    # full points for all correct selections and no extras, partial if missing or extra
    if user == good:
        score = 1.0
    elif user - good:
        # user selected at least one wrong answer – zero points
        score = 0.0
    else:
        # partial credit based on intersection
        score = len(user & good) / len(good) if good else 0.0
    st.session_state.scores[st.session_state.current_index] = score


def update_stats() -> None:
    """Aggregate quiz results into persistent statistics at the end of a quiz."""
    stats = load_stats()
    # Build key: module/lesson or module/Exam-X
    if st.session_state.lesson:
        key = f"{st.session_state.module}/{st.session_state.lesson[:-5]}"
    else:
        key = f"{st.session_state.module}/Exam-{st.session_state.exam_size}"
    total_correct = sum(1 for s in st.session_state.scores if s == 1)
    total_questions = len(st.session_state.scores)
    entry = stats.get(key, {"attempts": 0, "correct": 0, "total": 0})
    entry["attempts"] += 1
    entry["correct"] += total_correct
    entry["total"] += total_questions
    stats[key] = entry
    save_stats(stats)


def show_timer() -> None:
    """Display remaining time and end quiz if time has expired."""
    if st.session_state.timer_enabled and st.session_state.timer_end:
        remaining = st.session_state.timer_end - time.time()
        if remaining <= 0:
            # Time's up: finish the quiz immediately
            st.warning("⏰ Temps écoulé ! Le quiz est terminé.")
            st.session_state.finished = True
            return
        # Display remaining minutes and seconds
        mins, secs = divmod(int(remaining), 60)
        st.info(f"Temps restant : {mins:02d}:{secs:02d}")


def quiz_page() -> None:
    """Main logic for the Quiz page."""
    initialize_state()

    # --- Selection of module and lesson ---
    st.subheader("Choisis un module et une leçon ou un examen")
    modules = get_modules()
    if not modules:
        st.error("Aucun module trouvé. Créez un module via la page 'Add Question'.")
        return
    module = st.selectbox("Module", modules, index=modules.index(st.session_state.module) if st.session_state.module in modules else 0)
    st.session_state.module = module

    lessons = get_jsons(module)
    lesson_options = [lf[:-5] for lf in lessons]
    exam_options = ["Exam 20", "Exam 40", "Exam personnalisé"]
    choice = st.selectbox("Leçon ou examen", lesson_options + exam_options, index=0)

    # Determine whether a lesson or exam is selected
    selected_lesson_file: Optional[str] = None
    exam_size: Optional[int] = None
    if choice in lesson_options:
        selected_lesson_file = lessons[lesson_options.index(choice)]
        st.session_state.lesson = selected_lesson_file
        st.session_state.exam_size = None
    else:
        st.session_state.lesson = None
        if choice == "Exam 20":
            exam_size = 20
        elif choice == "Exam 40":
            exam_size = 40
        else:
            # Custom exam size input
            max_size = sum(len(load_qcm(os.path.join(module, lf))) for lf in lessons)
            exam_size = st.number_input("Nombre de questions dans l'examen", min_value=1, max_value=max_size, value=20)
        st.session_state.exam_size = int(exam_size)

    # --- Options ---
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.random_order = st.radio("Ordre des questions", ["Aléatoire", "Fixe"], index=0 if st.session_state.random_order else 1) == "Aléatoire"
    with col2:
        st.session_state.timer_enabled = st.checkbox("Activer un compte à rebours", value=st.session_state.timer_enabled)
        if st.session_state.timer_enabled:
            st.session_state.timer_duration = st.number_input("Durée (minutes)", min_value=1, max_value=120, value=int(st.session_state.timer_duration))
    # Start quiz button
    if st.button("▶️ Commencer le QCM"):
        # Load questions depending on lesson or exam
        if selected_lesson_file:
            qcm_path = os.path.join(module, selected_lesson_file)
            st.session_state.quiz_questions = load_qcm(qcm_path)
        else:
            st.session_state.quiz_questions = build_exam(module, st.session_state.exam_size)
        # If there are no questions, abort
        if not st.session_state.quiz_questions:
            st.error("Aucune question trouvée pour ce choix.")
        else:
            reset_quiz()

    # If there is an active quiz, display it
    if st.session_state.quiz_questions and not st.session_state.finished:
        show_timer()
        question_list = st.session_state.quiz_questions
        total_questions = len(question_list)
        cur_index = st.session_state.current_index
        current_question = question_list[st.session_state.question_order[cur_index]]
        st.progress((cur_index + 1) / total_questions, text=f"Question {cur_index + 1}/{total_questions}")
        st.write(f"**{current_question['question']}**")
        # Retrieve stored answers or initialise
        stored = st.session_state.answers.get(cur_index, set()).copy()
        new_selection: set = set()
        for i, txt in enumerate(current_question.get('choices', [])):
            # Multi-select via checkboxes
            if st.checkbox(f"{chr(65 + i)}. {txt}", value=i in stored, key=f"q{cur_index}_{i}"):
                new_selection.add(i)
        st.session_state.answers[cur_index] = new_selection
        # Navigation buttons
        col_p, col_v, col_n = st.columns([1, 2, 1])
        with col_p:
            st.button("← Précédente", disabled=cur_index == 0, on_click=lambda: move_question(-1))
        with col_v:
            st.button("Vérifier", on_click=lambda: st.session_state.__setitem__('show_check', True))
        with col_n:
            st.button("Suivante →", on_click=lambda: move_question(+1))

        # Show immediate feedback when requested
        if st.session_state.get('show_check'):
            record_score()
            note = st.session_state.scores[cur_index]
            correct_indices = set(current_question.get('correct', []))
            if note == 1.0:
                st.success('✅ Correct')
            elif note == 0.0:
                st.error('❌ Incorrect')
            else:
                st.warning('⚠️ Partiellement correct')
            st.write('Réponse(s) attendue(s) : ' + ', '.join(chr(65 + i) for i in correct_indices))
            st.write(f'Note : {note:.2f}/1')
            # Reset show_check so it must be clicked again for the next question
            st.session_state.show_check = False

    # If the quiz is finished, display results
    if st.session_state.quiz_questions and st.session_state.finished:
        # Ensure final score for last question is recorded
        if st.session_state.scores[st.session_state.current_index] is None:
            record_score()
        total = len(st.session_state.scores)
        final_score = sum(st.session_state.scores)
        st.markdown(f"## Score final : {final_score:.2f}/{total}")
        # Buttons after completion
        c1, c2, c3 = st.columns(3)
        with c1:
            st.button('Corrections', on_click=lambda: st.session_state.__setitem__('show_review', not st.session_state.show_review))
        with c2:
            st.button('Recommencer', on_click=lambda: (reset_quiz(), st.experimental_rerun()))
        with c3:
            st.button('Retour au menu', on_click=lambda: st.session_state.__setitem__('quiz_questions', []))
        # Show review of wrong or partially correct questions
        if st.session_state.show_review:
            for idx_in_order, score in enumerate(st.session_state.scores):
                if score < 1.0:
                    q_index = st.session_state.question_order[idx_in_order]
                    question = st.session_state.quiz_questions[q_index]
                    st.write(f"**Q{idx_in_order + 1}. {question['question']}**")
                    for i, choice in enumerate(question.get('choices', [])):
                        prefix = '✅' if i in question.get('correct', []) else '❌'
                        st.write(f"{prefix} {chr(65 + i)}. {choice}")
                    st.divider()
        # Update stats after showing results (only once per completion)
        if not st.session_state.get('stats_updated', False):
            update_stats()
            st.session_state.stats_updated = True


def move_question(delta: int) -> None:
    """Move to the next or previous question, recording the current score."""
    record_score()
    st.session_state.current_index += delta
    if st.session_state.current_index >= len(st.session_state.quiz_questions):
        st.session_state.finished = True
        st.session_state.current_index = len(st.session_state.quiz_questions) - 1
    if st.session_state.current_index < 0:
        st.session_state.current_index = 0
    # Reset immediate feedback flag
    st.session_state.show_check = False


# -----------------------------------------------------------------------------
# Add question page
# -----------------------------------------------------------------------------

def add_question_page() -> None:
    """Form allowing the user to add questions or create modules/lessons."""
    st.subheader("Ajouter une question / Créer un module")
    modules = get_modules()
    # Provide option to select existing module or enter a new module name
    col_mod_sel, col_mod_new = st.columns(2)
    with col_mod_sel:
        module = st.selectbox("Module existant", modules + ["<Créer un nouveau module>"], index=0)
    new_module_name: Optional[str] = None
    with col_mod_new:
        if module == "<Créer un nouveau module>":
            new_module_name = st.text_input("Nom du nouveau module")
    if new_module_name:
        module = new_module_name.strip()
    if not module:
        st.info("Saisissez un nom de module pour continuer.")
        return

    # Determine lesson file
    existing_lessons = get_jsons(module) if os.path.exists(module) else []
    lesson_placeholder = "<Créer une nouvelle leçon>"
    lesson = st.selectbox("Leçon existante", [lf for lf in existing_lessons] + [lesson_placeholder], index=0)
    new_lesson_name: Optional[str] = None
    if lesson == lesson_placeholder:
        new_lesson_name = st.text_input("Nom de la nouvelle leçon (sans .json)")
    if new_lesson_name:
        lesson_file = new_lesson_name.strip() + ".json"
    else:
        lesson_file = lesson

    # Question input
    st.markdown("---")
    st.subheader("Saisie de la question")
    question_text = st.text_area("Enoncé de la question")
    choice_inputs: List[str] = []
    for i in range(4):
        choice_inputs.append(st.text_input(f"Choix {chr(65 + i)}", key=f"choice_add_{i}"))
    correct_indices = st.multiselect("Réponses correctes", options=list(range(4)), format_func=lambda x: chr(65 + x))
    # Save button
    if st.button("Enregistrer la question"):
        if not question_text.strip():
            st.error("Le texte de la question ne peut pas être vide.")
        elif any(not c.strip() for c in choice_inputs):
            st.error("Tous les choix doivent être renseignés.")
        elif not correct_indices:
            st.error("Veuillez sélectionner au moins une réponse correcte.")
        else:
            # Build path and load existing data
            if module not in get_modules() and new_module_name:
                os.makedirs(module, exist_ok=True)
            path = os.path.join(module, lesson_file)
            data = load_qcm(path) if os.path.exists(path) else []
            data.append({
                "question": question_text.strip(),
                "choices": [c.strip() for c in choice_inputs],
                "correct": sorted(list(correct_indices))
            })
            save_qcm(path, data)
            st.success(f"Question ajoutée à {module}/{lesson_file}")


# -----------------------------------------------------------------------------
# Statistics page
# -----------------------------------------------------------------------------

def stats_page() -> None:
    """Display aggregated statistics of quiz results across sessions."""
    st.subheader("Statistiques")
    stats = load_stats()
    if not stats:
        st.info("Aucune tentative enregistrée pour l'instant.")
        return
    # Build table data
    rows = []
    for key, entry in stats.items():
        attempts = entry.get("attempts", 0)
        correct = entry.get("correct", 0)
        total = entry.get("total", 0)
        avg = (correct / total) * 100 if total else 0
        rows.append({
            "Module/Leçon ou Examen": key,
            "Tentatives": attempts,
            "Total questions": total,
            "Réponses correctes": correct,
            "Score moyen (%)": round(avg, 2)
        })
    # Sort by module name
    rows.sort(key=lambda x: x["Module/Leçon ou Examen"])
    st.dataframe(rows, hide_index=True)


# -----------------------------------------------------------------------------
# Main app
# -----------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="QCM Trainer Amélioré", layout="wide")
    st.title("🎓 QCM Trainer – Version améliorée")
    # Sidebar navigation
    page = st.sidebar.radio("Navigation", options=["Quiz", "Add Question", "Stats"])
    if page == "Quiz":
        quiz_page()
    elif page == "Add Question":
        add_question_page()
    elif page == "Stats":
        stats_page()


if __name__ == "__main__":
    main()
