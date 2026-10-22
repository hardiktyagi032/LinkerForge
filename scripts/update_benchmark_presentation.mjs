#!/usr/bin/env node
/** Build the complete verified public-acceptance section and update the project deck. */

import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SKILL = "C:\\Users\\HARDIK\\.codex\\plugins\\cache\\openai-primary-runtime\\presentations\\26.1020.11127\\skills\\presentations";
const PYTHON = "C:\\Users\\HARDIK\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe";
const RUNTIME_NODE_MODULES = "C:\\Users\\HARDIK\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules";
const DEFAULT_BASE = path.join(ROOT, "deliverables", "LinkerForge_Detailed_Architecture_Data_Provenance_4_Presenters_Final.pptx");
const DEFAULT_FINAL = path.join(ROOT, "deliverables", "LinkerForge_Detailed_Architecture_Data_Provenance_4_Presenters_Multi_Protein_Benchmark.pptx");
const BUILD = path.join(ROOT, ".codex", "presentation-build", "multi-protein-benchmark");
const CANDIDATE = path.join(BUILD, "candidate-multi-protein-benchmark.pptx");
const CANDIDATE_REPORT = path.join(BUILD, "verified-public-acceptance-run.md");
const PREVIEW_DIR = path.join(BUILD, "previews");
const ARTIFACT_TOOL = "C:\\Users\\HARDIK\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\@oai\\artifact-tool\\dist\\artifact_tool.mjs";

process.env.RUNTIME_NODE_MODULES ??= RUNTIME_NODE_MODULES;
process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES ??= RUNTIME_NODE_MODULES;

const { FileBlob, PresentationFile } = await import(pathToFileURL(ARTIFACT_TOOL).href);
const utils = await import(pathToFileURL(path.join(SKILL, "container_tools", "artifact_tool_utils.mjs")).href);
const { applyPresentationChartFont, finalizePresentation } = utils;

const C = {
  bg: "091A15", paper: "102720", paperAlt: "143128", ink: "F4F7F5", muted: "AFC0B8", faint: "29433A",
  cyan: "3FC6D6", cyanDark: "167D89", magenta: "E84AAB", green: "2DBD73",
  yellow: "F1C84B", red: "E46760", blue: "4E9BEC", violet: "A88CEB",
};
const FONT = "Arial";
const MONO = "Cascadia Mono";
const W = 1280;

function parseArgs() {
  const parsed = {};
  for (let i = 2; i < process.argv.length; i += 2) parsed[process.argv[i].replace(/^--/, "")] = process.argv[i + 1];
  if (!parsed.summary || !parsed.progress) {
    throw new Error("Required: --summary PATH --progress PATH [--base PATH] [--output PATH] [--report PATH]");
  }
  const summary = path.resolve(parsed.summary);
  return {
    summary,
    progress: path.resolve(parsed.progress),
    base: path.resolve(parsed.base ?? DEFAULT_BASE),
    output: path.resolve(parsed.output ?? DEFAULT_FINAL),
    report: path.resolve(parsed.report ?? path.join(path.dirname(summary), "verified_public_acceptance_run.md")),
  };
}

function shape(slide, geometry, x, y, w, h, fill = "none", lineFill = "none", lineWidth = 0, radius) {
  return slide.shapes.add({
    geometry,
    position: { left: x, top: y, width: w, height: h },
    fill,
    line: { style: "solid", fill: lineFill, width: lineWidth },
    ...(radius ? { borderRadius: radius } : {}),
  });
}

function text(slide, value, x, y, w, h, opts = {}) {
  const box = shape(slide, "textbox", x, y, w, h, opts.fill ?? "none", opts.lineFill ?? "none", opts.lineWidth ?? 0);
  box.text = String(value);
  box.text.style = {
    typeface: opts.typeface ?? FONT,
    fontSize: opts.fontSize ?? 20,
    color: opts.color ?? C.ink,
    bold: opts.bold ?? false,
    italic: opts.italic ?? false,
    alignment: opts.alignment ?? "left",
    verticalAlignment: opts.verticalAlignment ?? "top",
    autoFit: opts.autoFit ?? "shrinkText",
    ...(opts.letterSpacing !== undefined ? { letterSpacing: opts.letterSpacing } : {}),
  };
  if (opts.margin !== undefined) box.text.margin = opts.margin;
  return box;
}

function base(slide, number, section, presenter, source) {
  slide.background.fill = C.bg;
  shape(slide, "rect", 0, 0, W, 8, C.cyan, "none", 0);
  text(slide, "LINKERFORGE", 54, 24, 180, 18, { fontSize: 12, bold: true, color: C.cyan, letterSpacing: 1.5 });
  text(slide, section.toUpperCase(), 234, 24, 650, 18, { fontSize: 12, bold: true, color: C.muted, letterSpacing: 1.2 });
  text(slide, source, 54, 684, 1000, 16, { fontSize: 9, color: C.muted });
  text(slide, `${presenter}  ·  ${String(number).padStart(2, "0")}`, 1080, 681, 150, 18, { fontSize: 10, bold: true, color: C.muted, alignment: "right" });
}

