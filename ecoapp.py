"""
EcoTransit: Green Freight Optimizer + Real-Time Route Climate Safety
Extended for Round 2 Hackathon Submission
Preserves base Round 1 routing engine and appends climate/safety intelligence.
"""

import os
import requests
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

# Load keys from .env
load_dotenv()

# =========================================================================
# 1. BASE GRAPH DATA (ROUND 1 CODEBASE - UNTOUCHED)
# =========================================================================

ROUTES = [
    ("Delhi", "Jaipur", 280),
    ("Delhi", "Nagpur", 1050),
    ("Delhi", "Kolkata", 1500),
    ("Jaipur", "Ahmedabad", 650),
    ("Ahmedabad", "Mumbai", 530),
    ("Mumbai", "Nagpur", 830),
    ("Mumbai", "Hyderabad", 710),
    ("Nagpur", "Hyderabad", 500),
    ("Nagpur", "Kolkata", 1100),
    ("Hyderabad", "Bengaluru", 570),
    ("Hyderabad", "Chennai", 630),
    ("Bengaluru", "Chennai", 350),
    ("Kolkata", "Chennai", 1670),
]

MODES = {
    "Air": {"speed": 700, "handling": 6, "cost": 12.0, "co2": 600},
    "Rail": {"speed": 45, "handling": 12, "cost": 1.2, "co2": 25},
    "Road": {"speed": 40, "handling": 3, "cost": 2.5, "co2": 90},
}

GRAPH = {}
for a, b, km in ROUTES:
    GRAPH.setdefault(a, []).append((b, km))
    GRAPH.setdefault(b, []).append((a, km))


# =========================================================================
# 2. CORE LOGIC (ROUND 1 CODEBASE - UNTOUCHED)
# =========================================================================

def leg_stats(km, mode, tonnes):
    m = MODES[mode]
    time = km / m["speed"] + m["handling"]
    cost = km * tonnes * m["cost"]
    co2 = (km * tonnes * m["co2"]) / 1000.0
    return time, cost, co2


def find_paths(current, end, path):
    if current == end:
        return [path]
    found = []
    for nxt, _ in GRAPH.get(current, []):
        if nxt not in path:
            found += find_paths(nxt, end, path + [nxt])
    return found


def distance(a, b):
    for nxt, km in GRAPH.get(a, []):
        if nxt == b:
            return km
    return 0


def plan_route(src, dst, tonnes, w_co2, w_cost, w_speed):
    max_t = max_c = max_e = 0.0

    for a, b, km in ROUTES:
        for mode in MODES:
            t, c, e = leg_stats(km, mode, tonnes)
            max_t = max(max_t, t)
            max_c = max(max_c, c)
            max_e = max(max_e, e)

    paths = find_paths(src, dst, [src])
    if not paths:
        return None

    best = None

    for path in paths:
        legs = []
        tot_t = tot_c = tot_e = tot_score = 0.0

        for i in range(len(path) - 1):
            km = distance(path[i], path[i + 1])
            choice = None

            for mode in MODES:
                t, c, e = leg_stats(km, mode, tonnes)
                score = (w_co2 * e / max_e) + (w_cost * c / max_c) + (w_speed * t / max_t)
                if choice is None or score < choice[0]:
                    choice = (score, mode, t, c, e)

            score, mode, t, c, e = choice
            legs.append((path[i], path[i + 1], km, mode))
            tot_t += t
            tot_c += c
            tot_e += e
            tot_score += score

        if best is None or tot_score < best["score"]:
            best = {
                "path": path,
                "legs": legs,
                "time": tot_t,
                "cost": tot_c,
                "co2": tot_e,
                "score": tot_score,
            }

    return best


