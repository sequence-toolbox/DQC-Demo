"""Simulation adapters. Imported only by an isolated worker process."""
import contextlib
import io
from importlib import import_module
import math
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def connect_sources():
    """Prefer a local checkout, otherwise use the engine installed from GitHub."""
    cache = ROOT / "runs" / ".matplotlib"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache))
    engine = Path(os.environ.get("SEQUENCE_DQC_ROOT", ROOT.parent / "SeQUeNCe.DQC")).expanduser().resolve()
    local = (engine / "sequence" / "dqc").is_dir()
    if local:
        # Move the checkout ahead of any installed copy, including editable installs.
        sys.path[:] = [str(engine)] + [path for path in sys.path if path != str(engine)]
    try:
        package = import_module("sequence")
        import_module("sequence.dqc.runtime")
    except ModuleNotFoundError as error:
        if error.name == "sequence" or (error.name or "").startswith("sequence."):
            raise RuntimeError("SeQUeNCe.DQC is unavailable. Install requirements.txt to get the GitHub engine, "
                               "or provide a local checkout using SEQUENCE_DQC_ROOT.") from error
        raise
    loaded = Path(package.__file__).resolve().parent
    return {"engine": str(loaded), "engine_source": "local checkout" if local else "installed package",
            "demo": str(ROOT)}


def nature(config, progress):
    from demo.grover.nature_pipeline import run_single
    from demo.grover.error_budget import resolve_noise

    model, shots = config["model"], int(config["shots"])
    if model not in ("Noiseless", "Detailed") or not 1 <= shots <= 2000:
        raise ValueError("Invalid Nature reproduction configuration")
    bell, budget, local_fidelity, readout_fidelity = resolve_noise(config)
    rows, done = [], 0
    for state in range(4):
        hits = 0
        for shot in range(shots):
            seed = int(config["seed"]) + state * shots + shot
            hits += int(run_single(state, 1.0, 1 - bell, seed, budget=budget,
                                   local_1q_fid=local_fidelity, readout_fid=readout_fidelity))
            done += 1
            progress(done / (4 * shots), f"Marked |{state:02b}〉 · shot {shot + 1}/{shots}")
        rows.append({"state": f"{state:02b}", "hits": hits, "shots": shots, "success": hits / shots})
    return {"rows": rows, "success": sum(r["success"] for r in rows) / 4,
            "total_shots": 4 * shots, "model": model,
            "effective_noise": {"bell_fidelity": bell, "cz_fidelity": 1.0 if model == "Noiseless" else None,
                                "budget": budget, "local_1q_fidelity": local_fidelity,
                                "readout_fidelity": readout_fidelity}}


def exploration(config, progress):
    from demo.topologies import topology_graph
    from sequence.dqc.architecture import make_star, make_grid, make_caveman
    from sequence.dqc.compilers import build_compiler
    from sequence.dqc.compilers.fgp import FGPCompiler
    from sequence.dqc.runtime import run
    from demo.grover.grover_circuit_builder import GroverCircuitBuilder
    from demo.grover.noise_z import ZTABLE, apply_z

    n, modules, shots = int(config["qubits"]), int(config["modules"]), int(config["shots"])
    if n not in (3, 4, 5, 6) or modules not in range(2, 11) or not 1 <= shots <= 250:
        raise ValueError("Invalid live exploration size")
    if modules > 2 * n - 2:
        raise ValueError("Quantum nodes cannot exceed the total number of circuit qubits")
    if (2 * n - 2) % modules:
        raise ValueError("Total circuit qubits must divide evenly among quantum nodes")
    z = config.get("z", 0.95)
    if z not in ZTABLE:
        raise ValueError("Hardware quality z must be one of the supported ZTABLE values")
    if not 0.01 <= config["link_km"] <= 20:
        raise ValueError("Fiber length must be between 0.01 and 20 km")
    graph = topology_graph(config["topology"], modules)
    circuit = GroverCircuitBuilder(n, [2 ** n - 1], math.floor(math.pi / 4 * math.sqrt(2 ** n))).build_grover_circuit()
    capacity = circuit.size // modules

    def make_topology():
        comm = 8 if config.get("paper_setup") else 16
        builders = {"Star": lambda: make_star(modules, capacity, comm_memo=comm),
                    "Grid": lambda: make_grid(2 if modules % 2 == 0 else 1, modules // 2 if modules % 2 == 0 else modules, capacity, comm_memo=comm),
                    "Caveman": lambda: make_caveman(2, modules // 2, capacity, comm_memo=comm)}
        topology = builders[config["topology"]]()
        topology.link_km = config["link_km"]
        topology.mem_efficiency = config["efficiency"]
        if config["noise"]:
            apply_z(topology, z)
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
            "shots": results, "edges": list(graph.edges())}


def simulate(config, progress):
    paths = connect_sources()
    start = time.monotonic()
    result = nature(config, progress) if config["scenario"] == "nature" else exploration(config, progress)
    return {**result, "config": config, "source": "Live SeQUeNCe.DQC simulation", "source_paths": paths,
            "wall_seconds": time.monotonic() - start}
