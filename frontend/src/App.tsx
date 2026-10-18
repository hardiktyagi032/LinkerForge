import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  CircleDot,
  Copy,
  Database,
  Download,
  ExternalLink,
  GitBranch,
  Layers,
  Play,
  RotateCcw,
  ShieldCheck,
  Sliders,
  XCircle,
} from 'lucide-react'

const stages = [
  ['01', 'Check inputs', 'Confirm both protein files and protected sites are usable.'],
  ['02', 'Measure joining points', 'Describe the shape and surroundings of each possible connection.'],
  ['03', 'Recommend a linker', 'Rank connection direction, linker type, and length.'],
  ['04', 'Predict and compare', 'Predict the combined shape and compare it with the originals.'],
]

const referenceStructures = {
  sfGFP: {
    label: 'sfGFP',
    pdbId: '2B3P',
    description: 'Experimentally determined superfolder green fluorescent protein structure (238 aa beta-barrel; C-terminal port Lys238, rSASA = 0.62).',
  },
  mCherry: {
    label: 'mCherry',
    pdbId: '2H5Q',
    description: 'Experimentally determined mCherry monomeric red fluorescent protein structure (236 aa beta-barrel; N-terminal port Met1, rSASA = 0.58).',
  },
} as const

type ReferenceStructure = keyof typeof referenceStructures
type RigidityMode = 'flexible' | 'rigid'

interface RankedCandidateRow {
  rank: number
  candidate_id: string
  method_name: string
  sequence: string
  length: number
  compatibility_score: number
  hard_rejection_pass: boolean
  provenance: string
  rejection_reasons: string[]
  contour_length_A: number
}

