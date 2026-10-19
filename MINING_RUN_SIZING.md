# UniProt Mining Run: Sizing and Pipeline Design (partial)

Status: partial, written 2026-10-17 when work paused. Verified numbers are marked
VERIFIED with source. Everything else is arithmetic on those numbers or is listed
under "Not verified".

## Verified counts

| Item | Value | Source |
|---|---|---|
| UniProt release | 2026_03, 02-Sep-2026 | UniProt relnotes.txt (DDBJ mirror) |
| Swiss-Prot entries | 575,748 | relnotes.txt, Expasy relstat |
| Swiss-Prot residues | 209,017,843 (mean length 363) | Expasy relstat |
| TrEMBL entries | 149,430,635 | relnotes.txt |
| UniRef100 / 90 / 50 | 221,143,266 / 121,494,192 / 38,840,027 | relnotes.txt |
| AlphaFold DB | "over 214 million" predictions (NAR 2024, PMC10767828) | paper title only, current count not checked |

Sources: https://ddbj.nig.ac.jp/public/mirror_database/uniprot/relnotes.txt ,
https://web.expasy.org/docs/relnotes/relstat.html

## Storage arithmetic (per-residue embeddings, fp16)

| Set | Residues | ESM-2 650M (1280 d, 2560 B/res) | ProtT5-XL (1024 d, 2048 B/res) | Classifier output (uint8 prob/res) |
|---|---|---|---|---|
| Swiss-Prot | 209.0 M | 535 GB | 428 GB | 209 MB |
| UniRef50 reps (assume mean 300 aa, UNVERIFIED) | ~11.7 B | ~30 TB | ~24 TB | ~12 GB |
| TrEMBL (assume mean 330 aa, UNVERIFIED) | ~49 B | ~126 TB | ~101 TB | ~49 GB |

Conclusion from storage alone: per-residue embeddings must never be stored at
UniProt scale. Encoder and head run in the same pass, and only head outputs are kept.

## Recommendation

1. UniProt-wide (TrEMBL) mining is not feasible on RTX 3050 + free tiers. Even
   with embeddings streamed, it is ~49 B residues of ESM-2 650M forward passes.
2. MVP target: Swiss-Prot (575,748 seqs, 209 M residues). Reviewed annotations,
   near-complete AlphaFold DB coverage expected, fits one encoder pass on free
   GPU time (throughput benchmark still needed, see below).
3. Scale-up target (college cloud): UniRef50 representatives (38.8 M). Principle:
   one sequence per 50% identity cluster maximises family diversity per GPU hour
   and avoids flooding the design model with near-duplicate linkers.
4. Structure features: use AlphaFold DB only, never fold. Proteins with no AFDB
   model run sequence-only and are flagged, not folded.

## Benchmark leakage control

- Build a "forbidden" set: every protein in CAID3 common-27, DP94 candidate
  benchmark, the conformal calibration set, and the classifier test split.
- Run MMseqs2 `easy-search` of the mining set against the forbidden set and drop any
  hit at >=30% identity over >=50% coverage. Also drop any shared Pfam family
  (InterPro mapping from UniProt) with the forbidden set, matching the
  family-disjoint rule in RESEARCH_HANDOFF.md.
- Persist the excluded accession list with the run so the filter is auditable.

## Pipeline design

- Input: FASTA filtered by leakage control, sorted by length, sharded into
  fixed shards of ~10k sequences (`shard_00000.fasta` ...). Shard id = hash of
  sorted accession list, so reruns map to the same shards.
- Batching: length-bucketed, token budget per batch (not fixed batch size) to fit
  6 GB / 16 GB GPUs. Sequences > 1022 aa (ESM-2 limit) use overlapping 1022-aa
  windows with 256-aa overlap, averaged in overlap.
- Resumability: one output file per shard, written to `*.tmp` then atomically
  renamed. A run manifest (`manifest.jsonl`) records shard id, encoder + head
  checkpoint hash, UniProt release, status. On restart, skip shards with a
  complete output. Works on Colab/Kaggle session kills.
- Output: per shard Parquet with columns `accession, seq_sha1, length,
  probs (uint8 list), afdb_used (bool), segments (list of start,end,mean_prob)`.
  Segments = runs above the conformal threshold chosen by the classifier thread.
- Dedup: key on `seq_sha1`, keep one row per identical sequence; at the mined-
  segment level dedup linker sequences with MMseqs2 at 90% identity before they
  go to the design model.
- Final artifact: `mined_linkers.parquet` (accession, segment span, linker
  sequence, flanking domain ids, confidence) plus the manifest and the exclusion list.

## Not verified (to do next)

- Current AlphaFold DB entry count and exact coverage of Swiss-Prot / TrEMBL
  (UniProt query `database:alphafolddb` was blocked from the cloud container).
- Mean length of TrEMBL and UniRef50 (assumed above).
- ESM-2 650M and ProtT5 throughput (residues/s) on T4 and RTX 3050. Needs a
  ~5 min benchmark before any time estimate is stated. Time = residues / rate.
- Whether free-tier weekly GPU quotas cover one Swiss-Prot pass.
