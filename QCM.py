import json, os, random
import streamlit as st

st.set_page_config(page_title="QCM Trainer", layout="wide")

# --------------------------------------------------
# Helpers
# --------------------------------------------------

def force_rerun():
    (st.rerun if hasattr(st, "rerun") else st.experimental_rerun)()


def get_modules():
    return [d for d in os.listdir() if os.path.isdir(d) and not d.startswith('.')]


def get_jsons(module):
    return [f for f in os.listdir(module) if f.endswith('.json')]


def load_qcm(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)

# ---------------- Exam‑simili ---------------------

def build_exam(module: str, target: int):
    """Build composite exam (20 or 40 Q). Rules:
    target=20 → min1 / max5  — target=40 → min2 / max10"""
    lessons = get_jsons(module)
    banks   = {lf: load_qcm(os.path.join(module, lf)) for lf in lessons}

    # single lesson ⇒ just slice up to target
    if len(banks) == 1:
        bank = next(iter(banks.values()))
        random.shuffle(bank)
        return bank[:min(target, len(bank))]

    # multi‑lesson
    min_q, max_q = (1, 5) if target == 20 else (2, 10)
    sizes = {lf: len(b) for lf,b in banks.items()}; tot = sum(sizes.values())
    quotas = {lf: max(min_q, min(max_q, round(sizes[lf]/tot*target))) for lf in lessons}

    while sum(quotas.values()) < target:
        for lf in quotas:
            if quotas[lf] < min(max_q, sizes[lf]):
                quotas[lf] += 1
                if sum(quotas.values()) == target: break
    while sum(quotas.values()) > target:
        for lf in quotas:
            if quotas[lf] > min_q:
                quotas[lf] -= 1
                if sum(quotas.values()) == target: break

    exam=[]
    for lf, n in quotas.items():
        exam.extend(random.sample(banks[lf], n))
    random.shuffle(exam)
    return exam

# --------------------------------------------------
# Session init (unchanged)
# --------------------------------------------------

def init_state():
    base=dict(screen='menu', selected_module=None, selected_lesson=None,
              qcm=[], order=[], idx=0, scores=[], answers={}, mode='Aléatoire',
              show=False, finished=False, show_review=False, exam_mode=False)
    for k,v in base.items(): st.session_state.setdefault(k,v)
init_state()

# --------------------------------------------------
# Quiz reset (unchanged)
# --------------------------------------------------

def reset_quiz():
    tot=len(st.session_state.qcm)
    st.session_state.order=(random.sample(range(tot),tot)
                            if st.session_state.mode=='Aléatoire' or st.session_state.exam_mode
                            else list(range(tot)))
    st.session_state.idx=0; st.session_state.scores=[None]*tot
    st.session_state.answers={}; st.session_state.show=False
    st.session_state.finished=False; st.session_state.show_review=False

# --------------------------------------------------
# Sidebar nav (unchanged)
# --------------------------------------------------
with st.sidebar:
    st.header('Navigation')
    if st.button('🏠 Menu principal'):
        st.session_state.update(screen='menu', selected_module=None,
                                selected_lesson=None, exam_mode=False); force_rerun()
    if st.session_state.selected_module:
        if st.button(f"📚 {st.session_state.selected_module}"):
            st.session_state.update(screen='lesson', selected_lesson=None,
                                    exam_mode=False); force_rerun()
    if st.session_state.exam_mode: st.markdown('**Exam‑simili**')
    elif st.session_state.selected_lesson:
        st.markdown(f"**Leçon :** {st.session_state.selected_lesson[:-5]}")

# --------------------------------------------------
# Header+arrow (unchanged)
# --------------------------------------------------
col_b,col_t=st.columns([0.05,0.95])
if st.session_state.screen in {'lesson','mode','quiz'}:
    if col_b.button('⬅', key='back'):        
        prev={'lesson':'menu','mode':'lesson','quiz':'lesson' if st.session_state.exam_mode else 'mode'}
        st.session_state.screen=prev[st.session_state.screen]
        if st.session_state.screen!='quiz': st.session_state.exam_mode=False
        force_rerun()
else: col_b.write(' ')
col_t.markdown('## 🎓 QCM Trainer')

# --------------------------------------------------
# Screens
# --------------------------------------------------
if st.session_state.screen=='menu':
    st.subheader('Choisis un module :')
    for m in get_modules():
        if st.button(m):
            st.session_state.update(selected_module=m, screen='lesson'); force_rerun()