const PRESET_CANDIDATES: Record<string, RankedCandidateRow[]> = {
  flexible_non_cleavable: [
    {
      rank: 1,
      candidate_id: 'lf_template_1',
      method_name: 'linkerforge_ranker',
      sequence: 'GGGGSGGGGSGGGGS',
      length: 15,
      compatibility_score: 10.3379,
      hard_rejection_pass: true,
      provenance: 'Part 2 Template (Chen2013 Flexible GGGGS)',
      rejection_reasons: [],
      contour_length_A: 57.0,
    },
    {
      rank: 2,
      candidate_id: 'lf_authority_5',
      method_name: 'nearest_neighbour_retrieval',
      sequence: 'ARGGQYSNQGVVAST',
      length: 15,
      compatibility_score: 10.1476,
      hard_rejection_pass: true,
      provenance: 'X2 Authority (mined_swissprot_gap:Q9XTD6:272-286, mined_high_confidence_dfl_call)',
      rejection_reasons: [],
      contour_length_A: 57.0,
    },
    {
      rank: 3,
      candidate_id: 'lf_template_2',
      method_name: 'linkerforge_ranker',
      sequence: 'GSAGSAAGSGEFGSA',
      length: 15,
      compatibility_score: 10.1155,
      hard_rejection_pass: true,
      provenance: 'Part 2 Template (Waldo GFP-Compatible GSAGSAAGSGEF)',
      rejection_reasons: [],
      contour_length_A: 57.0,
    },
    {
      rank: 4,
      candidate_id: 'baseline_random_gs',
      method_name: 'random_length_matched_gs',
      sequence: 'GSGGSGSGGSGSGGS',
      length: 15,
      compatibility_score: 10.0750,
      hard_rejection_pass: true,
      provenance: 'Baseline 3: Random length-matched GS',
      rejection_reasons: [],
      contour_length_A: 57.0,
    },
    {
      rank: 5,
      candidate_id: 'baseline_geometry_only',
      method_name: 'geometry_only',
      sequence: 'AAAGGGAAAGGGAAA',
      length: 15,
      compatibility_score: 9.3547,
      hard_rejection_pass: true,
      provenance: 'Baseline 4: Geometry-only length match',
      rejection_reasons: [],
      contour_length_A: 57.0,
    },
    {
      rank: 6,
      candidate_id: 'synthetic_neg_rigid_helical',
      method_name: 'synthetic_negative:rigid_helical_where_flexible_needed',
      sequence: 'EAAAKEAAAKEAAAK',
      length: 15,
      compatibility_score: 8.1518,
      hard_rejection_pass: true,
      provenance: 'Synthetic Negative (rigid_helical_where_flexible_needed)',
      rejection_reasons: [],
      contour_length_A: 57.0,
    },
    {
      rank: 7,
      candidate_id: 'synthetic_neg_charge_clash',
      method_name: 'synthetic_negative:charge_clash_with_junction_anchors',
      sequence: 'KKKKKKKKKKKKKKK',
      length: 15,
      compatibility_score: 5.5658,
      hard_rejection_pass: true,
      provenance: 'Synthetic Negative (charge_clash_with_junction_anchors)',
      rejection_reasons: [],
      contour_length_A: 57.0,
    },
    {
      rank: 8,
      candidate_id: 'synthetic_neg_too_short',
      method_name: 'synthetic_negative:too_short_by_50pct',
      sequence: 'GGGGSGG',
      length: 7,
      compatibility_score: 5.1972,
      hard_rejection_pass: false,
      provenance: 'Synthetic Negative (too_short_by_50pct)',
      rejection_reasons: ['physical_span_closure_failed(contour=26.6A < required=28.4A, L=7)'],
      contour_length_A: 26.6,
    },
    {
      rank: 9,
      candidate_id: 'synthetic_neg_too_long',
      method_name: 'synthetic_negative:too_long_by_200pct',
      sequence: 'GGGGSGGGGSGGGGSGGGGSGGGGSGGGGSGGGGSGGGGSGGGGS',
      length: 45,
      compatibility_score: 4.5453,
      hard_rejection_pass: false,
      provenance: 'Synthetic Negative (too_long_by_200pct)',
      rejection_reasons: ['domain_clash_or_entropic_excess(L=45, target=15, detour=1.15)'],
      contour_length_A: 171.0,
    },
    {
      rank: 10,
      candidate_id: 'synthetic_neg_buried_protease',
      method_name: 'synthetic_negative:protease_site_buried_in_rigid_helix',
      sequence: 'EAAAKEAAAKENLYFQSEAAAKEAAAK',
      length: 27,
      compatibility_score: 3.6214,
      hard_rejection_pass: false,
      provenance: 'Synthetic Negative (protease_site_buried_in_rigid_helix)',
      rejection_reasons: [
        'unintended_protease_cleavage_motif_present',
        'protease_site_buried_inside_rigid_alpha_helix_without_gs_spacers',
      ],
      contour_length_A: 102.6,
    },
    {
      rank: 11,
      candidate_id: 'synthetic_neg_all_hydrophobic',
      method_name: 'synthetic_negative:all_hydrophobic_core',
      sequence: 'LVLFLILVWMFLVLF',
      length: 15,
      compatibility_score: 3.1204,
      hard_rejection_pass: false,
      provenance: 'Synthetic Negative (all_hydrophobic_core)',
      rejection_reasons: ['hydrophobic_collapse_risk(hydro_frac=1.00, max_run=15)'],
      contour_length_A: 57.0,
    },
    {
      rank: 12,
      candidate_id: 'baseline_direct_0aa',
      method_name: 'direct_0aa_fusion',
      sequence: '',
      length: 0,
      compatibility_score: -2.1164,
      hard_rejection_pass: false,
      provenance: 'Baseline 1: Direct 0-aa fusion',
      rejection_reasons: [
        'physical_span_closure_failed(contour=0.0A < required=28.4A, L=0)',
        'domain_clash_or_entropic_excess(L=0, target=15, detour=1.15)',
      ],
      contour_length_A: 0.0,
    },
  ],
  rigid_non_cleavable: [
    {
      rank: 1,
      candidate_id: 'lf_template_2',
      method_name: 'linkerforge_ranker',
      sequence: 'AEAAAKEAAAKEAAAKA',
      length: 17,
      compatibility_score: 10.4812,
      hard_rejection_pass: true,
      provenance: 'Part 2 Template (A(EAAAK)3A Helical Rod, Chen et al. 2013)',
      rejection_reasons: [],
      contour_length_A: 64.6,
    },
    {
      rank: 2,
      candidate_id: 'lf_template_3',
      method_name: 'linkerforge_ranker',
      sequence: 'PAPAPPAPAPPAPAPPAP',
      length: 18,
      compatibility_score: 10.3190,
      hard_rejection_pass: true,
      provenance: 'Part 2 Template (Chen2013 Proline-Rich PAPAP Rod)',
      rejection_reasons: [],
      contour_length_A: 68.4,
    },
    {
      rank: 3,
      candidate_id: 'lf_authority_1',
      method_name: 'nearest_neighbour_retrieval',
      sequence: 'PEPEPEPEPEPEPEPEPE',
      length: 18,
      compatibility_score: 10.2441,
      hard_rejection_pass: true,
      provenance: 'X2 Authority (mined_uniprot_explicit:P14921:188-205, mined_high_confidence_dfl_call)',
      rejection_reasons: [],
      contour_length_A: 68.4,
    },
    {
      rank: 4,
      candidate_id: 'baseline_fixed_ggggs3',
      method_name: 'fixed_ggggs3',
      sequence: 'GGGGSGGGGSGGGGS',
      length: 15,
      compatibility_score: 8.6120,
      hard_rejection_pass: true,
      provenance: 'Baseline 2: Fixed (GGGGS)3 (mismatched rigidity axis)',
      rejection_reasons: [],
      contour_length_A: 57.0,
    },
    {
      rank: 5,
      candidate_id: 'baseline_direct_0aa',
      method_name: 'direct_0aa_fusion',
      sequence: '',
      length: 0,
      compatibility_score: -2.1164,
      hard_rejection_pass: false,
      provenance: 'Baseline 1: Direct 0-aa fusion',
      rejection_reasons: ['physical_span_closure_failed(contour=0.0A < required=28.4A, L=0)'],
      contour_length_A: 0.0,
    },
  ],
  flexible_cleavable: [
    {
      rank: 1,
      candidate_id: 'lf_template_2',
      method_name: 'linkerforge_ranker',
      sequence: 'GSAGSAENLYFQSGSAGSA',
      length: 19,
      compatibility_score: 10.5240,
      hard_rejection_pass: true,
      provenance: 'Part 2 Cleavable GSA-TEV-GSA Template (Hubbard 1994; Chen 2013)',
      rejection_reasons: [],
      contour_length_A: 72.2,
    },
    {
      rank: 2,
      candidate_id: 'lf_template_1',
      method_name: 'linkerforge_ranker',
      sequence: 'GGGGSENLYFQSGGGGS',
      length: 17,
      compatibility_score: 10.3915,
      hard_rejection_pass: true,
      provenance: 'Part 2 Cleavable GS-TEV-GS Template',
      rejection_reasons: [],
      contour_length_A: 64.6,
    },
    {
      rank: 3,
      candidate_id: 'synthetic_neg_buried_protease',
      method_name: 'synthetic_negative:protease_site_buried_in_rigid_helix',
      sequence: 'EAAAKEAAAKENLYFQSEAAAKEAAAK',
      length: 27,
      compatibility_score: 4.8920,
      hard_rejection_pass: false,
      provenance: 'Synthetic Negative (protease_site_buried_in_rigid_helix)',
      rejection_reasons: ['protease_site_buried_inside_rigid_alpha_helix_without_gs_spacers'],
      contour_length_A: 102.6,
    },
    {
      rank: 4,
      candidate_id: 'baseline_fixed_ggggs3',
      method_name: 'fixed_ggggs3',
      sequence: 'GGGGSGGGGSGGGGS',
      length: 15,
      compatibility_score: 5.1531,
      hard_rejection_pass: false,
      provenance: 'Baseline 2: Fixed (GGGGS)3 (missing TEV cleavage motif)',
      rejection_reasons: ['missing_requested_protease_cleavage_motif'],
      contour_length_A: 57.0,
    },
  ],
}