function title(slide, heading, subtitle) {
  text(slide, heading, 54, 60, 1172, 58, { fontSize: 34, bold: true });
  text(slide, subtitle, 56, 120, 1160, 42, { fontSize: 17, color: C.muted });
}

function note(slide, presenter, talk, sources) {
  slide.speakerNotes.text = [
    `Presenter: ${presenter}`, "", talk, "", "Sources and evidence:", ...sources.map((source) => `- ${source}`),
  ].join("\n");
  slide.speakerNotes.setVisible(true);
}

function styleTable(table, rows, columns, fontSize = 11) {
  table.cells.block({ row: 0, column: 0, rowCount: 1, columnCount: columns }).assign({
    fill: C.cyanDark,
    textStyle: { typeface: FONT, fontSize: 12, bold: true, color: "FFFFFF" },
    verticalAlignment: "middle",
  });
  for (let row = 1; row < rows; row += 1) {
    table.cells.block({ row, column: 0, rowCount: 1, columnCount: columns }).assign({
      fill: row % 2 === 0 ? C.paperAlt : C.paper,
      textStyle: { typeface: FONT, fontSize, color: C.ink },
      verticalAlignment: "middle",
    });
  }
  table.borders.assign({ style: "solid", fill: C.faint, width: 1 });
}

function displayPair(pair) {
  return ({ "1UBQ_2GB1": "Ubiquitin–GB1", "1CRN_4PTI": "Crambin–BPTI", "1PGA_1LMB": "Protein G–repressor" })[pair] ?? pair;
}

function value(number, digits = 1) {
  return number === null || number === undefined ? "—" : Number(number).toFixed(digits);
}

function chartValue(number, digits = 2) {
  return Number(Number(number).toFixed(digits));
}

function displaySequence(sequence) {
  return sequence ? sequence : "— direct fusion —";
}

function markdownCell(input) {
  return String(input ?? "—").replaceAll("|", "\\|").replaceAll("\n", " ");
}

async function sha256File(file) {
  return crypto.createHash("sha256").update(await fs.readFile(file)).digest("hex");
}

async function pathExists(file) {
  try {
    await fs.access(file);
    return true;
  } catch {
    return false;
  }
}

async function atomicJson(file, object) {
  const temporary = `${file}.tmp`;
  await fs.writeFile(temporary, `${JSON.stringify(object, null, 2)}\n`, "utf8");
  await fs.rename(temporary, file);
}

async function replaceExact(presentation, replacements) {
  const inspected = await presentation.inspect({
    select: "$.slides[*]",
    include: ["id", "index", "elements.id", "elements.text"],
  });
  const found = new Map();
  for (const record of inspected.records) {
    for (const element of record.elements ?? []) {
      if (typeof element.text !== "string") continue;
      for (const [before, after] of Object.entries(replacements)) {
        if (element.text !== before) continue;
        presentation.resolve(element.id).text = after;
        found.set(before, (found.get(before) ?? 0) + 1);
      }
    }
  }
  const missing = Object.keys(replacements).filter((key) => !found.has(key));
  if (missing.length) throw new Error(`Expected source-deck text was not found: ${missing.join(" | ")}`);
}

function metricCard(slide, x, y, w, label, valueText, explanation, color) {
  shape(slide, "roundRect", x, y, w, 154, C.paper, C.faint, 1, "rounded-lg");
  shape(slide, "rect", x, y, 6, 154, color, "none", 0);
  text(slide, label.toUpperCase(), x + 22, y + 18, w - 42, 20, { fontSize: 12, bold: true, color });
  text(slide, valueText, x + 22, y + 48, w - 42, 35, { fontSize: 25, bold: true });
  text(slide, explanation, x + 22, y + 91, w - 42, 48, { fontSize: 13, color: C.muted });
}

