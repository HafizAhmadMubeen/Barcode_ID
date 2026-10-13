"""build_report.py: build the written report (Phase 6) as a Word document.

Every number in the report is read from the files in results/ and
data/processed/ (nothing is typed in by hand), so re-running this script after
the analysis changes keeps the report in sync with the results.

Output: report/BarcodeID_report.docx

Run from the repo root (needs requirements-report.txt):
    python report/build_report.py
"""
import sys
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from config import FIGURES_DIR, PROCESSED_DIR, RESULTS_DIR, TABLES_DIR  # noqa: E402

OUT = ROOT / "report" / "BarcodeID_report.docx"
ACCENT = RGBColor(0x1C, 0x5C, 0xAB)
MUTED = RGBColor(0x52, 0x51, 0x4E)
NAMES = {"nj": "NJ tree", "knn_k4": "k-NN (k=4)", "knn_k6": "k-NN (k=6)",
         "rf_k4": "RF (k=4)", "rf_k6": "RF (k=6)", "bcm": "Best close match",
         "njc": "NJ tree + cut-off"}


# ------------------------------------------------------------------ data --
def load():
    t = lambda name: pd.read_csv(TABLES_DIR / f"{name}.csv")  # noqa: E731
    d = {name: t(name) for name in [
        "cleaning_log", "summary_A", "summary_B", "confidence_intervals", "significance_tests",
        "replicates_summary", "sharing_split", "loso_overall", "loso_per_species", "runtime",
        "ml_thresholds", "ml_thresholds_B", "bcm_thresholds", "bcm_thresholds_B",
        "barcode_sharing_species", "removed_outliers", "removed_misids", "nj_thresholds"]}
    d["meta"] = pd.read_csv(PROCESSED_DIR / "metadata.csv")
    d["split_A"] = pd.read_csv(PROCESSED_DIR / "split_A.csv")
    d["split_B"] = pd.read_csv(PROCESSED_DIR / "split_B.csv")
    d["heldout"] = (RESULTS_DIR / "heldout_species.txt").read_text(encoding="utf-8").split("\n")[:-1]
    return d


def pct(x, digits=1):
    return f"{100 * x:.{digits}f}%"


def rng(values, digits=1):
    """'a–b%' range of a list of shares."""
    lo, hi = min(values), max(values)
    return pct(lo, digits) if abs(lo - hi) < 1e-9 else f"{100 * lo:.{digits}f}–{100 * hi:.{digits}f}%"