def deadline_sweep(src, dst, tonnes, w_co2, w_cost, w_speed, deadlines=(20, 40, 60, 80, 100)):
    """Stretch: best plan at each deadline. Returns one row per deadline."""
    rows = []
    for d in deadlines:
        plan, fastest = plan_route_deadline(src, dst, tonnes, w_co2, w_cost, w_speed, d)
        if plan is None:
            rows.append({"Deadline (h)": d, "Result": f"Infeasible (fastest {fastest:.2f} h)",
                         "Route": "-", "Modes": "-", "Time (h)": "-", "Cost (Rs)": "-", "CO2 (kg)": "-"})
        else:
            rows.append({"Deadline (h)": d, "Result": "Feasible",
                         "Route": " > ".join(plan["path"]),
                         "Modes": "/".join(m for *_, m in plan["legs"]),
                         "Time (h)": f"{plan['time']:.1f}",
                         "Cost (Rs)": f"{plan['cost']:,.0f}",
                         "CO2 (kg)": f"{plan['co2']:,.0f}"})
    return rows


def render_table(rows):
    """Plain markdown table (works even if pyarrow is blocked)."""
    cols = list(rows[0].keys())
    md = "| " + " | ".join(cols) + " |\n| " + " | ".join("---" for _ in cols) + " |\n"
    for row in rows:
        md += "| " + " | ".join(str(row[c]).replace("|", "/") for c in cols) + " |\n"
    st.markdown(md)


def render_deadline_sweep(src, dst, tonnes, w_co2, w_cost, w_speed):
    """Stretch: expander with cost/CO2 across several deadlines."""
    with st.expander("📊 Cost / CO₂ across deadlines"):
        render_table(deadline_sweep(src, dst, tonnes, w_co2, w_cost, w_speed))


# =========================================================================
# 3. ROUND 2 EXTENSION: LIVE WEATHER & AI CLIMATE SAFETY (PRUNE / GEMINI)
# =========================================================================

HUB_COORDS = {
    "Delhi": (28.6139, 77.2090),
    "Jaipur": (26.9124, 75.7873),
    "Nagpur": (21.1458, 79.0882),
    "Kolkata": (22.5726, 88.3639),
    "Ahmedabad": (23.0225, 72.5714),
    "Mumbai": (19.0760, 72.8777),
    "Hyderabad": (17.3850, 78.4867),
    "Bengaluru": (12.9716, 77.5946),
    "Chennai": (13.0827, 80.2707),
}


def get_live_weather(hub_name):
    """Fetches real-time weather metrics using Open-Meteo (open public API)."""
    coords = HUB_COORDS.get(hub_name)
    if not coords:
        return {"temp": 28.0, "rain": 0.0, "wind": 10.0}

    lat, lon = coords
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,precipitation,wind_speed_10m"
    try:
        res = requests.get(url, timeout=2.5)
        if res.status_code == 200:
            cur = res.json().get("current", {})
            return {
                "temp": cur.get("temperature_2m", 25.0),
                "rain": cur.get("precipitation", 0.0),
                "wind": cur.get("wind_speed_10m", 10.0),
            }
    except Exception:
        pass
    return {"temp": 28.0, "rain": 0.0, "wind": 10.0}


def rule_based_safety_engine(legs_weather):
    """Deterministic fallback: guarantees safety metrics even when offline."""
    results = []
    for item in legs_weather:
        src = item["src"]
        dst = item["dst"]
        km = item["km"]
        mode = item["mode"]
        w = item["weather"]

        temp = w.get("temp", 25.0)
        rain = w.get("rain", 0.0)
        wind = w.get("wind", 10.0)

        level = "🟢 SAFE"
        advisory = "Normal operations. Clear corridor."

        if mode == "Road" and rain > 5.0:
            level = "🟠 CAUTION"
            advisory = "Wet pavement. Reduced braking traction, enforce highway speed limits."
        elif mode == "Road" and temp > 42.0:
            level = "🟠 CAUTION"
            advisory = "Extreme heat corridor. Risk of tire degradation and coolant pressure."
        elif mode == "Air" and wind > 40.0:
            level = "🔴 HIGH RISK"
            advisory = "High crosswinds at runway hub. Potential cargo takeoff/landing delays."
        elif mode == "Rail" and rain > 20.0:
            level = "🟠 CAUTION"
            advisory = "Monsoon runoff. Track signal and drainage clearance caution."

        results.append({
            "Leg": f"{src} ➔ {dst}",
            "Mode": mode,
            "Distance": f"{km} km",
            "Safety Level": level,
            "Live Conditions": f"{temp}°C | Rain: {rain} mm | Wind: {wind} km/h",
            "Advisory": advisory
        })
    return results


