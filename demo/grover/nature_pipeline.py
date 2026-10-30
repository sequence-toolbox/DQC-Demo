"""Two-node Grover simulation for the noiseless control and detailed error budget.

Adapted from the experiment runner; the standalone CLI is not included.
"""
from __future__ import annotations

import contextlib
import io
import logging

import numpy as np

from sequence.topology.dqc_net_topo import DQCNetTopo
from sequence.components.circuit import Circuit
from sequence.dqc.worker_program import TeleportationWorkerProgram
from sequence.dqc.compilers import build_compiler
from sequence.dqc.runtime import purification_policy
from sequence.dqc.noise import DENSITY_MATRIX_NOISE_FORMALISM
import sequence.dqc.architecture as topo

from demo.grover.cz_grover_circuit_builder import CZGroverCircuitBuilder
from demo.grover.noisy_barrier import NoisyBarrierController
from demo.grover.error_budget import TABLE1_BUDGET

logging.disable(logging.CRITICAL)

N_DATA = 2
MARKED_STATES = [0, 1, 2, 3]

def _build_net():
    """Build a 2-module density-matrix network whose partition forces the two data qubits onto
    separate modules (so each Grover CZ is a teleported CZ). Returns (net, qnodes, controller)."""
    T = topo.make_star(2, 1)                            # 2 modules, capacity 1 -> one data qubit each
    T.controller_policy = "barrier"
    T.compiler_spec = {"partitioner": "topo-aware", "scheduler": "packed"}   # telegate, no moves
    config = T.sim_config()
    config["formalism"] = DENSITY_MATRIX_NOISE_FORMALISM
    for nd in config["nodes"]:
        if nd.get("type") == "DQCNode":
            nd["data_memo_size"] = 1                    # force the 1-qubit-per-module split
            nd["memo_size"] = max(nd.get("memo_size", 0), 8 * N_DATA + 8)
    with contextlib.redirect_stdout(io.StringIO()):
        net = DQCNetTopo(config)
    qn = {node.name: node for node in net.nodes[DQCNetTopo.DQC_NODE]}
    return net, qn, net.controller


def run_single(marked_state, cz_fidelity, p_bell, seed, budget=None,
               local_1q_fid=1.0, meas_fid=1.0, readout_fid=1.0, node_overrides=None) -> bool:
    """Run one density-matrix Grover shot through the real pipeline. Returns success (measured ==
    marked). Per-node fidelities (``two_qubit_gate_fid`` / ``one_qubit_gate_fid``) are read by the
    controller's surgical hook; ``node_overrides`` makes them heterogeneous."""
    node_overrides = node_overrides or {}
    rng = np.random.default_rng(seed)
    circuit = CZGroverCircuitBuilder(N_DATA, [marked_state], 1, total_qubits=N_DATA).build_grover_circuit()

    net, qn, ctrl = _build_net()
    tl = net.tl
    qm = tl.quantum_manager
    qm.noise_rng = np.random.default_rng(seed)          # randomness for the surgical channels

    for node in qn.values():                            # per-node knobs the hook reads
        ov = node_overrides.get(node.name, {})
        node.two_qubit_gate_fid = ov.get("cz", cz_fidelity)
        node.one_qubit_gate_fid = ov.get("q1", local_1q_fid)
        node.measurement_fid = ov.get("meas", meas_fid)

    ctrl.__class__ = NoisyBarrierController              # swap in the surgical-noise policy
    with contextlib.redirect_stdout(io.StringIO()):
        program = build_compiler("topo-aware", "packed").compile(circuit, net, seed=seed)
        ctrl.load(program)                               # install the plan; seeds the registry
    ctrl.configure_noise(p_bell=p_bell, budget=budget)

    # Near-stateless executors, WITHOUT register_qubits -> native per-gate noise stays off.
    hop = net.hop_distances()
    for nm, nd in qn.items():
        TeleportationWorkerProgram(node=nd, controller_name=ctrl.name,
                                   hop_distances=hop.get(nm, {}), reservation_policy=purification_policy)

    tl.stop_time = int((program.max_step + 16) * 2e9 * 8)
    with contextlib.redirect_stderr(io.StringIO()):
        tl.init()
        ctrl.start_execution()
        tl.run()

    meas = {}                                           # read out the two data qubits, with SPAM
    for gq in range(N_DATA):
        name, slot = ctrl.registry.location(gq)
        nd = qn[name]
        key = nd.get_component_by_name(nd.data_memo_arr_name)[slot].qstate_key
        c = Circuit(1)
        c.measure(0)
        bit = qm.run_circuit(c, [key], rng.random())[key]
        if readout_fid < 1.0 and rng.random() > readout_fid:   # final-readout SPAM bit-flip
            bit ^= 1
        meas[gq] = bit
    return sum(b << gq for gq, b in meas.items()) == marked_state

