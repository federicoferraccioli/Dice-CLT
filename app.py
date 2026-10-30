"""Roll the dice: the central limit theorem with the whole class (Lesson 10).

Students (default page): two quick predictions, then 30 rolls of a die
(rolled by the app, or a real die typed in), then submit.
Teacher (add ?teacher to the address, then the password): live results,
the histograms of single rolls and of averages, the spread versus sigma/sqrt(n),
CSV export (readable by R/dice.R), reset.

Run locally:   streamlit run app.py
Deploy:        see README.md in this folder (Streamlit Community Cloud).
"""

import csv
import io
import math
import os
import re
import threading
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st

# ----------------------------------------------------------------------------- settings
N_ROLLS = 30
MU, VAR = 3.5, 35 / 12                          # one roll of a balanced die
TEAL, RED, GREY = "#1B9E97", "#9B0E14", "#484F59"
FACES = "⚀⚁⚂⚃⚄⚅"

Q_SHAPE = "Before rolling: the averages of 10 rolls, collected from the whole class, will look..."
SHAPES = ["Flat, like a single die", "Bell-shaped, around 3.5",
          "U-shaped, mostly near 1 and 6", "I have no idea"]
Q_SPREAD = "Compared with single rolls, the averages of 10 rolls will spread..."
SPREADS = ["More", "About the same", "Less", "I have no idea"]
Q_ROLLS = "Your 30 rolls"
FIELDS = ["time", "source", Q_SHAPE, Q_SPREAD, Q_ROLLS]

DATA_DIR = Path(os.environ.get("DICE_DATA_DIR", Path(__file__).parent / "responses"))
DATA_FILE = DATA_DIR / "class_dice.csv"


def secret(name, default=None):
    try:
        return st.secrets[name]
    except Exception:
        return os.environ.get(name, default)


# ----------------------------------------------------------------------------- shared store
class Store:
    """All the answers of the class, shared by every visitor of the app.
    Kept in memory and appended to a CSV file, so a restart does not lose them."""

    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.Lock()
        self.rows = []
        if path.exists():
            with open(path, newline="", encoding="utf-8") as f:
                self.rows = list(csv.DictReader(f))

    def add(self, row):
        with self.lock:
            self.rows.append(row)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            new = not self.path.exists()
            with open(self.path, "a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=FIELDS)
                if new:
                    w.writeheader()
                w.writerow(row)

    def clear(self):
        with self.lock:
            if self.path.exists():
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                self.path.rename(self.path.with_name(f"class_dice_{stamp}.csv"))
            self.rows = []

    def snapshot(self):
        with self.lock:
            return list(self.rows)


@st.cache_resource
def get_store():
    return Store(DATA_FILE)


# ----------------------------------------------------------------------------- data helpers
def parse_rolls(text):
    """'3 6 1', '3,6,1', '361' ... -> [3, 6, 1]; values outside 1-6 are dropped."""
    out = []
    for tok in re.split(r"[^0-9]+", text or ""):
        if not tok:
            continue
        if len(tok) > 1 and re.fullmatch(r"[1-6]+", tok):
            out.extend(int(c) for c in tok)
        elif tok.isdigit() and 1 <= int(tok) <= 6:
            out.append(int(tok))
    return out


def class_rolls(rows):
    """One list of rolls per student (at most 30, at least 10)."""
    res = []
    for r in rows:
        v = parse_rolls(r.get(Q_ROLLS, ""))[:N_ROLLS]
        if len(v) >= 10:
            res.append(v)
    return res


def averages(rolls_by_student, k):
    """Averages of k consecutive rolls, within each student (complete groups only)."""
    out = []
    for v in rolls_by_student:
        g = len(v) // k
        out.extend(np.mean(np.array(v[: g * k]).reshape(g, k), axis=1))
    return np.array(out)


def bars(means, k, min_width=0.25):
    """Histogram as densities; each bar holds the same number of possible averages."""
    m = math.ceil(min_width * k)
    j = np.floor((np.round(means * k) - k) / m).astype(int)
    idx, counts = np.unique(j, return_counts=True)
    centre = (k + idx * m + (m - 1) / 2) / k
    return centre, counts / len(means) / (m / k), 0.9 * m / k


def example_rows(n_students=20, seed=None):
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n_students):
        rows.append({
            "time": datetime.now().isoformat(timespec="seconds"), "source": "example",
            Q_SHAPE: rng.choice(SHAPES, p=[0.3, 0.35, 0.1, 0.25]),
            Q_SPREAD: rng.choice(SPREADS, p=[0.2, 0.3, 0.4, 0.1]),
            Q_ROLLS: " ".join(map(str, rng.integers(1, 7, N_ROLLS))),
        })
    return rows


