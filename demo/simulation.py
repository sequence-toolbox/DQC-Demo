"""Simulation adapters. Imported only by an isolated worker process."""
import contextlib
import io
import math
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def connect_sources():
    """Prefer the requested local source checkouts over unrelated installed packages."""
    engine = Path(os.environ.get("SEQUENCE_DQC_ROOT", ROOT.parent / "SeQUeNCe.DQC"))
    experiments = Path(os.environ.get("DQC_EXPERIMENTS_ROOT", ROOT.parent / "dqc-experiments"))
    for path in (experiments, engine):
        if not path.is_dir():
            raise FileNotFoundError(f"Source checkout missing: {path}. See README.md for setup.")
        sys.path.insert(0, str(path))
    cache = ROOT / "runs" / ".matplotlib"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache))
    return {"engine": str(engine), "experiments": str(experiments)}


def nature(config, progress):
    from dqc_experiments.paper_replication.grover_2node_pipeline import TABLE1_BUDGET, run_single

    model, shots = config["model"], int(config["shots"])
    if model not in ("Noiseless", "Lumped", "Detailed") or not 1 <= shots <= 2000:
        raise ValueError("Invalid Nature reproduction configuration")
    bell, cz = config["bell"], config["cz"]
    if not 0.5 <= bell <= 1 or not 0.5 <= cz <= 1:
        raise ValueError("Fidelities must be between 0.5 and 1")
    if model == "Noiseless":
        bell = cz = 1.0
    budget = {**TABLE1_BUDGET, "raw_entanglement": 1 - bell} if model == "Detailed" else None
    rows, done = [], 0
    for state in range(4):
        hits = 0
        for shot in range(shots):
            seed = int(config["seed"]) + state * shots + shot
            hits += int(run_single(state, cz, 1 - bell, seed, budget=budget,
                                   local_1q_fid=0.9999 if model == "Detailed" else 1.0,
                                   readout_fid=0.995 if model == "Detailed" else 1.0))
            done += 1
            progress(done / (4 * shots), f"Marked |{state:02b}〉 · shot {shot + 1}/{shots}")
        rows.append({"state": f"{state:02b}", "hits": hits, "shots": shots, "success": hits / shots})
    return {"rows": rows, "success": sum(r["success"] for r in rows) / 4,
            "total_shots": 4 * shots, "model": model,
            "effective_noise": {"bell_fidelity": bell, "cz_fidelity": cz if model != "Detailed" else None,
                                "budget": budget, "local_1q_fidelity": 0.9999 if model == "Detailed" else 1.,
                                "readout_fidelity": 0.995 if model == "Detailed" else 1.}}


def exploration(config, progress):
    import networkx as nx
    from sequence.dqc.architecture import DQCArchitecture
    from sequence.dqc.compilers import build_compiler
    from sequence.dqc.compilers.fgp import FGPCompiler
    from sequence.dqc.runtime import run
    from dqc_experiments.circuits.grover_circuit_builder import GroverCircuitBuilder
    from dqc_experiments.noise_z import apply_z

    n, modules, shots = int(config["qubits"]), int(config["modules"]), int(config["shots"])
    if n not in (3, 4) or modules not in (2, 4) or not 1 <= shots <= 20:
        raise ValueError("Invalid live exploration size")
    graphs = {"Star": nx.star_graph(modules - 1), "Ring": nx.cycle_graph(modules),
              "Grid": nx.convert_node_labels_to_integers(nx.grid_2d_graph(2, modules // 2))}
    circuit = GroverCircuitBuilder(n, [2 ** n - 1], round(math.pi / 4 * math.sqrt(2 ** n))).build_grover_circuit()
    capacity = math.ceil(circuit.size / modules)

    def make_topology():
        topology = DQCArchitecture.from_nx_graph("demo", graphs[config["topology"]], capacity, comm_memo=16)
        topology.link_km = config["link_km"]
        topology.mem_efficiency = config["efficiency"]
        if config["noise"]:
            apply_z(topology, 0.95)
        return topology

    if config["compiler"] == "FGP · low margin":
        compiler = FGPCompiler(seed_partitioner="qap", lookahead=20, move_margin=FGPCompiler._CUR)
    elif config["compiler"] == "FGP · default":
        compiler = build_compiler("qap", "fgp")
    else:
        compiler = build_compiler("random" if config["compiler"] == "Random" else "qap", "packed")
    results = []
    for shot in range(shots):
        progress(shot / shots, f"Executing shot {shot + 1}/{shots}")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = run(circuit, make_topology(), compiler=compiler, seed=int(config["seed"]),
                         data_qubits=range(n), expected=2 ** n - 1, shots=1, meas_seed=int(config["seed"]) + shot * 1009)
        if result["reached"] < result["steps"]:
            raise RuntimeError("Simulation stopped before the compiled program completed; no result reported.")
        results.append(result)
    hits = sum(r.get("successes", int(r.get("ok", False))) for r in results)
    return {"success": hits / shots, "hits": hits, "total_shots": shots,
            "sim_ms": sum(r["sim_ms"] for r in results) / shots,
            "gates": results[0]["gates"], "moves": results[0]["moves"],
            "hops": results[0]["hops"], "total_qubits": circuit.size, "capacity": capacity,
            "shots": results, "edges": list(graphs[config["topology"]].edges())}


def simulate(config, progress):
    paths = connect_sources()
    start = time.monotonic()
    result = nature(config, progress) if config["scenario"] == "nature" else exploration(config, progress)
    return {**result, "config": config, "source": "Live SeQUeNCe.DQC simulation", "source_paths": paths,
            "wall_seconds": time.monotonic() - start}