def call_ai_risk_intelligence(enriched_legs):
    """
    Connects to AI inference:
    1. Prune AI Gateway (using PRUNE_API_KEY / base_url: api.withprune.com)
    2. Direct Google Gemini (using GEMINI_API_KEY)
    3. Graceful fallback (returns None if no key or offline)
    """
    prune_key = os.getenv("PRUNE_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    prompt_text = f"""
    You are an expert Indian freight logistics and climate risk analyst.
    Evaluate these active freight legs with real-time weather metrics:
    {enriched_legs}

    Provide:
    1. **Overall Route Risk Assessment**: (Low Risk / Moderate Risk / High Risk)
    2. **Climate Hazards Analysis**: (Specific risks regarding road slickness, rail flooding, or air turbulence)
    3. **Dispatch Recommendation**: (2 clear, practical sentences for logistics managers)
    """

    # --- 1. Try Prune AI Gateway ---
    active_key = prune_key or (gemini_key if gemini_key and gemini_key.startswith("prune_") else None)
    if active_key:
        try:
            url = "https://api.withprune.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {active_key}",
                "Content-Type": "application/json"
            }
            body = {
                "model": "gemini-2.5-flash",
                "messages": [
                    {"role": "system", "content": "You are a freight risk specialist."},
                    {"role": "user", "content": prompt_text}
                ],
                "temperature": 0.2
            }
            resp = requests.post(url, headers=headers, json=body, timeout=6)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"], "Prune AI Gateway (Gemini 2.5 Flash)"
        except Exception:
            pass

    # --- 2. Try Direct Google GenAI SDK ---
    if gemini_key and not gemini_key.startswith("prune_"):
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt_text
            )
            return response.text, "Google AI Studio (Gemini 2.5 Flash)"
        except Exception:
            pass

    return None, "Rule-Based Deterministic Safety Engine (Offline Mode)"


# =========================================================================
# 2b. ROUND 2 EXTENSION: DELIVERY DEADLINE PLANNER (PURE PYTHON, NO STREAMLIT)
# =========================================================================

def _normalizers(tonnes):
    """Same normalisation constants plan_route uses: max time/cost/CO2 over
    every route leg x every mode. Kept identical so scores are comparable."""
    max_t = max_c = max_e = 0.0
    for a, b, km in ROUTES:
        for mode in MODES:
            t, c, e = leg_stats(km, mode, tonnes)
            max_t = max(max_t, t)
            max_c = max(max_c, c)
            max_e = max(max_e, e)
    return max_t, max_c, max_e


def fastest_time(src, dst, tonnes=1.0):
    """Smallest achievable total transit time over ALL paths (fastest mode on
    every leg). Returns None if no path exists. Unrounded."""
    paths = find_paths(src, dst, [src])
    if not paths:
        return None
    best = None
    for path in paths:
        total = 0.0
        for i in range(len(path) - 1):
            km = distance(path[i], path[i + 1])
            total += min(leg_stats(km, m, tonnes)[0] for m in MODES)
        if best is None or total < best:
            best = total
    return best


def _prune(states):
    """Keep only Pareto-optimal (time, score) states: sorted by time, a state
    survives only if its score beats every faster state. Exact - never discards
    a state that could be part of the optimum."""
    states.sort(key=lambda s: (s["time"], s["score"]))
    kept, best_score = [], float("inf")
    for s in states:
        if s["score"] < best_score:
            kept.append(s)
            best_score = s["score"]
    return kept


def plan_route_deadline(src, dst, tonnes, w_co2, w_cost, w_speed, deadline_hrs):
    """Jointly choose path + per-leg mode minimising the weighted score subject
    to total transit time <= deadline_hrs (compared UNROUNDED).

    Returns (plan, fastest_hrs):
      plan        -> same dict shape as plan_route (+ "deadline", "spare"), or
                     None when infeasible / no path
      fastest_hrs -> fastest achievable time (float) or None if no path
    Per path, a DP over legs keeps only Pareto-optimal (time, score) states,
    so it is exact without enumerating 3^legs mode combinations.
    """
    paths = find_paths(src, dst, [src])
    if not paths:
        return None, None

    fastest = fastest_time(src, dst, tonnes)
    if deadline_hrs is None:
        return None, fastest

    max_t, max_c, max_e = _normalizers(tonnes)
    best = None

    for path in paths:
        states = [{"time": 0.0, "cost": 0.0, "co2": 0.0, "score": 0.0, "modes": []}]
        for i in range(len(path) - 1):
            km = distance(path[i], path[i + 1])
            nxt_states = []
            for s in states:
                for mode in MODES:
                    t, c, e = leg_stats(km, mode, tonnes)
                    new_time = s["time"] + t
                    if new_time > deadline_hrs:      # time only grows -> safe prune
                        continue
                    leg_score = (w_co2 * e / max_e) + (w_cost * c / max_c) + (w_speed * t / max_t)
                    nxt_states.append({
                        "time": new_time,
                        "cost": s["cost"] + c,
                        "co2": s["co2"] + e,
                        "score": s["score"] + leg_score,
                        "modes": s["modes"] + [mode],
                    })
            states = _prune(nxt_states)
            if not states:
                break
        if not states:
            continue
        cand = min(states, key=lambda s: (s["score"], s["time"]))
        if best is None or cand["score"] < best["score"]:
            legs = [(path[i], path[i + 1], distance(path[i], path[i + 1]), cand["modes"][i])
                    for i in range(len(path) - 1)]
            best = {
                "path": path,
                "legs": legs,
                "time": cand["time"],
                "cost": cand["cost"],
                "co2": cand["co2"],
                "score": cand["score"],
                "deadline": deadline_hrs,
                "spare": deadline_hrs - cand["time"],
            }
    return best, fastest



# =========================================================================
# 4. STREAMLIT WEB UI
# =========================================================================

def main():
    # Streamlit Page Setup
    st.set_page_config(
        page_title="EcoTransit: Green Freight & Safety",
        layout="wide",
        page_icon="🌱"
    )


    st.title("🌱 EcoTransit: Green Freight & Climate Safety Router")
    st.caption("Pareto Multi-Objective Optimization balancing Carbon, Cost, and Speed with Live Climate Intelligence.")

    hubs = sorted(list(GRAPH.keys()))
    col_left, col_right = st.columns([1, 2], gap="large")

    with col_left:
        st.subheader("1. Shipment Parameters")
        src = st.selectbox("Origin Hub", hubs, index=hubs.index("Delhi"))
        dst = st.selectbox("Destination Hub", hubs, index=hubs.index("Chennai"))
        tonnes = st.number_input("Cargo Weight (Tonnes)", min_value=0.5, max_value=500.0, value=10.0, step=0.5)

        st.subheader("2. Priority Weights")
        co2_pct = st.slider("Carbon Reduction (%)", 0, 100, 60, step=5)
        cost_pct = st.slider("Cost Minimization (%)", 0, 100, 30, step=5)
        speed_pct = st.slider("Transit Speed (%)", 0, 100, 10, step=5)

        st.subheader("3. Delivery Deadline")
        use_deadline = st.checkbox("Set a delivery deadline", value=False)
        deadline_hrs = None
        if use_deadline:
            deadline_hrs = st.number_input("Delivery deadline (hours)", min_value=0.1,
                                           max_value=1000.0, value=100.0, step=0.5)
        else:
            st.caption("No deadline (default)")

        total_pct = co2_pct + cost_pct + speed_pct
        if total_pct != 100:
            st.warning(f"Priority total must equal 100%. Currently: **{total_pct}%**")
            run_btn = st.button("Calculate Optimal Route", disabled=True)
        else:
            st.success("Priorities balanced (100%)")
            run_btn = st.button("Calculate Optimal Route", type="primary")

    with col_right:
        if run_btn:
            if src == dst:
                st.error("Origin and Destination cannot be the same hub.")
            else:
                w_co2 = co2_pct / 100.0
                w_cost = cost_pct / 100.0
                w_speed = speed_pct / 100.0

                fast = plan_route(src, dst, tonnes, 0, 0, 1)
                infeasible = False
                if deadline_hrs is None:
                    eco = plan_route(src, dst, tonnes, w_co2, w_cost, w_speed)
                else:
                    eco, fastest_hrs = plan_route_deadline(
                        src, dst, tonnes, w_co2, w_cost, w_speed, deadline_hrs)
                    infeasible = fast is not None and eco is None

                if infeasible:
                    st.error(
                        f"Deadline of {deadline_hrs:g} h is infeasible. "
                        f"The fastest achievable time for {src} ➔ {dst} is "
                        f"**{fastest_hrs:.2f} h**. No plan generated."
                    )
                elif not eco or not fast:
                    st.error("No valid route found between selected hubs.")
                else:
                    saved_co2 = fast["co2"] - eco["co2"]
                    pct_saved = (saved_co2 / fast["co2"] * 100) if fast["co2"] else 0
                    cost_diff = eco["cost"] - fast["cost"]
                    time_diff = eco["time"] - fast["time"]

                    # High-level KPI Cards
                    st.subheader("Optimization Impact")
                    m1, m2, m3 = st.columns(3)
                    m1.metric("CO₂ Reduction", f"{saved_co2:,.0f} kg", f"-{pct_saved:.1f}%")
                    m2.metric("Cost Savings", f"Rs {abs(cost_diff):,.0f}", f"{'-' if cost_diff <= 0 else '+'}")
                    m3.metric("Transit Duration", f"{eco['time']:.1f} hrs", f"+{time_diff:.1f} hrs")

                    st.divider()

                    # Detailed Route Comparison
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("### ✈️ Baseline: Speed-Only Plan")
                        st.write(f"**Route:** `{' ➔ '.join(fast['path'])}`")
                        st.write(f"- **Transit Time:** {fast['time']:.1f} hrs")
                        st.write(f"- **Financial Cost:** Rs {fast['cost']:,.0f}")
                        st.write(f"- **CO₂ Emissions:** {fast['co2']:,.0f} kg")
                        for a, b, km, mode in fast["legs"]:
                            st.caption(f"• {a} to {b} ({km} km) via **{mode}**")

                    with c2:
                        st.markdown("### 🌿 Optimized EcoTransit Plan")
                        st.write(f"**Route:** `{' ➔ '.join(eco['path'])}`")
                        if deadline_hrs is not None:
                            st.success(f"Meets deadline, {deadline_hrs - eco['time']:.1f} h spare.")
                        st.write(f"- **Transit Time:** {eco['time']:.1f} hrs")
                        st.write(f"- **Financial Cost:** Rs {eco['cost']:,.0f}")
                        st.write(f"- **CO₂ Emissions:** {eco['co2']:,.0f} kg")
                        for a, b, km, mode in eco["legs"]:
                            st.caption(f"• {a} to {b} ({km} km) via **{mode}**")

                    st.divider()

                    render_deadline_sweep(src, dst, tonnes, w_co2, w_cost, w_speed)
                    st.divider()

                    # Real-Time Climate & Route Safety Intelligence
                    st.subheader("🌦️ Real-Time Climate & Route Safety Intelligence")

                    with st.spinner("Fetching live corridor weather and assessing risks..."):
                        enriched = [
                            {
                                "src": a,
                                "dst": b,
                                "km": km,
                                "mode": mode,
                                "weather": get_live_weather(a)
                            }
                            for a, b, km, mode in eco["legs"]
                        ]

                        ai_report, engine_source = call_ai_risk_intelligence(enriched)
                        safety_table = rule_based_safety_engine(enriched)

                    st.caption(f"Active Safety Engine: **{engine_source}**")
                    try:
                        st.dataframe(pd.DataFrame(safety_table), use_container_width=True)
                    except ImportError:
                        # pyarrow blocked (e.g. Windows Application Control) -> plain table
                        render_table(safety_table)

                    if ai_report:
                        st.info("🧠 AI Climate Risk & Dispatch Advisory")
                        st.markdown(ai_report)


if __name__ == "__main__":
    main()