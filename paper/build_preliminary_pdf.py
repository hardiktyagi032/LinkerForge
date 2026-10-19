"""Render the measured preliminary study as a black-and-white PDF."""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, KeepTogether, PageTemplate, Paragraph,
    Spacer, Table, TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
OUTPUT = ROOT / "output" / "pdf" / "LinkerForge_Preliminary_Study.pdf"


class Bars(Flowable):
    def __init__(self, rows, maximum, unit=""):
        super().__init__()
        self.rows = rows
        self.maximum = maximum
        self.unit = unit
        self.width = 170 * mm
        self.height = (len(rows) * 10 + 6) * mm

    def draw(self):
        canvas = self.canv
        bar_x, bar_width = 74 * mm, 76 * mm
        for i, (label, value) in enumerate(self.rows):
            y = self.height - (i + 1) * 10 * mm
            canvas.setFont("Helvetica", 8.2)
            canvas.setFillColor(colors.black)
            canvas.drawString(0, y + 2.5 * mm, label)
            canvas.setFillColor(colors.HexColor("#e9e9e9"))
            canvas.rect(bar_x, y, bar_width, 5 * mm, fill=1, stroke=0)
            canvas.setFillColor(colors.HexColor("#404040"))
            canvas.rect(bar_x, y, min(value / self.maximum, 1) * bar_width,
                        5 * mm, fill=1, stroke=0)
            canvas.setFont("Helvetica-Bold", 8.2)
            canvas.setFillColor(colors.black)
            shown = f"{value:.4f}" if isinstance(value, float) else str(value)
            canvas.drawRightString(169 * mm, y + 2.5 * mm, shown + self.unit)


