"""Explicit attachment/topology plans delegated to the existing geometry engine."""
from dataclasses import dataclass
import math

from linkerforge.generation.contracts import canonical_hash, sequence, strict_dataclass
from linkerforge.geometry.junction import evaluate_tether_set
from .data import sequence_sha256

RESIDUE_CODES = dict(zip("ALA CYS ASP GLU PHE GLY HIS ILE LYS LEU MET ASN PRO GLN ARG SER THR VAL TRP TYR".split(), "ACDEFGHIKLMNPQRSTVWY"))


@dataclass(frozen=True)
class AttachmentPlan:
    plan_id: str
    domain_a_id: str
    domain_b_id: str
    sequence_a: str
    sequence_b: str
    topology: str = "tandem"
    insertion_after: int | None = None
    linker_lengths: tuple[int, ...] = (15,)
    linker_type: str = "flexible"

    def __post_init__(self):
        sequence(self.sequence_a, "sequence_a")
        sequence(self.sequence_b, "sequence_b")
        if not self.plan_id or not self.domain_a_id or not self.domain_b_id or self.domain_a_id == self.domain_b_id:
            raise ValueError("Plan and distinct domain identities required")
        if self.topology not in {"tandem", "insertion"} or self.linker_type not in {"flexible", "helical"}:
            raise ValueError("Only explicit one-chain tandem or one-donor insertion plans are implemented")
        object.__setattr__(self, "linker_lengths", tuple(self.linker_lengths))
        if any(type(n) is not int or n < 0 for n in self.linker_lengths):
            raise ValueError("Linker lengths are explicit nonnegative residue counts")
        if self.topology == "tandem" and (len(self.linker_lengths) != 1 or self.insertion_after is not None):
            raise ValueError("Tandem has one connection and no internal cut")
        if self.topology == "insertion" and (len(self.linker_lengths) != 2 or type(self.insertion_after) is not int or not 1 <= self.insertion_after < len(self.sequence_a)):
            raise ValueError("Insertion has two connections flanking an explicit recipient bond")

    @classmethod
    def from_dict(cls, value):
        return strict_dataclass(cls, value)

    def contacts(self):
        if self.topology == "tandem":
            return [(len(self.sequence_a), 1, self.linker_type, self.linker_lengths[0])]
        return [(self.insertion_after, 1, self.linker_type, self.linker_lengths[0]),
                (self.insertion_after+1, len(self.sequence_b), self.linker_type, self.linker_lengths[1])]

    def required_scores(self):
        if self.topology == "tandem":
            return [(self.domain_a_id, "c_terminal_extension", len(self.sequence_a)),
                    (self.domain_b_id, "n_terminal_extension", 1)]
        return [(self.domain_a_id, "internal_insertion", self.insertion_after),
                (self.domain_b_id, "n_terminal_extension", 1),
                (self.domain_b_id, "c_terminal_extension", len(self.sequence_b))]


def evaluate_geometry(plan, chain_a, chain_b, mapping_a, mapping_b, restarts=2, iterations=20, seed=17):
    if type(restarts) is not int or type(iterations) is not int or not 1 <= restarts <= 8 or not 1 <= iterations <= 100:
        raise ValueError("Bounded geometry adapter ceiling: 8 restarts x 100 iterations")
    def validate_map(mapping, chain, seq):
        if not mapping or any(type(k) is not int or type(v) is not int for k, v in mapping.items()) or len(set(mapping.values())) != len(mapping):
            raise ValueError("Explicit one-to-one sequence-position to PDB-number mapping required")
        for position, number in mapping.items():
            if not 1 <= position <= len(seq) or RESIDUE_CODES.get(chain.residue(number).name) != seq[position-1]:
                raise ValueError("Sequence/PDB anchor mapping mismatch")
    validate_map(mapping_a, chain_a, plan.sequence_a)
    validate_map(mapping_b, chain_b, plan.sequence_b)
    tethers = tuple((mapping_a[a], mapping_b[b], kind, length) for a, b, kind, length in plan.contacts())
    report = evaluate_tether_set(chain_a, chain_b, tethers, restarts=restarts, iterations=iterations, seed=seed)
    return {"plan_id": plan.plan_id, "plan_sha256": canonical_hash(plan.__dict__), "geometry": report,
            "geometry_sha256": canonical_hash(report), "number_of_peptide_connections": len(tethers),
            "resource_ceiling": {"restarts": restarts, "iterations": iterations, "seed": seed}}


def rank_plans(plans, domain_scores, geometry_reports):
    if len({plan.plan_id for plan in plans}) != len(plans):
        raise ValueError("Duplicate plan identity")
    results = []
    for plan in plans:
        evidence = geometry_reports.get(plan.plan_id)
        if evidence and (evidence["plan_sha256"] != canonical_hash(plan.__dict__) or evidence["geometry_sha256"] != canonical_hash(evidence["geometry"])):
            raise ValueError("Plan/geometry identity mismatch")
        verdict = evidence["geometry"]["verdict"] if evidence else "not_assessed"
        assessed, missing = [], []
        for identity, task, position in plan.required_scores():
            score = domain_scores.get(identity)
            seq = plan.sequence_a if identity == plan.domain_a_id else plan.sequence_b
            if score and (score["sequence_sha256"] != sequence_sha256(seq) or score["length"] != len(seq)):
                raise ValueError("Domain-score sequence identity mismatch")
            item = score.get("tasks", {}).get(task, {}) if score else {}
            values = [site["logit"] for site in item.get("sites", []) if site["residue_position"] == position]
            if item.get("status") != "scored_uncalibrated" or len(values) != 1 or values[0] is None or not math.isfinite(values[0]):
                missing.append({"domain_id": identity, "task": task, "position": position})
            else:
                assessed.append(values[0])
        rejected = verdict in {"certified_infeasible", "spans_satisfiable_but_domains_clash"}
        results.append({"plan_id": plan.plan_id, "topology": plan.topology,
                        "number_of_peptide_connections": len(plan.linker_lengths), "linker_lengths": list(plan.linker_lengths),
                        "contacts_a_to_b": plan.contacts(), "geometry_verdict": verdict,
                        "status": "rejected_geometry" if rejected else ("unassessed_site_tasks" if missing else "sequence_rank_only"),
                        "mean_operation_logit": sum(assessed)/len(assessed) if assessed and not missing and not rejected else None,
                        "unassessed_tasks": missing, "generator_topology_supported": plan.topology == "tandem" and all(plan.linker_lengths),
                        "synthetic_software_fixture": any(domain_scores.get(x, {}).get("synthetic_software_fixture", False) for x in (plan.domain_a_id, plan.domain_b_id)),
                        "fusion_function_validated": False})
    results.sort(key=lambda row: (row["status"] == "rejected_geometry", row["mean_operation_logit"] is None,
                                  row["geometry_verdict"] != "feasible_with_witness",
                                  -(row["mean_operation_logit"] or 0), row["plan_id"]))
    return {"plans": results, "interpretation": "Heuristic mean of operation logits, not a joint probability or optimum tether-count prediction.",
            "limitations": ["An insertion needs two connections; it is not two independent tandem fusions.",
                            "Number of connections follows supplied topology; no optimal-count labels or count model exist.",
                            "Undetermined geometry remains unknown, and a witness establishes geometry only."]}