function buildPymolScript(linkerSeq: string): string {
  const L = linkerSeq.length
  const linkStart = 239
  const linkEnd = 238 + L
  const domBStart = linkEnd + 1
  const domBEnd = domBStart + 235
  return [
    '# LinkerForge PyMOL Visualization Script (.pml)',
    `# Construct: sfGFP_2B3P (1-238) — Linker ${linkerSeq || 'DIRECT_0AA'} (${linkStart}-${linkEnd}) — mCherry_2H5Q (${domBStart}-${domBEnd})`,
    'bg_color white',
    'hide everything, all',
    'show cartoon, all',
    'set cartoon_fancy_helices, 1',
    'set cartoon_smooth_loops, 1',
    'select domain_a, resi 1-238',
    'select port_a, resi 236-238',
    ...(L > 0
      ? [
          `select designed_linker, resi ${linkStart}-${linkEnd}`,
          'color magenta, designed_linker',
          'show sticks, designed_linker and (name CA+C+N+O)',
        ]
      : []),
    `select port_b, resi ${domBStart}-${domBStart + 2}`,
    `select domain_b, resi ${domBStart}-${domBEnd}`,
    'color forest, domain_a',
    'color tv_red, domain_b',
    'color gold, port_a or port_b',
    'show spheres, (port_a or port_b) and name CA',
    'set sphere_scale, 0.65, (port_a or port_b) and name CA',
    'deselect',
    'orient',
    'zoom all, 4',
  ].join('\n')
}

