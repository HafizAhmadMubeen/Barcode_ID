"""build_slides.py: build the presentation (Phase 6) as a PowerPoint deck.

Like the report, every number is read from results/ (via report/build_report.py's
loader), so the slides always match the analysis. Speaker notes on every slide
help the team practise the 15-20 minute talk.

Output: presentation/BarcodeID_slides.pptx

Run from the repo root (needs requirements-report.txt):
    python presentation/build_slides.py
"""
import sys
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "report"))
from config import FIGURES_DIR  # noqa: E402
from build_report import load, pct  # noqa: E402

OUT = ROOT / "presentation" / "BarcodeID_slides.pptx"

# Palette: deep pond teal (dominant), white content slides, one amber accent.
POND = RGBColor(0x0F, 0x3B, 0x40)
POND_LIGHT = RGBColor(0xE6, 0xF0, 0xEF)
AMBER = RGBColor(0xE0, 0x9F, 0x1F)
INK = RGBColor(0x1A, 0x1A, 0x1A)
MUTED = RGBColor(0x5A, 0x5A, 0x55)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SAFE = RGBColor(0x0C, 0x8A, 0x0C)
AMBER_TEXT = RGBColor(0x8A, 0x5A, 0x00)   # darker amber: readable on light cards
DANGER = RGBColor(0xC0, 0x35, 0x35)
HEAD, BODY = "Cambria", "Calibri"
W, H = 13.333, 7.5


class Deck:
    def __init__(self):
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = Inches(W), Inches(H)
        self.blank = self.prs.slide_layouts[6]
        self.n = 0

    def slide(self, dark=False, notes=""):
        s = self.prs.slides.add_slide(self.blank)
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = POND if dark else WHITE
        s.notes_slide.notes_text_frame.text = notes
        self.n += 1
        if self.n > 1:                                   # slide number, bottom right
            self.text(s, str(self.n), W - 1.0, H - 0.5, 0.5, 0.3, 10,
                      color=WHITE if dark else MUTED, align=PP_ALIGN.RIGHT)
        return s

    def text(self, s, content, x, y, w, h, size, bold=False, color=INK, font=BODY,
             align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, italic=False):
        """A text box. content: a string, or a list of paragraphs, each a string or
        a list of (text, {"bold":..., "color":...}) runs."""
        box = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = box.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = anchor
        for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
            setattr(tf, side, 0)
        paragraphs = content if isinstance(content, list) else [content]
        for i, para in enumerate(paragraphs):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            p.space_after = Pt(size * 0.45)
            runs = para if isinstance(para, list) else [(para, {})]
            for txt, opt in runs:
                r = p.add_run()
                r.text = txt
                r.font.size, r.font.name = Pt(opt.get("size", size)), opt.get("font", font)
                r.font.bold = opt.get("bold", bold)
                r.font.italic = opt.get("italic", italic)
                r.font.color.rgb = opt.get("color", color)
        return box

    def title(self, s, text, dark=False):
        self.text(s, text, 0.6, 0.45, W - 1.2, 0.9, 34, bold=True, font=HEAD,
                  color=WHITE if dark else POND)

    def card(self, s, x, y, w, h, fill=POND_LIGHT):
        shape = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        shape.adjustments[0] = 0.08
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
        shape.line.fill.background()
        shape.shadow.inherit = False
        return shape

    def badge(self, s, label, x, y, d=0.62, fill=POND, color=WHITE, size=18):
        """A numbered/lettered circle, the deck's visual motif."""
        c = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
        c.fill.solid()
        c.fill.fore_color.rgb = fill
        c.line.fill.background()
        c.shadow.inherit = False
        tf = c.text_frame
        for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
            setattr(tf, side, 0)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = label
        r.font.size, r.font.bold, r.font.name, r.font.color.rgb = Pt(size), True, HEAD, color

    def stat(self, s, value, label, x, y, w, color=POND, size=54):
        self.text(s, value, x, y, w, 0.95, size, bold=True, font=HEAD, color=color)
        self.text(s, label, x, y + 0.95, w, 0.8, 14, color=MUTED)

    def picture(self, s, filename, x, y, w=None, h=None):
        """Add a figure, keeping its aspect ratio; give w or h (inches)."""
        path = FIGURES_DIR / filename
        with Image.open(path) as im:
            ratio = im.height / im.width
        if w is None:
            w = h / ratio
        s.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w), Inches(w * ratio))
        return w * ratio

    def save(self):
        OUT.parent.mkdir(parents=True, exist_ok=True)
        self.prs.save(OUT)


