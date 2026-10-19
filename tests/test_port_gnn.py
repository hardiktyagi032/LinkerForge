"""Contract tests for the experimental geometry ranker."""

import math
import unittest

from linkerforge.models.port_gnn import PortGraph, PortGNNRanker, pairwise_loss, tensorize_port, torch


class PortGNNContractTests(unittest.TestCase):
    def setUp(self):
        self.graph = PortGraph(
            sequence="ACDEFGHIKL",
            coordinates=tuple((float(i), float(i % 3), 0.0) for i in range(10)),
            port_index=9,
        )

    def test_reject_invalid_graph(self):
        with self.assertRaises(ValueError):
            PortGraph("AC", ((0.0, 0.0, 0.0),), 1)

    @unittest.skipIf(torch is None, "PyTorch not installed in this Python environment")
    def test_rigid_transform_invariance(self):
        torch.manual_seed(7)
        model = PortGNNRanker(hidden=16).eval()
        transformed = PortGraph(
            self.graph.sequence,
            tuple((-y + 31.0, x - 17.0, z + 5.0) for x, y, z in self.graph.coordinates),
            self.graph.port_index,
        )
        with torch.no_grad():
            first = model(self.graph, self.graph, "GGGGSGGGGS")
            second = model(transformed, self.graph, "GGGGSGGGGS")
        self.assertTrue(math.isclose(first.item(), second.item(), abs_tol=1e-5))

    @unittest.skipIf(torch is None, "PyTorch not installed in this Python environment")
    def test_trainable_pairwise_score(self):
        model = PortGNNRanker(hidden=16)
        loss = pairwise_loss(model, self.graph, self.graph, "GGGGSGGGGS", "AAAAASSSSS")
        self.assertTrue(torch.isfinite(loss).item())
        loss.backward()
        self.assertTrue(any(p.grad is not None for p in model.parameters()))

    @unittest.skipIf(torch is None, "PyTorch not installed in this Python environment")
    def test_port_included_at_node_limit(self):
        features, coordinates = tensorize_port(self.graph, max_nodes=1)
        self.assertEqual(features.shape, (1, 21))
        self.assertEqual(coordinates.shape, (1, 3))
        self.assertEqual(features[0, 20].item(), 1.0)


if __name__ == "__main__":
    unittest.main()