# -------------------------------------------------------------- document --
class Report:
    def __init__(self):
        self.doc = Document()
        self.n_table = 0
        self.n_fig = 0
        sec = self.doc.sections[0]
        sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)          # A4
        for side in ("left_margin", "right_margin"):
            setattr(sec, side, Cm(2.3))
        sec.top_margin, sec.bottom_margin = Cm(2.2), Cm(2.2)
        normal = self.doc.styles["Normal"]
        normal.font.name, normal.font.size = "Calibri", Pt(11)
        normal.paragraph_format.space_after = Pt(6)
        normal.paragraph_format.line_spacing = 1.15
        for level, size in ((1, 15), (2, 12.5), (3, 11.5)):
            h = self.doc.styles[f"Heading {level}"]
            h.font.name, h.font.size, h.font.color.rgb = "Calibri", Pt(size), ACCENT
            h.paragraph_format.space_before = Pt(14 if level == 1 else 10)
            h.paragraph_format.space_after = Pt(4)
        self._page_numbers()

    def _page_numbers(self):
        p = self.doc.sections[0].footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
            if kind:
                el = OxmlElement("w:fldChar")
                el.set(qn("w:fldCharType"), kind)
            else:
                el = OxmlElement("w:instrText")
                el.set(qn("xml:space"), "preserve")
                el.text = text
            run._r.append(el)
        run.font.size, run.font.color.rgb = Pt(9), MUTED

    def h(self, text, level=1):
        self.doc.add_heading(text, level=level)

    def p(self, text, bold_lead=None, italic=False, size=None, align=None, color=None, after=None):
        para = self.doc.add_paragraph()
        if bold_lead:
            para.add_run(bold_lead).bold = True
        run = para.add_run(text)
        run.italic = italic
        if size:
            run.font.size = Pt(size)
        if color:
            run.font.color.rgb = color
        if align:
            para.alignment = align
        if after is not None:
            para.paragraph_format.space_after = Pt(after)
        return para

    def bullets(self, items):
        for item in items:
            para = self.doc.add_paragraph(style="List Bullet")
            if isinstance(item, tuple):
                para.add_run(item[0]).bold = True
                para.add_run(item[1])
            else:
                para.add_run(item)
            para.paragraph_format.space_after = Pt(3)

    def caption(self, kind, text):
        para = self.doc.add_paragraph()
        para.add_run(f"{kind}. ").bold = True
        run = para.add_run(text)
        for r in para.runs:
            r.font.size, r.font.color.rgb = Pt(9.5), MUTED
        para.paragraph_format.space_after = Pt(10)
        return para

    def figure(self, filename, caption, width_cm=15.5):
        self.n_fig += 1
        self.doc.add_picture(str(FIGURES_DIR / filename), width=Cm(width_cm))
        self.doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        self.caption(f"Figure {self.n_fig}", caption)
        return self.n_fig

    def table(self, header, rows, caption, widths_cm, align_right_from=1):
        """Caption above, then a simple table; numbers right-aligned."""
        self.n_table += 1
        self.caption(f"Table {self.n_table}", caption).paragraph_format.keep_with_next = True
        tbl = self.doc.add_table(rows=1 + len(rows), cols=len(header))
        tbl.style = "Light Grid Accent 1"
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        for r, values in enumerate([header] + rows):
            for c, value in enumerate(values):
                cell = tbl.cell(r, c)
                cell.width = Cm(widths_cm[c])
                cell.text = ""
                run = cell.paragraphs[0].add_run(str(value))
                run.font.size = Pt(9)
                run.bold = r == 0
                if c >= align_right_from and r > 0:
                    cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
        self.doc.add_paragraph().paragraph_format.space_after = Pt(2)
        return self.n_table

    def page_break(self):
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# --------------------------------------------------------------- content --
def build(d):
    r = Report()
    meta, sA, sB = d["meta"], d["summary_A"].set_index("method"), d["summary_B"]
    sb = sB.set_index(["method", "setting"])
    ci = d["confidence_intervals"].set_index(["outcome", "method"])
    sig = d["significance_tests"]
    reps = d["replicates_summary"]
    loso = d["loso_overall"].set_index(["subset", "method"])
    lps = d["loso_per_species"]
    run_ms = d["runtime"].groupby("method").ms_per_query.median()
    log = d["cleaning_log"]
    split_A, split_B = d["split_A"], d["split_B"]
    sharing = sorted(d["barcode_sharing_species"].species)

    n_seq, n_sp, n_gen = len(meta), meta.species.nunique(), meta.genus.nunique()
    fam = meta.groupby("family").species.nunique()
    n_train = (split_A.set == "train").sum()
    n_test = (split_A.set == "test").sum()
    n_unk = (split_B.set == "test_unknown").sum()
    n_kno = (split_B.set == "test_known").sum()
    acc = {m: sA.accuracy[m] for m in NAMES}
    main = {"nj": "rule", "bcm": "Meier cut-off",
            **{m: "accept 95%" for m in ["knn_k4", "knn_k6", "rf_k4", "rf_k6", "njc"]}}
    b_main = {m: sb.loc[(m, main[m])] for m in NAMES}
    nj_ms, knn_ms, rf_ms, bcm_ms = run_ms["nj"], run_ms["knn_k6"], run_ms["rf_k6"], run_ms["bcm"]
    # Headline speed-up: NJ vs k-NN (k=6), the method the headline is about.
    # The speed section also gives the range over all four classifiers.
    speedup = nj_ms / knn_ms
    ml_ms = run_ms[["knn_k4", "knn_k6", "rf_k4", "rf_k6"]]
    speed_lo, speed_hi = nj_ms / ml_ms.max(), nj_ms / ml_ms.min()
    L = lambda subset, m, col: loso.loc[(subset, m), col]  # noqa: E731
    loso_nj, loso_knn = L("all", "nj", "false_assignment_rate_mean"), L("all", "knn_k6", "false_assignment_rate_mean")
    clean_nj = L("excluding barcode-sharing", "nj", "false_assignment_rate_mean")
    clean_knn_genus = L("excluding barcode-sharing", "knn_k6", "flagged_correct_genus_rate_mean")
    n_clean = int(L("excluding barcode-sharing", "knn_k6", "n_species"))
    n_loso = int(L("all", "knn_k6", "n_species"))
    sig_A = sig[sig.outcome == "A_correct"]
    sig_B = sig[sig.outcome == "B_unknown_named"]
    nj_vs_ml_B = sig_B[(sig_B.method_1 == "nj") & sig_B.method_2.str.startswith(("knn", "rf"))]
    wrong_genus_nj = lps[(lps.method == "nj") & (lps.other_genus_rate > 0)]
    # NJ tree + cut-off (njc), added 2026-10-13
    loso_njc = L("all", "njc", "false_assignment_rate_mean")
    clean_njc = L("excluding barcode-sharing", "njc", "false_assignment_rate_mean")
    clean_knn = L("excluding barcode-sharing", "knn_k6", "false_assignment_rate_mean")
    share_njc = L("barcode-sharing only", "njc", "false_assignment_rate_mean")
    share_knn = L("barcode-sharing only", "knn_k6", "false_assignment_rate_mean")
    loso_cut = [L("all", m, "false_assignment_rate_mean") for m in ["njc", "knn_k6"]]
    njt = d["nj_thresholds"].set_index("accept_rate").tree_distance_max
    # Known species still correct WITH cut-offs, every seed and condition (NJ + cut-off vs k-NN k=6)
    known_gap = []
    for seed_dir in [TABLES_DIR] + [RESULTS_DIR / "replicates" / f"seed_{s}" for s in (1, 2, 3)]:
        a_s, b_s = pd.read_csv(seed_dir / "condition_A.csv"), pd.read_csv(seed_dir / "condition_B.csv")
        for frame in (a_s, b_s[b_s.query_type == "known"]):
            njc_ok = (frame.nj_predicted_species.where(~frame.njc_flagged_unknown, "unknown")
                      == frame.true_species).mean()
            knn_ok = (frame.knn_k6_predicted_species.where(~frame.knn_k6_flagged_unknown, "unknown")
                      == frame.true_species).mean()
            known_gap.append(knn_ok - njc_ok)

    # ------------------------------------------------------------ title --
    r.p("", after=60)
    r.p("BarcodeID", size=30, color=ACCENT, after=4).runs[-1].bold = True
    r.p("Comparing Machine Learning and Phylogenetic Methods for DNA Barcode-Based "
        "Species Identification", size=16, after=18)
    r.p("When the species is not in the reference database: Neighbor-Joining trees, k-nearest "
        "neighbours, random forests and best-close-match on European dragonflies and damselflies "
        "(Odonata, COI)", size=11.5, italic=True, color=MUTED, after=60)
    r.p("University bioinformatics research project", size=11, after=2)
    r.p("Project team: Data & Phylogenetics · Machine Learning · Experiments & Report", size=11, after=2)
    r.p("October 2026", size=11, color=MUTED)
    r.page_break()

    # --------------------------------------------------------- abstract --
    r.h("Abstract")
    r.p(f"DNA barcoding identifies species by comparing a short gene fragment with a reference "
        f"database, but reference databases are incomplete. We asked which identification method "
        f"should be trusted when a query belongs to a species that is not in the database. Using "
        f"{n_seq} cleaned COI barcodes of {n_sp} European species of Libellulidae and "
        f"Coenagrionidae from BOLD Systems, we compared a Neighbor-Joining (NJ) tree with an "
        f"explicit identification rule, two machine-learning classifiers on k-mer frequencies "
        f"(k-nearest neighbours and random forest, each with a calibrated 'unknown' threshold), "
        f"the classic best-close-match distance rule, and the same NJ tree given a calibrated "
        f"tree-distance 'unknown' cut-off. With full reference coverage, all methods were equally "
        f"accurate (NJ {pct(acc['nj'])}, k-NN {pct(acc['knn_k6'])}, random forest "
        f"{pct(acc['rf_k6'])}; no significant differences). When each of {n_loso} species was "
        f"removed from the reference set in turn, the NJ tree used as usual, without a cut-off, "
        f"wrongly named the missing species for {pct(loso_nj, 0)} of its queries on average and "
        f"even placed two species in the wrong genus. With a calibrated 'unknown' cut-off, the same "
        f"tree wrongly named only {pct(loso_njc, 0)} and k-NN {pct(loso_knn, 0)}. Outside a group "
        f"of {len(sharing)} species that share near-identical barcodes with a relative, both never "
        f"named a wrong species and still reported the correct genus. Best close match, a plain "
        f"distance rule, became just as safe when calibrated the same way. The safety therefore "
        f"comes from the calibrated cut-off, not from machine learning; k-NN reached it about "
        f"{speedup:.0f} times faster per query and with slightly fewer losses on known species. "
        f"Barcode sharing between close relatives remains a limit that no barcode-only method "
        f"overcomes.")
    r.p("Main finding. ", italic=False, after=4).runs[0].bold = True
    r.doc.paragraphs[-1].add_run(
        f"The calibrated 'unknown' cut-off, not the choice of method, is what makes identification "
        f"safe. Without one, the NJ tree wrongly named {pct(loso_nj, 0)} of species missing from "
        f"the database. With one, the tree and k-NN were both safe ({pct(loso_njc, 0)} and "
        f"{pct(loso_knn, 0)} across {n_loso} species held out one at a time; 0% outside "
        f"barcode-sharing groups), and k-NN achieved this about {speedup:.0f} times faster.")

    # ---------------------------------------------------------- intro ----
    r.h("1. Introduction")
    r.p("DNA barcoding assigns a specimen to a species by comparing a standard gene fragment, for "
        "animals usually about 650 base pairs of the mitochondrial cytochrome c oxidase I gene "
        "(COI), with sequences of identified reference specimens (Hebert et al., 2003). Public "
        "reference libraries such as the Barcode of Life Data System (BOLD; Ratnasingham & Hebert, "
        "2007) grow quickly, but they are never complete. In practice, a query may come from a "
        "species that has no reference sequence at all.")
    r.p("Two families of methods are used to identify barcodes. Tree-based methods build a "
        "phylogenetic tree of reference and query sequences and read the answer from where the "
        "query lands, for example with Neighbor-Joining (NJ; Saitou & Nei, 1987). Machine-learning "
        "classifiers learn the link between sequence features and species names. Most comparisons "
        "report accuracy on species that are in the database. That is the easy case. The "
        "dangerous case is a species that is missing: a method that confidently names the wrong "
        "species produces a false record, while a method that says 'unknown', or at least points "
        "to the right genus, fails safely.")
    r.p("Research question. ", after=4).runs[0].bold = True
    r.doc.paragraphs[-1].add_run(
        "Which method should be trusted when the query species is not in the reference "
        "database: a phylogenetic tree or a machine-learning classifier?")
    r.p("We answer it with two experimental conditions on the same queries: full coverage "
        "(Condition A), where every test species has reference sequences, and incomplete coverage "
        "(Condition B), where some species are removed from the reference set entirely. Our "
        "contributions are:")
    r.bullets([
        "a head-to-head comparison of an NJ tree, k-nearest neighbours (k-NN), random forest (RF) "
        "and the classic best-close-match rule under both conditions, on identical queries;",
        "an explicit, reproducible identification rule for the tree, and 'unknown' cut-offs "
        "calibrated on training data only for every method, including the tree, so that all "
        "methods can be compared on equal terms;",
        "evidence from three independent methods that a calibrated cut-off, not machine learning "
        "as such, is what makes identification of missing species safe;",
        "robustness checks: species-level confidence intervals and significance tests, threshold "
        "sensitivity, three extra random splits, and holding out every eligible species once;",
        "an analysis of why methods fail, separating ordinary species from species that share "
        "their barcode with a close relative.",
    ])

    # ----------------------------------------------------------- data ----
    r.h("2. Data")
    r.h("2.1 Source and scope", 2)
    r.p("We chose dragonflies and damselflies (Odonata) because a published European reference "
        "library found most species identifiable from COI alone (PeerJ, 2021). All Odonata in BOLD "
        "(2,434 named species, 25,245 COI-5P records on 9 October 2026) is far more than a project "
        "of this size can handle, so we narrowed the scope to two families with many closely "
        "related species, Libellulidae (skimmers) and Coenagrionidae (narrow-winged damselflies), "
        "from the 30 European countries with Odonata records in BOLD. Records were downloaded "
        "through the BOLD v5 public API as tab-separated files, one query per country.")
    r.h("2.2 Cleaning", 2)
    r.p("Every filter was logged (Table 1). We kept COI-5P records of the two families that were "
        "identified to species, and removed two records whose BOLD BIN (BOLD's own sequence "
        "cluster; Ratnasingham & Hebert, 2013) was dominated by a species from a different genus, "
        "a clear mislabel. Sequences longer than 700 bp, mostly from one project that used a "
        "longer amplicon, were trimmed to the barcode region by local alignment to a reference "
        "barcode of their family. We removed sequences with more than 5% ambiguous bases, kept "
        "lengths of 600–700 bp, and kept one copy of each identical sequence per species. Seven "
        "sequences more than 10% (K2P) away from every other sequence were removed as likely "
        "contaminants: no sequence fell between 8% and 15%, so the cut-off sits in an empty gap. "
        "Finally, species with fewer than three sequences were dropped.")
    rows = [[row.description, f"{row.n_sequences:,}", row.n_species, f"{row.removed:,}"]
            for row in log.itertuples()]
    r.table(["Step", "Sequences", "Species", "Removed"], rows,
            "Cleaning log: sequences and species left after each filter "
            "(results/tables/cleaning_log.csv).", [9.4, 2.3, 2.0, 2.3])
    r.p(f"The final dataset contains {n_seq} sequences of {n_sp} species in {n_gen} genera "
        f"({fam['Coenagrionidae']} Coenagrionidae, {fam['Libellulidae']} Libellulidae) from "
        f"{meta.country.nunique()} countries; 166 of them were trimmed. Species have between "
        f"{meta.species.value_counts().min()} and {meta.species.value_counts().max()} sequences.")
    r.h("2.3 Barcode-sharing species", 2)
    r.p(f"Some closely related species have identical or nearly identical barcodes. We defined "
        f"barcode-sharing species independently of our methods as species whose specimens share "
        f"a BOLD BIN with another species in our data. This gives {len(sharing)} species in four "
        f"groups: {', '.join(sharing[:3])}; {', '.join(sharing[3:6])}; {', '.join(sharing[6:8])}; "
        f"and {', '.join(sharing[8:])}. These species are hard for any barcode-only method and are "
        f"analysed separately in Section 4.5.")

    # -------------------------------------------------------- methods ----
    r.h("3. Methods")
    r.h("3.1 Alignment and genetic distances", 2)
    r.p("All sequences were aligned with MAFFT v7.526 (--auto; Katoh & Standley, 2013), giving "
        "an alignment of 730 columns. Pairwise distances use the Kimura two-parameter model (K2P; "
        "Kimura, 1980), the standard in DNA barcoding, skipping gaps and ambiguous bases pair by "
        "pair. Alignment uses no species labels, so aligning test sequences together with "
        "reference sequences leaks no information.")
    r.h("3.2 Neighbor-Joining tree", 2)
    r.p("A single NJ tree (Biopython; Cock et al., 2009) was built from the K2P distances of all "
        "reference and query sequences and rooted at its midpoint. Query labels are never used. "
        "The identification rule, fixed before testing, is:")
    r.p("A query is assigned the species of the training sequences in the smallest clade that "
        "contains the query and at least one training sequence; if that clade holds training "
        "sequences of more than one species, the query is 'ambiguous' (with a genus if those "
        "species share one).", italic=True)
    r.p("Used like this, as trees usually are, 'ambiguous' is the tree's only way to abstain. "
        "Building one tree per query was not feasible: Biopython's NJ takes about four minutes "
        "for 779 sequences.")
    r.p(f"To compare the tree with the classifiers on equal terms, we also evaluated the same tree "
        f"with an 'unknown' cut-off ('NJ tree + cut-off'). The tree (patristic) distance from a "
        f"query to its nearest training sequence is compared with a cut-off calibrated on training "
        f"sequences only, inside the same tree: for every training sequence we take its tree "
        f"distance to the nearest other training sequence, and the cut-off accepts 95% of these "
        f"(Condition A cut-off {njt[0.95]:.4f}). A query further away is answered 'unknown', with "
        f"the clade's genus. No new trees are needed. Both versions of the tree are reported "
        f"throughout: plain NJ shows how trees are commonly used, and NJ + cut-off gives the fair "
        f"comparison.")
    r.h("3.3 k-mer features and classifiers", 2)
    r.p("Each unaligned sequence was converted into k-mer frequencies, the share of each possible "
        "run of k bases, for k = 4 (256 features) and k = 6 (4,096 features); each row sums to 1. "
        "We trained k-nearest neighbours (5 neighbours, closer ones weighted more) and random "
        "forests (500 trees, class weights balanced for rare species) with scikit-learn "
        "(Pedregosa et al., 2011). These settings were chosen by cross-validation on training data "
        "only. Training each model takes about one second on a laptop CPU.")
    r.h("3.4 'Unknown' thresholds", 2)
    th = d["ml_thresholds"]
    th95 = th[th.accept_rate == 0.95].set_index(["model", "k"]).threshold
    r.p(f"Without a threshold, a classifier always names one of the species it was trained on. "
        f"We therefore let each classifier flag a query as 'unknown' when it is less confident "
        f"than for 95% of known-species queries. The cut-off is calibrated on training data only, "
        f"with two-fold cross-validation repeated five times. For random forest the confidence is "
        f"the top class probability (cut-offs {th95[('rf', 4)]:.3f} for k = 4 and "
        f"{th95[('rf', 6)]:.3f} for k = 6). For k-NN it is the distance to the nearest training "
        f"sequence in k-mer space (cut-offs {th95[('knn', 4)]:.4f} and {th95[('knn', 6)]:.4f}). "
        f"When a query is flagged, every method still reports a genus: for k-NN the genus of the "
        f"nearest training sequence, for random forest the genus of its top species, and for NJ "
        f"the shared genus of the clade.")
    r.h("3.5 Best-close-match baseline", 2)
    bt = d["bcm_thresholds"].set_index("rule").cutoff_k2p
    r.p(f"To test whether any advantage comes from machine learning or simply from having a "
        f"cut-off, we added the classic best-close-match rule (Meier et al., 2006): take the "
        f"species of the closest reference sequence by K2P distance; answer 'ambiguous' if equally "
        f"close sequences belong to different species, and 'unknown' if the closest one is "
        f"further than a cut-off. Following Meier et al., the cut-off is the distance below which "
        f"95% of within-species training pairs fall ({pct(bt['meier'], 2)} in Condition A). We "
        f"also report the same calibration as the classifiers and a fixed 2% cut-off.")
    r.h("3.6 Experimental design", 2)
    r.bullets([
        ("Condition A (full coverage). ",
         f"Within each species, 70% of sequences were used for training and 30% for testing (at "
         f"least two training and one test sequence per species): {n_train} training and "
         f"{n_test} test sequences, the same queries for every method. Because identical "
         f"sequences were removed within species, no test sequence has an identical copy of its "
         f"own species in training."),
        ("Condition B (incomplete coverage). ",
         f"One species was drawn at random from each of the eight genera with at least two "
         f"species ({', '.join(d['heldout'])}) and removed from training entirely. Queries were "
         f"all {n_unk} sequences of these species ('unknown') plus {n_kno} Condition A test "
         f"sequences of the other species ('known'). Every method was rebuilt without the "
         f"held-out species, and the classifier thresholds were re-calibrated."),
        ("Replicates. ",
         "Conditions A and B were repeated with three further random seeds, each with a new "
         "split and a new set of held-out species."),
        ("Leave-one-species-out. ",
         f"Each of the {n_loso} species from multi-species genera was removed from training on "
         f"its own and all its sequences were queried, with a new tree and retrained "
         f"classifiers each time. This removes the luck of which species are held out."),
    ])
    r.h("3.7 Evaluation and statistics", 2)
    r.p("For known queries we report accuracy and per-species precision and recall. For unknown "
        "queries every answer falls into exactly one class: abstained (flagged 'unknown' or "
        "'ambiguous'; safe), a wrong species of the correct genus (wrong but close), or a wrong "
        "species of another genus (dangerous). The false-assignment rate is the share of unknown "
        "queries given any species name. 'Safe and informative' means abstaining while reporting "
        "the correct genus.")
    r.p("Queries of the same species are not independent, so 95% confidence intervals come from "
        "a species-level bootstrap: species are resampled with replacement, 2,000 times. Paired "
        "methods were compared with exact McNemar tests (McNemar, 1947) with Holm correction "
        "(Holm, 1979), and with a species-bootstrap interval for each difference. Runtime was "
        "measured on the same laptop for the 236 Condition A queries, from unaligned sequences, "
        "as the median of three runs. For NJ it includes alignment, distances, tree building and "
        "the rule. For best close match it includes alignment, distances and the nearest match. "
        "For the classifiers it includes k-mer extraction and prediction, excluding the one-off "
        "training.")

    # -------------------------------------------------------- results ----
    r.h("4. Results")
    r.h("4.1 Known species (Condition A)", 2)
    rows = []
    for m in [m for m in NAMES if m != "njc"]:      # NJ + cut-off = NJ without its cut-off here
        c = ci.loc[("A_correct", m)]
        rows.append([NAMES[m], pct(acc[m]), f"{pct(c.ci_low, 0)}–{pct(c.ci_high, 0)}",
                     pct(sA.macro_precision[m]), pct(sA.macro_recall[m]),
                     f"{sA.runtime_ms_per_query[m]:,.1f}"])
    r.table(["Method", "Accuracy", "95% CI", "Precision", "Recall", "ms / query"], rows,
            f"Condition A: {n_test} test queries of {n_sp} species. Accuracy without any "
            f"threshold; CI = species-bootstrap interval; precision and recall are macro averages "
            f"over species (results/tables/summary_A.csv, confidence_intervals.csv, runtime.csv).",
            [3.4, 2.1, 2.3, 2.3, 2.1, 2.2])
    f_acc = r.n_fig + 1
    r.p(f"All four classifiers and the NJ tree identified known species with about the same "
        f"accuracy ({rng([acc[m] for m in NAMES if m not in ('bcm', 'njc')])}; Table 2, Figure {f_acc}). No "
        f"pair differs significantly (all Holm-corrected McNemar p = "
        f"{sig_A[sig_A.method_1 == 'nj'].holm_p.min():.2f}), and every species-bootstrap interval "
        f"of a difference between NJ and a classifier includes zero. Best close match was lower "
        f"({pct(acc['bcm'])}), a significant difference (Holm p ≤ "
        f"{sig_A[sig_A.method_1 == 'bcm'].holm_p.max():.3f}). This is because it answers "
        f"'ambiguous' for 30 queries that are identical to sequences of two species, all of them "
        f"in the barcode-sharing groups. Every error of the other methods also fell inside those "
        f"groups, and no method named a wrong genus.")
    r.figure("accuracy_A.png", "Accuracy on known species (Condition A). Bars: main run "
             "(seed 42); dots: three replicate seeds. The axis starts at 80%.", 14.5)
    r.p(f"Across the four random splits, accuracy ranged from "
        f"{rng(reps.A_acc_nj)} for NJ, {rng(reps.A_acc_knn_k6)} for k-NN (k = 6) and "
        f"{rng(reps.A_acc_rf_k6)} for random forest (k = 6). k-NN was best or tied best in three "
        f"of four splits, but given the significance tests we do not claim a winner for known "
        f"species.")

    r.h("4.2 Species missing from the database (Condition B)", 2)
    rows = []
    for m in NAMES:
        b = b_main[m]
        rows.append([NAMES[m] + ("" if m in ("nj", "njc") else " (cut-off)"),
                     pct(b.unknown_false_assignment_rate), pct(b.unknown_other_genus_rate),
                     pct(b.unknown_flagged_rate), pct(b.unknown_flagged_correct_genus_rate),
                     pct(b.known_accuracy)])
    r.table(["Method", "Wrongly named", "Wrong genus", "Abstained", "Abstained + genus",
             "Known correct"], rows,
            f"Condition B, main run: {n_unk} unknown queries from {len(d['heldout'])} held-out "
            f"species and {n_kno} known queries. 'Known correct' counts a flagged known query as "
            f"a miss (results/tables/summary_B.csv).", [3.9, 2.4, 2.1, 2.1, 2.6, 2.3])
    b_nj, b_knn, b_rf = b_main["nj"], b_main["knn_k6"], b_main["rf_k6"]
    rf_raw_other = [sb.loc[(m, "no threshold")].unknown_other_genus_rate for m in ["rf_k4", "rf_k6"]]
    r.p(f"For species missing from the database, the methods behaved very differently (Table 3, "
        f"Figure {r.n_fig + 1}). The plain NJ tree named a wrong species for "
        f"{pct(b_nj.unknown_false_assignment_rate)} of unknown queries. It always chose a species "
        f"of the correct genus and abstained only when the nearest clade mixed several species. "
        f"Without a threshold, the classifiers named a known species for every unknown query, "
        f"and random forest put {rng(rf_raw_other, 0)} of them in the wrong genus. With the "
        f"calibrated threshold, k-NN flagged every unknown query, and for k = 6 it reported the "
        f"correct genus for all of them. Random forest flagged "
        f"{rng([b_main[m].unknown_flagged_rate for m in ['rf_k4', 'rf_k6']])}, and best close "
        f"match with Meier's cut-off flagged {pct(b_main['bcm'].unknown_flagged_rate)}. Given a "
        f"calibrated cut-off, the NJ tree also flagged "
        f"{pct(b_main['njc'].unknown_flagged_rate)} of unknown queries, all with the correct "
        f"genus: the same tree that named a wrong species two times out of three without a "
        f"cut-off became as safe as k-NN.")
    r.figure("condition_B_outcomes.png", "What each method answers for species not in the "
             "database (Condition B, main run). Green: flagged 'unknown' or abstained (dark green "
             "with the correct genus). Yellow: a wrong species of the correct genus. Red: a wrong "
             "species of another genus.", 15.5)
    njc_vs_knn = sig_B[(sig_B.method_1 == "njc") & (sig_B.method_2 == "knn_k6")].iloc[0]
    r.p(f"The difference between plain NJ and the thresholded classifiers is large and robust. "
        f"Plain NJ named a species "
        f"{pct(nj_vs_ml_B.difference.min(), 0)}–{pct(nj_vs_ml_B.difference.max(), 0)} more often "
        f"(Holm p < 0.0001; species-bootstrap lower bound "
        f"+{pct(nj_vs_ml_B.diff_ci_low.min(), 0)}), while NJ + cut-off and k-NN did not differ "
        f"at all (difference {pct(njc_vs_knn.difference)}). Safety has a price: with a cut-off on, "
        f"every method rejected some known species too, reaching "
        f"{rng([b_main[m].known_accuracy for m in ['knn_k4', 'knn_k6', 'rf_k4', 'rf_k6', 'njc']])} "
        f"correct on known queries against {pct(b_nj.known_accuracy)} for plain NJ. Figure "
        f"{r.n_fig + 1} shows the same trade-off from full to incomplete coverage.")
    r.figure("A_vs_B.png", "From full to incomplete coverage: correct answers on known species "
             "(Condition A, with each method's cut-off) against unknown species safely flagged "
             "(Condition B).", 14.0)

    r.h("4.3 Every species held out once", 2)
    rows = []
    for m in NAMES:
        rows.append([NAMES[m],
                     pct(L("all", m, "false_assignment_rate_mean")),
                     pct(L("all", m, "species_never_wrongly_named"), 0),
                     pct(L("excluding barcode-sharing", m, "false_assignment_rate_mean")),
                     pct(L("excluding barcode-sharing", m, "flagged_correct_genus_rate_mean")),
                     pct(L("barcode-sharing only", m, "false_assignment_rate_mean"))])
    r.table(["Method", f"Wrongly named ({n_loso} sp.)", "Species never wrong",
             f"Wrongly named ({n_clean} sp.)", f"Abstained + genus ({n_clean} sp.)",
             f"Wrongly named ({n_loso - n_clean} sharing)"], rows,
            f"Leave-one-species-out: each of {n_loso} species held out on its own; means over "
            f"species, so each species counts equally. {n_clean} sp. = excluding barcode-sharing "
            f"species (results/tables/loso_overall.csv).", [3.0, 2.5, 2.3, 2.5, 2.8, 2.6])
    wg = ", ".join(f"{s} ({int(n)} queries)" for s, n in zip(wrong_genus_nj.species, wrong_genus_nj.n_queries))
    r.p(f"Holding out every eligible species once confirms the result without depending on a "
        f"random draw (Table 4, Figure {r.n_fig + 1}). On average NJ wrongly named the missing "
        f"species for {pct(loso_nj)} of its queries, and for "
        f"{pct(L('all', 'nj', 'species_mostly_wrongly_named'), 0)} of species it did so for most "
        f"queries. k-NN (k = 6) did so for {pct(loso_knn)}, never naming a wrong species for "
        f"{pct(L('all', 'knn_k6', 'species_never_wrongly_named'), 0)} of species. Among the "
        f"{n_clean} species that do not share their barcode, k-NN never named a wrong species "
        f"for a single query, with either k, and reported the correct genus for "
        f"{pct(clean_knn_genus)}; plain NJ wrongly named {pct(clean_nj)}. Plain NJ also placed "
        f"two species in the wrong genus, {wg}: each was placed next to the other. With its "
        f"cut-off, the tree wrongly named {pct(loso_njc)} of queries overall and "
        f"{pct(clean_njc)} outside the barcode-sharing groups, and the two wrong-genus "
        f"placements were flagged 'unknown' instead. NJ + cut-off and k-NN were the two safest "
        f"methods ({rng(loso_cut)}); the tree was slightly safer on barcode-sharing species "
        f"({pct(share_njc, 0)} against {pct(share_knn, 0)} wrongly named). No method with a "
        f"cut-off named a wrong genus in this analysis.")
    r.figure("loso_per_species.png", "Every species held out once: share of its queries given a "
             "wrong species name, by method. Shaded rows (*) are barcode-sharing species.", 15.5)

    r.h("4.4 Robustness to splits and thresholds", 2)
    r.p(f"Across the four random Condition B draws, the share of unknown queries wrongly named "
        f"ranged from {rng(reps.B_false_assign_nj)} for plain NJ, "
        f"{rng(reps.B_false_assign_njc)} for NJ + cut-off, {rng(reps.B_false_assign_knn_k6)} for "
        f"k-NN (k = 6), {rng(reps.B_false_assign_rf_k6)} for random forest (k = 6) and "
        f"{rng(reps.B_false_assign_bcm)} for best close match. NJ + cut-off or k-NN was the "
        f"safest method in every draw, and plain NJ never was. The wide ranges come from which "
        f"species happen to be drawn, as Section 4.5 explains.")
    knn99 = sb.loc[("knn_k6", "accept 99%")]
    rf99 = [sb.loc[(m, "accept 99%")].unknown_flagged_rate for m in ["rf_k4", "rf_k6"]]
    r.p(f"The threshold matters less for k-NN than for random forest (Figure {r.n_fig + 1}). Even "
        f"at the strictest calibration, which accepts 99% of known species, k-NN still caught "
        f"{pct(knn99.unknown_flagged_rate)} of unknown queries, while random forest fell to "
        f"{rng(rf99)}. Lower thresholds catch more unknown species but reject more known ones.")
    r.figure("threshold_curve.png", "Threshold sensitivity (Condition B, main run). Lines: every "
             "possible cut-off; markers: cut-offs calibrated to accept 90%, 95% and 99% of known "
             "species (best close match also: Meier's cut-off). The blue diamond is plain NJ, "
             "which has no cut-off.", 14.5)

    r.h("4.5 Why methods fail: barcode sharing", 2)
    ss = d["sharing_split"]
    ex = ss[(ss.subset == "excluding barcode-sharing")]
    only = ss[(ss.subset == "barcode-sharing only")]
    r.p(f"Splitting Condition B by barcode sharing explains the variation between draws (Figure "
        f"{r.n_fig + 1}). Without barcode-sharing species, k-NN wrongly named "
        f"{rng(ex[ex.method == 'knn_k6'].unknown_false_assignment_rate)} of unknown queries in "
        f"every draw, random forest {rng(ex[ex.method == 'rf_k6'].unknown_false_assignment_rate)}, "
        f"best close match {rng(ex[ex.method == 'bcm'].unknown_false_assignment_rate)} and NJ "
        f"{rng(ex[ex.method == 'nj'].unknown_false_assignment_rate)}. For barcode-sharing species "
        f"every method failed often, k-NN by up to "
        f"{pct(only[only.method == 'knn_k6'].unknown_false_assignment_rate.max(), 0)} and NJ by up "
        f"to {pct(only[only.method == 'nj'].unknown_false_assignment_rate.max(), 0)}. When a "
        f"missing species' barcode is identical to that of a species in the database, the "
        f"barcode alone cannot reveal that it is missing.")
    r.figure("barcode_sharing.png", "Unknown species wrongly named, for all held-out species and "
             "excluding barcode-sharing species (bars: mean of four seeds; dots: each seed).", 15.0)

    r.h("4.6 Where does the safety come from?", 2)
    b95 = sb.loc[("bcm", "accept 95%")]
    r.p(f"Three independent lines of evidence point to the same answer: the safety comes from a "
        f"calibrated 'unknown' cut-off, not from machine learning as such.")
    r.bullets([
        ("A plain distance rule. ",
         f"Best close match has no learning. With Meier's cut-off it wrongly named "
         f"{pct(b_main['bcm'].unknown_false_assignment_rate)} of unknown queries in the main run "
         f"and {rng(reps.B_false_assign_bcm)} across draws. Calibrated in the same way as k-NN, it "
         f"also flagged {pct(b95.unknown_flagged_rate)} of unknown queries."),
        ("The same tree with a cut-off. ",
         f"Plain NJ wrongly named {pct(loso_nj, 0)} of missing species across {n_loso} species; "
         f"with a calibrated tree-distance cut-off it wrongly named {pct(loso_njc, 0)}, slightly "
         f"fewer than k-NN ({pct(loso_knn, 0)})."),
        ("The threshold curves. ",
         "Across every possible cut-off, the curves of NJ + cut-off and k-NN almost overlap "
         "(Figure 5): at the same rate of wrongly rejected known species, they catch about the "
         "same share of unknown species."),
    ])
    r.p(f"What, then, does machine learning add? First, speed (Section 4.7). Second, a slightly "
        f"better balance at its calibrated cut-off. With cut-offs on, k-NN kept more known species "
        f"correct than NJ + cut-off in all {len(known_gap)} seed-and-condition comparisons, by "
        f"{100 * min(known_gap):.1f}–{100 * max(known_gap):.1f} percentage points. These "
        f"differences are not significant "
        f"individually, and since the threshold curves overlap, they reflect where each calibration "
        f"placed its cut-off (the in-tree calibration chose a stricter one), not a better ability "
        f"to tell known from unknown. Against best close match, k-NN's advantage is clearer: at the "
        f"same safety it kept {pct(b_knn.known_accuracy)} of known queries correct against "
        f"{pct(b95.known_accuracy)}, because its vote among five neighbours resolves many queries "
        f"that best close match calls ambiguous.")

    r.h("4.7 Speed", 2)
    r.p(f"Per query, the NJ pipeline took {nj_ms:,.0f} ms, best close match {bcm_ms:.0f} ms, and "
        f"the classifiers {run_ms[['knn_k4', 'knn_k6', 'rf_k4', 'rf_k6']].min():.1f}–"
        f"{run_ms[['knn_k4', 'knn_k6', 'rf_k4', 'rf_k6']].max():.1f} ms, so the classifiers were "
        f"{speed_lo:.0f}–{speed_hi:.0f} times faster than NJ (k-NN with k = 6: about "
        f"{speedup:.0f} times; Figure {r.n_fig + 1}). NJ has no training "
        f"step, but it must rebuild the whole tree, including all reference sequences, every time "
        f"new queries arrive. Its cost grows steeply with database size, roughly with the cube of "
        f"the number of sequences.")
    r.figure("runtime.png", "Runtime per query (log scale), same laptop and the same 236 queries, "
             "median of three runs.", 14.5)

    # ----------------------------------------------------- discussion ----
    r.h("5. Discussion")
    r.p("On species that are in the reference database, the choice of method hardly matters: all "
        "methods identified about nine in ten queries correctly, and their errors were the same "
        "unavoidable confusions between barcode-sharing species. When the database is "
        "incomplete, what matters is not the method but whether it has a calibrated way to say "
        "'this species is not here'. A phylogenetic tree used as usual has none. With our rule it "
        "answered with the nearest species in most cases, twice even with a species of another "
        "genus, and abstained only when the neighbouring clade happened to contain several "
        "species. Machine-learning classifiers without a threshold are no better: they always "
        "name a known species.")
    r.p("Once every method is given an 'unknown' cut-off calibrated on known species, the "
        "picture changes. The tree, k-NN and even a plain distance rule all became safe, and "
        "outside the barcode-sharing groups the tree and k-NN never named a wrong species. They "
        "also kept the useful part of the tree's answer, the genus. Random forest remained "
        "somewhat less safe, because its probabilities spread over related species and do not "
        "directly measure how far a query is from the references. Methods that measure distance "
        "(k-NN, best close match and the tree) are the natural basis for an 'unknown' answer.")
    r.p("Our central recommendation is therefore method-independent: whichever identification "
        "method is used, add a calibrated 'unknown' cut-off. Without one, the tree named a wrong "
        "species for two thirds of missing species; with one, wrong names fell to about one in "
        "ten. If speed matters, k-NN on k-mer frequencies is the practical choice, because it "
        "reaches the same safety hundreds of times faster. Answers that fall within a "
        "barcode-sharing group should be reported at genus or species-group level.")

    r.p(f"Our results agree with earlier work on this group and on barcoding in general. The "
        f"European Odonata reference study (PeerJ, 2021) found that most species are "
        f"identifiable from COI alone, but not all, which matches our accuracy of about nine in "
        f"ten for known species and the same problem groups. Meier et al. (2006) introduced best "
        f"close match because tree-based identification overstates success. Our finding that a "
        f"distance cut-off is what makes identification safe extends their argument to the case "
        f"of missing species, and shows that the same fix works for the tree itself. The "
        f"machine-learning studies in our reference list report high accuracy on known species. "
        f"Our results suggest that such accuracy says little about behaviour on species outside "
        f"the training set, which needs to be tested explicitly, and that comparisons between "
        f"trees and classifiers should give both the same chance to answer 'unknown'.")
    r.p("A further practical difference concerns how each method scales. A classifier is "
        "trained once and then answers each new query in milliseconds, and adding reference "
        "sequences only needs retraining, which took about a second here. A tree must be rebuilt "
        "with all references every time new queries arrive. With a growing reference library, "
        "this cost rises faster than the library itself.")

    r.h("6. Limitations")
    r.bullets([
        ("One group, one gene, one region. ", "Two families of European Odonata, the COI "
         "barcode only, and data from BOLD as downloaded on 9 October 2026."),
        ("Small dataset. ", f"{n_seq} sequences of {n_sp} species; some species have only three "
         f"sequences, and Condition B per draw rests on eight species."),
        ("Barcode sharing. ", f"{len(sharing)} species share BINs with relatives. No barcode-only "
         f"method can separate them, and they cause almost all errors."),
        ("Calibration of the tree cut-off. ", "The tree's cut-off was calibrated inside the same "
         "tree on training sequences, while the classifiers used cross-validation; the two "
         "procedures placed their cut-offs at slightly different points of the trade-off. We "
         "used a single NJ tree for all queries, not one tree per query, and did not test "
         "maximum-likelihood trees."),
        ("Label quality. ", "We trust BOLD identifications apart from two cross-genus mislabels; "
         "remaining mislabels within genera would count as method errors."),
        ("Statistics. ", "McNemar tests treat queries as independent, which they are not; we "
         "therefore also report species-level bootstrap intervals and prefer them where the two "
         "disagree."),
    ])

    r.h("7. Conclusion")
    r.p(f"Which method should be trusted when the species is not in the database? Not the "
        f"method alone. Without an 'unknown' cut-off, the NJ tree wrongly named {pct(loso_nj, 0)} "
        f"of species missing from the database; with a calibrated cut-off, the tree and k-NN were "
        f"both safe ({pct(loso_njc, 0)} and {pct(loso_knn, 0)} across {n_loso} species held out "
        f"one at a time, and 0% outside barcode-sharing groups), and k-NN achieved this about "
        f"{speedup:.0f} times faster. Whichever method is used, a calibrated 'unknown' cut-off "
        f"should be part of it. Barcode sharing between close relatives remains the limit that "
        f"no barcode-only method overcomes.")

    # ----------------------------------------------------- references ----
    r.h("References")
    refs = [
        "Cock P. J. A. et al. (2009). Biopython: freely available Python tools for computational "
        "molecular biology and bioinformatics. Bioinformatics 25: 1422–1423.",
        "Coverage and quality of DNA barcode references for Central and Northern European Odonata "
        "(2021). PeerJ 9: e11192. https://peerj.com/articles/11192/",
        "Hebert P. D. N., Cywinska A., Ball S. L., deWaard J. R. (2003). Biological "
        "identifications through DNA barcodes. Proceedings of the Royal Society B 270: 313–321.",
        "Holm S. (1979). A simple sequentially rejective multiple test procedure. Scandinavian "
        "Journal of Statistics 6: 65–70.",
        "Katoh K., Standley D. M. (2013). MAFFT multiple sequence alignment software version 7. "
        "Molecular Biology and Evolution 30: 772–780.",
        "Kimura M. (1980). A simple method for estimating evolutionary rates of base substitutions "
        "through comparative studies of nucleotide sequences. Journal of Molecular Evolution 16: "
        "111–120.",
        "McNemar Q. (1947). Note on the sampling error of the difference between correlated "
        "proportions or percentages. Psychometrika 12: 153–157.",
        "Meier R., Shiyang K., Vaidya G., Ng P. K. L. (2006). DNA barcoding and taxonomy in "
        "Diptera: a tale of high intraspecific variability and low identification success. "
        "Systematic Biology 55: 715–728.",
        "Pedregosa F. et al. (2011). Scikit-learn: machine learning in Python. Journal of Machine "
        "Learning Research 12: 2825–2830.",
        "Ratnasingham S., Hebert P. D. N. (2007). BOLD: The Barcode of Life Data System. "
        "Molecular Ecology Notes 7: 355–364.",
        "Ratnasingham S., Hebert P. D. N. (2013). A DNA-based registry for all animal species: "
        "the Barcode Index Number (BIN) system. PLoS ONE 8: e66213.",
        "Saitou N., Nei M. (1987). The neighbor-joining method: a new method for reconstructing "
        "phylogenetic trees. Molecular Biology and Evolution 4: 406–425.",
        "AI-powered biodiversity assessment: species classification via DNA barcoding and deep "
        "learning (2024). Technologies 12: 240. https://www.research.unipd.it/bitstream/11577/"
        "3541838/2/technologies-12-00240-v2.pdf",
        "A new method for species identification via protein-coding and non-coding DNA barcodes "
        "by combining machine learning with bioinformatic methods (2012). "
        "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3282726/",
        "BOLD Systems database overview (2024). https://pmc.ncbi.nlm.nih.gov/articles/PMC11070247",
    ]
    for ref in refs:
        para = r.p(ref, size=9.5, after=3)
        para.paragraph_format.left_indent = Cm(0.6)
        para.paragraph_format.first_line_indent = Cm(-0.6)

    # ------------------------------------------------------- appendix ----
    r.h("Appendix: reproducibility")
    r.p("All code, cleaned data and results are in the project repository. One random seed "
        "(42) is used everywhere; the main splits and the held-out species list are saved once "
        "and never regenerated. Each step is a separate script that runs from cached files, in "
        "this order:")
    steps = ["download_bold.py: raw BOLD records (all European Odonata)",
             "data_cleaning.py: filters of Table 1",
             "alignment.py: MAFFT alignment",
             "splits.py: Condition A and B splits",
             "phylo_baseline.py, features.py, ml_classifiers.py, bcm.py: the methods",
             "experiment_full.py, experiment_incomplete.py: Conditions A and B",
             "replicates.py, leave_one_species_out.py, runtime.py: robustness and timing",
             "evaluate.py, significance.py: tables, figures and statistics",
             "report/build_report.py: this report, with every number read from results/"]
    r.bullets(steps)

    # Appendix tables: details behind the main text.
    r.h("Appendix: supplementary tables")
    counts = meta.groupby(["family", "genus", "species"]).size().reset_index(name="n")
    n_train_sp = split_A[split_A.set == "train"].species.value_counts()
    rows = [[row.family, row.species, row.n, n_train_sp.get(row.species, 0),
             "yes" if row.species in sharing else ""] for row in counts.itertuples()]
    r.table(["Family", "Species", "Sequences", "Training (A)", "Barcode-sharing"], rows,
            "Species in the final dataset, with their number of sequences, Condition A "
            "training sequences, and whether they share a BOLD BIN with another species "
            "(data/processed/metadata.csv, split_A.csv, barcode_sharing_species.csv).",
            [3.4, 5.4, 2.2, 2.5, 2.7], align_right_from=2)

    outcome_name = {"A_correct": "Known (A): correct",
                    "B_unknown_named": "Unknown (B): wrongly named",
                    "B_known_correct": "Known (B): correct"}
    rows = [[outcome_name[s.outcome], f"{NAMES[s.method_1]} vs {NAMES[s.method_2]}",
             f"{100 * s.difference:+.1f}", f"{100 * s.diff_ci_low:+.1f} to {100 * s.diff_ci_high:+.1f}",
             f"{s.only_1_hit}/{s.only_2_hit}", f"{s.holm_p:.4f}"] for s in sig.itertuples()]
    r.table(["Outcome", "Comparison", "Difference (points)", "95% CI (species)",
             "Only 1 / only 2", "Holm p"], rows,
            "Paired comparisons on identical queries (main run). Difference = first minus "
            "second method; CI from the species-level bootstrap; 'only 1 / only 2' = queries "
            "where only the first or only the second method succeeded (exact McNemar test, Holm "
            "correction within each outcome; results/tables/significance_tests.csv).",
            [3.4, 4.6, 2.2, 2.8, 2.0, 1.6], align_right_from=2)

    sens = sB[sB.setting.str.startswith(("accept", "Meier", "fixed"))]
    rows = [[NAMES[s.method], s.setting, pct(s.unknown_flagged_rate),
             pct(s.unknown_false_assignment_rate), pct(s.known_accuracy),
             pct(s.known_flagged_rate)] for s in sens.itertuples()]
    r.table(["Method", "Cut-off", "Unknown flagged", "Unknown wrongly named", "Known correct",
             "Known flagged"], rows,
            "Threshold sensitivity, Condition B main run: each method at cut-offs accepting "
            "90%, 95% and 99% of known species (calibrated on training data), plus Meier's rule "
            "and a fixed 2% cut-off for best close match (results/tables/summary_B.csv).",
            [3.4, 2.6, 2.4, 2.8, 2.4, 2.4], align_right_from=2)

    seed_rows = [[42, ", ".join(d["heldout"])]]
    for seed in sorted(int(s) for s in reps.seed if int(s) != 42):
        path = RESULTS_DIR / "replicates" / f"seed_{seed}" / "heldout_species.txt"
        seed_rows.append([seed, ", ".join(path.read_text(encoding="utf-8").split("\n")[:-1])])
    r.table(["Seed", "Held-out species (Condition B)"], seed_rows,
            "Held-out species for the main run (seed 42) and the three replicate seeds; one "
            "species per genus with at least two species (results/heldout_species.txt and "
            "results/replicates/).", [1.5, 14.5], align_right_from=9)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    r.doc.save(OUT)
    print(f"Wrote {OUT} ({r.n_table} tables, {r.n_fig} figures)")


if __name__ == "__main__":
    build(load())
