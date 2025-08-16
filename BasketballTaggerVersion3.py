import streamlit as st
import pandas as pd
from datetime import datetime, date
from collections import defaultdict
import re

st.set_page_config(page_title="Basketball Tagging App", layout="wide")

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
st.title("🏀 Basketball Tagging Application")

if not ready_to_tag:
    st.warning("Select Opponent, Game Date, and Quarter in the sidebar to begin tagging.")
    st.stop()
else:
    st.write(f"**Game:** vs **{st.session_state['opponent']}** | **Date:** {st.session_state['game_date']} | **Quarter:** {st.session_state['quarter']}")

# Play buttons grid
if not st.session_state["plays"]:
    st.info("Add at least one play in the sidebar to start tagging.")
else:
    st.subheader("Select a
