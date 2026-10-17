"""Residue-exact FIM serialization; no IDs, scores or target leakage in prompts."""
import torch

from .contracts import AMINO_ACIDS, DesignRequest, GeneratorConfig


class FIMTokenizer:
    def __init__(self, max_linker_length=128):
        self.max_linker_length = max_linker_length
        controls = ["<pad>", "<bos>", "<prefix>", "<suffix>", "<middle>", "<motif>", "<motif_at>",
                    "<rigid>", "<flexible>", "<unknown>", "<cleavable>", "<no_known_motif>"]
        self.tokens = list(AMINO_ACIDS) + controls + [f"<len_{i}>" for i in range(max_linker_length + 1)]
        self.ids = {token: i for i, token in enumerate(self.tokens)}
        self.pad_id = self.ids["<pad>"]

    def amino_ids(self, seq):
        return [self.ids[x] for x in seq]

    def prompt(self, request: DesignRequest, config: GeneratorConfig):
        if request.length > self.max_linker_length:
            raise ValueError("Requested length exceeds this model's configured vocabulary")
        controls = [self.ids[f"<{request.rigidity}>"], self.ids[f"<{request.cleavage}>"],
                    self.ids[f"<len_{request.length}>"]]
        if request.motif:
            controls += [self.ids["<motif>"], *self.amino_ids(request.motif),
                         self.ids["<motif_at>"], self.ids[f"<len_{request.motif_start}>"]]
        overhead = 4 + len(controls)
        # Reserve space for the entire linker before cropping context, including
        # at inference. Both sides retain at least one attachment-adjacent residue.
        budget = config.max_positions - request.length - overhead
        if budget < 2:
            raise ValueError("Context window cannot hold controls, target and both attachment flanks")
        left = min(len(request.domain_a), config.flank_residues, budget // 2)
        right = min(len(request.domain_b), config.flank_residues, budget - left)
        left = min(len(request.domain_a), config.flank_residues, budget - right)
        return [self.ids["<bos>"], self.ids["<prefix>"], *self.amino_ids(request.domain_a[-left:]),
                self.ids["<suffix>"], *self.amino_ids(request.domain_b[:right]),
                *controls, self.ids["<middle>"]]

    def batch(self, examples, config, device="cpu"):
        if not examples:
            raise ValueError("Cannot collate an empty batch")
        sequences, labels = [], []
        for example in examples:
            prefix = self.prompt(example.request, config)
            values = prefix + self.amino_ids(example.linker)
            target = [-100] * len(prefix) + self.amino_ids(example.linker)
            # Motif identity and length are supplied constraints, not learned
            # biological targets or evidence of successful generation.
            for position in example.request.locked_positions():
                target[len(prefix) + position] = -100
            if not any(value != -100 for value in target):
                raise ValueError("Example has no learnable linker positions")
            sequences.append(values)
            labels.append(target)
        width = max(map(len, sequences))
        ids = torch.full((len(examples), width), self.pad_id, dtype=torch.long, device=device)
        mask = torch.zeros_like(ids, dtype=torch.bool)
        targets = torch.full_like(ids, -100)
        for i, (values, target) in enumerate(zip(sequences, labels)):
            ids[i, :len(values)] = torch.tensor(values, device=device)
            mask[i, :len(values)] = True
            targets[i, :len(values)] = torch.tensor(target, device=device)
        return {"input_ids": ids, "attention_mask": mask, "labels": targets}
