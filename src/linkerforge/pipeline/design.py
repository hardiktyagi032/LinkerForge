"""Bounded site/geometry/template/FIM orchestration without structural jobs."""
from dataclasses import asdict, dataclass
from itertools import islice, product
import math

from linkerforge.attachment.plans import rank_plans
from linkerforge.generation.contracts import DesignRequest, canonical_hash
from linkerforge.generation.constraints import candidate_flags, generate
from linkerforge.generation.templates import template_candidates
from .routes import assemble, junctions, segments


@dataclass(frozen=True)
class DesignBudget:
    max_plans: int = 8
    candidates_per_junction: int = 2
    attempts_per_junction: int = 4
    assemblies_per_plan: int = 8
    seed: int = 17
    allow_junction_context_transfer: bool = False

    def __post_init__(self):
        for name, ceiling in (("max_plans", 64), ("candidates_per_junction", 16),
                              ("attempts_per_junction", 64), ("assemblies_per_plan", 64)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError(f"{name} must be 1..{ceiling}")
        if (self.candidates_per_junction > self.attempts_per_junction or type(self.seed) is not int
                or self.seed < 0 or type(self.allow_junction_context_transfer) is not bool):
            raise ValueError("Invalid sampling budget/seed/explicit transfer choice")


def local_request(junction, controls):
    allowed = {"rigidity", "cleavage", "motif", "motif_source", "motif_start", "cassette_flank",
               "allowed_amino_acids", "forbidden_motifs"}
    if set(controls) - allowed:
        raise ValueError("Junction controls cannot override anchor context, length or topology")
    values = {"rigidity": "flexible" if junction["linker_type"] == "flexible" else "rigid", **controls}
    expected = "flexible" if junction["linker_type"] == "flexible" else "rigid"
    if values["rigidity"] != expected:
        raise ValueError("Sequence design intent must match the supplied geometry type")
    return DesignRequest(junction["left_context"], junction["right_context"], junction["length"], **values)


def zero_length_flags(junction, controls):
    if not isinstance(controls, dict) or set(controls) - {"rigidity", "cleavage", "motif", "motif_source", "motif_start", "cassette_flank", "allowed_amino_acids", "forbidden_motifs"}:
        raise ValueError("Explicit junction control fields required")
    if controls.get("cleavage", "unknown") == "cleavable" or controls.get("motif"):
        return ["direct_fusion_cannot_contain_cleavage_cassette"]
    # The existing positive-length request validator is deliberately not bypassed.
    request = local_request({**junction, "length": 1}, controls)
    return [flag for flag in candidate_flags(request, "") if flag != "wrong_length"]


def assembly_flags(assembly, controls):
    failures = []
    domain_intervals = [(r["fusion_start"], r["fusion_end"]) for r in assembly["residue_mapping"] if r["kind"] == "domain"]
    for motif in {m for c in controls for m in c.get("forbidden_motifs", ())}:
        start = assembly["sequence"].find(motif)
        while start != -1:
            first, last = start+1, start+len(motif)
            if not any(a <= first and last <= b for a, b in domain_intervals):
                failures.append("known_forbidden_motif_in_assembled_junctions")
                break
            start = assembly["sequence"].find(motif, start+1)
    return sorted(set(failures))


def design(plans, domain_scores, geometry_reports, *, library=None, model=None,
           model_identity=None, controls=None, budget=DesignBudget()):
    if not 1 <= len(plans) <= 64:
        raise ValueError("Supply 1..64 explicit plans; no unbounded site-pair enumeration")
    controls = controls or {}
    if set(controls) - {p.plan_id for p in plans}:
        raise ValueError("Controls name an unknown plan")
    if model is not None and (not isinstance(model_identity, dict) or type(model_identity.get("synthetic_software_fixture")) is not bool
                              or not model_identity.get("model_metadata_sha256")):
        raise ValueError("Loaded generator needs checkpoint identity and explicit synthetic mode")
    ranked = rank_plans(plans, domain_scores, geometry_reports)
    by_id = {p.plan_id: p for p in plans}
    output = []
    for rank, summary in enumerate(ranked["plans"]):
        plan = by_id[summary["plan_id"]]
        record = {**summary, "plan_sha256": canonical_hash(plan.__dict__), "junction_proposals": [], "assemblies": []}
        if rank >= budget.max_plans or summary["status"] == "rejected_geometry":
            record["proposal_status"] = "not_selected_budget" if rank >= budget.max_plans else "rejected_geometry"
            output.append(record)
            continue
        per_junction = controls.get(plan.plan_id, [{} for _ in plan.linker_lengths])
        if not isinstance(per_junction, list) or len(per_junction) != len(plan.linker_lengths):
            raise ValueError("Supply exactly one control object per route connection")
        pools = []
        for edge, edge_controls in zip(junctions(plan), per_junction):
            if not isinstance(edge_controls, dict):
                raise ValueError("Junction controls must be objects")
            item = {k: v for k, v in edge.items() if k not in {"left_context", "right_context"}}
            item.update(methods={}, candidates=[])
            if not edge["length"]:
                flags = zero_length_flags(edge, edge_controls)
                item["methods"]["direct_fusion"] = {"attempts": [{"status": "rejected" if flags else "admissible_sequence_only", "reasons": flags}]}
                if not flags:
                    item["candidates"].append({"linker_sequence": "", "method": "direct_fusion", "source": None})
            else:
                request = local_request(edge, edge_controls)
                if library is not None:
                    result = template_candidates(library, request, budget.candidates_per_junction)
                    item["methods"]["source_library"] = result
                    item["candidates"] += [{**c, "method": "source_library"} for c in result["candidates"]]
                native_tandem = len(segments(plan)) == 2 and segments(plan)[0][0] == "a"
                if model is not None and (native_tandem or budget.allow_junction_context_transfer):
                    result = generate(model, request, budget.candidates_per_junction, budget.attempts_per_junction,
                                      budget.seed + rank*16 + edge["index"])
                    result["context_use"] = "original_tandem" if native_tandem else "explicit_unvalidated_fragment_context_transfer"
                    item["methods"]["infiller"] = result
                    item["candidates"] += [{**c, "method": "infiller"} for c in result["candidates"]]
                elif model is not None:
                    item["methods"]["infiller"] = {"status": "not_run_unreviewed_context_transfer", "attempts": []}
            # Keep evidence for identical sequences from different methods.
            unique = {}
            for candidate in item["candidates"]:
                seq = candidate["linker_sequence"]
                if seq not in unique:
                    unique[seq] = {"linker_sequence": seq, "methods": []}
                unique[seq]["methods"].append(candidate["method"])
            pools.append(list(unique.values()))
            record["junction_proposals"].append(item)
        record["possible_assembly_combinations"] = math.prod(map(len, pools))
        admitted = 0
        for combination in islice(product(*pools), budget.assemblies_per_plan):
            sequences = [c["linker_sequence"] for c in combination]
            assembly = assemble(plan, sequences)
            flags = assembly_flags(assembly, per_junction)
            admitted += not flags
            record["assemblies"].append({**assembly, "linkers": list(combination), "reasons": flags,
                                         "status": "rejected_sequence_rule" if flags else "sequence_proposal_requires_structural_review", "fusion_function_validated": False})
        record["admissible_sequence_assemblies"] = admitted
        record["proposal_status"] = "proposed_sequences_only" if admitted else "no_admissible_complete_assembly"
        output.append(record)
    return {"format": "fusion-design-pipeline.v0", "budget": asdict(budget), "plans": output,
            "generator_identity": model_identity, "library_sha256": canonical_hash(library) if library is not None else None,
            "synthetic_software_fixture": bool((model_identity or {}).get("synthetic_software_fixture")) or any(p["synthetic_software_fixture"] for p in output),
            "scientific_performance": None, "training_performed": False,
            "limitations": ranked["limitations"] + ["Each multi-tether route uses one shared domain placement, not independently optimized junctions.",
                "Fragment-context FIM transfer is opt-in and unvalidated; tandem training does not establish insertion tolerance.",
                "Assemblies preserve sequence only. Linker conformations, closure, folds, protected sites and function remain unassessed.",
                "Template enumeration and neural sampling have different costs; this design report is not a matched benchmark.",
                "No automatic data collection, structure prediction, simulation or training occurs."]}
