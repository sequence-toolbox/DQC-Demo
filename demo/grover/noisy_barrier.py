#!/usr/bin/env python3
"""Barrier controller variant that injects the density-matrix Grover replication's surgical noise.

Subclasses the library :class:`~sequence.dqc.controllers.barrier.BarrierController` and adds, at
each step boundary, the paper's calibrated error channels applied *directly to the two data qubits*
of a just-completed teleported CZ (and single-qubit noise after a local gate). It uses the density
manager's ``reduce_to`` + ``apply_noise`` and does NOT register the qubits, so the native per-gate
noise path stays off and the teleportation itself is exact -- exactly the "in-place noise after each
CZ, once the comm qubits are traced out" model of Main et al. All of this is experiment-specific and
lives here, not in the library; the library barrier is used unchanged via a class swap.

Note on ``reduce_to``: SeQUeNCe's density measurement does not drop the telegate's measured comm
qubits from the joint state, so the two data qubits stay entangled with stale comm qubits that are
later reset. Those comm qubits are separable (definite) once the gate has completed, so partial-
tracing them out yields the exactly-correct 2-qubit data state and detaches it before any reset.
"""
from __future__ import annotations

import sequence.utils.log as log

from sequence.dqc.controllers.barrier import BarrierController


class NoisyBarrierController(BarrierController):
    """A BarrierController that applies surgical post-CZ / post-local-gate noise on completion.

    Instantiate the library controller as usual (e.g. via ``DQCNetTopo``), swap the instance's
    class to this one, then call :meth:`configure_noise` after ``compile`` seeds the registry.
    """

    def configure_noise(self, p_bell: float = 0.0, budget: dict | None = None, p_1q: float = 0.0):
        """Store the noise config and precompute which steps carry a remote CZ / local 1q gate.

        Args:
            p_bell (float): raw network-entanglement (Bell-pair) error probability, applied as an
                extra 2-qubit depolarizing channel per teleported CZ (0 = off).
            budget (dict | None): the detailed per-source Table-1 error budget (see the driver). When
                set it replaces the lumped per-node CZ error.
            p_1q (float): fallback single-qubit gate infidelity for local gates on ideal nodes.

        Returns:
            NoisyBarrierController: self.
        """
        self.p_bell = p_bell
        self.error_budget = budget
        self.p_1q = p_1q
        self.p_cz = 0.0
        self._remote_cz_steps: dict = {}   # step -> [control_q, target_q]
        self._local_1q_steps: dict = {}    # step -> [data qubit, ...]
        for grp in self.program.node_ops.values():
            for op in grp.get("remote", []):
                targets = op.get("targets", [])
                if op.get("gate") in ("cz", "cx") and len(targets) == 2:
                    self._remote_cz_steps[op["step"]] = list(targets)
            for op in grp.get("local", []):
                targets = op.get("targets", [])
                if len(targets) == 1:
                    self._local_1q_steps.setdefault(op["step"], [])
                    if targets[0] not in self._local_1q_steps[op["step"]]:
                        self._local_1q_steps[op["step"]].append(targets[0])
        return self

    # ── inject noise at each completed step, then let the barrier advance normally ──
    def receive_message(self, src, msg) -> None:
        before = self.current
        super().receive_message(src, msg)
        if self.current > before:                      # step `before` just completed on all nodes
            self._after_teleported_cz(before)
            self._after_local_gate(before)

    # ── resolve data qubits against the controller's registry ─────────────────
    def _node_for(self, global_q: int):
        name = self.registry.qubit_to_node.get(global_q)
        return next((nd for nd in self.qnodes if nd.name == name), None)

    def _data_qubit_key(self, global_q: int):
        name, slot = self.registry.location(global_q)
        nd = next((n for n in self.qnodes if n.name == name), None)
        if nd is None or slot is None:
            return None
        arr = nd.get_component_by_name(nd.data_memo_arr_name)
        return arr[slot].qstate_key if arr is not None and slot < len(arr) else None

    @staticmethod
    def _fid(node, attr: str) -> float:
        return float(getattr(node, attr, 1.0)) if node is not None else 1.0

    # ── the surgical channels (density manager: reduce_to + apply_noise) ───────
    def _after_teleported_cz(self, step: int) -> None:
        """After a remote (teleported-CZ) step: trace out the comm ghosts, then depolarize the two
        data qubits at the calibrated CZ fidelity (or the detailed Table-1 budget)."""
        qubits = self._remote_cz_steps.get(step)
        if not qubits or len(qubits) != 2:
            return
        keys = [self._data_qubit_key(q) for q in qubits]
        if any(k is None for k in keys):
            log.logger.warning("[cz-noise] step %d: could not resolve data keys %s", step, qubits)
            return
        qm = self.timeline.quantum_manager
        qm.reduce_to(keys)                                   # detangle comm ghosts (keys[0]=A, keys[1]=B)
        if self.error_budget:
            self._apply_error_budget(qm, keys)              # detailed Table-1 model
            return
        ctrl_node, tgt_node = self._node_for(qubits[0]), self._node_for(qubits[1])
        cz_infid = 1.0 - min(self._fid(ctrl_node, "two_qubit_gate_fid"), self._fid(tgt_node, "two_qubit_gate_fid"))
        if cz_infid > 0.0:                                   # lumped per-node CZ error (avg infidelity)
            qm.apply_noise(keys, "depolarize", cz_infid, is_infidelity=True)
        elif self.p_cz > 0.0:
            qm.apply_noise(keys, "depolarize", self.p_cz, is_infidelity=False)
        if self.p_bell > 0.0:                               # raw Bell-pair error (link property)
            qm.apply_noise(keys, "depolarize", self.p_bell, is_infidelity=False)

    def _after_local_gate(self, step: int) -> None:
        """Single-qubit depolarizing after each local gate on a data qubit in ``step``."""
        qm = self.timeline.quantum_manager
        for gq in self._local_1q_steps.get(step, ()):
            key = self._data_qubit_key(gq)
            if key is None:
                continue
            infid = 1.0 - self._fid(self._node_for(gq), "one_qubit_gate_fid")
            if infid <= 0.0:
                infid = self.p_1q
            if infid > 0.0:
                qm.apply_noise([key], "depolarize", infid)

    def _apply_error_budget(self, qm, keys) -> None:
        """The paper's Table-1 per-teleported-CZ budget (keys[0]=Alice/control, keys[1]=Bob/target).
        Each value is an average-gate-infidelity contribution the manager converts to a channel."""
        b = self.error_budget
        qm.apply_noise(keys, "depolarize", b.get("raw_entanglement", 0.0))          # 2-qubit
        for src in ("mixed_species", "xc_transfer", "qc_rotations"):
            e_a, e_b = b.get(src, (0.0, 0.0))
            qm.apply_noise([keys[0]], "depolarize", e_a)
            qm.apply_noise([keys[1]], "depolarize", e_b)
        e_a, e_b = b.get("qc_decoherence", (0.0, 0.0))                              # T2 dephasing
        qm.apply_noise([keys[0]], "dephase", e_a)
        qm.apply_noise([keys[1]], "dephase", e_b)
        e_a, e_b = b.get("midcircuit_meas", (0.0, 0.0))                             # readout bit-flip
        qm.apply_noise([keys[0]], "bit_flip", e_a)
        qm.apply_noise([keys[1]], "bit_flip", e_b)
