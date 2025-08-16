import streamlit as st
import pandas as pd
from datetime import datetime, date
from collections import defaultdict
import re

st.set_page_config(page_title="StFx Mens Basketball Tagger", layout="wide")

# ---------------------------
# Session State & Utilities
# ---------------------------
def init_state():
    st.session_state.setdefault("plays", [])               # list[str]
    st.session_state.setdefault("log", [])                 # list[dict]
    st.session_state.setdefault("selected_play", None)     # str | None
    st.session_state.setdefault("opponent", "")
    st.session_state.setdefault("game_date", date.today())
    st.session_state.setdefault("quarter", "")
    st.session_state.setdefault("new_play", "")

def safe_filename(s: str) -> str:
    s = s.strip().replace(" ", "_")
    s = re.sub(r"[^A-Za-z0-9_\-\.]", "", s)
    return s

def points_from_result(result: str) -> int:
    return {"Made 2": 2, "Made 3": 3, "Missed 2": 0, "Missed 3": 0, "Foul": 0}.get(result, 0)

def add_log(play: str, result: str):
    st.session_state["log"].append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "opponent": st.session_state["opponent"],
        "game_date": str(st.session_state["game_date"]),
        "quarter": st.session_state["quarter"],
        "play": play,
        "result": result,
        "points": points_from_result(result),
    })

def compute_metrics(log_df: pd.DataFrame) -> pd.DataFrame:
    if log_df.empty:
        return pd.DataFrame(columns=["Play", "Attempts", "Points", "PPP", "Frequency", "Success Rate"])

    # Attempts = every tag (includes fouls)
    attempts = log_df.groupby("play").size().rename("Attempts")

    # Points
    points = log_df.groupby("play")["points"].sum().rename("Points")

    metrics = pd.concat([attempts, points], axis=1).reset_index().rename(columns={"play": "Play"})
    metrics["PPP"] = metrics["Points"] / metrics["Attempts"]

    total_attempts = metrics["Attempts"].sum()
    metrics["Frequency"] = metrics["Attempts"] / (total_attempts if total_attempts else 1)

    made_mask = log_df["result"].isin(["Made 2", "Made 3"])
    att_mask = log_df["result"].isin(["Made 2", "Made 3", "Missed 2", "Missed 3"])
    made_counts = log_df[made_mask].groupby("play").size()
    shot_attempts = log_df[att_mask].groupby("play").size()

    def success_rate(play_name):
        made = int(made_counts.get(play_name, 0))
        atts = int(shot_attempts.get(play_name, 0))
        return (made / atts) if atts else 0.0

    metrics["Success Rate"] = metrics["Play"].map(success_rate)

    # nicer ordering
    metrics = metrics.sort_values(by=["PPP", "Attempts"], ascending=[False, False]).reset_index(drop=True)
    return metrics

init_state()

# ---------------------------
# Sidebar: Game Setup & Playbook
# ---------------------------
st.sidebar.header("Game Setup")
st.session_state["opponent"] = st.sidebar.text_input("Opponent", value=st.session_state["opponent"])
st.session_state["game_date"] = st.sidebar.date_input("Game Date", value=st.session_state["game_date"])
st.session_state["quarter"] = st.sidebar.selectbox("Quarter", ["", "1", "2", "3", "4", "OT"], index=["", "1", "2", "3", "4", "OT"].index(st.session_state["quarter"]) if st.session_state["quarter"] in ["", "1", "2", "3", "4", "OT"] else 0)

ready_to_tag = bool(st.session_state["opponent"] and st.session_state["game_date"] and st.session_state["quarter"])

st.sidebar.markdown("---")
st.sidebar.subheader("Playbook")

st.session_state["new_play"] = st.sidebar.text_input("New Play Name", value=st.session_state["new_play"])

def add_play():
    raw = st.session_state["new_play"].strip()
    if not raw:
        return
    # case-insensitive dedupe
    existing_lower = {p.lower() for p in st.session_state["plays"]}
    if raw.lower() in existing_lower:
        st.sidebar.warning("Play already exists.")
        return
    st.session_state["plays"].append(raw)
    st.session_state["new_play"] = ""

if st.sidebar.button("ADD NEW PLAY", use_container_width=True):
    add_play()

if st.session_state["plays"]:
    st.sidebar.caption("Current plays:")
    # show compact list
    for p in st.session_state["plays"]:
        st.sidebar.write(f"• {p}")

st.sidebar.markdown("---")
if st.sidebar.button("Reset Game (clears log & selections)", type="secondary"):
    st.session_state["log"] = []
    st.session_state["selected_play"] = None
    st.success("Game state cleared.")

