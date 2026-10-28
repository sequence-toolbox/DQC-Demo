"""Local subprocess lifecycle; files also preserve downloadable run records."""
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT = 600


def start(config):
    directory = ROOT / "runs" / uuid.uuid4().hex
    directory.mkdir(parents=True)
    (directory / "config.json").write_text(json.dumps(config, indent=2))
    with (directory / "worker.log").open("w") as log:
        process = subprocess.Popen([sys.executable, "-m", "demo.worker", str(directory)], cwd=ROOT, stdout=log, stderr=log)
    return {"process": process, "directory": directory, "started": time.monotonic(), "config": config}


def stop(job):
    process = job["process"]
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def poll(job):
    directory = job["directory"]
    for filename, status in (("result.json", "complete"), ("error.json", "error")):
        if (directory / filename).exists():
            job["process"].wait(timeout=3)
            return status, json.loads((directory / filename).read_text())
    if time.monotonic() - job["started"] > TIMEOUT:
        stop(job)
        return "error", {"message": "Run exceeded 10 minutes. Try fewer shots or a smaller circuit."}
    if job["process"].poll() is not None:
        return "error", {"message": "Simulation worker stopped unexpectedly. See worker.log in the run folder."}
    path = directory / "progress.json"
    return "running", json.loads(path.read_text()) if path.exists() else {"value": 0, "message": "Building the quantum network…"}