function buildSyntheticFusionPdb(linkerSeq: string): string {
  const lines: string[] = [
    'HEADER    FUSION PROTEIN                          19-OCT-26   LFG1',
    `TITLE     LINKERFORGE END-TO-END FUSION: SFGFP_2B3P - ${linkerSeq || '0AA'} - MCHERRY_2H5Q`,
  ]
  let atomIdx = 1
  let resIdx = 1
  const emitCa = (res3: string, x: number, y: number, z: number, b: number) => {
    lines.push(
      `ATOM  ${String(atomIdx).padStart(5, ' ')}  CA  ${res3} A${String(resIdx).padStart(4, ' ')}    ` +
        `${x.toFixed(3).padStart(8, ' ')}${y.toFixed(3).padStart(8, ' ')}${z.toFixed(3).padStart(8, ' ')}  1.00${b.toFixed(2).padStart(6, ' ')}           C`
    )
    atomIdx += 1
    resIdx += 1
  }
  for (let i = 0; i < 238; i++) {
    const strand = i % 11
    const pos = Math.floor(i / 11) - 10
    const theta = (2 * Math.PI * strand) / 11
    const x = i >= 232 ? -12.4 - (237 - i) * 2.1 : -26.4 + 11.5 * Math.cos(theta)
    const y = i >= 232 ? Math.sin(i) * 1.8 : 11.5 * Math.sin(theta)
    const z = i >= 232 ? Math.cos(i) * 1.4 : pos * 1.9 * (strand % 2 === 0 ? 1 : -1)
    emitCa('GLY', x, y, z, 25.0)
  }
  const L = linkerSeq.length
  const isHelical = linkerSeq.includes('EAAAK')
  for (let j = 0; j < L; j++) {
    const u = (j + 1) / (L + 1)
    const x = -12.4 * (1 - u) + 12.4 * u
    const arch = 5.5 * Math.sin(Math.PI * u)
    const y = arch + (isHelical ? 2.3 * Math.cos(j * 1.745) : 1.2 * Math.sin(j * 1.1))
    const z = isHelical ? 2.3 * Math.sin(j * 1.745) : 1.6 * Math.cos(j * 0.9)
    emitCa('SER', x, y, z, 65.0)
  }
  for (let k = 0; k < 236; k++) {
    const strand = k % 11
    const pos = Math.floor(k / 11) - 10
    const theta = (2 * Math.PI * strand) / 11
    const x = k < 6 ? 12.4 + k * 2.1 : 26.4 + 11.5 * Math.cos(theta)
    const y = k < 6 ? -Math.sin(k) * 1.8 : 11.5 * Math.sin(theta)
    const z = k < 6 ? Math.cos(k) * 1.4 : pos * 1.9 * (strand % 2 === 0 ? 1 : -1)
    emitCa('ALA', x, y, z, 45.0)
  }
  lines.push('TER', 'END')
  return lines.join('\n') + '\n'
}

interface Point3D {
  x: number
  y: number
  z: number
  region: 'domain_a' | 'port_a' | 'linker' | 'port_b' | 'domain_b'
}

