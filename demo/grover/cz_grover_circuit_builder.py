#!/usr/bin/env python3
"""CZ Grover circuit builder for the paper replication (Main et al., Nature 638, 2025).

Same Grover circuit as the base GroverCircuitBuilder, but the oracle/diffuser phase
flip is emitted as a *direct* CZ instead of the default H·CX·H decomposition. So the
remote (distributed) gate becomes a **teleported CZ**, matching the paper's hardware
primitive — the 2-qubit distributed Grover there is two teleported CZ gates (oracle
+ diffusion). `dqc_app` forwards gate_type='cz' to the telegate, which applies the
CZ and its Z-correction (vs the X-correction for CX).
"""
from __future__ import annotations

from demo.grover.grover_circuit_builder import GroverCircuitBuilder      # parent base


class CZGroverCircuitBuilder(GroverCircuitBuilder):
    """Grover circuit whose MCZ phase flip is a direct CZ (teleported CZ), not H·CX·H."""

    def _apply_cz(self, circ, ctrl: int, targ: int) -> None:
        circ.cz(ctrl, targ)
