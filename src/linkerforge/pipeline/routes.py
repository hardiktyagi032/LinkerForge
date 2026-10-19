"""Explicit one-chain routes through two domains, including multiple tethers.

Splitting a domain is an engineering operation, not evidence of tolerance.
Routes preserve each supplied domain sequence once, in its original order.
"""
from dataclasses import dataclass

from linkerforge.attachment.plans import AttachmentPlan
from linkerforge.generation.contracts import sequence, strict_dataclass


def segments(plan):
    if isinstance(plan, ContactRoute):
        return plan.segments
    if plan.topology == "tandem":
        return (("a", 1, len(plan.sequence_a)), ("b", 1, len(plan.sequence_b)))
    return (("a", 1, plan.insertion_after), ("b", 1, len(plan.sequence_b)),
            ("a", plan.insertion_after + 1, len(plan.sequence_a)))


def junctions(plan):
    route = segments(plan)
    kinds = plan.linker_types if isinstance(plan, ContactRoute) else (plan.linker_type,) * len(plan.linker_lengths)
    return [{"index": i, "left_domain": left[0], "left_position": left[2],
             "right_domain": right[0], "right_position": right[1],
             "left_context": getattr(plan, "sequence_" + left[0])[left[1]-1:left[2]],
             "right_context": getattr(plan, "sequence_" + right[0])[right[1]-1:right[2]],
             "linker_type": kind, "length": length}
            for i, (left, right, kind, length) in enumerate(zip(route, route[1:], kinds, plan.linker_lengths))]


@dataclass(frozen=True)
class ContactRoute:
    plan_id: str
    domain_a_id: str
    domain_b_id: str
    sequence_a: str
    sequence_b: str
    segments: tuple[tuple[str, int, int], ...]
    linker_lengths: tuple[int, ...]
    linker_types: tuple[str, ...]
    topology: str = "explicit_route"

    def __post_init__(self):
        sequence(self.sequence_a, "sequence_a")
        sequence(self.sequence_b, "sequence_b")
        if (any(not isinstance(x, str) or not x.strip() for x in (self.plan_id, self.domain_a_id, self.domain_b_id))
                or self.domain_a_id == self.domain_b_id or self.topology != "explicit_route"):
            raise ValueError("Distinct domain IDs and an explicit route are required")
        if not isinstance(self.segments, (list, tuple)) or not 2 <= len(self.segments) <= 16:
            raise ValueError("A bounded route requires 2..16 segments (software ceiling, not biology)")
        if not isinstance(self.linker_lengths, (list, tuple)) or not isinstance(self.linker_types, (list, tuple)):
            raise ValueError("Explicit linker lengths/types required")
        if len(self.linker_lengths) != len(self.segments)-1 or len(self.linker_types) != len(self.linker_lengths):
            raise ValueError("Every route edge needs exactly one length and type")
        if any(type(n) is not int or n < 0 for n in self.linker_lengths) or any(k not in {"flexible", "helical"} for k in self.linker_types):
            raise ValueError("Peptide edges need nonnegative integer lengths and flexible/helical geometry types")
        next_position, last_domain = {"a": 1, "b": 1}, None
        clean = []
        for item in self.segments:
            if not isinstance(item, (list, tuple)) or len(item) != 3:
                raise ValueError("Segments are [domain, first_residue, last_residue]")
            domain, start, end = item
            if (domain not in next_position or domain == last_domain or type(start) is not int or type(end) is not int
                    or start != next_position[domain] or not start <= end <= len(getattr(self, "sequence_" + domain))):
                raise ValueError("Alternating segments must cover each domain once, without omitted/reordered/repeated residues")
            clean.append((domain, start, end))
            next_position[domain], last_domain = end + 1, domain
        if any(next_position[d] != len(getattr(self, "sequence_" + d)) + 1 for d in next_position):
            raise ValueError("Route must preserve both complete domain sequences")
        object.__setattr__(self, "segments", tuple(clean))
        object.__setattr__(self, "linker_lengths", tuple(self.linker_lengths))
        object.__setattr__(self, "linker_types", tuple(self.linker_types))

    def contacts(self):
        return [(j["left_position"], j["right_position"], j["linker_type"], j["length"])
                if j["left_domain"] == "a" else
                (j["right_position"], j["left_position"], j["linker_type"], j["length"])
                for j in junctions(self)]

    def required_scores(self):
        operations = set()
        for j in junctions(self):
            for domain, position, side in ((j["left_domain"], j["left_position"], "left"),
                                            (j["right_domain"], j["right_position"], "right")):
                seq, identity = getattr(self, "sequence_" + domain), getattr(self, "domain_" + domain + "_id")
                if side == "left" and position == len(seq):
                    task, anchor = "c_terminal_extension", position
                elif side == "right" and position == 1:
                    task, anchor = "n_terminal_extension", position
                else:
                    task, anchor = "internal_insertion", position if side == "left" else position-1
                operations.add((identity, task, anchor))
        return sorted(operations)


def parse_plan(value):
    return strict_dataclass(ContactRoute, value) if value.get("topology") == "explicit_route" else AttachmentPlan.from_dict(value)


def assemble(plan, linkers):
    """Return full sequence and exact source mapping; do not model closure."""
    if len(linkers) != len(plan.linker_lengths):
        raise ValueError("One linker per connection required")
    for value, length in zip(linkers, plan.linker_lengths):
        if length:
            sequence(value, "linker")
        if not isinstance(value, str) or len(value) != length:
            raise ValueError("A zero-length connection uses the empty string, never a generated residue")
    pieces, mapping, cursor = [], [], 1
    for index, (domain, start, end) in enumerate(segments(plan)):
        part = getattr(plan, "sequence_" + domain)[start-1:end]
        pieces.append(part)
        mapping.append({"kind": "domain", "domain_id": getattr(plan, "domain_" + domain + "_id"),
                        "source_start": start, "source_end": end, "fusion_start": cursor, "fusion_end": cursor+len(part)-1})
        cursor += len(part)
        if index < len(linkers):
            linker = linkers[index]
            pieces.append(linker)
            mapping.append({"kind": "linker", "junction": index, "length": len(linker),
                            "fusion_start": cursor if linker else None, "fusion_end": cursor+len(linker)-1 if linker else None})
            cursor += len(linker)
    return {"sequence": "".join(pieces), "residue_mapping": mapping,
            "domain_sequences_preserved": True, "chain_closure_assessed": False}
