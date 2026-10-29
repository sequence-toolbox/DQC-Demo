"""SC26 local interactive demo. Run with: streamlit run app.py."""
import json
import math
from pathlib import Path

import streamlit as st

from demo import charts, jobs

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="SeQUeNCe.DQC · SC26", page_icon="⚛", layout="wide")
st.markdown("""<style>
.block-container {max-width: 1450px; padding-top: 2.2rem;}
h1 {letter-spacing: -.045em; font-weight: 750;}
[data-testid="stMetric"] {background: #f3f6fa; padding: 18px; border-radius: 12px;}
[data-testid="stSidebar"] {border-right: 1px solid #dce4ee;}
.eyebrow {color: #087f73; letter-spacing: .16em; font-size: .78rem; font-weight: 700;}
</style>""", unsafe_allow_html=True)


def load_data(name):
    return json.loads((ROOT / "data" / f"{name}.json").read_text())


def launch(config):
    st.session_state["job"] = jobs.start(config)
    st.session_state.pop("job_error", None)


@st.fragment(run_every=1)
def monitor():
    job = st.session_state.get("job")
    if not job:
        return
    status, payload = jobs.poll(job)
    if status == "running":
        st.progress(payload["value"], text=payload["message"])
        st.caption("Live simulation · runs continue while you explore · 10-minute limit")
        if st.button("Cancel simulation", key="cancel"):
            jobs.stop(job)
            del st.session_state["job"]
            st.rerun()
    else:
        if status == "complete":
            scenario = job["config"]["scenario"]
            st.session_state.setdefault(f"{scenario}_history", []).append(payload)
            if scenario == "nature":
                st.session_state["nature_view"] = "Live runs"
        else:
            st.session_state["job_error"] = payload
        del st.session_state["job"]
        st.rerun()


def results_download(result, key):
    st.download_button("Download result + settings", json.dumps(result, indent=2), file_name=f"sequence-dqc-{key}.json", mime="application/json", key=f"download_{key}")


def nature_page():
    st.markdown('<div class="eyebrow">01 / EXPERIMENT REPRODUCTION</div>', unsafe_allow_html=True)
    st.title("One algorithm. Two quantum modules.")
    st.write("Reproduce the distributed Grover experiment of Main et al., as modeled in Section 3 of the SeQUeNCe.DQC manuscript.")
    left, right = st.columns([1, 1.6], gap="large")
    with left:
        st.subheader("The quantum network")
        st.plotly_chart(charts.network(), width="stretch", key="nature_network")
        st.caption("One data qubit per module. Two teleported CZ gates connect the oracle and diffusion steps.")
        with st.form("nature_controls"):
            model = st.selectbox("Noise model", ["Detailed", "Noiseless"])
            bell = st.slider("Bell-pair fidelity", 0.80, 1.0, 0.9689, 0.0001, format="%.4f")
            st.caption("Detailed: Bell fidelity changes the raw-entanglement budget; other Table 1 terms stay fixed. Noiseless: Bell fidelity is ignored.")
            shots = st.select_slider("Shots per marked state", options=[10, 25, 50, 100, 250, 500, 2000], value=25)
            seed = st.number_input("Random seed", min_value=0, max_value=1000000, value=1, key="nature_seed")
            if st.form_submit_button("Run distributed Grover", type="primary", disabled="job" in st.session_state):
                launch({"scenario": "nature", "model": model, "bell": bell, "shots": shots, "seed": seed})
                st.rerun()
    with right:
        st.subheader("From circuit to experiment")
        st.plotly_chart(charts.circuit(), width="stretch", key="nature_circuit")
        st.caption("Schematic: marked-state X masks around the oracle are omitted. Each CZ uses the network; local gates stay on their module.")
        reference = load_data("nature_reference")
        history = [r for r in st.session_state.get("nature_history", []) if r["model"] in ("Detailed", "Noiseless")]
        view = st.radio("Results", ["Manuscript reference", "Live runs"], horizontal=True, key="nature_view")
        if view == "Manuscript reference":
            series = {label: [{"state": f"{i:02b}", "success": value} for i, value in enumerate(values)] for label, values in reference["series"].items()}
            st.caption("SAVED REFERENCE · 2,000 shots per state · rounded values from Section 3")
            st.plotly_chart(charts.success_chart(series), width="stretch", key="reference_success")
            columns = st.columns(len(series))
            for column, (label, values) in zip(columns, reference["series"].items()):
                column.metric(label, f"{100 * sum(values) / 4:.1f}%")
        elif history:
            choices = list(range(len(history)))
            chosen = st.multiselect("Compare completed runs", choices, default=choices[-2:], format_func=lambda i: f"Run {i + 1} · {history[i]['model']} · {history[i]['total_shots']} shots")
            series = {f"Run {i + 1} · {history[i]['model']}": history[i]["rows"] for i in chosen}
            st.caption("LIVE SIMULATION · bars show 95% Wilson intervals · Nature band is the reported 71% average")
            st.plotly_chart(charts.success_chart(series), width="stretch", key="live_success")
            latest = history[-1]
            columns = st.columns(3)
            columns[0].metric("Latest mean success", f"{100 * latest['success']:.1f}%")
            columns[1].metric("Total shots", latest["total_shots"])
            columns[2].metric("Wall time", f"{latest['wall_seconds']:.1f} s")
            st.json(latest["config"], expanded=False)
            st.dataframe([{"Run": i + 1, "Model": r["model"], "Bell fidelity": r["config"].get("bell"),
                           "Shots": r["total_shots"], "Success (%)": round(r["success"] * 100, 1)}
                          for i, r in enumerate(history)], hide_index=True, width="stretch")
            results_download({"runs": history}, "nature")
        else:
            st.info("Run a simulation to compare all four marked states. Start with 25 shots per state; increase for a more precise estimate.")
    with st.expander("What is reproduced?", expanded=False):
        st.write("The live run uses the existing density-matrix telegate and BSM pipeline, with the compiler fixed. The detailed model uses the Table 1 budget plus local-gate and final-readout errors. The noiseless control disables these noise channels.")
        st.write("These are effective calibrated noise models. Bell errors are injected after the gate; this view does not claim microscopic trapped-ion modeling. Link distance is fixed by the existing reproduction pipeline, and decoherence is a fixed error-budget term.")
        st.write("The manuscript reports 73.8% for the detailed model, compared with the experimental 71% average. Finite-shot live runs will vary. The shaded experimental band is not a 95% confidence interval.")
        st.caption(reference["source"])