async function rebuildSourceCharts(presentation, originalSlides) {
  const inspected = await presentation.inspect({
    select: "$.slides[*]",
    include: ["index", "elements.id", "elements.kind"],
  });
  const sourceChartIds = inspected.records
    .filter((record) => record.index === 17 || record.index === 18)
    .flatMap((record) => (record.elements ?? []).filter((element) => element.kind === "chart").map((element) => element.id));
  if (sourceChartIds.length !== 2) throw new Error(`Expected two source charts to rebuild; found ${sourceChartIds.length}`);
  presentation.delete(sourceChartIds);

  const regional = originalSlides[17].charts.add("bar", {
    position: { left: 667, top: 172, width: 548, height: 350 },
    title: "Regional mean pLDDT (0–100)",
    categories: ["Domain A", "Whole chain", "Domain B", "Linker"],
    series: [{ name: "Mean pLDDT", values: [91.10, 81.74, 76.90, 37.73], fill: C.cyanDark }],
    hasLegend: false,
    dataLabels: { showValue: true, position: "outEnd", textStyle: { fontSize: 12, fill: C.ink } },
    xAxis: { title: { text: "Region", textStyle: { fontSize: 12, fill: C.muted } }, textStyle: { fontSize: 12, fill: C.ink } },
    yAxis: { min: 0, max: 100, majorUnit: 20, title: { text: "pLDDT", textStyle: { fontSize: 12, fill: C.muted } }, textStyle: { fontSize: 11, fill: C.muted }, majorGridlines: { style: "solid", fill: C.faint, width: 1 } },
    titleTextStyle: { fontSize: 16, bold: true, fill: C.ink },
  });
  applyPresentationChartFont(regional, { fontFamily: FONT });

  const comparison = originalSlides[18].charts.add("bar", {
    position: { left: 57, top: 165, width: 1164, height: 398 },
    title: "Overall and linker-region pLDDT by construct",
    categories: ["Direct", "GGGGS", "GS10", "(GGGGS)3", "WALDO12", "BIRD18", "EAAAK15"],
    series: [
      { name: "Whole chain", values: [88.25, 87.03, 81.74, 82.75, 84.09, 80.21, 87.88], fill: C.cyanDark },
      { name: "Linker region", values: [0, 48.57, 37.73, 38.99, 44.42, 44.87, 50.88], fill: C.magenta },
    ],
    hasLegend: true,
    legend: { position: "bottom", textStyle: { fontSize: 12, fill: C.ink } },
    dataLabels: { showValue: true, position: "outEnd", textStyle: { fontSize: 10, fill: C.ink } },
    xAxis: { textStyle: { fontSize: 11, fill: C.ink } },
    yAxis: { min: 0, max: 100, majorUnit: 20, title: { text: "pLDDT", textStyle: { fontSize: 12, fill: C.muted } }, textStyle: { fontSize: 11, fill: C.muted }, majorGridlines: { style: "solid", fill: C.faint, width: 1 } },
    titleTextStyle: { fontSize: 16, bold: true, fill: C.ink },
  });
  applyPresentationChartFont(comparison, { fontFamily: FONT });
}

function resultRows(records) {
  return [["Linker condition", "Sequence", "L", "Fusion\npLDDT", "Linker\npLDDT", "pTM", "Cross-domain\nPAE (Å)", "Global\nrank"], ...records.map((row) => [
    row.linker_id,
    displaySequence(row.linker_sequence),
    String(row.linker_length),
    value(row.mean_plddt),
    value(row.linker_mean_plddt),
    value(row.ptm, 2),
    value(row.mean_cross_domain_pae_angstrom),
    String(row.descriptive_mean_plddt_rank),
  ])];
}

function addPairSlide(presentation, number, pair, rows, summaryPath) {
  const slide = presentation.slides.add();
  base(slide, number, "Verified public acceptance run", "Presenter 2", `Complete rank-1 results for ${pair}; all seven matched conditions retained`);
  title(slide, `${displayPair(pair)}: every linker condition`, `${rows[0].domain_sources.join(" + ")} · five AlphaFold2-ptm models per construct · rank 1 reported`);
  const values = resultRows(rows);
  const table = slide.tables.add({
    rows: values.length,
    columns: 8,
    left: 48,
    top: 172,
    width: 1184,
    height: 392,
    columnWidths: [168, 264, 52, 116, 116, 82, 156, 82],
    values,
  });
  styleTable(table, values.length, 8, 10.5);
  shape(slide, "roundRect", 54, 588, 1172, 66, C.paper, C.faint, 1, "rounded-lg");
  text(slide, "Reading the table", 78, 604, 175, 22, { fontSize: 14, bold: true, color: C.cyan });
  text(slide, "Global rank is post-hoc mean pLDDT order across this 21-construct panel. It is not a linker-success rank; lower cross-domain PAE means more confident relative placement.", 251, 599, 946, 43, { fontSize: 15, bold: true });
  note(slide, "Presenter 2 (major)", `Present all seven ${displayPair(pair)} conditions. Compare the same metrics across the row, but do not call the top pLDDT row the best biological linker. The direct fusion is a control with no linker-residue pLDDT.`, [summaryPath, ...rows[0].domain_sources]);
  return slide;
}