# ---------------------------
# Main: Tagging & Metrics
# ---------------------------
st.title("StFx Mens Basketball Tagger")

if not ready_to_tag:
    st.warning("Select Opponent, Game Date, and Quarter in the sidebar to begin tagging.")
    st.stop()
else:
    st.write(f"**Game:** vs **{st.session_state['opponent']}** | **Date:** {st.session_state['game_date']} | **Quarter:** {st.session_state['quarter']}")

# Play buttons grid
if not st.session_state["plays"]:
    st.info("Add at least one play in the sidebar to start tagging.")
else:
    st.subheader("Select a Play")
    cols_per_row = 4
    rows = (len(st.session_state["plays"]) + cols_per_row - 1) // cols_per_row
    idx = 0
    for r in range(rows):
        row_cols = st.columns(cols_per_row)
        for c in range(cols_per_row):
            if idx >= len(st.session_state["plays"]):
                break
            play = st.session_state["plays"][idx]
            if row_cols[c].button(play, key=f"play_btn_{idx}", use_container_width=True):
                st.session_state["selected_play"] = play
            idx += 1

# Tagging actions for selected play
if st.session_state["selected_play"]:
    st.markdown(f"**Tagging:** `{st.session_state['selected_play']}`")
    a, b, c, d, e, f = st.columns(6)
    if a.button("Made 2", key="act_m2", use_container_width=True):
        add_log(st.session_state["selected_play"], "Made 2")
    if b.button("Made 3", key="act_m3", use_container_width=True):
        add_log(st.session_state["selected_play"], "Made 3")
    if c.button("Missed 2", key="act_x2", use_container_width=True):
        add_log(st.session_state["selected_play"], "Missed 2")
    if d.button("Missed 3", key="act_x3", use_container_width=True):
        add_log(st.session_state["selected_play"], "Missed 3")
    if e.button("Foul", key="act_fl", use_container_width=True):
        add_log(st.session_state["selected_play"], "Foul")
    if f.button("Undo Last", key="undo_last", use_container_width=True):
        if st.session_state["log"]:
            st.session_state["log"].pop()
            st.toast("Last tag removed.")
        else:
            st.toast("No tags to undo.", icon="⚠️")

st.markdown("---")

# Build DataFrames
log_df = pd.DataFrame(st.session_state["log"])
metrics_df = compute_metrics(log_df) if not log_df.empty else pd.DataFrame(columns=["Play", "Attempts", "Points", "PPP", "Frequency", "Success Rate"])

# Metrics table
st.subheader("📊 Per Play Metrics")
if metrics_df.empty:
    st.info("No data yet — tag some plays to see metrics.")
else:
    st.dataframe(
        metrics_df.style.format({
            "PPP": "{:.2f}",
            "Frequency": "{:.1%}",
            "Success Rate": "{:.1%}"
        }),
        use_container_width=True,
        hide_index=True
    )

    # Quick visuals
    left, right = st.columns(2)
    with left:
        st.caption("PPP by Play")
        st.bar_chart(metrics_df.set_index("Play")["PPP"], use_container_width=True)
    with right:
        st.caption("Frequency by Play")
        st.bar_chart(metrics_df.set_index("Play")["Frequency"], use_container_width=True)

# Play-by-play table
st.subheader("🧾 Play-by-Play Log")
if log_df.empty:
    st.info("No events logged yet.")
else:
    st.dataframe(log_df, use_container_width=True, hide_index=True)

# Exports
st.subheader("📥 Export")
if st.button("Prepare Exports"):
    st.session_state["__exports_ready"] = True

if st.session_state.get("__exports_ready") and not log_df.empty:
    opp = safe_filename(str(st.session_state["opponent"]))
    gdt = safe_filename(str(st.session_state["game_date"]))
    qtr = safe_filename(str(st.session_state["quarter"]))

    metrics_csv = metrics_df.to_csv(index=False).encode("utf-8")
    log_csv = log_df.to_csv(index=False).encode("utf-8")
    json_blob = log_df.to_json(orient="records", indent=2).encode("utf-8")

    st.download_button(
        "Download Per-Play Metrics (CSV)",
        data=metrics_csv,
        file_name=f"{opp}_{gdt}_Q{qtr}_metrics.csv",
        mime="text/csv",
        use_container_width=True
    )
    st.download_button(
        "Download Play-by-Play (CSV)",
        data=log_csv,
        file_name=f"{opp}_{gdt}_Q{qtr}_playbyplay.csv",
        mime="text/csv",
        use_container_width=True
    )
    st.download_button(
        "Download Snapshot (JSON)",
        data=json_blob,
        file_name=f"{opp}_{gdt}_Q{qtr}_snapshot.json",
        mime="application/json",
        use_container_width=True
    )
