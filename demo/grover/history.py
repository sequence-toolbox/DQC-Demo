"""Applied error settings recorded for completed Grover runs."""
from demo.grover.error_budget import ERROR_LABELS, resolve_noise


def history_row(result, run_number):
    """Flatten the applied noise parameters for the run-history table."""
    config = {"bell": 0.9689, "model": result["model"], **result.get("config", {})}
    effective = result.get("effective_noise")
    if effective is None:
        bell, budget, local, readout = resolve_noise(config)
    else:
        bell, budget = effective["bell_fidelity"], effective["budget"]
        local, readout = effective["local_1q_fidelity"], effective["readout_fidelity"]
    row = {"Run": run_number, "Model": result["model"], "Bell fidelity": bell,
           "Raw entanglement error (%)": round(100 * (1 - bell), 6)}
    for name, label in ERROR_LABELS.items():
        a, b = budget[name] if budget is not None else (0.0, 0.0)
        row[f"{label} · Alice (%)"] = round(100 * a, 6)
        row[f"{label} · Bob (%)"] = round(100 * b, 6)
    row.update({"Local H/X error (%)": round(100 * (1 - local), 6),
                "Final readout error (%)": round(100 * (1 - readout), 6),
                "Seed": config.get("seed"), "Shots": result["total_shots"],
                "Success (%)": round(result["success"] * 100, 1)})
    return row