function buildReport(summary, manifest, summaryPath) {
  const lines = [
    "# Verified public acceptance run",
    "",
    `Generated: ${summary.created_at}`,
    "",
    "## What was run",
    "",
    `- ${summary.domain_pair_count} public protein-domain pairs, ${summary.construct_count} complete fusion constructs, ${summary.models_per_construct} AlphaFold2-ptm models per construct, and ${summary.rankable_model_count} rankable models in total.`,
    `- Predictor: ${manifest.planned_settings.predictor}; MSA mode: ${manifest.planned_settings.msa_mode}; templates: ${manifest.planned_settings.templates}; seed set: ${manifest.planned_settings.seeds.join(", ")}.`,
    "- Every construct is reported. Sorting by mean pLDDT was performed only after prediction and is descriptive.",
    `- Data firewall: public sequences only = ${manifest.data_firewall.public_sequences_only}; protected benchmark labels read = ${manifest.data_firewall.protected_benchmark_labels_read}; used for training = ${manifest.data_firewall.used_for_model_training}.`,
    "- OpenMM, Rosetta, ensemble agreement, reference-domain lDDT/TM-score, automatic site mapping, DSSP, and post-OpenMM change analysis were not run in this acceptance panel.",
    "",
    "## Complete result matrix",
    "",
    "| Global rank | Protein pair | Construct | Linker | Sequence | Length | Fusion pLDDT | Domain A pLDDT | Linker pLDDT | Domain B pLDDT | pTM | Cross-domain PAE (Å) | Rank-1 model | PDB SHA-256 | Score SHA-256 |",
    "|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
  ];
  for (const row of [...summary.records].sort((a, b) => a.descriptive_mean_plddt_rank - b.descriptive_mean_plddt_rank)) {
    lines.push(`| ${row.descriptive_mean_plddt_rank} | ${markdownCell(displayPair(row.domain_pair))} | ${markdownCell(row.construct_id)} | ${markdownCell(row.linker_id)} | ${markdownCell(displaySequence(row.linker_sequence))} | ${row.linker_length} | ${value(row.mean_plddt)} | ${value(row.domain_a_mean_plddt)} | ${value(row.linker_mean_plddt)} | ${value(row.domain_b_mean_plddt)} | ${value(row.ptm, 2)} | ${value(row.mean_cross_domain_pae_angstrom)} | ${markdownCell(row.rank_1_model)} | \`${row.pdb_sha256}\` | \`${row.score_json_sha256}\` |`);
  }
  lines.push(
    "", "## Metric interpretation", "",
    `- **Fusion pLDDT:** ${summary.metric_interpretation.mean_plddt}`,
    `- **Linker pLDDT:** ${summary.metric_interpretation.linker_mean_plddt}`,
    `- **pTM:** ${summary.metric_interpretation.ptm}`,
    `- **Cross-domain PAE:** ${summary.metric_interpretation.mean_cross_domain_pae_angstrom}`,
    "", "## Provenance and reproducibility", "",
    `- Summary: \`${summaryPath}\``,
    `- Panel manifest: \`${summary.provenance.panel_manifest}\` (SHA-256 \`${summary.provenance.panel_manifest_sha256}\`)`,
    `- Existing reference-pair summary: \`${summary.provenance.existing_summary}\` (SHA-256 \`${summary.provenance.existing_summary_sha256}\`)`,
    `- Repository commit recorded by summarizer: \`${summary.provenance.commit_sha}\``,
    `- Summary schema: \`${summary.schema_version}\``,
    "- Each result row retains the exact rank-1 PDB and score-JSON path plus SHA-256 hashes.",
    "", "## Claim boundary", "", summary.claim_boundary,
    "", "## Limitations", "", ...summary.limitations.map((item) => `- ${item}`),
    "", "## Presentation rule", "",
    "The presentation may show the highest observed confidence example only as a transparent implementation example. It must not describe that construct as the best linker, a compatibility probability, a biological winner, or an experimentally validated fusion.",
    "",
  );
  return lines.join("\n");
}

