import { useEffect, useRef, useState } from 'react'
import { Camera, Pause, Play, RotateCcw } from 'lucide-react'
import type { AtomSelectionSpec, AtomStyleSpec, ColorschemeSpec, GLViewer, SurfaceStyleSpec } from '3dmol'
import { validateFusionPdb } from './fusion'
import { validateDomainReferencePdb } from './structureEvidence'

interface Props {
  pdb: string | null
  fullSequence: string
  domainALength: number
  linkerLength: number
  mode?: 'fusion' | 'reference'
  referenceColor?: string
  ariaLabel?: string
}

type Representation = 'cartoon' | 'sticks' | 'ball-stick' | 'spheres' | 'surface'
type ColourMode = 'domains' | 'confidence' | 'spectrum'
type CanvasTheme = 'dark' | 'light'

interface ViewerStyleOptions {
  representation: Representation
  colourMode: ColourMode
  mode: 'fusion' | 'reference'
  referenceColor: string
  domainALength: number
  linkerLength: number
  sequenceLength: number
}

const CONFIDENCE_COLOURS = {
  prop: 'b',
  gradient: 'linear',
  min: 0,
  max: 100,
  colors: ['#ff7d45', '#ffdb13', '#65cbf3', '#0053d6'],
}

function representationStyle(representation: Representation, colour: string | Exclude<ColorschemeSpec, string>): AtomStyleSpec {
  const colourSpec = typeof colour === 'string' ? { color: colour } : { colorscheme: colour }
  if (representation === 'sticks') return { stick: { ...colourSpec, radius: 0.22 } }
  if (representation === 'ball-stick') return {
    stick: { ...colourSpec, radius: 0.18 },
    sphere: { ...colourSpec, scale: 0.28 },
  }
  if (representation === 'spheres') return { sphere: { ...colourSpec, scale: 0.72 } }
  return { cartoon: colourSpec }
}

function domainSelections(options: ViewerStyleOptions): Array<{ selection: AtomSelectionSpec; color: string }> {
  if (options.mode === 'reference') return [{ selection: {}, color: options.referenceColor }]
  const linkerStart = options.domainALength + 1
  const linkerEnd = options.domainALength + options.linkerLength
  const selections: Array<{ selection: AtomSelectionSpec; color: string }> = [
    { selection: { resi: `1-${options.domainALength}` }, color: '#3acf78' },
    { selection: { resi: `${linkerEnd + 1}-${options.sequenceLength}` }, color: '#f66b62' },
  ]
  if (options.linkerLength > 0) selections.splice(1, 0, {
    selection: { resi: `${linkerStart}-${linkerEnd}` },
    color: '#ff4dba',
  })
  return selections
}

function applyViewerStyle(viewer: GLViewer, options: ViewerStyleOptions) {
  viewer.removeAllSurfaces()
  viewer.setStyle({}, {})
  const mappedColours = options.colourMode === 'confidence'
    ? CONFIDENCE_COLOURS
    : { prop: 'resi', gradient: 'roygb', min: 1, max: options.sequenceLength }

  if (options.representation === 'surface') {
    const surfaceSelections = options.colourMode === 'domains'
      ? domainSelections(options)
      : [{ selection: {}, color: '#69c6d5' }]
    for (const item of surfaceSelections) {
      const style: SurfaceStyleSpec = options.colourMode !== 'domains'
        ? { opacity: 0.84, colorscheme: mappedColours }
        : { opacity: 0.84, color: item.color }
      void viewer.addSurface('VDW', style, item.selection)
    }
    viewer.setStyle({}, { cartoon: { color: '#d5ded8', opacity: 0.32 } })
  } else if (options.colourMode === 'domains') {
    for (const item of domainSelections(options)) {
      viewer.setStyle(item.selection, representationStyle(options.representation, item.color))
    }
  } else if (options.colourMode === 'confidence') {
    viewer.setStyle({}, representationStyle(options.representation, CONFIDENCE_COLOURS))
  } else {
    viewer.setStyle({}, representationStyle(options.representation, mappedColours))
  }
  viewer.render()
}

function downloadViewerImage(viewer: GLViewer, filename: string) {
  const anchor = document.createElement('a')
  anchor.href = viewer.pngURI()
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
}