def page_decor(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#777777"))
    canvas.line(18 * mm, 282 * mm, 192 * mm, 282 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(18 * mm, 285 * mm, "LINKERFORGE  /  PRELIMINARY COMPUTATIONAL STUDY")
    canvas.line(18 * mm, 15 * mm, 192 * mm, 15 * mm)
    canvas.drawString(18 * mm, 11 * mm, "8 October 2026  |  Unreviewed pilot")
    canvas.drawRightString(192 * mm, 11 * mm, f"{doc.page}")
    canvas.restoreState()


def build():
    manifest = json.loads((DATA / "cath_full_pilot.manifest.json").read_text())
    report = json.loads((DATA / "cath_full_baseline.json").read_text())
    records = [json.loads(line) for line in (DATA / "cath_full_pilot.jsonl").read_text().splitlines()]
    assert manifest["accepted"] == len(records) == 91
    unresolved = sum(r["source"]["unresolved_linker_residues"] > 0 for r in records)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    doc = BaseDocTemplate(str(OUTPUT), pagesize=(210 * mm, 297 * mm),
                          leftMargin=18 * mm, rightMargin=18 * mm,
                          topMargin=22 * mm, bottomMargin=20 * mm)
    frame = Frame(18 * mm, 20 * mm, 174 * mm, 260 * mm, leftPadding=0,
                  rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates(PageTemplate(id="paper", frames=[frame], onPage=page_decor))
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="PaperTitle", fontName="Times-Bold", fontSize=17,
                              leading=20, alignment=TA_LEFT, spaceAfter=9))
    styles.add(ParagraphStyle(name="PaperSubtitle", fontName="Helvetica", fontSize=9,
                              leading=12, textColor=colors.HexColor("#444444"), spaceAfter=12))
    styles.add(ParagraphStyle(name="PaperHeading", fontName="Helvetica-Bold", fontSize=10,
                              leading=13, spaceBefore=11, spaceAfter=5))
    styles.add(ParagraphStyle(name="PaperBody", fontName="Times-Roman", fontSize=9.3,
                              leading=13, spaceAfter=6))
    styles.add(ParagraphStyle(name="PaperCaption", fontName="Times-Italic", fontSize=8,
                              leading=11, spaceAfter=9))
    styles.add(ParagraphStyle(name="PaperRef", fontName="Times-Roman", fontSize=7.8,
                              leading=10, spaceAfter=5))
    styles.add(ParagraphStyle(name="PaperSmall", fontName="Helvetica", fontSize=8,
                              leading=11, spaceAfter=5))
    p = lambda value: Paragraph(value, styles["PaperBody"])
    h = lambda value: Paragraph(value, styles["PaperHeading"])
    story = [Paragraph("LinkerForge: auditable natural-linker mining and context-aware ranking for two-domain fusion design", styles["PaperTitle"]),
             Paragraph("Preliminary computational study  |  LinkerForge Project Team", styles["PaperSubtitle"]),
             h("Abstract"),
             p("Choosing a peptide linker for two protein domains is context-dependent. We define a provenance-bearing pipeline that mines candidate inter-domain sequences and compares context-free retrieval with a small pairwise ranker. This manuscript reports an <b>unreviewed feasibility pilot</b>, not an experimentally validated design system or evidence of superiority over published linker predictors. Its graphs are generated from actual extraction and scoring outputs."),
             h("1. Research question and prior work"),
             p("For a specified A C-terminus to B N-terminus connection, can domain context improve ranking of feasible 5-30-residue peptide linkers? A recovered native sequence is only a compatibility proxy, not proof of optimal fusion function. SynLinker already designs linkers and assembles uploaded domains [1]. Random-forest linker identification [2], DFLpred [3], IDP-ELM [4], LINKER-Pred [5], and the recent DLD dataset [6] constrain any novelty claim. Our eventual test is a matched, homology-separated comparison of context-aware versus context-free ranking, not a claim that linker detection itself is new."),
             h("2. Data and methods"),
             p("CATH v4.4 boundaries [7] were filtered to exactly two continuous domains of at least 40 residues on one chain with a 5-30-residue author-numbered gap. The gap was labelled a <i>candidate</i> linker. A deterministic SHA-256-ordered subset of doubly classified chains was fetched from RCSB [8]. PDB C-alpha coordinates supplied local port-contact proxies; mmCIF polymer sequence supplied unresolved residues. Raw-file hashes, source IDs, a config hash, and the pipeline commit were retained. Manual biological adjudication remains outstanding."),
             p("Port-complete records were separated by ordered CATH family pair, a coarse architecture proxy <i>not</i> true homology clustering. Training contrasted an observed gap sequence with transplanted training linkers; these alternatives are synthetic comparisons, not measured failures. On the provisional blind split, nearest-training retrieval and a linear pairwise hand-feature ranker scored identical reference-injected candidate pools. Exact production-pool reference coverage was computed separately. No ESM-2, GNN, Rosetta, AlphaFold, or MD run contributed to these results."),
             h("3. Measured preliminary results"),
             KeepTogether([Bars([("Simple CATH gaps", 612), ("Both families annotated", 368),
                   ("RCSB subset requested", 120), ("Mechanically accepted", manifest["accepted"]),
                   ("Port-complete", len(records))], 612),
             Paragraph("Figure 1. Extraction funnel on a common 0-612 scale. Automatic acceptance is not biological validation.", styles["PaperCaption"])]),
             p(f"The pilot yielded {manifest['accepted']} mechanically accepted and {manifest['rejected']} rejected records. All {unresolved} accepted records contained at least one linker residue absent from resolved coordinates. The split comprised {report['split_counts']['train']} training, {report['split_counts']['validation']} validation, and {report['split_counts']['blind']} blind records; {report['training_pairs']} training pairs were formed. Every blind pool held {report['per_example'][0]['candidate_count']} candidates, including an evaluation-only injected reference."),
             KeepTogether([Bars([("Nearest-training MRR", report["metrics"]["retrieval"]["mrr"]),
                   ("Hand-feature MRR", report["metrics"]["hand_feature"]["mrr"])], 0.25),
             Paragraph("Figure 2. Reference-injected mean reciprocal rank (MRR) on 13 provisional blind examples; bar range 0-0.25. Both methods had 0% top-1 and top-5 recovery. Production exact-reference coverage was 0%.", styles["PaperCaption"])]),
             h("4. Interpretation and million-scale extension"),
             p("The hand-feature MRR of 0.0632 versus retrieval MRR of 0.0319 is a diagnostic observation, not a defensible improvement claim: the blind set is small, CATH gaps are unreviewed, all accepted linker regions are partly unresolved, and family-pair grouping does not exclude all homologues. Natural linkers are not necessarily optimal. The current pipeline demonstrates mechanics and failure modes only."),
             p("The next stage trains a CUDA residue-level classifier on independently annotated DLD/DisProt linker and non-linker sequences. It predicts IDL, DDL, boundary positions, or an explicit no-linker decision. A cheap domain filter then routes a much larger UniProt/InterPro sequence stream to the detector. High-confidence predictions are <i>weak labels</i> for later ranking, never independent truth. A bounded loader holds only the current and next network batches. Metadata-only CSV shards record accessions, release IDs, predicted spans, confidence, sequence hashes, homology clusters, splits, and model/config hashes. A million training and a million validation records are targets, not achieved counts."),
             p("A credible final comparison requires a pinned-source run, true homology-aware splits, calibrated no-linker and region-level detector metrics on untouched annotations, matched ranking candidate sets, and a separate engineered-fusion benchmark for unrelated source proteins. The modern protein-language-model alternative is an ablation, not an assumed winner; published PLM fine-tuning work [9] and CAID3 [10] motivate testing it."),
             h("5. Conclusion"),
             p("The present evidence supports a scripted, traceable feasibility baseline only. It neither establishes a million-scale labelled dataset nor shows LinkerForge outperforming prior methods. The next falsifiable question is whether domain context improves family-held-out linker ranking after independent annotation and leakage controls."),
             h("References")]
    refs = [
        ("1", "Liu et al. SynLinker. Bioinformatics (2015).", "https://doi.org/10.1093/bioinformatics/btv447"),
        ("2", "Shatnawi et al. Random-forest inter-domain linker prediction. BMC Bioinformatics (2014).", "https://doi.org/10.1186/1471-2105-15-S16-S8"),
        ("3", "DFLpred. High-throughput disordered flexible linker prediction (2016).", "https://pmc.ncbi.nlm.nih.gov/articles/PMC4908364/"),
        ("4", "IDP-ELM. Journal of Chemical Information and Modeling (2024).", "https://doi.org/10.1021/acs.jcim.3c01202"),
        ("5", "LINKER-Pred/Lite web documentation and open source (server paper listed as submitted).", "https://pcrgwd.ucd.ie/linker_pred/help/"),
        ("6", "Meng et al. DLD dataset. Journal of Molecular Biology (2026).", "https://doi.org/10.1016/j.jmb.2026.169994"),
        ("7", "Waman et al. CATH v4.4. Nucleic Acids Research (2025).", "https://doi.org/10.1093/nar/gkae1087"),
        ("8", "Burley et al. RCSB Protein Data Bank. Nucleic Acids Research (2021).", "https://doi.org/10.1093/nar/gkaa1038"),
        ("9", "Fine-tuning protein language models boosts predictions. Nature Communications (2024).", "https://doi.org/10.1038/s41467-024-51844-2"),
        ("10", "CAID3: Predicting Disorder in the Era of Protein Language Models.", "https://pmc.ncbi.nlm.nih.gov/articles/PMC12750029/"),
    ]
    for number, title, url in refs:
        story.append(Paragraph(f"[{number}] {title} <link href='{url}' color='black'>{url}</link>",
                               styles["PaperRef"]))
    doc.build(story)
    print(OUTPUT)


if __name__ == "__main__":
    build()
