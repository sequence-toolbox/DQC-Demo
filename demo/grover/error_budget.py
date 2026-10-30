"""Table I defaults and validation, shared by the controls and simulator."""
TABLE1_BUDGET = {"raw_entanglement": 0.0311,
                 "mixed_species": (0.024, 0.020),
                 "qc_decoherence": (0.019, 0.018),
                 "xc_transfer": (0.0076, 0.0052),
                 "midcircuit_meas": (0.00091, 0.00122),
                 "qc_rotations": (0.00016, 0.00015)}

ERROR_LABELS = {"mixed_species": "Mixed-species gate",
                "qc_decoherence": "QC decoherence (Z dephasing)",
                "xc_transfer": "QX ↔ QC transfer",
                "midcircuit_meas": "Mid-circuit measurement",
                "qc_rotations": "In-CZ rotations"}


def resolve_noise(config):
    bell = float(config["bell"])
    if not 0.5 <= bell <= 1:
        raise ValueError("Bell fidelity must be between 0.5 and 1")
    overrides = config.get("budget", {})
    if set(overrides) - set(ERROR_LABELS):
        raise ValueError("Unknown Table I error source; use Bell fidelity for raw entanglement")
    budget = {"raw_entanglement": 1 - bell}
    for name in ERROR_LABELS:
        values = overrides.get(name, TABLE1_BUDGET[name])
        if not isinstance(values, (list, tuple)) or len(values) != 2:
            raise ValueError(f"{name} requires Alice and Bob error values")
        pair = tuple(float(value) for value in values)
        if any(not 0 <= value <= 0.5 for value in pair):
            raise ValueError(f"{name} errors must be between 0 and 0.5")
        budget[name] = pair
    local = float(config.get("local_gate_error", 0.0001))
    readout = float(config.get("readout_error", 0.005))
    if not 0 <= local <= 0.5 or not 0 <= readout <= 1:
        raise ValueError("Invalid local-gate or final-readout error")
    if config["model"] == "Noiseless":
        return 1.0, None, 1.0, 1.0
    return bell, budget, 1 - local, 1 - readout