export default function FusionStructureViewer({
  pdb,
  fullSequence,
  domainALength,
  linkerLength,
  mode = 'fusion',
  referenceColor = '#55a7ff',
  ariaLabel = 'Predicted full fusion structure',
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const viewerRef = useRef<GLViewer | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [representation, setRepresentation] = useState<Representation>('cartoon')
  const [colourMode, setColourMode] = useState<ColourMode>(mode === 'fusion' ? 'domains' : 'spectrum')
  const [canvasTheme, setCanvasTheme] = useState<CanvasTheme>('dark')
  const [spinning, setSpinning] = useState(false)
  const [viewerReady, setViewerReady] = useState(0)

  useEffect(() => {
    const container = containerRef.current
    if (!container || !pdb) return
    let disposed = false
    let observer: ResizeObserver | null = null
    const load = async () => {
      try {
        if (mode === 'fusion') validateFusionPdb(pdb, fullSequence)
        else validateDomainReferencePdb(pdb, fullSequence, 'Domain')
        const mol = await import('3dmol')
        if (disposed) return
        container.replaceChildren()
        const viewer = mol.createViewer(container, { backgroundColor: canvasTheme === 'dark' ? '#0b1712' : '#f5f7f5' })
        viewer.addModel(pdb, 'pdb')
        viewerRef.current = viewer
        viewer.zoomTo()
        applyViewerStyle(viewer, {
          representation,
          colourMode,
          mode,
          referenceColor,
          domainALength,
          linkerLength,
          sequenceLength: fullSequence.length,
        })
        observer = new ResizeObserver(() => viewer.resize())
        observer.observe(container)
        setError(null)
        setViewerReady((value) => value + 1)
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : 'Could not display this structure.')
      }
    }
    void load()
    return () => {
      disposed = true
      observer?.disconnect()
      viewerRef.current?.spin(false)
      viewerRef.current = null
      container.replaceChildren()
    }
    // Viewer creation is tied to the coordinate record. Display controls are applied below without rebuilding it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ariaLabel, domainALength, fullSequence, linkerLength, mode, pdb, referenceColor])

  useEffect(() => {
    const viewer = viewerRef.current
    if (!viewer) return
    viewer.setBackgroundColor(canvasTheme === 'dark' ? '#0b1712' : '#f5f7f5', 1)
    applyViewerStyle(viewer, {
      representation,
      colourMode,
      mode,
      referenceColor,
      domainALength,
      linkerLength,
      sequenceLength: fullSequence.length,
    })
  }, [canvasTheme, colourMode, domainALength, fullSequence.length, linkerLength, mode, referenceColor, representation, viewerReady])

  useEffect(() => {
    viewerRef.current?.spin(spinning ? 'y' : false, 0.7)
    return () => viewerRef.current?.spin(false)
  }, [spinning, viewerReady])

  if (!pdb) {
    return (
      <div className="structure-empty">
        <strong>{mode === 'fusion' ? 'No full-fusion structure loaded' : 'No reference structure loaded'}</strong>
        <p>{mode === 'fusion'
          ? 'Export the selected full-fusion FASTA, predict that whole sequence with AlphaFold/ColabFold, then load its single-chain PDB here. No coordinates are invented by this page.'
          : 'Load a single-chain PDB whose C-alpha sequence exactly matches this entered domain. The application does not guess a reference structure from a name.'}</p>
      </div>
    )
  }

  return (
    <div className="embedded-structure-viewer">
      <div className="structure-viewer-toolbar" aria-label="Structure display controls">
        <label>
          Representation
          <select aria-label="Structure representation" value={representation}
            onChange={(event) => setRepresentation(event.target.value as Representation)}>
            <option value="cartoon">Cartoon</option>
            <option value="sticks">Sticks</option>
            <option value="ball-stick">Ball and stick</option>
            <option value="spheres">Space-filling spheres</option>
            <option value="surface">Molecular surface</option>
          </select>
        </label>
        <label>
          Colour
          <select aria-label="Structure colour scheme" value={colourMode}
            onChange={(event) => setColourMode(event.target.value as ColourMode)}>
            <option value="domains">{mode === 'fusion' ? 'Domains and linker' : 'Reference colour'}</option>
            <option value="confidence">B-factor / pLDDT</option>
            <option value="spectrum">Residue spectrum</option>
          </select>
        </label>
        <label>
          Canvas
          <select aria-label="Viewer background" value={canvasTheme}
            onChange={(event) => setCanvasTheme(event.target.value as CanvasTheme)}>
            <option value="dark">Dark</option>
            <option value="light">Light</option>
          </select>
        </label>
        <button type="button" aria-pressed={spinning} onClick={() => setSpinning((value) => !value)}>
          {spinning ? <Pause size={15} /> : <Play size={15} />} {spinning ? 'Stop spin' : 'Spin'}
        </button>
        <button type="button" onClick={() => { viewerRef.current?.zoomTo(); viewerRef.current?.render() }}>
          <RotateCcw size={15} /> Reset view
        </button>
        <button type="button" onClick={() => viewerRef.current && downloadViewerImage(viewerRef.current, mode === 'fusion' ? 'linkerforge-fusion.png' : 'linkerforge-reference.png')}>
          <Camera size={15} /> Save PNG
        </button>
      </div>
      <p className="structure-viewer-hint">Drag to rotate · scroll to zoom · right-drag to translate. Confidence colouring reads the PDB B-factor field; interpret it as pLDDT only for compatible prediction files.</p>
      {error && <p role="alert" className="structure-error">{error}</p>}
      <div ref={containerRef} className={`fusion-3d-canvas canvas-${canvasTheme}`} aria-label={ariaLabel} />
    </div>
  )
}