def saved_exploration():
    st.subheader("Explore the manuscript results")
    mode = st.radio("Hold the workload fixed and compare", ["Networks", "Compilers"], horizontal=True)
    data = load_data("topo_exec" if mode == "Networks" else "compiler_comparison")
    st.caption("SAVED SIMULATION RESULTS · snapshot from dqc-experiments · changing the selection does not run a simulation")
    if mode == "Networks":
        st.write("6 search qubits + 4 ancillas · 10 modules · one data slot per module · FGP compiler · z = 0.95")
        selected = st.selectbox("Inspect a topology", [r["name"] for r in data["rows"]])
        row = next(r for r in data["rows"] if r["name"] == selected)
        left, right = st.columns([1, 1.5])
        with left:
            st.plotly_chart(charts.network(selected.title(), 10), width="stretch", key="saved_network")
        with right:
            st.plotly_chart(charts.comparison(data["rows"], "sim_ms", "Simulated execution time (ms)", "name"), width="stretch", key="topo_times")
        columns = st.columns(3)
        columns[0].metric("Remote gates", row["gates"])
        columns[1].metric("Execution time", f"{row['sim_ms']:.2f} ms")
        columns[2].metric("Success", f"{100 * row['success']:.1f}%")
        st.info("All three networks execute 588 remote gates. Routes and hop counts change the communication overhead and success probability.")
    else:
        st.write("4 search qubits + 2 ancillas · 2 modules · three data slots per module · same network · z = 0.95")
        labels = {r["key"]: r["label"].replace("\n", " ") for r in data["rows"]}
        selected = st.multiselect("Compiler configurations", list(labels), default=list(labels), format_func=labels.get)
        rows = [r for r in data["rows"] if r["key"] in selected]
        if rows:
            st.plotly_chart(charts.comparison(rows, "sim_ms", "Simulated execution time (ms)"), width="stretch", key="compiler_times")
            st.dataframe([{"Compiler": labels[r["key"]], "Remote gates": r["gates"], "Qubit moves": r["moves"],
                           "Time (ms)": r["sim_ms"], "Success (%)": round(100 * r["success"], 1)} for r in rows], hide_index=True, width="stretch")
        st.caption("Random is an average over placements; other rows are individual compiled plans. Remote gates and qubit moves are operation counts, not measured Bell-pair consumption. Amaro is available here as saved results.")
    st.download_button("Download saved dataset", json.dumps(data, indent=2), file_name=f"{data['experiment']}.json", mime="application/json")


