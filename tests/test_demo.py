"""Behavior checks for the demo and its real simulation boundary."""
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from demo import jobs
from demo.simulation import simulate

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def radio(app, label):
    return next(widget for widget in app.radio if widget.label == label)


class AppTests(unittest.TestCase):
    def test_navigation_and_saved_comparisons(self):
        app = AppTest.from_file(APP, default_timeout=20).run()
        self.assertFalse(app.exception)
        self.assertEqual([m.value for m in app.metric], ["100.0%", "72.2%", "73.8%"])
        radio(app, "Results").set_value("Live runs").run()
        self.assertFalse(app.exception)
        self.assertTrue(app.info)
        radio(app, "Explore").set_value("Networks & compilers").run()
        self.assertFalse(app.exception)
        radio(app, "Hold the workload fixed and compare").set_value("Compilers").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe[0].value), 8)
        app.multiselect[0].set_value([]).run()
        self.assertFalse(app.exception)
        radio(app, "Experience").set_value("Live simulation").run()
        self.assertFalse(app.exception)
        self.assertTrue(any(b.label == "Compile and simulate" for b in app.button))
        self.assertEqual(next(w for w in app.selectbox if w.label == "Network topology").options, ["Star", "Grid", "Caveman"])
        fiber = next(w for w in app.slider if w.label == "Fiber length parameter (km)")
        self.assertEqual((fiber.proto.min, fiber.proto.max), (0.01, 20.0))
        fiber.set_value(20.0)
        next(w for w in app.slider if w.label == "Simulation shots").set_value(1000)
        quality = next(w for w in app.select_slider if w.label == "Hardware quality (z)")
        self.assertEqual(quality.options, ["0.00", "0.25", "0.50", "0.65", "0.80", "0.90", "0.95", "1.00"])
        quality.set_value(0.25)
        with patch("demo.jobs.start", return_value={"config": {}}) as start, patch("demo.jobs.poll", return_value=("running", {"value": 0, "message": "Testing submission"})):
            next(b for b in app.button if b.label == "Compile and simulate").click().run()
        submitted = start.call_args.args[0]
        self.assertEqual((submitted["link_km"], submitted["shots"], submitted["z"]), (20.0, 1000, 0.25))
        self.assertFalse(app.exception)

    def test_live_history_renders(self):
        app = AppTest.from_file(APP, default_timeout=20)
        app.session_state["nature_history"] = [{"model": "Noiseless", "total_shots": 4, "success": 1.,
                                               "wall_seconds": 1., "config": {"model": "Noiseless"},
                                               "rows": [{"state": f"{s:02b}", "success": 1., "hits": 1, "shots": 1} for s in range(4)]}]
        app.run()
        radio(app, "Results").set_value("Live runs").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, "100.0%")


class SimulationTests(unittest.TestCase):
    def test_real_noiseless_worker_and_cancel(self):
        config = {"scenario": "nature", "model": "Noiseless", "bell": 1., "cz": 1., "shots": 1, "seed": 1}
        job = jobs.start(config)
        try:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                status, result = jobs.poll(job)
                if status != "running":
                    break
                time.sleep(0.1)
            self.assertEqual(status, "complete", result)
            self.assertEqual(result["success"], 1.)
            self.assertEqual(len(result["rows"]), 4)
            self.assertEqual(result["total_shots"], 4)
        finally:
            jobs.stop(job)
        job = jobs.start({**config, "shots": 2000})
        jobs.stop(job)
        self.assertIsNotNone(job["process"].poll())

    def test_real_network_and_compiler(self):
        config = {"scenario": "exploration", "qubits": 3, "modules": 4, "shots": 1, "topology": "Caveman",
                  "compiler": "FGP · default", "link_km": .01, "efficiency": .9, "noise": True, "z": .25, "seed": 1}
        result = simulate(config, lambda *args: None)
        self.assertEqual(result["total_qubits"], 4)
        self.assertEqual(result["capacity"], 1)
        self.assertGreater(result["gates"], 0)
        self.assertGreater(result["sim_ms"], 0)
        self.assertGreaterEqual(result["shots"][0]["reached"], result["shots"][0]["steps"])


if __name__ == "__main__":
    unittest.main()