async function main() {
  const input = parseArgs();
  if (await pathExists(input.output)) throw new Error(`Refusing to overwrite completed presentation: ${input.output}`);
  if (await pathExists(input.report)) throw new Error(`Refusing to overwrite completed acceptance report: ${input.report}`);

  const summary = JSON.parse(await fs.readFile(input.summary, "utf8"));
  if (summary.status !== "complete" || summary.construct_count !== 21 || summary.rankable_model_count !== 105) {
    throw new Error("The presentation requires a complete 21-construct, 105-model summary");
  }
  if (summary.records.some((row) => typeof row.linker_sequence !== "string")) {
    throw new Error("Every acceptance record must retain its exact linker sequence");
  }
  const manifest = JSON.parse(await fs.readFile(summary.provenance.panel_manifest, "utf8"));
  if (manifest.record_count !== 14 || manifest.data_firewall.protected_benchmark_labels_read !== false) {
    throw new Error("Unexpected multi-pair manifest or data-firewall state");
  }

  await fs.mkdir(BUILD, { recursive: true });
  await fs.mkdir(PREVIEW_DIR, { recursive: true });
  await fs.mkdir(path.dirname(input.output), { recursive: true });
  await fs.mkdir(path.dirname(input.report), { recursive: true });

  const presentation = await PresentationFile.importPptx(await FileBlob.load(input.base));
  if (presentation.slides.items.length !== 25) throw new Error(`Expected 25 source slides; found ${presentation.slides.items.length}`);
  const originalSlides = [...presentation.slides.items];

  await replaceExact(presentation, {
    "Computational prototype · verified results only": "Computational prototype · matched public-sequence evidence",
    "PUBLIC ACCEPTANCE CONSTRUCT": "PUBLIC ACCEPTANCE PANEL · 3 PAIRS",
    "A 32-minute briefing with clear handoffs": "A 40-minute briefing with clear handoffs",
    "13 min  ·  Slides 13–20": "19 min  ·  Slides 13–20, 23–30",
    "4 min  ·  Slides 21–25": "6 min  ·  Slides 21–22, 31–34",
    "Verified public acceptance run": "Verified acceptance run: reference pair",
    "Matched structural sensitivity panel": "Reference-pair structural sensitivity panel",
    "142-aa public acceptance + 7-construct panel": "3 public pairs · 21 constructs",
    "35 rankable models": "105 rankable models",
    "Presenter 4  ·  23": "Presenter 4  ·  32",
    "Presenter 4  ·  24": "Presenter 4  ·  33",
    "Presenter 4  ·  25": "Presenter 4  ·  34",
    "LinkerForge links exact candidate sequences to matched structural evidence and provenance.": "LinkerForge links exact candidate sequences to matched structural evidence and provenance across three public pairs.",
    "Verified local runs establish execution, not biological success or optimality.": "The 21-construct public panel verifies execution and traceability, not biological success or optimality.",
  });
  await rebuildSourceCharts(presentation, originalSlides);

  originalSlides[17].speakerNotes.text += `\n\nUpdated acceptance context: this slide is the original Ubiquitin–GB1 reference-pair run. Slides 23–31 report the complete three-pair panel. Source: ${input.summary}`;
  originalSlides[19].speakerNotes.text += `\n\nUpdated execution count: 21 constructs and 105 rankable AlphaFold2-ptm models after the complete matched public panel. Source: ${input.summary}`;
  originalSlides[24].speakerNotes.text += `\n\nUpdated conclusion evidence: ${input.summary}`;

  const inserted = [];
  const slide23 = presentation.slides.add();
  inserted.push(slide23);
  base(slide23, 23, "Verified public acceptance run", "Presenter 2", "Public-sequence panel manifest + versioned comparison schema; protected labels were not read");
  title(slide23, "Acceptance run design and verification gates", "Matched settings across three short public domain pairs; every condition is retained");
  metricCard(slide23, 54, 186, 265, "Protein pairs", "3 public pairs", "Ubiquitin–GB1, crambin–BPTI, and protein G–repressor", C.blue);
  metricCard(slide23, 335, 186, 265, "Constructs", "21 complete fusions", "Seven matched linker conditions per pair, including direct fusion", C.cyan);
  metricCard(slide23, 616, 186, 265, "Structure models", "105 rankable models", "Five AlphaFold2-ptm models per construct; rank 1 summarized", C.magenta);
  metricCard(slide23, 897, 186, 329, "Firewall", "Protected labels: not read", "Public sequences only; no training or threshold selection", C.green);
  const gateRows = [
    ["Gate", "Recorded evidence", "Outcome"],
    ["Matched predictor settings", "AF2-ptm · seed 0 · templates off · same MSA mode", "Pass"],
    ["Completeness", "21/21 constructs · 105/105 rankable models", "Pass"],
    ["Sequence identity", "Rank-1 PDB sequence checked against immutable input", "Pass"],
    ["Traceability", "PDB + score JSON paths and SHA-256 per result", "Pass"],
    ["Claim firewall", "No compatibility, function, stability, or optimality label", "Enforced"],
  ];
  const gates = slide23.tables.add({ rows: gateRows.length, columns: 3, left: 54, top: 373, width: 1172, height: 250, columnWidths: [255, 700, 217], values: gateRows });
  styleTable(gates, gateRows.length, 3, 12);
  note(slide23, "Presenter 2 (major)", "Start the expanded acceptance section with what was actually run and what was deliberately excluded. The completion count verifies pipeline execution and traceability only; it does not validate a compatibility ranker.", [input.summary, summary.provenance.panel_manifest]);

  const slide24 = presentation.slides.add();
  inserted.push(slide24);
  base(slide24, 24, "Matched public panel", "Presenter 2", "Rank-1 AlphaFold2-ptm confidence; descriptive top linker-containing row per pair; all 21 constructs retained");
  title(slide24, "Three protein pairs, one matched evaluation design", "Highest observed confidence examples are presentation aids—not biological winners");
  const perPair = summary.descriptive_top_per_domain_pair;
  const chart = slide24.charts.add("bar", {
    position: { left: 56, top: 172, width: 1168, height: 365 },
    title: "Descriptive top linker-containing construct per pair",
    categories: perPair.map((row) => displayPair(row.domain_pair)),
    series: [
      { name: "Whole fusion pLDDT", values: perPair.map((row) => chartValue(row.mean_plddt)), fill: C.cyanDark },
      { name: "Linker pLDDT", values: perPair.map((row) => chartValue(row.linker_mean_plddt)), fill: C.magenta },
    ],
    hasLegend: true,
    legend: { position: "bottom", textStyle: { fontSize: 12, fill: C.ink } },
    dataLabels: { showValue: true, position: "outEnd", textStyle: { fontSize: 11, fill: C.ink } },
    xAxis: { textStyle: { fontSize: 12, fill: C.ink } },
    yAxis: { min: 0, max: 100, majorUnit: 20, title: { text: "pLDDT", textStyle: { fontSize: 12, fill: C.muted } }, textStyle: { fontSize: 11, fill: C.muted }, majorGridlines: { style: "solid", fill: C.faint, width: 1 } },
    titleTextStyle: { fontSize: 16, bold: true, fill: C.ink },
  });
  applyPresentationChartFont(chart, { fontFamily: FONT });
  shape(slide24, "roundRect", 56, 564, 1168, 82, C.paper, C.faint, 1, "rounded-lg");
  text(slide24, "Interpretation boundary", 80, 579, 212, 24, { fontSize: 15, bold: true, color: C.yellow });
  text(slide24, "pLDDT is model confidence in local coordinates. It is not a compatibility probability, a stability measurement, or evidence that a linker will express or function.", 289, 578, 910, 49, { fontSize: 17, bold: true });
  note(slide24, "Presenter 2 (major)", "Use the chart to show that the same pipeline ran on three distinct public pairs. State that each bar is the top linker-containing row observed after prediction, while the next three slides preserve every condition.", [input.summary, "https://www.nature.com/articles/s41586-021-03819-2", "https://www.nature.com/articles/s41592-022-01488-1"]);

  const grouped = Object.fromEntries([...new Set(summary.records.map((row) => row.domain_pair))].sort().map((pair) => [pair, summary.records.filter((row) => row.domain_pair === pair)]));
  for (const [offset, pair] of ["1UBQ_2GB1", "1CRN_4PTI", "1PGA_1LMB"].entries()) {
    if (!grouped[pair] || grouped[pair].length !== 7) throw new Error(`Expected seven records for ${pair}`);
    inserted.push(addPairSlide(presentation, 25 + offset, pair, grouped[pair], input.summary));
  }

  const slide28 = presentation.slides.add();
  inserted.push(slide28);
  base(slide28, 28, "Descriptive examples", "Presenter 2", "Sorted after prediction by rank-1 whole-fusion pLDDT; not an independent test or biological selection rule");
  title(slide28, "Highest observed structure-confidence examples", "Complete JSON, CSV, and slides 25–27 retain every construct, metric, file hash, and limitation");
  const top = summary.descriptive_top_by_mean_plddt;
  const topRows = [["Rank", "Protein pair", "Linker", "Fusion\npLDDT", "Linker\npLDDT", "pTM", "Cross-domain\nPAE (Å)"], ...top.map((row) => [
    String(row.descriptive_mean_plddt_rank), displayPair(row.domain_pair), row.linker_id,
    value(row.mean_plddt), value(row.linker_mean_plddt), value(row.ptm, 2), value(row.mean_cross_domain_pae_angstrom),
  ])];
  const topTable = slide28.tables.add({ rows: topRows.length, columns: 7, left: 54, top: 169, width: 1172, height: 395, columnWidths: [70, 226, 190, 132, 132, 104, 198], values: topRows });
  styleTable(topTable, topRows.length, 7, 10.5);
  shape(slide28, "roundRect", 54, 588, 1172, 66, C.paper, C.faint, 1, "rounded-lg");
  text(slide28, "Demo use", 78, 604, 115, 22, { fontSize: 14, bold: true, color: C.cyan });
  text(slide28, "Show rank 1 as the cleanest public execution example, then immediately display linker pLDDT, pTM, and cross-domain PAE so uncertainty remains visible.", 192, 599, 1005, 43, { fontSize: 16, bold: true });
  note(slide28, "Presenter 2 (major)", "Read the first row as the highest mean pLDDT observed in this small panel, not as the best linker. The ranking was not preregistered and cannot support an optimality claim.", [input.summary]);

  const slide29 = presentation.slides.add();
  inserted.push(slide29);
  base(slide29, 29, "Interpretation", "Presenter 2", "Metric definitions are taken from the versioned comparison JSON and AlphaFold/ColabFold output semantics");
  title(slide29, "What the structure confidence does—and does not—mean", "All four values come from ColabFold/AlphaFold2-ptm outputs, not from the proposed LinkerForge ranker");
  metricCard(slide29, 54, 184, 560, "Fusion mean pLDDT", "Local-coordinate confidence", "Average over the complete fusion. High values do not establish function, expression, stability, or correct domain orientation.", C.cyan);
  metricCard(slide29, 666, 184, 560, "Linker mean pLDDT", "Inserted-residue confidence", "Low values may be consistent with flexibility, but they do not prove flexibility or incompatibility.", C.magenta);
  metricCard(slide29, 54, 366, 560, "pTM", "Global topology confidence", "A model-level AlphaFold estimate. It is not a linker-specific success probability.", C.blue);
  metricCard(slide29, 666, 366, 560, "Cross-domain PAE", "Relative-placement uncertainty", "Mean bidirectional Domain A↔Domain B PAE. Lower values imply more confident relative placement, not validated activity.", C.yellow);
  shape(slide29, "roundRect", 54, 558, 1172, 86, C.paper, C.red, 1, "rounded-lg");
  text(slide29, "Permitted claim", 78, 576, 160, 22, { fontSize: 15, bold: true, color: C.red });
  text(slide29, summary.claim_boundary, 240, 570, 955, 51, { fontSize: 17, bold: true });
  note(slide29, "Presenter 2 (major)", "This is the slide to use if someone asks which model produced the confidence. Every displayed confidence metric comes from the AlphaFold2-ptm/ColabFold structure prediction. The proposed compatibility ranker remains scientifically untrained.", [input.summary, "https://www.nature.com/articles/s41586-021-03819-2", "https://www.nature.com/articles/s41592-022-01488-1"]);

  const slide30 = presentation.slides.add();
  inserted.push(slide30);
  base(slide30, 30, "Reproducibility", "Presenter 2", "Versioned JSON + CSV + exact PDB/score files + SHA-256 hashes; generated only after full-panel completion");
  title(slide30, "Acceptance evidence can be traced back to every file", "The slide deck is a view of the run artifacts—not the sole scientific record");
  const trail = [
    ["01", "Immutable inputs", "panel.fasta + panel_manifest.json", "Sequence hashes, public sources, matched settings"],
    ["02", "Prediction outputs", "105 score JSON files + 105 PDB models", "Five models per construct; rank-1 path retained"],
    ["03", "Versioned summary", "three_pair_comparison.json + .csv", "All 21 rows, metric meanings, limitations"],
    ["04", "Integrity", "Per-row PDB and score SHA-256", "Detects file substitution after reporting"],
    ["05", "Presentation", "Editable charts, tables, and speaker notes", "All numbers derived from the JSON summary"],
  ];
  for (const [i, [number, heading, artifact, meaning]] of trail.entries()) {
    const y = 172 + i * 89;
    shape(slide30, "roundRect", 54, y, 1172, 72, i % 2 ? C.paperAlt : C.paper, C.faint, 1, "rounded-lg");
    shape(slide30, "ellipse", 72, y + 15, 42, 42, i === 4 ? C.magenta : C.cyan, "none", 0);
    text(slide30, number, 72, y + 23, 42, 22, { fontSize: 12, bold: true, color: C.bg, alignment: "center" });
    text(slide30, heading, 136, y + 13, 215, 24, { fontSize: 17, bold: true });
    text(slide30, artifact, 360, y + 12, 430, 26, { fontSize: 15, bold: true, typeface: MONO, color: C.cyan });
    text(slide30, meaning, 807, y + 11, 388, 46, { fontSize: 14, color: C.muted });
  }
  note(slide30, "Presenter 2 (major)", "Use this slide to demonstrate provenance. The Markdown acceptance report contains the complete matrix; the JSON remains the machine-readable authority; the CSV supports analysis; hashes bind each row to its PDB and score JSON.", [input.summary, input.report, summary.provenance.panel_manifest]);

  const slide31 = presentation.slides.add();
  inserted.push(slide31);
  base(slide31, 31, "Future structural validation", "Presenter 4", "Deferred by decision; not executed by this acceptance run; full protocols are documented in the future roadmap");
  title(slide31, "Deferred analyses and why they remain useful", "These methods add orthogonal evidence later; none can retroactively turn this panel into biological validation");
  const futureRows = [
    ["Deferred method", "Why it is needed", "How it would be run later"],
    ["Ensemble agreement", "Separates one-model confidence from repeatability", "Compare seeds/models and report residue- and domain-level dispersion"],
    ["Reference lDDT / TM-score", "Tests domain preservation beyond RMSD", "Align each predicted domain to the sequence-matched PDB reference"],
    ["Automatic functional-site mapping", "Checks whether protected sites remain spatially accessible", "Map curated residues; calculate exposure, occlusion, and linker proximity"],
    ["DSSP", "Tracks secondary-structure changes near junctions", "Run DSSP on references and predictions; compare junction windows"],
    ["Post-OpenMM change analysis", "Measures drift from the starting prediction", "Compare minimized/replicated trajectories with the same structural metrics"],
    ["Production OpenMM", "Tests longer-timescale mechanical stability", "Pre-register protocol; run replicated GPU trajectories only after resource approval"],
  ];
  const future = slide31.tables.add({ rows: futureRows.length, columns: 3, left: 50, top: 164, width: 1180, height: 454, columnWidths: [260, 420, 500], values: futureRows });
  styleTable(future, futureRows.length, 3, 10.5);
  shape(slide31, "roundRect", 50, 631, 1180, 32, C.paper, C.yellow, 1, "rounded-lg");
  text(slide31, "OpenMM remains on hold. Rosetta and independent predictor families also remain future integrations; no hidden substitute is claimed.", 70, 637, 1140, 20, { fontSize: 13, bold: true, alignment: "center" });
  note(slide31, "Presenter 4 (minor)", "Explain each deferred method as a future evidence layer, not a missing red failure. Production OpenMM is intentionally on hold. Rosetta requires a licensed installation, and other structure-model families require pinned matched environments.", [path.join(ROOT, "docs", "FUTURE_STRUCTURAL_VALIDATION_ROADMAP_2026-10-21.md")]);

  const slideInventory = await presentation.inspect({ select: "$.slides[*]", include: ["id", "index"] });
  const slideIds = slideInventory.records.map((record) => record.id);
  if (slideIds.length !== 34) throw new Error(`Expected 34 slides before reorder; found ${slideIds.length}`);
  presentation.slides.reorder([
    ...slideIds.slice(0, 22),
    ...slideIds.slice(25),
    ...slideIds.slice(22, 25),
  ]);

  await fs.writeFile(CANDIDATE_REPORT, buildReport(summary, manifest, input.summary), "utf8");
  await (await PresentationFile.exportPptx(presentation)).save(CANDIDATE);
  const result = await finalizePresentation({
    explicitTotalSlideCount: 34,
    workspaceDir: ROOT,
    candidatePath: CANDIDATE,
    finalPath: input.output,
    pythonExecutable: PYTHON,
    integrityValidatorPath: path.join(SKILL, "container_tools", "inspect_presentation_package_integrity.py"),
    layoutValidatorPath: path.join(SKILL, "container_tools", "inspect_presentation_layout_geometry.py"),
    layoutArgs: [
      "--expected-slide-size-emu", "12192000,6858000", "--validate-bullet-geometry", "--validate-heading-fit",
      ...[6, 7, 13, 22, 23, 25, 26, 27, 28, 31].flatMap((number) => ["--require-native-table-slide", String(number)]),
    ],
    requiredNativeTableOwnerSlides: [6, 7, 13, 22, 23, 25, 26, 27, 28, 31],
    requiredNativeChartOwnerSlides: [18, 19, 24],
    materializeLiteralChartWorkbooks: true,
    fontPolicy: { basis: "reference", families: [FONT, MONO], referencePath: input.base, referenceSha256: await sha256File(input.base) },
    verifyArtifactToolImport: true,
    receiptPath: path.join(BUILD, "multi-protein-benchmark.final.validation.json"),
  });

  await fs.copyFile(CANDIDATE_REPORT, input.report);
  for (const [index, slide] of presentation.slides.items.entries()) {
    const png = await presentation.export({ slide, format: "png", scale: 1 });
    await fs.writeFile(path.join(PREVIEW_DIR, `slide-${String(index + 1).padStart(2, "0")}.png`), new Uint8Array(await png.arrayBuffer()));
  }
  const montage = await presentation.export({ format: "webp", montage: true });
  const montagePath = path.join(BUILD, "multi-protein-benchmark-montage.webp");
  await fs.writeFile(montagePath, new Uint8Array(await montage.arrayBuffer()));

  const progress = JSON.parse(await fs.readFile(input.progress, "utf8"));
  Object.assign(progress, {
    state: "complete",
    overall_percent: 100.0,
    acceptance_report: input.report,
    presentation: input.output,
    presentation_sha256: await sha256File(input.output),
    presentation_validation: result,
    presentation_montage: montagePath,
    updated_utc: new Date().toISOString(),
  });
  await atomicJson(input.progress, progress);
  process.stdout.write(`${JSON.stringify({ output: input.output, report: input.report, slides: 34, result })}\n`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