def build(d):
    deck = Deck()
    meta, sA, sb = d["meta"], d["summary_A"].set_index("method"), d["summary_B"].set_index(["method", "setting"])
    loso = d["loso_overall"].set_index(["subset", "method"])
    reps = d["replicates_summary"]
    run_ms = d["runtime"].groupby("method").ms_per_query.median()
    sig = d["significance_tests"]
    log = d["cleaning_log"]
    L = lambda subset, m, col: loso.loc[(subset, m), col]  # noqa: E731
    acc = sA.accuracy
    loso_nj, loso_knn = L("all", "nj", "false_assignment_rate_mean"), L("all", "knn_k6", "false_assignment_rate_mean")
    clean_nj = L("excluding barcode-sharing", "nj", "false_assignment_rate_mean")
    clean_knn = L("excluding barcode-sharing", "knn_k6", "false_assignment_rate_mean")
    clean_genus = L("excluding barcode-sharing", "knn_k6", "flagged_correct_genus_rate_mean")
    n_loso = int(L("all", "knn_k6", "n_species"))
    n_clean = int(L("excluding barcode-sharing", "knn_k6", "n_species"))
    speed = run_ms["nj"] / run_ms["knn_k6"]
    b_nj, b_knn = sb.loc[("nj", "rule")], sb.loc[("knn_k6", "accept 95%")]
    b_bcm95 = sb.loc[("bcm", "accept 95%")]
    sig_A = sig[(sig.outcome == "A_correct") & (sig.method_1 == "nj")]
    n_sharing = len(d["barcode_sharing_species"])

    # 1 ---------------------------------------------------------- title --
    s = deck.slide(dark=True, notes=(
        "Introduce the project in one sentence: we compared a classic phylogenetic tree with "
        "machine-learning classifiers for identifying dragonflies and damselflies from DNA "
        "barcodes, and focused on what happens when the species is not in the reference "
        "database."))
    deck.text(s, "BarcodeID", 0.9, 1.6, 11, 1.2, 60, bold=True, font=HEAD, color=WHITE)
    deck.text(s, "Machine learning vs phylogenetic trees for DNA barcode species identification",
              0.9, 2.85, 11, 1.2, 26, font=HEAD, color=WHITE)
    deck.text(s, "What happens when the species is not in the database?", 0.9, 4.15, 11, 0.6, 20,
              italic=True, color=AMBER)
    deck.text(s, ["European dragonflies and damselflies (Odonata) · COI barcodes from BOLD",
                  "Project team: Data & Phylogenetics · Machine Learning · Experiments & Report"],
              0.9, 5.6, 11, 1.0, 15, color=WHITE)

    # 2 -------------------------------------------------------- question --
    s = deck.slide(notes=(
        "Reference databases are never complete. Most studies only test species that are in "
        "the database. We test both: Condition A, every test species is in the database; "
        "Condition B, some species are removed entirely. A safe method says 'unknown' or at "
        "least the right genus. A dangerous method confidently names the wrong species."))
    deck.title(s, "The question: which method can you trust?")
    deck.text(s, "A barcode is a ~650-letter piece of the COI gene. We identify a specimen by "
              "comparing it with reference barcodes of known species, but reference databases "
              "are never complete.", 0.6, 1.45, 12.1, 0.9, 18, color=MUTED)
    for i, (label, head, body, fill) in enumerate([
            ("A", "Condition A: full coverage",
             "Every test species is in the reference database. The usual benchmark.", POND_LIGHT),
            ("B", "Condition B: incomplete coverage",
             "Some species are removed from the database entirely, then queried as 'unknown'. "
             "This is our focus.", RGBColor(0xFB, 0xF1, 0xDC))]):
        x = 0.6 + i * 6.25
        deck.card(s, x, 2.7, 5.85, 2.1, fill)
        deck.badge(s, label, x + 0.35, 2.95, fill=POND if i == 0 else AMBER)
        deck.text(s, head, x + 1.2, 2.98, 4.4, 0.5, 20, bold=True, color=POND)
        deck.text(s, body, x + 1.2, 3.55, 4.4, 1.1, 16)
    deck.text(s, [[("Fails safely: ", {"bold": True, "color": SAFE}),
                   ("says 'unknown', or at least names the right genus", {})],
                  [("Fails dangerously: ", {"bold": True, "color": DANGER}),
                   ("confidently names the wrong species", {})]],
              0.6, 5.25, 12.1, 1.2, 18)

    # 3 ------------------------------------------------------------ data --
    s = deck.slide(notes=(
        f"Data came from BOLD Systems, the public barcode database. All Odonata was far too "
        f"large, so we took two families with many close relatives, from 30 European countries. "
        f"Cleaning was logged at every step: from {log.n_sequences.iloc[0]:,} raw records to "
        f"{len(meta)} clean, unique barcodes of {meta.species.nunique()} species. We removed "
        f"mislabels, trimmed overlong sequences, removed duplicates and 7 likely contaminants, "
        f"and kept species with at least 3 sequences."))
    deck.title(s, "Data: 779 clean barcodes of 45 species")
    stats = [(f"{log.n_sequences.iloc[0]:,}", "raw BOLD records\n(all European Odonata)"),
             (f"{len(meta)}", "clean, unique\nCOI barcodes"),
             (f"{meta.species.nunique()}", f"species in {meta.genus.nunique()} genera,\n2 families"),
             ("30", "European countries\nsearched")]
    for i, (v, lab) in enumerate(stats):
        deck.stat(s, v, lab, 0.6 + i * 3.1, 1.6, 2.9, color=AMBER if i == 1 else POND)
    deck.card(s, 0.6, 3.9, 12.1, 2.75)
    steps = ["Download\nfrom BOLD", "Keep COI-5P,\n2 families", "Remove\nmislabels",
             "Trim to\nbarcode", "Remove duplicates\n& outliers", "≥ 3 sequences\nper species"]
    for i, step in enumerate(steps):
        x = 0.9 + i * 1.98
        deck.badge(s, str(i + 1), x + 0.55, 4.15, d=0.55, size=16)
        deck.text(s, step, x, 4.85, 1.7, 0.9, 14, align=PP_ALIGN.CENTER)
    deck.text(s, "Libellulidae (skimmers) and Coenagrionidae (narrow-winged damselflies): many "
              "closely related species, so 'is this a close relative?' can be tested.",
              0.9, 5.85, 11.5, 0.7, 14, color=MUTED, italic=True)

    # 4 --------------------------------------------------------- methods --
    th = d["ml_thresholds"]
    s = deck.slide(notes=(
        "Four methods, all given exactly the same queries. The NJ tree uses an explicit rule we "
        "fixed in advance; its only way to abstain is 'ambiguous'. k-NN and random forest use "
        "k-mer frequencies, the counts of short letter patterns, and get an 'unknown' threshold "
        "calibrated on training data only: flag a query when the model is less confident than "
        "for 95% of known species. Best close match is the classic barcoding rule from Meier et "
        "al. 2006, added to test whether any advantage is machine learning or just the cut-off."))
    deck.title(s, "Four methods, the same queries")
    methods = [
        ("NJ", "Neighbor-Joining tree", "Build a tree of reference + query barcodes. Answer = the "
         "species in the smallest clade around the query.", "Unknown? Only 'ambiguous' if that "
         "clade has several species"),
        ("kNN", "k-nearest neighbours", "Compare k-mer profiles; the 5 most similar reference "
         "barcodes vote.", "Unknown? If the nearest reference is too far away"),
        ("RF", "Random forest", "500 decision trees learn which k-mer patterns point to which "
         "species.", "Unknown? If its top probability is too low"),
        ("BCM", "Best close match", "Classic barcoding rule: species of the closest reference "
         "barcode (K2P distance).", "Unknown? If the closest one is beyond a cut-off"),
    ]
    for i, (badge, name, how, unk) in enumerate(methods):
        x = 0.6 + i * 3.08
        deck.card(s, x, 1.6, 2.85, 4.9)
        deck.badge(s, badge, x + 0.25, 1.85, d=0.85, size=15)
        deck.text(s, name, x + 0.25, 2.9, 2.4, 0.8, 19, bold=True, color=POND)
        deck.text(s, how, x + 0.25, 3.7, 2.4, 1.6, 15)
        deck.text(s, unk, x + 0.25, 5.35, 2.4, 1.0, 14, italic=True, color=AMBER_TEXT)
    deck.text(s, "k-NN and RF use k-mer frequencies (k = 4 and k = 6); 'unknown' thresholds are "
              "calibrated on training data only, accepting 95% of known species.",
              0.6, 6.7, 12.1, 0.5, 13, color=MUTED)

    # 5 ---------------------------------------------------------- design --
    s = deck.slide(notes=(
        "Condition A: a 70/30 split within each species, 543 training and 236 test sequences. "
        "Condition B: one species per genus removed from training, 139 unknown queries. Then two "
        "robustness checks: three more random splits, and the strongest one, holding out every "
        "one of the 39 eligible species on its own, with a new tree and retrained models each "
        "time, so the result cannot depend on a lucky choice of species."))
    deck.title(s, "Experiment: from one split to every species")
    n_train = (d["split_A"].set == "train").sum()
    n_test = (d["split_A"].set == "test").sum()
    n_unk = (d["split_B"].set == "test_unknown").sum()
    flow = [("1", "Condition A", f"70/30 split within each species\n{n_train} train · {n_test} test queries"),
            ("2", "Condition B", f"8 species removed entirely\n{n_unk} unknown queries"),
            ("3", "3 more seeds", "new splits and new\nheld-out species"),
            ("4", "Every species once", f"each of {n_loso} species held out\nalone: no luck involved")]
    for i, (num, head, body) in enumerate(flow):
        x = 0.6 + i * 3.1
        deck.card(s, x, 1.9, 2.8, 3.1, POND_LIGHT if i < 3 else RGBColor(0xFB, 0xF1, 0xDC))
        deck.badge(s, num, x + 0.25, 2.15, fill=POND if i < 3 else AMBER)
        deck.text(s, head, x + 0.25, 3.0, 2.4, 0.5, 20, bold=True, color=POND)
        deck.text(s, body, x + 0.25, 3.6, 2.4, 1.3, 15)
        if i < 3:
            arrow = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x + 2.83), Inches(3.3),
                                       Inches(0.24), Inches(0.35))
            arrow.fill.solid()
            arrow.fill.fore_color.rgb = MUTED
            arrow.line.fill.background()
    deck.text(s, [[("Also: ", {"bold": True}),
                   ("species-level confidence intervals and McNemar tests · thresholds at 90/95/99% · "
                    "runtime on the same laptop", {})]], 0.6, 5.5, 12.1, 0.8, 16, color=MUTED)

    # 6 ---------------------------------------------------- result: known --
    s = deck.slide(notes=(
        f"On species that ARE in the database, everything works about equally well: the NJ tree "
        f"{pct(acc['nj'])}, k-NN {pct(acc['knn_k6'])}, random forest {pct(acc['rf_k6'])}. The "
        f"statistics say these differences are noise: Holm-corrected McNemar p = "
        f"{sig_A.holm_p.min():.1f}. The dots are the three replicate splits. Every remaining error "
        f"is between species that share the same barcode."))
    deck.title(s, "Known species: all methods are equally good")
    deck.picture(s, "accuracy_A.png", 0.5, 1.45, w=7.6)
    deck.stat(s, "~92%", "correct for the NJ tree, k-NN\nand random forest (Condition A)", 8.6, 1.7, 4.2)
    deck.text(s, [[("No significant difference ", {"bold": True, "color": POND}),
                   (f"between the tree and any classifier (Holm p = {sig_A.holm_p.min():.1f}).", {})],
                  "Their errors are all between species that share a barcode with a close "
                  "relative. Best close match is lower: it answers 'ambiguous' for those."],
              8.6, 3.6, 4.2, 2.6, 17)

    # 7 -------------------------------------------------- result: unknown --
    s = deck.slide(notes=(
        f"Now the species is missing from the database. Read the colours: green is safe, yellow "
        f"a wrong species in the right genus, red a wrong genus. The NJ tree named a wrong "
        f"species for {pct(b_nj.unknown_false_assignment_rate, 0)} of unknown queries. Without a "
        f"threshold the classifiers always name a known species, and random forest even picks "
        f"the wrong genus. With the calibrated threshold, k-NN flagged every unknown query and "
        f"still gave the correct genus."))
    deck.title(s, "Unknown species: the methods split apart")
    deck.picture(s, "condition_B_outcomes.png", 0.4, 1.35, h=5.85)
    deck.stat(s, pct(b_nj.unknown_false_assignment_rate, 0), "NJ tree: unknown species\ngiven a wrong name",
              9.1, 1.6, 3.8, color=DANGER, size=50)
    deck.stat(s, pct(b_knn.unknown_false_assignment_rate, 0), "k-NN with its threshold:\nall flagged 'unknown'",
              9.1, 3.55, 3.8, color=SAFE, size=50)
    deck.text(s, "Main run: 8 held-out species, 139 unknown queries", 9.1, 5.6, 3.8, 0.6, 13,
              color=MUTED, italic=True)

    # 8 ------------------------------------------------------- every species --
    s = deck.slide(notes=(
        f"Is that just a lucky choice of 8 species? We removed every one of the {n_loso} "
        f"eligible species on its own. Averaged over species, the tree wrongly named the missing "
        f"species {pct(loso_nj, 0)} of the time, k-NN {pct(loso_knn, 0)}. For the {n_clean} "
        f"species that do not share their barcode, k-NN never named a wrong species, not for a "
        f"single query, and still gave the correct genus {pct(clean_genus, 0)} of the time. The "
        f"tree even put two species into the wrong genus."))
    deck.title(s, "Every species held out once")
    deck.card(s, 0.6, 1.55, 6.2, 2.45)
    deck.text(s, f"All {n_loso} species", 0.95, 1.75, 5.5, 0.5, 18, bold=True, color=POND)
    deck.stat(s, pct(loso_nj, 0), "NJ tree wrongly named", 0.95, 2.2, 2.6, color=DANGER, size=48)
    deck.stat(s, pct(loso_knn, 0), "k-NN wrongly named", 3.75, 2.2, 2.6, color=SAFE, size=48)
    deck.card(s, 0.6, 4.25, 6.2, 2.45, RGBColor(0xFB, 0xF1, 0xDC))
    deck.text(s, f"{n_clean} species without barcode sharing", 0.95, 4.45, 5.6, 0.5, 18, bold=True, color=POND)
    deck.stat(s, pct(clean_nj, 0), "NJ tree wrongly named", 0.95, 4.9, 2.6, color=DANGER, size=48)
    deck.stat(s, pct(clean_knn, 0), f"k-NN wrongly named\n(correct genus {pct(clean_genus, 0)})",
              3.75, 4.9, 2.6, color=SAFE, size=48)
    deck.picture(s, "loso_per_species.png", 7.75, 1.4, h=5.75)

    # 9 --------------------------------------------------------- sharing --
    ss = d["sharing_split"]
    only = ss[ss.subset == "barcode-sharing only"]
    s = deck.slide(notes=(
        f"Why do even the good methods sometimes fail? {n_sharing} species share their barcode "
        f"with a close relative; BOLD puts them in the same BIN. If a missing species looks "
        f"exactly like one in the database, no method using the barcode alone can tell it is "
        f"missing. Remove those species and the failures of k-NN disappear completely. This is a "
        f"limit of the barcode, not of the method."))
    deck.title(s, "Why methods fail: shared barcodes")
    deck.picture(s, "barcode_sharing.png", 0.5, 1.5, w=8.0)
    deck.text(s, [[(f"{n_sharing} species ", {"bold": True, "color": POND}),
                   ("share a BOLD BIN with a close relative (e.g. Coenagrion puella and C. pulchellum).", {})],
                  [("Without them, ", {"bold": True, "color": SAFE}),
                   ("k-NN made no false identifications in any run.", {})],
                  [("With them, ", {"bold": True, "color": DANGER}),
                   (f"every method fails often across the 4 runs (k-NN up to "
                    f"{pct(only[only.method == 'knn_k6'].unknown_false_assignment_rate.max(), 0)}, "
                    f"NJ up to {pct(only[only.method == 'nj'].unknown_false_assignment_rate.max(), 0)}).", {})]],
              8.9, 1.8, 4.0, 4.8, 17)

    # 10 ------------------------------------------------- where safety from --
    s = deck.slide(notes=(
        f"Is it machine learning that makes k-NN safe? We tested the classic best-close-match "
        f"rule with the same kind of cut-off: it also flagged "
        f"{pct(b_bcm95.unknown_flagged_rate, 0)} of unknown species. So the safety comes from "
        f"having a calibrated distance cut-off. What k-NN adds is that it loses fewer known "
        f"species at the same safety: {pct(b_knn.known_accuracy, 0)} correct versus "
        f"{pct(b_bcm95.known_accuracy, 0)}."))
    deck.title(s, "Where does the safety come from?")
    cols = [("Best close match", "same cut-off as k-NN", pct(b_bcm95.unknown_flagged_rate, 0),
             pct(b_bcm95.known_accuracy, 0)),
            ("k-NN", "calibrated cut-off", pct(b_knn.unknown_flagged_rate, 0), pct(b_knn.known_accuracy, 0))]
    for i, (name, sub, unk, kno) in enumerate(cols):
        x = 0.6 + i * 4.3
        deck.card(s, x, 1.6, 3.9, 4.6, POND_LIGHT if i == 0 else RGBColor(0xFB, 0xF1, 0xDC))
        deck.text(s, name, x + 0.35, 1.85, 3.3, 0.5, 22, bold=True, color=POND)
        deck.text(s, sub, x + 0.35, 2.4, 3.3, 0.4, 14, italic=True, color=MUTED)
        deck.stat(s, unk, "unknown species flagged", x + 0.35, 2.95, 3.3, color=SAFE, size=46)
        deck.stat(s, kno, "known species still correct", x + 0.35, 4.55, 3.3, color=POND, size=46)
    deck.text(s, [[("The safety comes from the cut-off, ", {"bold": True, "color": POND}),
                   ("not from machine learning itself.", {})],
                  [("What k-NN adds: ", {"bold": True, "color": POND}),
                   ("far fewer losses on known species: its vote among five neighbours resolves "
                    "near-ties that the plain distance rule calls 'ambiguous'.", {})],
                  [("Condition B, main run.", {"italic": True, "color": MUTED, "size": 13})]],
              9.4, 1.9, 3.5, 4.4, 17)

    # 11 ----------------------------------------------------------- speed --
    s = deck.slide(notes=(
        f"Speed, measured on the same laptop for the same 236 queries: the tree pipeline takes "
        f"{run_ms['nj']:,.0f} ms per query, k-NN {run_ms['knn_k6']:.1f} ms, about "
        f"{speed:.0f} times faster. The tree has no training, but it must be rebuilt with all "
        f"reference barcodes whenever new queries arrive, and that cost grows steeply with the "
        f"database. Training a classifier takes about one second."))
    deck.title(s, f"Speed: about {round(speed, -1):.0f} times faster")
    deck.picture(s, "runtime.png", 0.5, 1.5, w=8.0)
    deck.stat(s, f"{speed:.0f}×", "faster per query:\nk-NN vs the NJ tree", 9.0, 1.7, 3.9, color=AMBER, size=60)
    deck.text(s, [f"NJ: {run_ms['nj']:,.0f} ms per query, and the whole tree must be rebuilt for new queries.",
                  f"k-NN: {run_ms['knn_k6']:.1f} ms per query after ~1 second of training."],
              9.0, 3.75, 3.9, 2.6, 16)

    # 12 ----------------------------------------------------- limitations --
    s = deck.slide(notes=(
        "Be honest about the limits. One group, one gene, one region. A small dataset. Barcode "
        "sharing that no barcode-only method can solve. And the comparison is not perfectly "
        "like-for-like: we gave the tree no extra 'unknown' threshold, on purpose, to test the "
        "method as usually applied. A distance threshold on the tree could make it safer."))
    deck.title(s, "Limitations")
    lims = [("1", "One group, one gene", "Two European Odonata families, COI only, BOLD data of 9 Oct 2026."),
            ("2", "Small dataset", f"{len(meta)} sequences of {meta.species.nunique()} species; some species have only 3."),
            ("3", "Barcode sharing", f"{n_sharing} species can't be separated by any barcode-only method."),
            ("4", "Tree not fully like-for-like", "NJ had no extra 'unknown' threshold; one tree for all queries.")]
    for i, (num, head, body) in enumerate(lims):
        x = 0.6 + (i % 2) * 6.25
        y = 1.7 + (i // 2) * 2.4
        deck.card(s, x, y, 5.85, 2.05)
        deck.badge(s, num, x + 0.35, y + 0.35)
        deck.text(s, head, x + 1.25, y + 0.35, 4.3, 0.5, 20, bold=True, color=POND)
        deck.text(s, body, x + 1.25, y + 0.95, 4.3, 1.0, 16)

    # 13 ------------------------------------------------------ conclusion --
    s = deck.slide(dark=True, notes=(
        "Our one-sentence answer, and the practical advice: for identification, use a "
        "distance-aware method with a calibrated 'unknown' threshold, such as k-NN, rather than "
        "reading a species name off a tree; report barcode-sharing groups at genus level. Then "
        "invite questions."))
    deck.text(s, "Conclusion", 0.9, 0.7, 11, 0.9, 34, bold=True, font=HEAD, color=AMBER)
    deck.text(s, [[("Machine learning matched the tree on known species ", {}),
                   (f"({pct(acc['knn_k6'], 0)} vs {pct(acc['nj'], 0)}) ", {"bold": True}),
                   ("but wrongly named unknown species over four times less often ", {}),
                   (f"({pct(loso_knn, 0)} vs {pct(loso_nj, 0)}, {n_loso} species) ", {"bold": True}),
                   ("and was ", {}), (f"~{speed:.0f}× faster.", {"bold": True})]],
              0.9, 1.75, 11.5, 2.0, 28, font=HEAD, color=WHITE)
    deck.text(s, ["Use a distance-aware method with a calibrated 'unknown' threshold, not a "
                  "species name read off a tree.",
                  "Report barcode-sharing groups at genus level: no barcode-only method separates them."],
              0.9, 4.3, 11.5, 1.6, 18, color=WHITE)
    deck.text(s, "Questions?", 0.9, 6.2, 6, 0.6, 22, bold=True, font=HEAD, color=AMBER)

    deck.save()
    print(f"Wrote {OUT} ({deck.n} slides)")


if __name__ == "__main__":
    build(load())
