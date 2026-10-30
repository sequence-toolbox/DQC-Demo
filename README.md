# SeQUeNCe.DQC — SC26 demo

A local Streamlit + Plotly app with two scenarios:

1. **Nature reproduction:** the two-node Grover experiment from Section 3 of the manuscript. The compiler is fixed. Run the existing density-matrix/BSM/telegate pipeline with the noiseless control or detailed noise model. Adjust Bell fidelity and every Table I error source in the detailed model. Compare all four marked states with the manuscript and the experimental 71% average.
2. **Networks & compilers:** explore saved manuscript topology/compiler results immediately, or run small live Grover workloads while changing topology, compiler, fiber length, memory efficiency, and hardware noise.

## Run on this laptop

From this directory:

```bash
.venv/bin/python -m streamlit run app.py
```

Open http://127.0.0.1:8501. The server binds only to the local machine. Once dependencies are installed, running the demo requires no internet connection. Plots, fonts, and reference datasets use local resources; Streamlit usage telemetry is disabled.

The prepared `.venv` inherits scientific dependencies from the existing `dqc` conda environment and adds Streamlit locally. Other environments are unchanged.

## Set up another environment

Use the Python version supported by SeQUeNCe.DQC (this laptop uses Python 3.14):

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ../SeQUeNCe.DQC
.venv/bin/python -m pip install -r requirements.txt
```

The live worker uses the sibling SeQUeNCe.DQC engine checkout. For a different location, set `SEQUENCE_DQC_ROOT` to its absolute path before launching. Circuit builders, the Nature simulation adapter, and hardware-noise settings are included under `demo/`; installing or keeping the dqc-experiments repository is not required. Saved results are available without the engine checkout; live runs display an error if the engine or its dependencies are missing.

## Demo walkthrough

- Start on **Nature reproduction**. Explain the two data qubits, the link, and the two teleported CZ operations.
- The initial chart is the **saved manuscript reference**, not a newly computed result. It contains rounded percentages from `3-grovers.tex` (10,000 shots per marked state for the detailed model).
- Run **Noiseless** at 100 shots per state. Switch Results to **Live runs** to see the end-to-end baseline.
- Run **Detailed** at the manuscript default Bell fidelity of 0.9689. Compare with the noiseless control. Increase shots for a more stable estimate, or improve Bell fidelity to explore its effect.
- In **Detailed**, Bell fidelity changes the raw-entanglement term. The detailed-model form displays all five per-node error contributions in a compact editable table with Alice/control and Bob/target columns. Local H/X and final-readout error controls sit side by side below it. Controls use percentages; default local error 0.01% equals 0.0001 and readout error 0.5% equals 0.005. QC decoherence is an error contribution, not a time. Selecting Noiseless immediately hides the noise controls and fixes Bell fidelity to 1.0 and every error to zero. Run exports include the effective error budget and fidelities.
- Switch to **Networks & compilers**. Saved network results hold the FGP compiler fixed; saved compiler results hold the two-node network fixed. These are different workloads, not a joint factorial experiment.
- For a live comparison, keep the workload and seed fixed and change one network or compiler setting. Choose Star, Grid, or Caveman, matching the paper's topology families. Two-node layouts are the same physical graph; choose four nodes to compare distinct edge structures. The small live Caveman consists of two intact cliques joined by one bridge (four nodes give a four-node path). The ten-node Caveman uses two full five-node cliques joined by one bridge, matching the experiment. All layouts have balanced capacity per node. Graph definitions for previews and live simulations are shared in `demo/topologies.py`; at 10 nodes they match the original experiment builders exactly.

## Reproduce the three topology configurations

Under **Networks & compilers → Live simulation**, enable **Use paper topology setup**. It selects 6 search qubits plus 4 ancillas, 10 nodes with one data slot each, the QAP-seeded FGP compiler, 8 communication slots per node, 5 km fiber parameter, memory efficiency 0.9, and hardware noise z = 0.95. The default is 1,000 shots; reduce it for a quick preview. Choose Star, Grid, or Caveman and run each configuration. Node choices also include 6 and 8 for custom experiments.

The layouts are a hub with nine spokes, a 2×5 grid, and two full five-node cliques joined by a single bridge. Saved manuscript results provide the reported comparison immediately. Live success estimates are fresh finite-shot samples. The paper reports execution time from a separate noiseless execution; the live panel reports the mean execution time of its selected noisy or noiseless shots, so those times need not equal the saved bars.

## Interpretation and limits

- Nature reproduction uses effective calibrated error channels on the data qubits after each remote gate, following the existing experiment adapter. It does not propagate a physically degraded mixed Bell pair through the protocol. Distance and time-dependent decoherence are not controls in this scenario.
- The experimental 71% reference is an **average across four states**. Its 70–72% shaded band is the reported uncertainty, not a 95% confidence interval or four experimental state measurements.
- Live per-state bars and live exploration success estimates use **95% Wilson intervals**. At 100 total shots, several percentage points of uncertainty are expected. Manuscript bars have no invented error bars or raw counts.
- Larger circuits use the ket-vector runtime. With hardware noise enabled, select the existing coordinated hardware model at z = 0.00, 0.25, 0.50, 0.65, 0.80, 0.90, 0.95, or 1.00 (default 0.95). The worker uses the original `noise_z.ZTABLE` values, including fixed T1 and the tabulated T2 at z = 1; z = 1 is distinct from disabling noise entirely. Initialization fidelity is tabulated but not applied by that model. With noise disabled, circuit measurement is still probabilistic.
- Live simulated time is averaged across shots. The compiler placement seed is fixed across shots; noisy network and measurement seeds vary. Operation counts and hop histograms are reported from the first shot. These counts are not measured Bell-pair consumption.
- The fiber control passes the engine's `link_km` parameter unchanged. Its current channel generator assigns that distance to each QPU-to-BSM optical channel; do not interpret this UI value as a separately validated end-to-end physical length.
- Live sizes are bounded to 3–6 search qubits, 2, 4, 6, 8, or 10 nodes, and 1–1,000 shots. Fiber length ranges from 0.01 to 20 km in 0.01 km increments. Ancillas are included when automatically choosing balanced capacity. Grover uses floor(π√(2ⁿ)/4) iterations: 2, 3, 4, and 6 for n = 3, 4, 5, and 6. Custom jobs have a 10-minute timeout; paper-setup jobs have a 120-minute timeout. Both have a Cancel button; large runs on long links may require reducing the shot count.
- One worker runs per browser session. Workers isolate simulator globals from Streamlit. Closing/reloading the browser can lose the session history; run JSON files remain under `runs/`. Each worker enforces its own timeout even if the browser closes; Cancel stops it immediately.

## Sources and exports

- `data/nature_reference.json`: updated detailed simulation values from `dqc-experiments/figures/code/plot_grover_success.py`, cross-checked against Section 3, snapshot 2026-10-29 (10,000 shots per marked state; 72.9%, 72.7%, 72.7%, 73.2%). Values are copied into this repository; no runtime experiment-package dependency is introduced. The experimental average is quoted by that section.
- `data/topo_exec.json`, `data/compiler_comparison.json`: unchanged snapshots of the matching files under the sibling `dqc-experiments/dqc_experiments/results/`, taken 2026-10-28. Original metadata is preserved. In particular, the random compiler row is an average over placements; its shot metadata should be interpreted using the originating experiment rather than as a single binomial sample.
- Live execution uses the local `demo.grover.nature_pipeline.run_single` and the SeQUeNCe engine's `sequence.dqc.runtime.run`. It does not import the experiment package or modify the engine.
- Copied from dqc-experiments on 2026-10-29: `circuits/grover_circuit_builder.py`, `paper_replication/cz_grover_circuit_builder.py`, `paper_replication/noisy_barrier.py`, `paper_replication/grover_2node_pipeline.py`, and `noise_z.py`. Their local counterparts are `demo/grover/grover_circuit_builder.py`, `demo/grover/cz_grover_circuit_builder.py`, `demo/grover/noisy_barrier.py`, `demo/grover/nature_pipeline.py`, and `demo/grover/noise_z.py`. Imports now reference local modules; the unused runner CLI was omitted. Simulation algorithms and noise parameters are preserved.
- Download buttons export settings alongside results. Live run folders contain configuration, progress, result/error JSON, and worker logs.

## Verification

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Tests cover page navigation and chart rendering, a real noiseless two-node worker run over all four marked states, real compiler/network execution, cancellation, and both demo scenarios with imports of the experiment package explicitly blocked.
