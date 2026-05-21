import unittest

from experiments.synthetic_memory_graph import (
    attr_like,
    bfs_cooccurrence,
    dependency_closure,
    evaluate_world,
    generate_world,
    run_sweep,
    score_prediction,
)


class SyntheticMemoryGraphTests(unittest.TestCase):
    def test_generator_is_deterministic(self):
        first = generate_world(seed=7, noise_edges=12, hub_facts=3)
        second = generate_world(seed=7, noise_edges=12, hub_facts=3)

        self.assertEqual(first.facts, second.facts)
        self.assertEqual(first.dependency_edges, second.dependency_edges)
        self.assertEqual(first.cooccurrence_edges, second.cooccurrence_edges)
        self.assertEqual(first.triggers, second.triggers)

    def test_dependency_closure_follows_chain(self):
        world = generate_world(n_chains=1, chain_length=5, noise_edges=0, seed=1)

        closure = dependency_closure(world, trigger=0, depth=2)

        self.assertEqual(closure, {1, 2})

    def test_oracle_dependency_scores_perfectly(self):
        world = generate_world(noise_edges=50, hub_facts=10, seed=2)

        result = evaluate_world(world, depth=2)
        oracle = result["aggregate"]["oracle_dependency"]

        self.assertEqual(oracle["precision"], 1.0)
        self.assertEqual(oracle["recall"], 1.0)
        self.assertEqual(oracle["false_positive"], 0.0)
        self.assertEqual(oracle["false_negative"], 0.0)

    def test_noise_increases_bfs_false_positives(self):
        clean = evaluate_world(generate_world(noise_edges=0, hub_facts=0, seed=3))
        noisy = evaluate_world(generate_world(noise_edges=120, hub_facts=0, seed=3))

        clean_fp = clean["aggregate"]["bfs_cooccurrence"]["false_positive"]
        noisy_fp = noisy["aggregate"]["bfs_cooccurrence"]["false_positive"]

        self.assertGreater(noisy_fp, clean_fp)

    def test_hub_heavy_increases_blast_radius(self):
        noisy = evaluate_world(generate_world(noise_edges=120, hub_facts=0, seed=4))
        hub = evaluate_world(generate_world(noise_edges=120, hub_facts=20, seed=4))

        noisy_blast = noisy["aggregate"]["bfs_cooccurrence"]["blast_radius"]
        hub_blast = hub["aggregate"]["bfs_cooccurrence"]["blast_radius"]

        self.assertGreater(hub_blast, noisy_blast)

    def test_attr_like_reduces_false_positives_but_can_miss_dependencies(self):
        world = generate_world(noise_edges=120, hub_facts=20, seed=5)
        result = evaluate_world(world, depth=2)

        bfs = result["aggregate"]["bfs_cooccurrence"]
        attr = result["aggregate"]["attr_like"]

        self.assertLess(attr["false_positive"], bfs["false_positive"])
        self.assertGreaterEqual(attr["false_negative"], 0.0)

    def test_score_prediction_counts_error_types(self):
        score = score_prediction(
            predicted={1, 2, 3},
            truth={2, 3, 4},
            universe_size=10,
        )

        self.assertEqual(score["true_positive"], 2)
        self.assertEqual(score["false_positive"], 1)
        self.assertEqual(score["false_negative"], 1)
        self.assertAlmostEqual(score["precision"], 2 / 3)
        self.assertAlmostEqual(score["recall"], 2 / 3)

    def test_sweep_aggregates_grid(self):
        result = run_sweep(
            sizes=[30],
            noise_multipliers=[0.0, 2.0],
            hub_multipliers=[0.0],
            seeds=[0, 1],
        )

        self.assertEqual(len(result["rows"]), 4)
        self.assertEqual(len(result["summary"]), 2)

    def test_sweep_noise_increases_bfs_fp_in_summary(self):
        result = run_sweep(
            sizes=[30],
            noise_multipliers=[0.0, 2.0],
            hub_multipliers=[0.0],
            seeds=list(range(5)),
        )
        by_noise = {
            row["noise_multiplier"]: row["algorithms"]["bfs_cooccurrence"]
            for row in result["summary"]
        }

        self.assertGreater(
            by_noise[2.0]["false_positive"],
            by_noise[0.0]["false_positive"],
        )


if __name__ == "__main__":
    unittest.main()