# ----------------------------------------------------------------------------- plots
def style(ax):
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GREY)
    ax.tick_params(colors=GREY, labelsize=11)
    ax.yaxis.grid(True, color="#e6e6e6")
    ax.set_axisbelow(True)


def plot_predictions(rows):
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.2))
    for ax, q, opts, title in ((axes[0], Q_SHAPE, SHAPES, "The averages of 10 rolls will look..."),
                               (axes[1], Q_SPREAD, SPREADS, "...and will spread")):
        counts = [sum(r.get(q) == o for r in rows) for o in opts]
        ax.barh(range(len(opts))[::-1], counts, color=TEAL, alpha=0.6)
        ax.set_yticks(range(len(opts))[::-1], opts)
        ax.set_title(title, loc="left", fontsize=13)
        style(ax)
        ax.yaxis.grid(False)
        ax.xaxis.grid(True, color="#e6e6e6")
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    fig.tight_layout()
    return fig


def plot_single(rolls_by_student):
    allv = np.concatenate([np.array(v) for v in rolls_by_student])
    share = [np.mean(allv == f) for f in range(1, 7)]
    fig, ax = plt.subplots(figsize=(8, 3.4))
    ax.bar(range(1, 7), share, color=TEAL, alpha=0.6, width=0.8)
    ax.axhline(1 / 6, color=RED, linestyle="--", linewidth=1.2)
    ax.text(6.45, 1 / 6, "1/6", color=RED, va="center")
    ax.set_xticks(range(1, 7))
    ax.set_xlabel("Face")
    ax.set_ylabel("Share of the rolls")
    style(ax)
    fig.tight_layout()
    return fig, len(allv)


def plot_averages(rolls_by_student, ks=(1, 2, 10), curves=False):
    fig, axes = plt.subplots(1, len(ks), figsize=(12, 3.8), sharey=True)
    for ax, k in zip(axes, ks):
        m = averages(rolls_by_student, k)
        c, d, w = bars(m, k)
        ax.bar(c, d, width=w, color=TEAL, alpha=0.6)
        if curves and k > 1:
            x = np.linspace(0.6, 6.4, 400)
            sd = math.sqrt(VAR / k)
            ax.plot(x, np.exp(-0.5 * ((x - MU) / sd) ** 2) / (sd * math.sqrt(2 * math.pi)),
                    color=RED, linewidth=2)
        ax.set_xlim(0.6, 6.4)
        ax.set_xticks(range(1, 7))
        ax.set_title("single rolls" if k == 1 else f"averages of {k} rolls", loc="left", fontsize=13)
        ax.text(0.98, 0.95, f"{len(m)} values", transform=ax.transAxes, ha="right", va="top",
                color=GREY, fontsize=10)
        ax.set_xlabel("value")
        style(ax)
    axes[0].set_ylabel("Density")
    fig.tight_layout()
    return fig


def spread_table(rolls_by_student, ks=(1, 2, 10, 30)):
    rows = []
    for k in ks:
        m = averages(rolls_by_student, k)
        if len(m) < 2:
            continue
        rows.append({"rolls in each average": k, "values": len(m),
                     "average": round(float(np.mean(m)), 2),
                     "observed spread (sd)": round(float(np.std(m, ddof=1)), 2),
                     "theory: σ/√n": round(math.sqrt(VAR / k), 2)})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- student page
def student_page(store):
    st.title("🎲 Roll the dice")
    ss = st.session_state

    if ss.get("submitted"):
        st.success("Thank you! Your rolls are in. Now look at the screen.")
        v = ss.get("my_rolls", [])
        if v:
            st.write("Your rolls:", " ".join(FACES[x - 1] for x in v))
            st.write(f"Your average: **{np.mean(v):.2f}** · averages of your three groups of 10: "
                     + ", ".join(f"**{np.mean(v[i:i + 10]):.1f}**" for i in range(0, len(v) - 9, 10)))
        return

    st.markdown("**1. Two quick predictions, before rolling.** There is no wrong answer.")
    shape = st.radio(Q_SHAPE, SHAPES, index=None, key="shape")
    spread = st.radio(Q_SPREAD, SPREADS, index=None, key="spread")
    if shape is None or spread is None:
        st.info("Answer both questions to go on.")
        return

    st.markdown(f"**2. Roll a die {N_ROLLS} times.**")
    mode = st.radio("How?", ["Let the app roll for me", "I have a real die"], horizontal=True,
                    key="mode", label_visibility="collapsed")
    rolls = []
    if mode == "Let the app roll for me":
        if "virtual" not in ss:
            if st.button(f"Roll {N_ROLLS} times", type="primary"):
                ss.virtual = [int(x) for x in np.random.default_rng().integers(1, 7, N_ROLLS)]
                st.rerun()
        if "virtual" in ss:
            rolls = ss.virtual
            st.markdown(
                "<div style='font-size:2.3rem; line-height:1.15; letter-spacing:0.05em'>"
                + "".join(FACES[x - 1] for x in rolls) + "</div>", unsafe_allow_html=True)
            st.caption(" ".join(map(str, rolls)))
    else:
        text = st.text_area(f"Type your {N_ROLLS} rolls, separated by spaces", key="real",
                            placeholder="3 6 1 4 4 2 ...")
        rolls = parse_rolls(text)
        if text:
            msg = f"{len(rolls)} rolls read"
            (st.success if len(rolls) == N_ROLLS else st.warning)(
                msg + ("" if len(rolls) == N_ROLLS else f" (we need {N_ROLLS})"))
        rolls = rolls[:N_ROLLS] if len(rolls) >= N_ROLLS else []

    if rolls:
        st.markdown("**3. Send them.**")
        if st.button("Send my rolls", type="primary"):
            store.add({"time": datetime.now().isoformat(timespec="seconds"),
                       "source": "app" if mode.startswith("Let") else "real die",
                       Q_SHAPE: shape, Q_SPREAD: spread, Q_ROLLS: " ".join(map(str, rolls))})
            ss.submitted = True
            ss.my_rolls = rolls
            st.rerun()


