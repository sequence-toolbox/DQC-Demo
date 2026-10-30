"""SC26 local interactive demo. Run with: streamlit run app.py."""
import json
from pathlib import Path

import streamlit as st

from demo import charts, jobs
from demo.grover.error_budget import TABLE1_BUDGET, ERROR_LABELS
from demo.grover.history import history_row

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title="SeQUeNCe.DQC · SC26", page_icon="⚛", layout="wide")
st.markdown("""<style>
.block-container {max-width: 1450px; padding-top: 5rem;}
h1 {letter-spacing: -.045em; font-weight: 750;}
[data-testid="stMetric"] {background: #f3f6fa; padding: 18px; border-radius: 12px;}
[data-testid="stSidebar"] {border-right: 1px solid #dce4ee;}
.eyebrow {color: #087f73; letter-spacing: .16em; font-size: .78rem; font-weight: 700; line-height: 1.5;}
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
        st.caption(f"Live simulation · runs continue while you explore · {120 if job['config'].get('paper_setup') else 10}-minute limit")
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
    st.title("Distributed Grover's Algorithm (2 Qubits, 2 Nodes)")
    st.write("Reproduce the distributed Grover experiment from Main et al., "
             "[Distributed quantum computing across an optical network link](https://www.nature.com/articles/s41586-024-08404-x), "
             "Nature 638, 383–388 (2025).")
    left, right = st.columns([1, 1.6], gap="large")
    with left:
        st.subheader("The Quantum Network")
        st.plotly_chart(charts.network(), width="stretch", key="nature_network")
        model = st.selectbox("Noise model", ["Detailed", "Noiseless"])
        with st.form("nature_controls"):
            bell, budget, local_error, readout_error = 1.0, {name: [0.0, 0.0] for name in ERROR_LABELS}, 0.0, 0.0
            if model == "Detailed":
                bell = st.slider("Bell-pair fidelity", 0.5, 1.0, 0.9689, 0.0001, format="%.4f")
                error_rows = [{"Error source": label.replace(" (Z dephasing)", ""), "Alice (A)": 100 * TABLE1_BUDGET[name][0],
                               "Bob (B)": 100 * TABLE1_BUDGET[name][1]} for name, label in ERROR_LABELS.items()]
                edited_errors = st.data_editor(error_rows, hide_index=True, num_rows="fixed", width="stretch", height=220,
                                               disabled=["Error source"], key="nature_error_table",
                                               column_config={"Error source": st.column_config.TextColumn(width="medium"),
                                                              "Alice (A)": st.column_config.NumberColumn(width="small", min_value=0.0, max_value=50.0, step=0.001, format="%.3f", required=True),
                                                              "Bob (B)": st.column_config.NumberColumn(width="small", min_value=0.0, max_value=50.0, step=0.001, format="%.3f", required=True)})
                budget = {name: [row["Alice (A)"] / 100, row["Bob (B)"] / 100] for name, row in zip(ERROR_LABELS, edited_errors)}
                local, readout = st.columns(2)
                local_error = local.number_input("Local H/X error (%)", min_value=0.0, max_value=50.0, value=0.01, step=0.001, format="%.3f") / 100
                readout_error = readout.number_input("Final readout error (%)", min_value=0.0, max_value=100.0, value=0.5, step=0.01, format="%.3f") / 100
            shots_column, seed_column = st.columns(2)
            shots = shots_column.select_slider("Shots per marked state", options=[100, 250, 500, 1000, 2000], value=100)
            seed = seed_column.number_input("Random seed", min_value=0, max_value=1000000, value=1, key="nature_seed")
            if st.form_submit_button("Run distributed Grover", type="primary", disabled="job" in st.session_state):
                launch({"scenario": "nature", "model": model, "bell": bell, "budget": budget,
                        "local_gate_error": local_error, "readout_error": readout_error, "shots": shots, "seed": seed})
                st.rerun()
    with right:
        st.subheader("The Grover's Search Circuit")
        st.plotly_chart(charts.circuit(), width="stretch", key="nature_circuit")
        reference = load_data("nature_reference")
        history = [r for r in st.session_state.get("nature_history", []) if r["model"] in ("Detailed", "Noiseless")]
        view = st.radio("Results", ["Manuscript reference", "Live runs"], horizontal=True, key="nature_view")
        if view == "Manuscript reference":
            series = {label: [{"state": f"{i:02b}", "success": value} for i, value in enumerate(values)] for label, values in reference["series"].items()}
            st.caption(f"SAVED REFERENCE · {reference['shots_per_state']:,} shots per marked state for the detailed model · rounded source values")
            st.plotly_chart(charts.success_chart(series).update_layout(height=460 if model == "Detailed" else 390), width="stretch", key="reference_success")
            columns = st.columns(len(series))
            for column, (label, values) in zip(columns, reference["series"].items()):
                column.metric(label, f"{100 * sum(values) / 4:.1f}%")
        elif history:
            choices = list(range(len(history)))
            chosen = st.multiselect("Compare completed runs", choices, default=choices[-2:], format_func=lambda i: f"Run {i + 1} · {history[i]['model']} · {history[i]['total_shots']} shots")
            series = {f"Run {i + 1} · {history[i]['model']}": history[i]["rows"] for i in chosen}
            st.plotly_chart(charts.success_chart(series).update_layout(height=430 if model == "Detailed" else 390), width="stretch", key="live_success")
            latest = history[-1]
            columns = st.columns(3)
            columns[0].metric("Latest mean success", f"{100 * latest['success']:.1f}%")
            columns[1].metric("Total shots", latest["total_shots"])
            columns[2].metric("Wall time", f"{latest['wall_seconds']:.1f} s")
            st.json({"settings": latest["config"], "effective_noise": latest.get("effective_noise")}, expanded=False)
            st.dataframe([history_row(r, i + 1) for i, r in enumerate(history)], hide_index=True, width="stretch")
            results_download({"runs": history}, "nature")
        else:
            st.info("Run a simulation to compare all four marked states. Start with 100 shots per state; increase for a more precise estimate.")
    with st.expander("What is reproduced?", expanded=False):
        st.write("One data qubit per node. Two teleported CZ gates connect the oracle and diffusion steps.")
        st.write("Bell fidelity sets raw-entanglement error. The table lists errors per CZ, in percent; A = Alice/control, B = Bob/target.")
        st.write("Local and readout errors apply to both nodes. QC decoherence is a fixed Z-dephasing error, not a T₂ time.")
        st.write("The live run uses the existing density-matrix telegate and BSM pipeline, with the compiler fixed. The detailed model uses the Table 1 budget plus local-gate and final-readout errors. The noiseless control disables these noise channels.")
        st.write("These are effective calibrated noise models. Bell errors are injected after the gate; this view does not claim microscopic trapped-ion modeling. Link distance is fixed by the existing reproduction pipeline, and decoherence is a fixed error-budget term.")
        st.write("The latest reference reports 72.9% average success for the detailed model over 10,000 shots per marked state, compared with the experimental 71% average. Finite-shot live runs will vary. The shaded experimental band is not a 95% confidence interval.")
        st.caption(reference["source"])


def saved_exploration():
    st.subheader("Explore the manuscript results")
    mode = st.radio("Hold the workload fixed and compare", ["Networks", "Compilers", "Capacity"], horizontal=True)
    data = load_data({"Networks": "topo_exec", "Compilers": "compiler_comparison", "Capacity": "capacity_exec"}[mode])
    st.caption("SAVED SIMULATION RESULTS · snapshot from dqc-experiments · changing the selection does not run a simulation")
    if mode == "Networks":
        st.write("6 search qubits + 4 ancillas · 10 nodes · one data slot per node · FGP compiler · z = 0.95")
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
    elif mode == "Capacity":
        st.write("7 search qubits + 5 ancillas · fixed 4-node line · 12 total data slots · FGP, low move margin · z = 0.95 · 1,000 shots")
        left, right = st.columns([1, 1.5])
        with left:
            for row in data["rows"]:
                st.write(f"**{row['key'].title()}** · {row['caps']}")
                st.plotly_chart(charts.network("Line", 4, capacities=row["caps"]).update_layout(height=180), width="stretch", key=f"capacity_{row['key']}")
        with right:
            figure = charts.comparison(data["rows"], "sim_ms", "Simulated execution time (ms)")
            figure.update_traces(text=[f"{100 * row['success']:.1f}% success" for row in data["rows"]], textposition="outside", cliponaxis=False)
            figure.update_yaxes(range=[0, max(row["sim_ms"] for row in data["rows"]) * 1.2])
            st.plotly_chart(figure, width="stretch", key="capacity_times")
            st.dataframe([{"Distribution": row["key"], "Data slots": str(row["caps"]), "Remote gates": row["gates"],
                           "Qubit moves": row["moves"], "Time (ms)": row["sim_ms"], "Success (%)": round(100 * row["success"], 1)}
                          for row in data["rows"]], hide_index=True, width="stretch")
            st.info("The topology and total capacity stay fixed. Concentrating capacity lets the compiler co-locate interacting qubits, changing the remote-gate and qubit-move mix.")
            st.caption("Red circles show data slots. Execution times come from noiseless runs; success rates use 1,000 noisy shots at z = 0.95. These are saved Figure 6(b) results.")
    else:
        st.write("4 search qubits + 2 ancillas · 2 nodes · three data slots per node · same network · z = 0.95")
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
        with st.container(border=True):
            paper = st.checkbox("Use paper topology setup", value=False)
            suffix = "paper" if paper else "custom"
            qubits = st.selectbox("Search qubits", [3, 4, 5, 6], index=3 if paper else 1, disabled=paper, key=f"qubits_{suffix}")
            st.caption(f"Total qubits: {2 * qubits - 2} ({qubits} search + {qubits - 2} ancillas)")
            node_options = [count for count in range(2, 2 * qubits - 1) if (2 * qubits - 2) % count == 0]
            node_key = f"nodes_{suffix}"
            if node_key in st.session_state and st.session_state[node_key] not in node_options:
                st.session_state[node_key] = node_options[-1]
            modules = st.selectbox("Quantum nodes", node_options, index=len(node_options) - 1 if paper else 0, disabled=paper, key=node_key)
            topology_options = ["Star", "Grid", "Caveman"] if modules % 2 == 0 else ["Star", "Grid"]
            topology = st.selectbox("Network topology", topology_options)
            compiler = st.selectbox("Compiler", ["QAP", "Random", "FGP · default", "FGP · low margin"], index=2 if paper else 0, disabled=paper, key=f"compiler_{suffix}")
            link = st.slider("Fiber length parameter (km)", 0.01, 20.0, 5.0, 0.01, format="%.2f", disabled=paper, key=f"link_{suffix}")
            efficiency = st.slider("Quantum Memory efficiency", 0.5, 1.0, 0.9, 0.05, disabled=paper, key=f"efficiency_{suffix}")
            noise_column, quality_column = st.columns(2)
            noise = noise_column.checkbox("Include hardware noise", value=True, disabled=paper, key=f"noise_{suffix}")
            z = quality_column.select_slider("Hardware quality (z)", options=[0.00, 0.25, 0.50, 0.65, 0.80, 0.90, 0.95, 1.00], value=0.95, format_func=lambda value: f"{value:.2f}", disabled=paper or not noise, key=f"z_{suffix}")
            st.caption("Higher z improves hardware quality. This setting applies when hardware noise is enabled.")
            shots_column, seed_column = st.columns(2)
            shots = shots_column.select_slider("Simulation shots", options=[1, *range(5, 251, 5)], value=250 if paper else 5, key=f"shots_{suffix}")
            seed = seed_column.number_input("Random seed", min_value=0, max_value=1000000, value=0 if paper else 1, key=f"explore_seed_{suffix}")
            if paper:
                st.caption("6 search qubits + 4 ancillas · 10 nodes · 1 data slot per node · FGP · 8 communication slots · z = 0.95. Reduce shots for a quick preview; saved manuscript results show the reported comparison.")
            if st.button("Compile and simulate", type="primary", disabled="job" in st.session_state):
                launch({"scenario": "exploration", "qubits": qubits, "modules": modules, "topology": topology,
                        "compiler": compiler, "link_km": link, "efficiency": efficiency, "noise": noise, "z": z, "shots": shots, "seed": seed, "paper_setup": paper})
                st.rerun()
    with right:
        st.caption(f"SELECTED NETWORK · {topology} · {modules} nodes")
        st.plotly_chart(charts.network(topology, modules, capacity=(2 * qubits - 2) // modules), width="stretch", key="explore_preview")
        history = st.session_state.get("exploration_history", [])
        if not history:
            st.info("Choose a network and compiler, then run. For a controlled comparison, change one setting at a time and keep the seed fixed.")
            return
        result = history[-1]
        config = result["config"]
        st.caption(f"LATEST COMPLETED RUN · {config['topology']} · {config['compiler']} · {result['total_shots']} shots")
        columns = st.columns(4)
        columns[0].metric("Success Probability", f"{result['success']:.1%}")
        columns[1].metric("Execution time", f"{result['sim_ms']:.1f} ms")
        columns[2].metric("Remote gates", result["gates"])
        columns[3].metric("Qubit moves", result["moves"])
        st.caption("Small shot counts are for interaction; use the saved 1,000-shot datasets for more precise success comparisons. Simulated execution time differs from laptop wall time.")
        st.dataframe([{"Run": i + 1, "Network": r["config"]["topology"], "Compiler": r["config"]["compiler"],
                       "Fiber (km)": r["config"]["link_km"], "Memory efficiency": r["config"]["efficiency"],
                       "Noise": r["config"]["noise"], "z": r["config"].get("z", 0.95) if r["config"]["noise"] else None,
                       "Seed": r["config"]["seed"], "Search qubits": r["config"]["qubits"],
                       "Nodes": r["config"]["modules"], "Time (ms)": round(r["sim_ms"], 2),
                       "Remote gates": r["gates"], "Moves": r["moves"], "Success (%)": round(r["success"] * 100, 1),
                       "Shots": r["total_shots"]} for i, r in enumerate(history)], hide_index=True, width="stretch")
        results_download({"runs": history}, "exploration")


with st.sidebar:
    st.markdown("### SeQUeNCe.DQC")
    st.caption("Interactive simulation")
    page = st.radio("Explore", ["Nature reproduction", "Networks & compilers"], label_visibility="collapsed")
    st.divider()
    st.write("**The Question**")
    st.write("How does quantum network and compilation jointly shape distributed quantum computation?")

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