def live_exploration():
    left, right = st.columns([1, 1.6], gap="large")
    with left:
        with st.form("explore_controls"):
            qubits = st.selectbox("Search qubits", [3, 4], index=1)
            modules = st.selectbox("Quantum modules", [2, 4])
            topology = st.selectbox("Network topology", ["Star", "Grid", "Caveman"])
            compiler = st.selectbox("Compiler", ["QAP", "Random", "FGP · default", "FGP · low margin"])
            link = st.slider("Fiber length parameter (km)", 0.01, 20.0, 5.0, 0.01, format="%.2f")
            efficiency = st.slider("Memory efficiency", 0.5, 1.0, 0.9, 0.05)
            noise = st.checkbox("Include hardware noise", value=True)
            z = st.select_slider("Hardware quality (z)", options=[0.00, 0.25, 0.50, 0.65, 0.80, 0.90, 0.95, 1.00], value=0.95, format_func=lambda value: f"{value:.2f}")
            st.caption("Higher z improves hardware quality. This setting applies when hardware noise is enabled.")
            shots = st.slider("Simulation shots", 1, 1000, 5)
            seed = st.number_input("Random seed", min_value=0, max_value=1000000, value=1, key="explore_seed")
            if st.form_submit_button("Compile and simulate", type="primary", disabled="job" in st.session_state):
                launch({"scenario": "exploration", "qubits": qubits, "modules": modules, "topology": topology,
                        "compiler": compiler, "link_km": link, "efficiency": efficiency, "noise": noise, "z": z, "shots": shots, "seed": seed})
                st.rerun()
        st.caption("Small workloads keep live runs practical. Capacity is balanced automatically to hold the circuit and its ancillas. The fiber parameter is passed directly to the engine’s link_km setting.")
    with right:
        history = st.session_state.get("exploration_history", [])
        if not history:
            st.plotly_chart(charts.network(topology, modules, capacity=math.ceil((2 * qubits - 2) / modules)), width="stretch", key="explore_preview")
            st.info("Choose a network and compiler, then run. For a controlled comparison, change one setting at a time and keep the seed fixed.")
            return
        result = history[-1]
        config = result["config"]
        st.caption(f"LATEST COMPLETED RUN · {config['topology']} · {config['compiler']} · {result['total_shots']} shots")
        st.plotly_chart(charts.network(config["topology"], config["modules"], result["edges"], result["capacity"]), width="stretch", key="explore_result")
        columns = st.columns(3)
        columns[0].metric("Execution time · mean", f"{result['sim_ms']:.2f} ms")
        columns[1].metric("Remote gates", result["gates"])
        columns[2].metric("Qubit moves", result["moves"])
        low, high = charts.interval(result["hits"], result["total_shots"])
        st.write(f"Success: **{result['success']:.0%}** · 95% Wilson interval: {low:.0%}–{high:.0%}")
        st.caption("Small shot counts are for interaction; use the saved 1,000-shot datasets for more precise success comparisons. Simulated execution time differs from laptop wall time.")
        st.dataframe([{"Run": i + 1, "Network": r["config"]["topology"], "Compiler": r["config"]["compiler"],
                       "Fiber (km)": r["config"]["link_km"], "Memory efficiency": r["config"]["efficiency"],
                       "Noise": r["config"]["noise"], "z": r["config"].get("z", 0.95) if r["config"]["noise"] else None,
                       "Seed": r["config"]["seed"], "Search qubits": r["config"]["qubits"],
                       "Modules": r["config"]["modules"], "Time (ms)": round(r["sim_ms"], 2),
                       "Remote gates": r["gates"], "Moves": r["moves"], "Success (%)": round(r["success"] * 100, 1),
                       "Shots": r["total_shots"]} for i, r in enumerate(history)], hide_index=True, width="stretch")
        results_download({"runs": history}, "exploration")


with st.sidebar:
    st.markdown("### SeQUeNCe.DQC")
    st.caption("SC26 · Interactive simulation")
    page = st.radio("Explore", ["Nature reproduction", "Networks & compilers"], label_visibility="collapsed")
    st.divider()
    st.write("**The question**")
    st.write("How does a quantum network shape distributed quantum computation?")
    if st.session_state.get("nature_history") or st.session_state.get("exploration_history"):
        st.caption("Completed live runs are available in each scenario and saved under runs/.")

monitor()
if error := st.session_state.get("job_error"):
    st.error(error["message"])
    if "details" in error:
        with st.expander("Simulation error details"):
            st.code(error["details"])

if page == "Nature reproduction":
    nature_page()
else:
    st.markdown('<div class="eyebrow">02 / NETWORK & COMPILER EXPLORATION</div>', unsafe_allow_html=True)
    st.title("The network matters. So does the compiler.")
    st.write("Compare architectures and communication strategies for distributed Grover search.")
    mode = st.radio("Experience", ["Saved manuscript results", "Live simulation"], horizontal=True)
    if mode == "Saved manuscript results":
        saved_exploration()
    else:
        live_exploration()
