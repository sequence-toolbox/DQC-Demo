"""Behavior checks for the demo and its real simulation boundary."""
import time
import unittest
import subprocess
import sys
import textwrap
import os
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from demo import jobs
from demo.simulation import simulate

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def radio(app, label):
    return next(widget for widget in app.radio if widget.label == label)


class AppTests(unittest.TestCase):
    def test_star_has_centered_hub_and_spokes(self):
        from demo.charts import network
        figure = network("Star", 4)
        self.assertEqual(len(figure.data) - 1, 3)
        nodes = figure.data[-1]
        self.assertEqual((nodes.x[0], nodes.y[0]), (0., 0.))
        self.assertIn("hub", nodes.text[0])
        for edge in figure.data[:-1]:
            self.assertEqual((edge.x[0], edge.y[0]), (0., 0.))
        self.assertEqual(len(network("Star", 2).data[-1].x), 2)

    def test_paper_topology_preset(self):
        app = AppTest.from_file(APP, default_timeout=20).run()
        radio(app, "Explore").set_value("Networks & compilers").run()
        radio(app, "Experience").set_value("Live simulation").run()
        next(w for w in app.checkbox if w.label == "Use paper topology setup").check().run()
        self.assertFalse(app.exception)
        self.assertEqual(next(w for w in app.selectbox if w.label == "Search qubits").value, 6)
        self.assertEqual(next(w for w in app.selectbox if w.label == "Quantum nodes").value, 10)
        self.assertEqual(next(w for w in app.selectbox if w.label == "Compiler").value, "FGP · default")
        self.assertEqual(next(w for w in app.slider if w.label == "Simulation shots").value, 1000)

    def test_ten_node_graphs_match_engine(self):
        from demo.simulation import connect_sources
        connect_sources()
        from demo.topologies import topology_graph
        from sequence.dqc.architecture import make_star, make_grid, make_caveman
        import networkx as nx
        for kind, arch in (("Star", make_star(10, 1)), ("Grid", make_grid(2, 5, 1)), ("Caveman", make_caveman(2, 5, 1))):
            graph = topology_graph(kind, 10)
            self.assertTrue(nx.is_connected(graph))
            self.assertEqual(graph.number_of_nodes(), 10)
            actual = {frozenset((arch.node_names[a], arch.node_names[b])) for a, b in graph.edges()}
            self.assertEqual(actual, {frozenset(edge) for edge in arch.edges})
            if kind == "Caveman":
                self.assertEqual(graph.number_of_edges(), 21)
                self.assertEqual(graph.subgraph(range(5)).number_of_edges(), 10)
                self.assertEqual(graph.subgraph(range(5, 10)).number_of_edges(), 10)
                self.assertEqual([(a, b) for a, b in graph.edges() if (a < 5) != (b < 5)], [(4, 5)])

    def test_noiseless_hides_and_zeroes_errors(self):
        app = AppTest.from_file(APP, default_timeout=20).run()
        next(w for w in app.selectbox if w.label == "Noise model").set_value("Noiseless").run()
        self.assertFalse(app.exception)
        self.assertFalse(any(w.label == "Bell-pair fidelity" for w in app.slider))
        self.assertFalse(any(w.label == "A error (%)" for w in app.number_input))
        self.assertEqual(len(app.dataframe), 0)
        self.assertFalse(any(w.label.startswith("Local H/X") or w.label.startswith("Final readout") for w in app.number_input))
        with patch("demo.jobs.start", return_value={"config": {}}) as start, patch("demo.jobs.poll", return_value=("running", {"value": 0, "message": "Testing submission"})):
            next(b for b in app.button if b.label == "Run distributed Grover").click().run()
        config = start.call_args.args[0]
        self.assertEqual(config["bell"], 1.0)
        self.assertTrue(all(pair == [0., 0.] for pair in config["budget"].values()))
        self.assertEqual((config["local_gate_error"], config["readout_error"]), (0., 0.))
        from demo.grover.error_budget import resolve_noise
        self.assertEqual(resolve_noise(config), (1., None, 1., 1.))

    def test_navigation_and_saved_comparisons(self):
        app = AppTest.from_file(APP, default_timeout=20).run()
        self.assertFalse(app.exception)
        self.assertEqual([m.value for m in app.metric], ["100.0%", "72.9%"])
        self.assertEqual(next(w for w in app.selectbox if w.label == "Noise model").options, ["Detailed", "Noiseless"])
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
        self.assertEqual(next(w for w in app.selectbox if w.label == "Search qubits").options, ["3", "4", "5", "6"])
        self.assertEqual(next(w for w in app.selectbox if w.label == "Network topology").options, ["Star", "Grid", "Caveman"])
        next(w for w in app.selectbox if w.label == "Quantum nodes").set_value(4).run()
        self.assertTrue(any("SELECTED NETWORK · Star · 4 nodes" in w.value for w in app.caption))
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
        recorded = next(frame.value for frame in app.dataframe if "Bell fidelity" in frame.value.columns).iloc[0]
        self.assertEqual(recorded["Bell fidelity"], 1.)
        self.assertTrue(all(recorded[name] == 0 for name in recorded.index if name.endswith("(%)") and name != "Success (%)"))


