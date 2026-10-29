#!/usr/bin/env python3
"""Coordinated-z hardware noise (paper's 'Selected hardware parameters' table), applied to a
DQCArchitecture.

A single knob z sets every per-node fidelity and the dephasing time from realistic hardware at
z=0 to ideal at z=1, with amplitude damping fixed at T1=100 s. Applied knobs:
  * per-node gate/measurement fidelities F_1q, F_2q, F_m and T1/T2  -> node_noise, and
  * physical Bell-pair fidelity F_phys                              -> the JSON memory template
    (templates.teleportation.MemoryArray.fidelity), so every heralded pair is generated at F_phys.
F_init (initialization) is tabulated but not yet applied.
"""
T1 = 100.0   # seconds, fixed across the sweep

# z -> (F_1q, F_2q, F_m, F_init, F_phys, T2[s])
ZTABLE = {
    0.00: (0.99900, 0.99910, 0.99600, 0.99000, 0.96500, 2.000),
    0.25: (0.99925, 0.99933, 0.99700, 0.99250, 0.97375, 2.669),
    0.50: (0.99950, 0.99955, 0.99800, 0.99500, 0.98250, 4.008),
    0.65: (0.99965, 0.99969, 0.99860, 0.99650, 0.98775, 5.728),
    0.80: (0.99980, 0.99982, 0.99920, 0.99800, 0.99300, 10.030),
    0.90: (0.99990, 0.99991, 0.99960, 0.99900, 0.99650, 20.068),
    0.95: (0.99995, 0.99996, 0.99980, 0.99950, 0.99825, 40.144),
    1.00: (1.00000, 1.00000, 1.00000, 1.00000, 1.00000, 199.99),
}


def apply_z(T, z):
    """Apply the coordinated-z noise for sweep point ``z`` to architecture ``T`` (in place).

    Sets per-node F_1q/F_2q/F_m + T1/T2, and injects the Bell-pair fidelity F_phys through the
    memory template by wrapping ``T.sim_config``. Returns ``T``.
    """
    f1, f2, fm, _finit, fphys, t2 = ZTABLE[z]
    T.node_noise = {nm: {"one_qubit_gate_fid": f1, "two_qubit_gate_fid": f2,
                         "measurement_fid": fm, "t1": T1, "t2": t2} for nm in T.node_names}
    _orig = T.sim_config

    def _cfg(comm_memo=None, _orig=_orig, _f=fphys):
        c = _orig(comm_memo)
        c["templates"]["teleportation"]["MemoryArray"]["fidelity"] = _f
        return c

    T.sim_config = _cfg
    return T