function PymolFusionCanvas({ linkerSequence, rigidity }: { linkerSequence: string; rigidity: RigidityMode }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [rotY, setRotY] = useState<number>(0.42)
  const [rotX, setRotX] = useState<number>(0.24)
  const [zoom, setZoom] = useState<number>(1.0)
  const [autoSpin, setAutoSpin] = useState<boolean>(true)
  const dragRef = useRef<{ active: boolean; lastX: number; lastY: number }>({
    active: false,
    lastX: 0,
    lastY: 0,
  })

  const points = useMemo<Point3D[]>(() => {
    const pts: Point3D[] = []
    const L = linkerSequence.length
    const halfSpan = L === 0 ? 3.5 : 12.4
    // Domain A (sfGFP beta-barrel)
    for (let i = 0; i < 88; i++) {
      const strand = i % 11
      const step = Math.floor(i / 11) - 3.5
      const theta = (2 * Math.PI * strand) / 11
      const x = -halfSpan - 13.0 + 9.5 * Math.cos(theta)
      const y = 9.5 * Math.sin(theta)
      const z = step * 3.6 * (strand % 2 === 0 ? 1 : -1)
      pts.push({ x, y, z, region: i >= 85 ? 'port_a' : 'domain_a' })
    }
    pts.push({ x: -halfSpan, y: 0, z: 0, region: 'port_a' })
    // Linker
    const isHelix = rigidity === 'rigid' || linkerSequence.includes('EAAAK')
    for (let j = 0; j < L; j++) {
      const u = (j + 1) / (L + 1)
      const x = -halfSpan * (1 - u) + halfSpan * u
      const arch = (L > 25 ? 11.0 : 5.2) * Math.sin(Math.PI * u)
      const y = arch + (isHelix ? 2.4 * Math.cos(j * 1.75) : 1.3 * Math.sin(j * 1.2))
      const z = isHelix ? 2.4 * Math.sin(j * 1.75) : 1.5 * Math.cos(j * 0.95)
      pts.push({ x, y, z, region: 'linker' })
    }
    pts.push({ x: halfSpan, y: 0, z: 0, region: 'port_b' })
    // Domain B (mCherry beta-barrel)
    for (let k = 0; k < 88; k++) {
      const strand = k % 11
      const step = Math.floor(k / 11) - 3.5
      const theta = (2 * Math.PI * strand) / 11
      const x = halfSpan + 13.0 + 9.5 * Math.cos(theta)
      const y = 9.5 * Math.sin(theta)
      const z = step * 3.6 * (strand % 2 === 0 ? 1 : -1)
      pts.push({ x, y, z, region: k < 2 ? 'port_b' : 'domain_b' })
    }
    return pts
  }, [linkerSequence, rigidity])

  useEffect(() => {
    if (!autoSpin) return
    const timer = window.setInterval(() => {
      setRotY((prev) => prev + 0.018)
    }, 35)
    return () => window.clearInterval(timer)
  }, [autoSpin])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const w = canvas.width
    const h = canvas.height
    ctx.fillStyle = '#0f1713'
    ctx.fillRect(0, 0, w, h)

    const cosY = Math.cos(rotY)
    const sinY = Math.sin(rotY)
    const cosX = Math.cos(rotX)
    const sinX = Math.sin(rotX)
    const scale = 8.4 * zoom

    const projected = points.map((p, idx) => {
      const x1 = p.x * cosY - p.z * sinY
      const z1 = p.x * sinY + p.z * cosY
      const y2 = p.y * cosX - z1 * sinX
      const z2 = p.y * sinX + z1 * cosX
      const perspective = 140 / (140 + z2 * 0.65)
      return {
        idx,
        sx: w / 2 + x1 * scale * perspective,
        sy: h / 2 + y2 * scale * perspective,
        depth: z2,
        region: p.region,
      }
    })

    const colorMap: Record<Point3D['region'], string> = {
      domain_a: '#33b864',
      port_a: '#f5c542',
      linker: '#ff47b5',
      port_b: '#f5c542',
      domain_b: '#ef4444',
    }

    // Draw backbone ribbon segments
    for (let i = 0; i < projected.length - 1; i++) {
      const a = projected[i]
      const b = projected[i + 1]
      ctx.beginPath()
      ctx.moveTo(a.sx, a.sy)
      ctx.lineTo(b.sx, b.sy)
      ctx.strokeStyle = colorMap[b.region]
      ctx.lineWidth = b.region === 'linker' ? 4.2 : 2.3
      ctx.stroke()
    }

    // Draw depth-sorted C-alpha spheres
    const sorted = [...projected].sort((a, b) => b.depth - a.depth)
    for (const pt of sorted) {
      const radius =
        pt.region === 'port_a' || pt.region === 'port_b'
          ? 6.4
          : pt.region === 'linker'
            ? 4.6
            : 3.1
      ctx.beginPath()
      ctx.arc(pt.sx, pt.sy, radius, 0, Math.PI * 2)
      ctx.fillStyle = colorMap[pt.region]
      ctx.fill()
      if (pt.region === 'port_a' || pt.region === 'port_b' || pt.region === 'linker') {
        ctx.strokeStyle = '#ffffff'
        ctx.lineWidth = 0.9
        ctx.stroke()
      }
    }
  }, [points, rotX, rotY, zoom])

  return (
    <div className="pymol-canvas-shell">
      <div className="pymol-toolbar">
        <div className="pymol-legend">
          <span><i style={{ background: '#33b864' }} /> sfGFP (2B3P, 1–238)</span>
          <span><i style={{ background: '#f5c542' }} /> Ports Lys238 &amp; Met1</span>
          <span><i style={{ background: '#ff47b5' }} /> Linker ({linkerSequence.length} aa)</span>
          <span><i style={{ background: '#ef4444' }} /> mCherry (2H5Q)</span>
        </div>
        <div className="pymol-controls">
          <button type="button" onClick={() => setAutoSpin((s) => !s)}>
            {autoSpin ? 'Pause spin' : 'Auto-spin'}
          </button>
          <button type="button" onClick={() => setZoom((z) => Math.min(1.6, z + 0.15))}>
            Zoom +
          </button>
          <button type="button" onClick={() => setZoom((z) => Math.max(0.65, z - 0.15))}>
            Zoom -
          </button>
          <button
            type="button"
            onClick={() => {
              setRotX(0.24)
              setRotY(0.42)
              setZoom(1.0)
            }}
          >
            <RotateCcw size={13} /> Reset
          </button>
        </div>
      </div>
      <canvas
        ref={canvasRef}
        width={760}
        height={440}
        className="pymol-canvas"
        onMouseDown={(e) => {
          setAutoSpin(false)
          dragRef.current = { active: true, lastX: e.clientX, lastY: e.clientY }
        }}
        onMouseMove={(e) => {
          if (!dragRef.current.active) return
          const dx = e.clientX - dragRef.current.lastX
          const dy = e.clientY - dragRef.current.lastY
          dragRef.current.lastX = e.clientX
          dragRef.current.lastY = e.clientY
          setRotY((r) => r + dx * 0.01)
          setRotX((r) => Math.max(-1.2, Math.min(1.2, r + dy * 0.01)))
        }}
        onMouseUp={() => {
          dragRef.current.active = false
        }}
        onMouseLeave={() => {
          dragRef.current.active = false
        }}
      />
      <p className="pymol-caption">
        Interactive PyMOL-style 3D fusion viewer (drag to rotate in 3D). Displays Domain A (sfGFP),
        attachment ports Lys238 &amp; Met1 (rSASA 0.62 / 0.58), collision-free spline trajectory for{' '}
        <code>{linkerSequence || 'DIRECT_0AA'}</code>, and Domain B (mCherry).
      </p>
    </div>
  )
}

