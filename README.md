# SeQUeNCe.DQC Demo

An interactive Streamlit + Plotly demo of distributed Grover search:

- **Nature reproduction:** two qubits on two nodes, with noiseless and adjustable detailed error models.
- **Networks & compilers:** saved manuscript comparisons of topology, compiler, and capacity, plus small live simulations.

## Setup and run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open [localhost:8501](http://127.0.0.1:8501). If your environment is already configured, only the last command is needed. Stop the server with `Ctrl+C`.

The demo prefers the local `../SeQUeNCe.DQC` checkout. Set `SEQUENCE_DQC_ROOT` to use another location; otherwise it uses the engine installed from GitHub by `requirements.txt`. No `dqc-experiments` installation is required.

For Streamlit Community Cloud, select `app.py` and use this repository’s `requirements.txt`.

## Using the demo

Saved manuscript results are available immediately. Live simulations run when you click **Run distributed Grover**; keep the workload and seed fixed when comparing settings. Hover over question-mark icons for error-source explanations.

Live network exploration supports 3–6 search qubits and 1–250 shots. Node counts must evenly divide the total circuit qubits (`2n − 2`). Simulated execution time and wall time measure different things. The 71% Nature reference is the experimental average across four marked states.

Reference datasets are in `data/`; live outputs are saved in `runs/` and can be downloaded in the app. Figure 6(b)’s unequal-capacity comparison is available as saved results only.

## Tests

```bash
python -m unittest discover -s tests -v
```
