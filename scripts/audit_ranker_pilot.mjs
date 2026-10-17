/** Read-only audit of provisional CATH linker records and their cached PDBs. */
import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'

const root = path.resolve(import.meta.dirname, '..')
const recordPath = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(root, 'data', 'processed', 'cath_full_pilot.jsonl')
const cachePath = process.argv[3]
  ? path.resolve(process.argv[3])
  : path.join(root, 'data', 'raw', 'rcsb')
const raw = fs.readFileSync(recordPath)
const rows = raw.toString('utf8').trim().split(/\r?\n/).map((line) => JSON.parse(line))
const aa3 = new Map(Object.entries({ALA:'A',ARG:'R',ASN:'N',ASP:'D',CYS:'C',GLU:'E',GLN:'Q',GLY:'G',HIS:'H',ILE:'I',LEU:'L',LYS:'K',MET:'M',PHE:'F',PRO:'P',SER:'S',THR:'T',TRP:'W',TYR:'Y',VAL:'V'}))
const digest = (bytes) => crypto.createHash('sha256').update(bytes).digest('hex')
const report = {
  status: 'provisional_audit_not_training_approval',
  input_sha256: digest(raw),
  record_count: rows.length,
  evidence_quality: {},
  manual_review_status: {},
  resolved_attachment_pairs: 0,
  fully_resolved_linker_interiors: 0,
  coordinate_hash_matches: 0,
  port_coordinate_identity_matches: 0,
  unique_architecture_proxies: new Set(),
  failures: [],
}
const pdbCache = new Map()
for (const row of rows) {
  const id = row.example_id
  const quality = row.linker?.evidence_quality ?? 'missing'
  const review = row.source?.manual_review_status ?? 'missing'
  report.evidence_quality[quality] = (report.evidence_quality[quality] ?? 0) + 1
  report.manual_review_status[review] = (report.manual_review_status[review] ?? 0) + 1
  if (row.homology_cluster_id) report.unique_architecture_proxies.add(row.homology_cluster_id)
  if (row.source?.unresolved_linker_residues === 0) report.fully_resolved_linker_interiors++
  const mappings = row.residue_mapping ?? []
  const left = mappings[0]
  const right = mappings.at(-1)
  if (!left?.resolved || !right?.resolved) {
    report.failures.push({example_id:id, reason:'unresolved_attachment'})
    continue
  }
  report.resolved_attachment_pairs++
  const pdb = row.source?.pdb_id?.toUpperCase()
  const chain = row.source?.chain_id
  const filename = path.join(cachePath, `${pdb}.pdb`)
  if (!fs.existsSync(filename)) {
    report.failures.push({example_id:id, reason:'missing_pdb'})
    continue
  }
  if (!pdbCache.has(filename)) pdbCache.set(filename, fs.readFileSync(filename))
  const payload = pdbCache.get(filename)
  if (digest(payload) !== row.source.coordinate_sha256) {
    report.failures.push({example_id:id, reason:'coordinate_hash_mismatch'})
    continue
  }
  report.coordinate_hash_matches++
  const positions = new Map()
  for (const line of payload.toString('ascii').split(/\r?\n/)) {
    if (line.startsWith('ENDMDL')) break
    if (!line.startsWith('ATOM  ') || line.length < 54 || line[21] !== chain || line.slice(12, 16).trim() !== 'CA') continue
    if (![' ', 'A'].includes(line[16]) || line[26] !== ' ') continue
    const number = Number.parseInt(line.slice(22, 26), 10)
    const residue = aa3.get(line.slice(17, 20).trim())
    if (Number.isInteger(number) && residue && !positions.has(number)) positions.set(number, residue)
  }
  const leftExpected = row.domain_a.sequence.at(-1)
  const rightExpected = row.domain_b.sequence[0]
  if (positions.get(left.author_number) !== leftExpected || positions.get(right.author_number) !== rightExpected) {
    report.failures.push({example_id:id, reason:'port_residue_identity_mismatch'})
    continue
  }
  report.port_coordinate_identity_matches++
}
report.unique_architecture_proxies = report.unique_architecture_proxies.size
console.log(JSON.stringify(report, null, 2))
if (report.failures.length) process.exitCode = 1
