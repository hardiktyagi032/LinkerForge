import torch

from linkerforge.models.sam_linker_variants import SAMLinkerVariant, VARIANTS


def test_variants_mask_and_gradient():
    for variant in VARIANTS:
        model = SAMLinkerVariant(12, variant)
        embeddings = torch.randn(2, 9, 12)
        valid = torch.tensor([[True] * 9, [True] * 6 + [False] * 3])
        concept = torch.zeros(2, dtype=torch.long)
        output = model(embeddings, valid, concept)
        assert output["semantic_logits"].shape == (2, 9)
        assert (output["semantic_logits"][1, 6:] == -1e4).all()
        output["semantic_logits"][valid].sum().backward()
        if model.use_boundary:
            assert model.boundary_refiner[0].weight.grad is not None
        if model.use_multiscale:
            assert model.scale_fusion.weight.grad is not None
        if model.use_query:
            # Query pathway is trained by the existing query/boundary losses.
            assert model.query_attention.query_key.weight.requires_grad