elif st.session_state.screen=='lesson':
    mod = st.session_state.selected_module
    st.subheader(f'Module : {mod}')

    # ---------- Liste des leçons ----------
    st.write('Choisis une leçon :')
    for lf in get_jsons(mod):
        if st.button(lf[:-5]):
            st.session_state.update(selected_lesson=lf,
                                    qcm=load_qcm(os.path.join(mod, lf)),
                                    exam_mode=False, screen='mode'); force_rerun()

    # ---------- Exam‑simili ----------
    st.markdown('---')
    st.markdown('Générer un examen :')
    col20, col40 = st.columns(2)
    with col20:
        if st.button('🧪 Exam simili 20 Q'):
            st.session_state.update(qcm=build_exam(mod,20), exam_mode=True,
                                    mode='Aléatoire', screen='quiz'); reset_quiz(); force_rerun()
    with col40:
        if st.button('🧪 Exam simili 40 Q'):
            st.session_state.update(qcm=build_exam(mod,40), exam_mode=True,
                                    mode='Aléatoire', screen='quiz'); reset_quiz(); force_rerun()

elif st.session_state.screen=='mode':
    st.subheader(f"Leçon : {st.session_state.selected_lesson[:-5]}")
    st.radio('Mode des questions :', ('Aléatoire','Ordre fixe'),
             index=0 if st.session_state.mode=='Aléatoire' else 1, key='mode')
    if st.button('▶️ Commencer le QCM'):
        reset_quiz(); st.session_state.screen='quiz'; force_rerun()

elif st.session_state.screen=='quiz':
    qcm=st.session_state.qcm; total=len(qcm)
    def cur(): return qcm[ st.session_state.order[ st.session_state.idx ] ]
    def rec():
        q=cur(); good=set(q['correct']); user=st.session_state.answers.get(st.session_state.idx,set())
        score=1 if user==good else 0 if user-good else len(user&good)/len(good)
        st.session_state.scores[ st.session_state.idx ] = score; return score
    def move(d):
        rec(); st.session_state.idx+=d
        if st.session_state.idx>=total: st.session_state.finished=True
        if st.session_state.idx<0: st.session_state.idx=0
        st.session_state.show=False

    # ---- FIN ----
    if st.session_state.finished:
        final=sum(st.session_state.scores); wrong=[i for i,s in enumerate(st.session_state.scores) if s<1]
        st.markdown(f"## 🎉 Score : {final:.2f}/{total}")
        c1,c2,c3=st.columns(3)
        with c1:
            if wrong and st.button('📝 Corrections'):
                st.session_state.show_review=not st.session_state.show_review
        with c2:
            if st.button('🔄 Retry'):
                reset_quiz(); force_rerun()
        with c3:
            if st.button('🏠 Menu'):
                st.session_state.update(screen='menu', exam_mode=False); force_rerun()
        if st.session_state.show_review and wrong:
            for idx in wrong:
                q=qcm[ st.session_state.order[idx] ]
                st.write(f"**Q{idx+1}. {q['question']}**")
                for i,ch in enumerate(q['choices']):
                    st.write(f"{'✅' if i in q['correct'] else '❌'} {chr(65+i)}. {ch}")
                st.divider()
        st.stop()

    # ---- Question ----
    q=cur(); st.progress((st.session_state.idx+1)/total)
    st.write(f"Question {st.session_state.idx+1}/{total}")
    st.write(f"**{q['question']}**")
    stored=st.session_state.answers.get(st.session_state.idx,set()).copy(); new=set()
    for i,txt in enumerate(q['choices']):
        if st.checkbox(f"{chr(65+i)}. {txt}", value=i in stored): new.add(i)
    st.session_state.answers[ st.session_state.idx ] = new

    col_p,col_v,col_n=st.columns([1,3,1])
    with col_p: st.button('← Précédente', disabled=st.session_state.idx==0, on_click=lambda:move(-1))
    with col_v: st.button('Vérifier', on_click=lambda: st.session_state.__setitem__('show',True))
    with col_n: st.button('Suivante →', on_click=lambda:move(+1))

    if st.session_state.show:
        note=rec(); good=set(q['correct'])
        if note==1: st.success('✅ Correct')
        elif note==0: st.error('❌ Incorrect')
        else: st.warning('⚠️ Partiellement correct')
        st.write('Réponse(s) attendue(s) : '+', '.join(chr(65+i) for i in good))
        st.write(f'Note : {note:.2f}/1')
