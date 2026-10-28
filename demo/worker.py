"""Run each experiment outside Streamlit to isolate simulator globals and allow cancellation."""
import json
import os
from pathlib import Path
import sys
import threading
import traceback

from demo.simulation import simulate
from demo.jobs import TIMEOUT


def write_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)


if __name__ == "__main__":
    directory = Path(sys.argv[1])
    config = json.loads((directory / "config.json").read_text())

    def timeout():
        write_json(directory / "error.json", {"message": "Run exceeded 10 minutes. Try fewer shots or a smaller circuit."})
        os._exit(124)

    timer = threading.Timer(TIMEOUT, timeout)
    timer.daemon = True
    timer.start()
    try:
        result = simulate(config, lambda value, message: write_json(directory / "progress.json", {"value": value, "message": message}))
        write_json(directory / "result.json", result)
    except Exception as error:
        write_json(directory / "error.json", {"message": str(error), "details": traceback.format_exc()})
        sys.exit(1)
    finally:
        timer.cancel()