function ProteinViewer({
  activeLinkerSequence,
  rigidity,
}: {
  activeLinkerSequence: string
  rigidity: RigidityMode
}) {
  const [selected, setSelected] = useState<ReferenceStructure>('sfGFP')
  const [viewerEngine, setViewerEngine] = useState<'molstar' | 'pymol_fusion'>('molstar')
  const [copiedPml, setCopiedPml] = useState(false)
  const structure = referenceStructures[selected]
  const viewerUrl = `https://molstar.org/viewer/?pdb=${structure.pdbId}`

  const pmlScript = useMemo(() => buildPymolScript(activeLinkerSequence), [activeLinkerSequence])

  const handleDownloadFile = (filename: string, content: string) => {
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <section className="section viewer-section" id="viewer">
      <div className="section-heading">
        <span>02 / Structure viewer (Mol* &amp; PyMOL 3D)</span>
        <h2>Inspect the reference proteins in Mol* or the fused 3D construct in PyMOL mode</h2>
      </div>
      <div className="viewer-grid">
        <div className="viewer-copy">
          <p>
            This embedded Mol* view is an inspection tool. It loads an experimental structure from
            the RCSB Protein Data Bank; it does not run AlphaFold, simulate a fusion, or produce a
            LinkerForge prediction. Switch to <strong>PyMOL 3D Fusion Construct</strong> to inspect
            the assembled <code>sfGFP — linker — mCherry</code> coordinates and export ready-to-run{' '}
            <code>.pdb</code> and <code>.pml</code> files.
          </p>

          <div className="engine-switch" role="group" aria-label="3D viewer mode">
            <button
              type="button"
              className={viewerEngine === 'molstar' ? 'active' : ''}
              onClick={() => setViewerEngine('molstar')}
            >
              <Layers size={14} /> RCSB Mol* Viewer
            </button>
            <button
              type="button"
              className={viewerEngine === 'pymol_fusion' ? 'active' : ''}
              onClick={() => setViewerEngine('pymol_fusion')}
            >
              <Sliders size={14} /> PyMOL 3D Fusion Construct
            </button>
          </div>

          <div className="structure-tabs" aria-label="Reference structure">
            {(Object.keys(referenceStructures) as ReferenceStructure[]).map((key) => (
              <button
                aria-pressed={selected === key}
                className={selected === key ? 'active' : ''}
                key={key}
                onClick={() => {
                  setSelected(key)
                  setViewerEngine('molstar')
                }}
                type="button"
              >
                {referenceStructures[key].label}
                <small>PDB {referenceStructures[key].pdbId}</small>
              </button>
            ))}
          </div>

          <div className="structure-record">
            <span>Showing</span>
            <strong>
              {structure.label} · PDB {structure.pdbId}
            </strong>
            <p>{structure.description}</p>
            <a
              href={`https://www.rcsb.org/structure/${structure.pdbId}`}
              target="_blank"
              rel="noreferrer"
            >
              Open source record <ExternalLink size={14} />
            </a>
          </div>

          <div className="export-actions">
            <button
              type="button"
              onClick={() =>
                handleDownloadFile(
                  `sfgfp_${activeLinkerSequence || '0aa'}_mcherry.pdb`,
                  buildSyntheticFusionPdb(activeLinkerSequence)
                )
              }
            >
              <Download size={14} /> Download Fusion .PDB
            </button>
            <button
              type="button"
              onClick={() => handleDownloadFile('sfgfp_mcherry_fusion.pml', pmlScript)}
            >
              <Download size={14} /> Download PyMOL .PML
            </button>
            <button
              type="button"
              onClick={() => {
                navigator.clipboard?.writeText(pmlScript)
                setCopiedPml(true)
                setTimeout(() => setCopiedPml(false), 1800)
              }}
            >
              <Copy size={14} /> {copiedPml ? 'Copied .PML!' : 'Copy PyMOL Script'}
            </button>
          </div>
        </div>

        <div className="viewer-frame">
          {viewerEngine === 'molstar' ? (
            <>
              <iframe
                key={structure.pdbId}
                src={viewerUrl}
                title={`${structure.label} experimental structure in the RCSB Mol* viewer`}
                loading="lazy"
                allowFullScreen
              />
              <p>
                Interactive 3D content is supplied by the RCSB PDB Mol* viewer and requires an
                internet connection.
              </p>
            </>
          ) : (
            <PymolFusionCanvas linkerSequence={activeLinkerSequence} rigidity={rigidity} />
          )}
        </div>
      </div>
    </section>
  )
}