# ----------------------------------------------------------------------------- teacher page
def teacher_page(store):
    st.title("🎲 Roll the dice: the class")
    password = secret("TEACHER_PASSWORD", "dice")
    if not st.session_state.get("teacher_ok"):
        pw = st.text_input("Teacher password", type="password")
        if pw and pw == password:
            st.session_state.teacher_ok = True
            st.rerun()
        elif pw:
            st.error("Wrong password.")
        if secret("TEACHER_PASSWORD") is None:
            st.caption("No TEACHER_PASSWORD set: the password is 'dice'. Set it in the app secrets.")
        return

    @st.fragment(run_every=5)
    def counter():
        rows = store.snapshot()
        n_ok = len(class_rolls(rows))
        st.metric("Answers received", len(rows), help="Updates every 5 seconds")
        if len(rows) != n_ok:
            st.caption(f"{len(rows) - n_ok} answer(s) with fewer than 10 valid rolls are left out.")
    counter()

    rows = store.snapshot()
    rb = class_rolls(rows)
    st.button("Refresh the plots", on_click=lambda: None)

    tabs = st.tabs(["1 · Predictions", "2 · Single rolls", "3 · Averages", "4 · Spread", "Data"])
    with tabs[0]:
        if rows:
            st.pyplot(plot_predictions(rows))
        else:
            st.info("No answers yet.")
    with tabs[1]:
        if rb:
            fig, n = plot_single(rb)
            col, _ = st.columns([2, 1])
            col.pyplot(fig)
            st.caption(f"{n} rolls in total. Is the class die balanced?")
        else:
            st.info("No rolls yet.")
    with tabs[2]:
        if rb:
            curves = st.toggle("Show the normal curves N(3.5, (35/12)/n) of the central limit theorem")
            st.pyplot(plot_averages(rb, curves=curves))
            st.caption("Each student gives 30 single rolls, 15 averages of 2 rolls and 3 averages "
                       "of 10 rolls. Bars as densities: each panel has area 1.")
        else:
            st.info("No rolls yet.")
    with tabs[3]:
        if rb:
            st.dataframe(spread_table(rb), hide_index=True, width="stretch")
            st.caption("σ² = 35/12 for one roll of a balanced die, so σ ≈ 1.71.")
        else:
            st.info("No rolls yet.")
    with tabs[4]:
        if rows:
            df = pd.DataFrame(rows, columns=FIELDS)
            st.dataframe(df, hide_index=True, width="stretch")
            buf = io.StringIO()
            df.to_csv(buf, index=False)
            st.download_button("Download the answers (CSV)", buf.getvalue(), "class_dice.csv", "text/csv")
            st.caption("Save it as data/class_dice.csv in the course folder: "
                       "dice_live.R and L10.qmd read it.")
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Add 20 example students (for rehearsing)"):
                for r in example_rows():
                    store.add(r)
                st.rerun()
        with c2:
            def do_reset():
                store.clear()
                st.session_state.sure = False
            sure = st.checkbox("Yes, delete all the answers", key="sure")
            st.button("Reset", disabled=not sure, on_click=do_reset)
            st.caption("The old answers are kept in a backup file on the server.")


# ----------------------------------------------------------------------------- main
is_teacher = "teacher" in st.query_params
st.set_page_config(page_title="Roll the dice", page_icon="🎲",
                   layout="wide" if is_teacher else "centered")
store = get_store()
if is_teacher:
    teacher_page(store)
else:
    student_page(store)
