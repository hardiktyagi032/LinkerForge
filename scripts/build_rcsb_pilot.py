"""Fetch RCSB PDB files and make provisional, mechanically checked examples.

These records require manual source review before becoming paper-grade natural
observations. Only simple CATH D02/F00, one-segment-per-domain cases are used.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shlex
import subprocess
from datetime import datetime, timezone
from math import dist
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


AA3 = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLU": "E", "GLN": "Q", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def fetch_pdb(pdb_id: str, cache: Path) -> bytes:
    path = cache / f"{pdb_id.upper()}.pdb"
    if path.exists():
        return path.read_bytes()
    url = f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb"
    request = Request(url, headers={"User-Agent": "LinkerForge-research-pilot/0.1 (public PDB metadata)"})
    with urlopen(request, timeout=30) as response:
        payload = response.read(8_000_001)
    if len(payload) > 8_000_000 or not payload.startswith(b"HEADER"):
        raise ValueError("PDB file too large or not a legacy PDB coordinate file")
    cache.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def fetch_cif(pdb_id: str, cache: Path) -> bytes:
    path = cache / f"{pdb_id.upper()}.cif"
    if path.exists():
        return path.read_bytes()
    request = Request(f"https://files.rcsb.org/download/{pdb_id.upper()}.cif", headers={"User-Agent": "LinkerForge-research-pilot/0.1"})
    with urlopen(request, timeout=30) as response:
        payload = response.read(10_000_001)
    if len(payload) > 10_000_000 or not payload.startswith(b"data_"):
        raise ValueError("CIF file too large or malformed")
    cache.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def read_scheme(payload: bytes, chain_id: str) -> dict[int, tuple[int, str]]:
    """Read the simple, line-oriented _pdbx_poly_seq_scheme table from mmCIF."""
    lines = payload.decode("utf-8", errors="replace").splitlines()
    prefix = "_pdbx_poly_seq_scheme."
    starts = [i for i, line in enumerate(lines) if line.startswith(prefix)]
    if not starts:
        raise ValueError("No _pdbx_poly_seq_scheme category")
    start = starts[0]
    fields = []
    i = start
    while i < len(lines) and lines[i].startswith(prefix):
        fields.append(lines[i][len(prefix):].strip())
        i += 1
    required = ("seq_id", "mon_id", "pdb_seq_num", "pdb_strand_id", "pdb_ins_code")
    if any(field not in fields for field in required):
        raise ValueError("Incomplete sequence scheme category")
    index = {name: fields.index(name) for name in required}
    mapping = {}
    while i < len(lines) and lines[i].strip() != "#":
        line = lines[i].strip()
        i += 1
        if not line:
            continue
        columns = shlex.split(line)
        if len(columns) != len(fields):
            raise ValueError(f"Multiline or malformed sequence scheme row at line {i}: {line[:60]!r} ({len(columns)} vs {len(fields)})")
        if columns[index["pdb_strand_id"]] != chain_id or columns[index["pdb_ins_code"]] not in (".", "?", "-"):
            continue
        aa = AA3.get(columns[index["mon_id"]])
        if aa is None:
            continue
        number = int(columns[index["pdb_seq_num"]])
        seq_id = int(columns[index["seq_id"]])
        if number in mapping and mapping[number] != (seq_id, aa):
            raise ValueError("Ambiguous sequence scheme numbering")
        mapping[number] = (seq_id, aa)
    return mapping


def read_ca(payload: bytes, chain_id: str) -> dict[int, tuple[str, tuple[float, float, float]]]:
    residues = {}
    for line in payload.decode("ascii", errors="replace").splitlines():
        if line.startswith("ENDMDL"):
            break
        if not line.startswith("ATOM  ") or len(line) < 54:
            continue
        if line[21] != chain_id or line[12:16].strip() != "CA":
            continue
        if line[16] not in (" ", "A") or line[26] != " ":
            continue
        residue = AA3.get(line[17:20].strip())
        if residue is None:
            continue
        try:
            author_number = int(line[22:26])
            xyz = tuple(float(line[start:start + 8]) for start in (30, 38, 46))
        except ValueError:
            continue
        previous = residues.setdefault(author_number, (residue, xyz))
        if previous[0] != residue:
            raise ValueError("Conflicting CA residue identity")
    return residues


def local_port(ca: dict[int, tuple[str, tuple[float, float, float]]], number: int, start: int, end: int) -> dict[str, float]:
    """Simple within-domain CA contact-density proxy, not solvent SASA."""
    neighbors = [n for n in range(start, end + 1) if abs(n - number) > 3 and n in ca]
    contacts = sum(dist(ca[number][1], ca[n][1]) < 8.0 for n in neighbors)
    density = min(1.0, contacts / 12.0)
    return {"contact_density": density, "accessibility_proxy": 1.0 - density}


def commit_sha() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-requests", type=int, default=27)
    args = parser.parse_args()
    if args.max_requests < 1:
        raise ValueError("max-requests must be positive")
    from linkerforge.data import (  # import after PYTHONPATH is configured
        AdjudicationConfig, ChainSequence, DomainAssignment, Provenance,
        ResidueMap, SourceMetadata, extract_natural_example,
    )
    source_bytes = args.candidates.read_bytes()
    rows = list(csv.DictReader(source_bytes.decode("utf-8").splitlines()))
    eligible = [r for r in rows if int(r["family_annotations"]) == 2]
    eligible.sort(key=lambda r: sha256_bytes(f"{r['pdb_id']}.{r['chain_id']}".encode()))
    selected = eligible[: args.max_requests]
    config = {"selection": "CATH D02/F00, one segment/domain, 5-30 author-number gap, both domains classified", "sample_order": "SHA256(PDB.chain) ascending", "max_requests": args.max_requests}
    config_hash = sha256_bytes(json.dumps(config, sort_keys=True).encode())
    provenance = Provenance(commit_sha(), config_hash, {"linkerforge": "pilot-0.1", "cath": "4.4.0"})
    records, rejected = [], []
    for row in selected:
        source_id = f"{row['pdb_id']}.{row['chain_id']}"
        try:
            payload = fetch_pdb(row["pdb_id"], args.cache)
            cif_payload = fetch_cif(row["pdb_id"], args.cache)
            ca = read_ca(payload, row["chain_id"])
            scheme = read_scheme(cif_payload, row["chain_id"])
            first, last = int(row["domain_a_start_author"]), int(row["domain_b_end_author"])
            missing = [n for n in range(first, last + 1) if n not in scheme]
            if missing:
                raise ValueError(f"Unsequenced/unsupported positions: {len(missing)}")
            sequence = "".join(scheme[n][1] for n in range(first, last + 1))
            residues = tuple(ResidueMap(i, first + i - 1, "", scheme[first + i - 1][0], first + i - 1 in ca) for i in range(1, len(sequence) + 1))
            a_end = int(row["domain_a_end_author"]) - first + 1
            b_start = int(row["domain_b_start_author"]) - first + 1
            result = extract_natural_example(
                ChainSequence(sequence, residues),
                (DomainAssignment(1, a_end, (row["family_a"],)),
                 DomainAssignment(b_start, len(sequence), (row["family_b"],))),
                SourceMetadata(row["pdb_id"], row["chain_id"], None, datetime.now(timezone.utc).date().isoformat()),
                provenance, AdjudicationConfig(evidence_quality="uncertain", require_resolved_junctions=False),
            )
            if not result.accepted:
                raise ValueError(";".join(result.reason_codes))
            record = result.record
            record["source"]["coordinate_sha256"] = sha256_bytes(payload)
            record["source"]["mmcif_sha256"] = sha256_bytes(cif_payload)
            record["source"]["annotation_source"] = "CATH v4.4.0 domain list"
            record["source"]["manual_review_status"] = "pending"
            record["source"]["cath_author_numbered_range"] = [first, last]
            a_port, b_port = int(row["domain_a_end_author"]), int(row["domain_b_start_author"])
            if a_port in ca and b_port in ca:
                record["connection_features"] = {
                    "port_a": local_port(ca, a_port, first, a_port),
                    "port_b": local_port(ca, b_port, b_port, last),
                    "feature_note": "within-domain CA contact proxy; not measured solvent accessibility",
                }
            record["source"]["unresolved_linker_residues"] = sum(n not in ca for n in range(a_port + 1, b_port))
            record["homology_cluster_id"] = "CATH-architecture-proxy:" + row["family_a"] + ":" + row["family_b"]
            records.append(record)
        except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
            rejected.append({"source_id": source_id, "reason": type(exc).__name__, "detail": str(exc)[:180]})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records), encoding="utf-8")
    manifest = {
        "status": "provisional_unreviewed_pilot", "accepted": len(records), "rejected": len(rejected),
        "candidate_file_sha256": sha256_bytes(source_bytes), "config_hash": config_hash,
        "pipeline_commit": provenance.pipeline_commit, "rejections": rejected,
    }
    args.output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"accepted={len(records)} rejected={len(rejected)} status=provisional_unreviewed_pilot")


if __name__ == "__main__":
    main()