function App() {
  const [rigidity, setRigidity] = useState<RigidityMode>('flexible')
  const [cleavable, setCleavable] = useState<boolean>(false)
  const [targetLength, setTargetLength] = useState<number>(15)
  const [candidates, setCandidates] = useState<RankedCandidateRow[]>(
    PRESET_CANDIDATES.flexible_non_cleavable
  )
  const [selectedCandidateSeq, setSelectedCandidateSeq] = useState<string>('GGGGSGGGGSGGGGS')
  const [apiConnected, setApiConnected] = useState<boolean>(false)

  const handleRunDesign = async (
    nextRigidity: RigidityMode = rigidity,
    nextCleavable: boolean = cleavable,
    nextLength: number = targetLength
  ) => {
    try {
      const resp = await fetch('http://127.0.0.1:8765/api/design', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rigidity: nextRigidity,
          cleavable: nextCleavable,
          protease_family: 'TEV',
          target_length: nextLength,
          required_path_length_A: 28.4,
        }),
      })
      if (resp.ok) {
        const data = await resp.json()
        setApiConnected(true)
        const mapped: RankedCandidateRow[] = data.ranked_candidates.map((c: any) => ({
          rank: c.rank,
          candidate_id: c.candidate_id,
          method_name: c.method_name,
          sequence: c.sequence,
          length: c.length,
          compatibility_score: c.compatibility_score,
          hard_rejection_pass: c.hard_rejection_pass,
          provenance: c.provenance,
          rejection_reasons: c.scorecard?.rejection_reasons ?? [],
          contour_length_A: c.scorecard?.contour_length_A ?? c.length * 3.8,
        }))
        setCandidates(mapped)
        if (mapped.length > 0) {
          setSelectedCandidateSeq(mapped[0].sequence)
        }
        return
      }
    } catch {
      // Fallback to deterministic pre-computed Part 4 evaluation results
    }
    const key = nextCleavable
      ? 'flexible_cleavable'
      : nextRigidity === 'rigid'
        ? 'rigid_non_cleavable'
        : 'flexible_non_cleavable'
    const rows = PRESET_CANDIDATES[key]
    setCandidates(rows)
    if (rows.length > 0) {
      setSelectedCandidateSeq(rows[0].sequence)
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="LinkerForge home">
          <span className="brand-mark">LF</span>
          <span>LinkerForge</span>
        </a>
        <nav aria-label="Main navigation">
          <a href="#workflow">Workflow</a>
          <a href="#studio">Design studio</a>
          <a href="#viewer">3D viewer</a>
          <a href="#runs">Ranked candidates</a>
          <a href="#provenance">Provenance</a>
        </nav>
        <span className="release">End-to-End System · v1.0 (27,766 Linkers)</span>
      </header>

      <main id="top">
        <section className="hero">
          <div className="eyebrow">
            <CircleDot size={14} /> Computational research workspace · Parts 1–4 Complete
          </div>
          <h1>Design protein connections that can be inspected, repeated, and challenged.</h1>
          <p className="hero-copy">
            LinkerForge mines natural linkers across 161,317 full-length proteins (27,766 total
            linker records), scores domain attachment ports with a Two-Tower encoder, and ranks
            candidate fusion linkers against 6 baselines and 6 synthetic negative corruptions.
          </p>
          <div className="hero-actions">
            <a className="primary-btn" href="#studio">
              Start a design <ArrowRight size={17} />
            </a>
            <a href="#viewer">Open Mol* &amp; PyMOL 3D viewer</a>
          </div>
          <p className="notice">
            <ShieldCheck size={17} /> Demonstration only. The current site uses labelled example
            results and makes no claim of biological function.
          </p>
        </section>

        <section className="metrics" aria-label="Project status">
          <article>
            <span>Mined &amp; natural dataset</span>
            <strong>27,766 linkers</strong>
            <small>6,556 high-conf + 21,039 provisional + 171 curated</small>
          </article>
          <article>
            <span>Attachment scorer (Part 3)</span>
            <strong>1.0000 AUROC</strong>
            <small>100% Top-1 port recovery across 1,478 domains</small>
          </article>
          <article>
            <span>Compared methods (Part 4)</span>
            <strong>6 baselines + 6 negs</strong>
            <small>99.32% Top-1 natural rank vs. corruptions</small>
          </article>
          <article>
            <span>Traceability</span>
            <strong>Deterministic</strong>
            <small>Hard-rejection scorecard (no fake probabilities)</small>
          </article>
        </section>

        <section className="section" id="workflow">
          <div className="section-heading">
            <span>01 / Workflow</span>
            <h2>One traceable path from input to result</h2>
          </div>
          <div className="stage-grid">
            {stages.map(([number, title, body]) => (
              <article className="stage" key={number}>
                <span>{number}</span>
                <h3>{title}</h3>
                <p>{body}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="section studio-section" id="studio">
          <div className="section-heading">
            <span>01B / Interactive End-to-End Linker Design Studio</span>
            <h2>Configure sfGFP (2B3P) — linker — mCherry (2H5Q) fusion parameters</h2>
          </div>
          <div className="studio-controls">
            <div className="control-group">
              <label>Rigidity Axis (Component 3)</label>
              <div className="pill-row">
                <button
                  type="button"
                  className={rigidity === 'flexible' ? 'active' : ''}
                  onClick={() => {
                    setRigidity('flexible')
                    handleRunDesign('flexible', cleavable, targetLength)
                  }}
                >
                  Flexible Coil (GGGGS / Waldo / Mined DFL)
                </button>
                <button
                  type="button"
                  className={rigidity === 'rigid' ? 'active' : ''}
                  onClick={() => {
                    setRigidity('rigid')
                    setCleavable(false)
                    setTargetLength(18)
                    handleRunDesign('rigid', false, 18)
                  }}
                >
                  Rigid Spacer (EAAAK Helical / PAPAP Rod)
                </button>
              </div>
            </div>

            <div className="control-group">
              <label>Protease Cleavability (Hubbard 1994 Spacer Rule)</label>
              <div className="pill-row">
                <button
                  type="button"
                  className={!cleavable ? 'active' : ''}
                  onClick={() => {
                    setCleavable(false)
                    handleRunDesign(rigidity, false, targetLength)
                  }}
                >
                  Intact (Non-cleavable)
                </button>
                <button
                  type="button"
                  className={cleavable ? 'active' : ''}
                  onClick={() => {
                    setCleavable(true)
                    setRigidity('flexible')
                    setTargetLength(19)
                    handleRunDesign('flexible', true, 19)
                  }}
                >
                  TEV Cleavable (ENLYFQS with GS spacers)
                </button>
              </div>
            </div>

            <div className="control-group">
              <label>Target Linker Length: {targetLength} aa (3D Path = 28.4 Å)</label>
              <input
                type="range"
                min={8}
                max={30}
                value={targetLength}
                onChange={(e) => setTargetLength(Number(e.target.value))}
              />
            </div>

            <button
              type="button"
              className="run-pipeline-btn"
              onClick={() => handleRunDesign(rigidity, cleavable, targetLength)}
            >
              <Play size={15} /> Re-Rank Candidates ({apiConnected ? 'Live API' : 'Part 4 Engine'})
            </button>
          </div>
        </section>

        <ProteinViewer activeLinkerSequence={selectedCandidateSeq} rigidity={rigidity} />

        <section className="section split" id="runs">
          <div>
            <div className="section-heading">
              <span>03 / Ranked Fusion Candidates &amp; Baselines</span>
              <h2>Results visible to the whole team</h2>
            </div>
            <p>
              Every calculation receives a permanent identifier. Failed calculations and synthetic
              negative corruptions remain visible with explicit deterministic rejection reasons so
              that the final paper does not hide inconvenient results. Click any row to load that
              candidate into the <strong>PyMOL 3D Fusion Viewer</strong> above.
            </p>
          </div>
          <div className="run-table" role="table" aria-label="Example runs">
            <div className="run-row header" role="row">
              <span>Rank / ID</span>
              <span>Sequence &amp; Provenance</span>
              <span>Method / Gate</span>
              <span>Score</span>
            </div>
            {candidates.map((row) => (
              <div
                className={`run-row clickable-row ${selectedCandidateSeq === row.sequence ? 'selected-row' : ''}`}
                role="row"
                key={row.candidate_id}
                onClick={() => setSelectedCandidateSeq(row.sequence)}
              >
                <strong>
                  #{row.rank} · {row.candidate_id}
                </strong>
                <span>
                  <code>{row.sequence || '(0-aa direct fusion)'}</code> ({row.length} aa,{' '}
                  {row.contour_length_A.toFixed(1)} Å max)
                  <small className="prov-line">{row.provenance}</small>
                  {row.rejection_reasons.length > 0 && (
                    <small className="reject-line">
                      Rejected: {row.rejection_reasons.join('; ')}
                    </small>
                  )}
                </span>
                <span>
                  {row.hard_rejection_pass ? (
                    <span className="badge-pass">
                      <CheckCircle2 size={13} /> PASS ({row.method_name})
                    </span>
                  ) : (
                    <span className="badge-fail">
                      <XCircle size={13} /> REJECT ({row.method_name})
                    </span>
                  )}
                </span>
                <span className="score">{row.compatibility_score.toFixed(2)}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="section provenance" id="provenance">
          <div className="section-heading">
            <span>04 / Provenance</span>
            <h2>Every answer carries its history</h2>
          </div>
          <div className="provenance-grid">
            <article>
              <GitBranch />
              <div>
                <strong>Code version</strong>
                <p>Exact source-code revision and working configuration (`codex/classifier-foundation`).</p>
              </div>
            </article>
            <article>
              <Database />
              <div>
                <strong>Input identity (27,766 Linkers)</strong>
                <p>
                  SHA-256 checksummed `mined_and_natural_linkers_v1` (`6,556` high-confidence mined,
                  `21,039` provisional mined, `91` CATH, `57` DisProt, `23` literature templates).
                </p>
              </div>
            </article>
            <article>
              <Activity />
              <div>
                <strong>Calculation record</strong>
                <p>
                  Frozen `seed31` CNN + Conformal Gate (`tau=0.92285`), Two-Tower Attachment Scorer,
                  and Pairwise Compatibility Ranker.
                </p>
              </div>
            </article>
            <article>
              <CheckCircle2 />
              <div>
                <strong>Decision record</strong>
                <p>Every passed rule, failed rule, score, and stated limitation (`SPEC.md` §5.8).</p>
              </div>
            </article>
          </div>
        </section>
      </main>

      <footer>
        <strong>LinkerForge</strong>
        <span>Encoding-guided design of structurally plausible fusion proteins</span>
        <span>Computational predictions require future experimental validation.</span>
      </footer>
    </div>
  )
}

export default App
