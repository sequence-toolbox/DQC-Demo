# SeQUeNCe.DQC — SC26 demo

A local Streamlit + Plotly app with two scenarios:

1. **Nature reproduction:** the two-node Grover experiment from Section 3 of the manuscript. The compiler is fixed. Run the existing density-matrix/BSM/telegate pipeline with noiseless, lumped, or detailed noise. Change Bell fidelity, and (for lumped noise) teleported-CZ fidelity. Compare all four marked states with the manuscript and the experimental 71% average.
2. **Networks & compilers:** explore saved manuscript topology/compiler results immediately, or run small live Grover workloads while changing topology, compiler, fiber length, memory efficiency, and hardware noise.

## Run on this laptop

From this directory:

```bash
.venv/bin/python -m streamlit run app.py
```

Open http://127.0.0.1:8501. The server binds only to the local machine. Once dependencies are installed, running the demo requires no internet connection. Plots, fonts, and reference datasets use local resources; Streamlit usage telemetry is disabled.

The prepared `.venv` inherits scientific dependencies from the existing `dqc` conda environment and adds Streamlit locally. Other environments are unchanged.

## Set up another environment

Use the Python version supported by both local projects (this laptop uses Python 3.14):

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ../SeQUeNCe.DQC -e ../dqc-experiments
.venv/bin/python -m pip install -r requirements.txt
```

By default, the live worker imports these sibling checkouts directly. For different locations, set `SEQUENCE_DQC_ROOT` and `DQC_EXPERIMENTS_ROOT` to their absolute paths before launching. Saved results are available without the simulation checkouts; live runs display an error if the sources or their dependencies are missing.

## Demo walkthrough

- Start on **Nature reproduction**. Explain the two data qubits, the link, and the two teleported CZ operations.
- The initial chart is the **saved manuscript reference**, not a newly computed result. It contains rounded percentages from `3-grovers.tex` (2,000 shots per marked state).
- Run **Noiseless** at 25 shots per state. Switch Results to **Live runs** to see the end-to-end baseline.
- Run **Lumped** at the manuscript defaults (Bell 0.9689, CZ 0.862). Compare the completed runs. Increase shots for a more stable estimate, or improve Bell fidelity to explore its effect.
- In **Detailed**, Bell fidelity changes the raw-entanglement term; the remaining Table 1 terms, local-gate infidelity 0.0001, and final-readout infidelity 0.005 stay fixed. CZ fidelity is unused in this model. Noiseless ignores both fidelity sliders.
- Switch to **Networks & compilers**. Saved network results hold the FGP compiler fixed; saved compiler results hold the two-node network fixed. These are different workloads, not a joint factorial experiment.
- For a live comparison, keep the workload and seed fixed and change one network or compiler setting. Choose Star, Grid, or Caveman, matching the paper's topology families. Two-node layouts are the same physical graph; choose four modules to compare distinct edge structures. The small live Caveman consists of two intact cliques joined by one bridge (four modules give a four-node path). The saved ten-node Caveman retains the original experiment's NetworkX connected-caveman construction. All four-node layouts currently have equal capacity per node.

## Interpretation and limits

- Nature reproduction uses effective calibrated error channels on the data qubits after each remote gate, following the existing experiment adapter. It does not propagate a physically degraded mixed Bell pair through the protocol. Distance and time-dependent decoherence are not controls in this scenario.
- The experimental 71% reference is an **average across four states**. Its 70–72% shaded band is the reported uncertainty, not a 95% confidence interval or four experimental state measurements.
- Live per-state bars and live exploration success estimates use **95% Wilson intervals**. At 100 total shots, several percentage points of uncertainty are expected. Manuscript bars have no invented error bars or raw counts.
- Larger circuits use the ket-vector runtime. With hardware noise enabled, select the existing coordinated hardware model at z = 0.00, 0.25, 0.50, 0.65, 0.80, 0.90, 0.95, or 1.00 (default 0.95). The worker uses the original `noise_z.ZTABLE` values, including fixed T1 and the tabulated T2 at z = 1; z = 1 is distinct from disabling noise entirely. Initialization fidelity is tabulated but not applied by that model. With noise disabled, circuit measurement is still probabilistic.
- Live simulated time is averaged across shots. The compiler placement seed is fixed across shots; noisy network and measurement seeds vary. Operation counts and hop histograms are reported from the first shot. These counts are not measured Bell-pair consumption.
- The fiber control passes the engine's `link_km` parameter unchanged. Its current channel generator assigns that distance to each QPU-to-BSM optical channel; do not interpret this UI value as a separately validated end-to-end physical length.
- Live sizes are bounded to 3–4 search qubits, 2 or 4 modules, and 1–1,000 shots. Fiber length ranges from 0.01 to 20 km in 0.01 km increments. Ancillas are included when automatically choosing balanced capacity. A 10-minute timeout and Cancel button bound each job; large runs on long links may require reducing the shot count.
- One worker runs per browser session. Workers isolate simulator globals from Streamlit. Closing/reloading the browser can lose the session history; run JSON files remain under `runs/`. Each worker enforces its own timeout even if the browser closes; Cancel stops it immediately.

## Sources and exports

- `data/nature_reference.json`: rounded Section 3 simulation results transcribed from the local manuscript, snapshot 2026-10-28. The experimental average is quoted by that section.
- `data/topo_exec.json`, `data/compiler_comparison.json`: unchanged snapshots of the matching files under the sibling `dqc-experiments/dqc_experiments/results/`, taken 2026-10-28. Original metadata is preserved. In particular, the random compiler row is an average over placements; its shot metadata should be interpreted using the originating experiment rather than as a single binomial sample.
- Live execution uses `paper_replication/grover_2node_pipeline.run_single` and `sequence.dqc.runtime.run`. It does not modify either source project.
- Download buttons export settings alongside results. Live run folders contain configuration, progress, result/error JSON, and worker logs.

## Verification

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Tests cover page navigation and chart rendering, a real noiseless two-node worker run over all four marked states, real compiler/network execution, and cancellation.