class SimulationTests(unittest.TestCase):
    def test_engine_source_selection(self):
        from demo.simulation import connect_sources
        with TemporaryDirectory() as directory:
            checkout = Path(directory) / "checkout"
            (checkout / "sequence" / "dqc").mkdir(parents=True)
            package = SimpleNamespace(__file__=str(checkout / "sequence" / "__init__.py"))
            with patch.dict(os.environ, {"SEQUENCE_DQC_ROOT": str(checkout)}), patch.object(sys, "path", list(sys.path)):
                with patch("demo.simulation.import_module", return_value=package):
                    paths = connect_sources()
                self.assertEqual(paths["engine_source"], "local checkout")
                self.assertEqual(sys.path[0], str(checkout.resolve()))
            installed = SimpleNamespace(__file__=str(Path(directory) / "site-packages" / "sequence" / "__init__.py"))
            with patch.dict(os.environ, {"SEQUENCE_DQC_ROOT": str(Path(directory) / "absent")}):
                with patch("demo.simulation.import_module", return_value=installed):
                    paths = connect_sources()
                self.assertEqual(paths["engine_source"], "installed package")
                with patch("demo.simulation.import_module", side_effect=ModuleNotFoundError("No sequence", name="sequence")):
                    with self.assertRaisesRegex(RuntimeError, "Install requirements.txt"):
                        connect_sources()

    def test_table_budget_controls_reach_simulation(self):
        from demo.simulation import connect_sources
        connect_sources()
        app = AppTest.from_file(APP, default_timeout=20).run()
        app.session_state["nature_error_table"] = {"edited_rows": {0: {"Alice (A)": 1.5}, 1: {"Bob (B)": .25}}, "added_rows": [], "deleted_rows": []}
        next(w for w in app.number_input if w.label.startswith("Local H/X")).set_value(0.02)
        next(w for w in app.number_input if w.label.startswith("Final readout")).set_value(1.0)
        with patch("demo.jobs.start", return_value={"config": {}}) as start, patch("demo.jobs.poll", return_value=("running", {"value": 0, "message": "Testing submission"})):
            next(b for b in app.button if b.label == "Run distributed Grover").click().run()
        self.assertFalse(app.exception)
        config = {**start.call_args.args[0], "shots": 1}
        with patch("demo.grover.nature_pipeline.run_single", return_value=True) as shot:
            result = simulate(config, lambda *args: None)
        self.assertEqual(shot.call_count, 4)
        actual = shot.call_args.kwargs
        self.assertAlmostEqual(actual["budget"]["mixed_species"][0], .015)
        self.assertAlmostEqual(actual["budget"]["qc_decoherence"][1], .0025)
        self.assertAlmostEqual(actual["budget"]["midcircuit_meas"][0], .00091)
        self.assertAlmostEqual(actual["local_1q_fid"], .9998)
        self.assertAlmostEqual(actual["readout_fid"], .99)
        self.assertEqual(result["effective_noise"]["budget"], actual["budget"])
        from demo.grover.history import history_row
        recorded = history_row(result, 1)
        self.assertEqual(recorded["Mixed-species gate · Alice (%)"], 1.5)
        self.assertEqual(recorded["QC decoherence (Z dephasing) · Bob (%)"], .25)
        self.assertEqual(recorded["Local H/X error (%)"], .02)
        self.assertEqual(recorded["Final readout error (%)"], 1.)
        self.assertEqual(recorded["Raw entanglement error (%)"], 3.11)
        with self.assertRaises(ValueError):
            simulate({**config, "budget": {"mixed_species": [-.1, 0]}}, lambda *args: None)

    def test_runs_without_experiment_package(self):
        code = textwrap.dedent('''
            import sys
            import importlib.abc

            class BlockExperiments(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname == "dqc_experiments" or fullname.startswith("dqc_experiments."):
                        raise ImportError("Experiment package is unavailable in this test")

            sys.meta_path.insert(0, BlockExperiments())
            from demo.simulation import simulate
            from demo.grover.error_budget import ERROR_LABELS
            for model in ("Noiseless", "Detailed"):
                result = simulate(dict(scenario="nature", model=model, bell=.9689, shots=1, seed=1), lambda *args: None)
                assert result["total_shots"] == 4
                assert "experiments" not in result["source_paths"]
                if model == "Noiseless":
                    assert result["success"] == 1.
            result = simulate(dict(scenario="nature", model="Detailed", bell=1., shots=1, seed=1,
                                   budget={name: [0., 0.] for name in ERROR_LABELS},
                                   local_gate_error=0., readout_error=0.), lambda *args: None)
            assert result["success"] == 1.
            result = simulate(dict(scenario="exploration", qubits=3, modules=2, shots=1, topology="Star",
                                   compiler="QAP", link_km=.01, efficiency=.9, noise=True, z=.25, seed=1), lambda *args: None)
            assert result["total_qubits"] == 4
            assert result["shots"][0]["reached"] >= result["shots"][0]["steps"]
            assert not any(name == "dqc_experiments" or name.startswith("dqc_experiments.") for name in sys.modules)
        ''')
        result = subprocess.run([sys.executable, "-c", code], cwd=Path(APP).parent, capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_real_noiseless_worker_and_cancel(self):
        config = {"scenario": "nature", "model": "Noiseless", "bell": 1., "shots": 1, "seed": 1}
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
