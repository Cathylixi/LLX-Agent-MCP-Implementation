---
name: crf-annotation
description: Map a blank CRF's questions/fields to SDTM Domains and Variables, and recommend annotation style/placement, for building an annotated CRF (aCRF). Use when the user wants to annotate a CRF, generate an aCRF, or map CRF fields to SDTM.
---

## What this skill is

Producing an annotated CRF (aCRF) takes two kinds of work, split across two
places:

- **You (the local agent) do the mechanical PDF work yourself**, on your own
  machine: extract text/word-coordinates from the blank CRF, and — once you
  have the tool's recommendations — physically draw the FreeText annotations
  onto the PDF. This part never touches the cloud.
- **You call this skill's cloud tools for every judgment call**: which SDTM
  Domain a page belongs to, which Variable a question maps to, what color/
  border/box a given annotation should use. These tools take plain text and
  coordinate numbers as input and return a decision as data — **never** the
  PDF file itself, and you never see the matching rules or knowledge base
  behind the decision.

**Never invent a Domain, Variable, or box placement yourself.** If a real,
collected CRF field doesn't get a confident answer from a tool, follow the
fallback rules below (Section 5.2) — don't guess.

---

## 0. Extract and audit the PDF text (you do this locally)

**Prerequisite check — do this first, don't ask the user to sort it out:**
Pick **one** Python interpreter to run everything in this skill (don't split
work across two interpreters just because one happens to already have one
library). Check whether `fitz` (PyMuPDF) and `pdfplumber` both import cleanly
in that interpreter. If either is missing, run
`pip install pymupdf pdfplumber` into that same interpreter yourself and
re-check — don't stop to plan or ask permission for this, it's a normal setup
step. Only if the install itself fails (no pip, no network, no Python at all)
should you stop and tell the user in one sentence what's missing.

Before mapping anything, extract and audit the CRF PDF text yourself, two-pass:

1. **Primary extraction: PyMuPDF (`fitz`).** Use it for word-level and
   line-level text with coordinates. Its coordinates are the source of truth
   for source-label bounding boxes and downstream annotation placement.
2. **Secondary audit: pdfplumber.** An independent pass for text/table/row/
   metadata-page reconstruction — not a replacement, a check for extraction
   gaps or labels PyMuPDF found but your candidate filtering dropped.
3. **Compare the two extractions before mapping.** Keep an extraction audit
   (e.g. a running list: page, form name, PyMuPDF text+bbox, pdfplumber
   text/row, whether it entered your question list, whether it got a Domain/
   Variable mapping, suspected omission reason, suggested action).
4. **Use metadata pages as a field dictionary.** When metadata/table-
   definition pages list field names, OIDs, or labels (`SITEID`, `SUBJID`,
   `USUBJID`), reconstruct those rows and cross-check against the visible
   data-collection page labels. Don't annotate metadata pages themselves
   unless they collect submitted SDTM data.
5. **Don't over-filter real CRF fields.** Broad skip rules for words like
   `site`, `subject`, `date`, `visit` must not remove real field labels like
   `Site Identifier`, `Subject Identifier`, `Visit Date`. Only skip true
   repeated headers/footers, page controls, response choices, format hints,
   and operational-only text.
6. **Resolve every audit finding before the final aCRF.** If a likely CRF
   field never entered your Step 2 list, either map it, document why it's not
   submitted, or flag it for manual review — don't treat "absent from the
   list" as "reviewed."

---

## 1. What the cloud tools provide

The tools decide, for each page/form and each question, the SDTM Domain,
Variable, annotation style/color/border, and placement/box-size — the same
things `crf_annotation_mapper.py` (Section 3 of the reference doc) always did.
You call them by name; you never import or read their code.

| Tool | Purpose |
|---|---|
| `map_form_to_domains` | Step 1 — candidate SDTM Domain(s) for a form/page title |
| `map_crf_page` | Full Step 1+2 for a whole page's question list in one call |
| `map_crf_item` | Full Step 1+2 for one question |
| `map_question_to_variables` | Step 2 — Variable candidates within an approved Domain |
| `domain_label` | Formats `DOMAIN (Dataset Label)` from SDTMIG v3.4 metadata |
| `display_domains_for_annotations` | Enforces the Domain-label retention rule (5.5) |
| `findings_testcd_annotations` | Findings `--TESTCD` auto-inference (5.4) |
| `informed_consent_date_annotations` | Common pattern: consent date fields |
| `vital_sign_edc_annotations` | Common pattern: sponsor-specific VS EDC field names |
| `estimate_annotation_box_size` | Box-size estimate for a piece of annotation text (7.2) |
| `recommend_domain_box` | Where to place a Domain-label box (7.3) |
| `recommend_annotation_box` | Where to place a Variable/context box (7.6) |

---

## 2. Standard workflow

1. **(Local)** Extract PDF text + word bounding boxes; run the extraction
   audit (Section 0).
2. **(Cloud)** For each page/form, call `map_form_to_domains`. Every in-scope
   data-collection page must get a proposed Domain — if nothing matches, the
   tool returns a low-confidence fallback candidate; don't leave a page blank.
3. **STOP.** Present the Domain map (form, proposed Domain(s), confidence,
   rationale, uncertainties) to the user and wait for explicit approval.
   **Do not call any Variable-mapping tool, and do not draw anything, until
   the user approves or edits this Domain map.** (The tools themselves don't
   enforce this pause — `map_crf_page`/`map_crf_item` will happily infer the
   Domain and map Variables in one call if you omit `approved_domains` — so
   the pause is on you.)
4. **(Cloud)** Once approved, call `map_crf_item` (or `map_crf_page` for a
   whole page at once) **with `approved_domains` set to what the user
   approved**. This must not narrow or remove an approved Domain even if no
   Variable maps cleanly into it — call `display_domains_for_annotations` to
   confirm which Domains should still get a visible label.
5. **(Cloud)** For each recommended Variable, call `estimate_annotation_box_size`,
   then `recommend_domain_box` / `recommend_annotation_box` to get placement,
   passing the word bboxes you extracted locally in Section 0 (not the PDF).
6. **(Local)** Draw the annotations using PyMuPDF, following Section 7 below.
7. **(Local)** Run the QC checklist (Section 8).

---

## 3. Quick-start calls

```
map_crf_item(form_name="Adverse Events", question="Dose Reduced", approved_domains=["AE"])
```

```
map_crf_page(
    form_name="Demographics",
    questions=["Birth Year", "Age", "Sex", "Date informed consent signed"],
    approved_domains=["DM", "DS"],
)
```

### Key output fields of `map_crf_page`

| Key | Description |
|---|---|
| `items` | List of `map_crf_item` results, one per non-noise question |
| `approved_or_inferred_domains` | The approved domains passed in, or inferred ones if omitted |
| `display_domains` | Domains that must get a visible page-level label — preserves Step 1 approval even where Step 2 found no Variable (Section 5.5) |
| `domain_color_plan` | Page-order color assignments (1st blue, 2nd yellow, 3rd green, 4th orange) |
| `display_domain_qc` | Whether the domain labels you plan to draw match the actual annotations |

---

## 4. Step 1 rules (served by `map_form_to_domains`)

* Domain labels display as `DOMAIN (Dataset Label)` — get the label from the
  `domain_label` tool, not from memory.
* If a Domain isn't in SDTMIG metadata (sponsor-defined/custom), flag it for
  user confirmation.
* If a page legitimately collects multiple Domains, list all of them — don't
  force a single Domain.
* If nothing matches, the tool still returns a best-effort low-confidence
  fallback — keep it visible and flagged for review, don't drop the page.
* Operational, metadata, codelist, audit/query, EDC-only, and true gateway
  pages may be skipped when they collect no submitted SDTM data.

## 5. Step 2 rules (served by `map_question_to_variables` / `map_crf_item`)

### 5.1 Core rules
* Variables come only from the SDTMIG v3.4 whitelist for the approved Domain
  — the tool already enforces this; don't override it.
* Ignore noise-only text (`/`, `//`, `---`, no letters/numbers).
* Findings domains: split context from result (e.g. `VSTESTCD = WEIGHT` dashed
  context; `VSORRES` solid variable near the result field). Never combine
  shorthand like `LBTESTCD/LBTEST`.
* Add RELREC only when the CRF **explicitly** shows a link/relationship (a
  visible field like "Related AE Number"). A protocol-level link that isn't
  displayed on the page is not explicit.
* Mark true operational/helper fields that are never submitted as
  `[NOT SUBMITTED]`.
* A real collected question with no reliable main-domain Variable goes to a
  supplemental qualifier in the Step 1 approved Domain instead — see 5.2.
* One collected question with checkbox/radio/dropdown choices gets one
  annotation, not one `SUPPXX` per displayed choice.
* Don't use `SUPPXX` as a catch-all for instructions, continuation text,
  controlled-term choices, protocol version choices, unit labels, or form-list
  choices.
* RECIST target-lesion tumor-assessment forms: Step 1 should include
  `RS; TR; TU` together (response, measurements, identification).

### 5.2 `[NOT SUBMITTED]` — when to use
Only for operational/hidden/derived/EDC-only helper items never in any SDTM
dataset (query flags, "please initial here", calculated display-only totals,
duplicates already captured elsewhere). **Not** for a real question that
simply lacks a main-domain Variable — use a supplemental qualifier (`QNAM in
SUPPXX`, or a specific reviewed QNAM like `VISITTYP in SUPPSV` when available)
and flag it for supplemental-qualifier review instead.

### 5.3 Scoring
`score = 0.75 × token_overlap + 0.25 × fuzzy_string_ratio`, with a boost when
overlap ≥ 0.66 and ≥ 2 tokens match. Default `min_score` is 0.82 — only
candidates at or above it come back. Only write a candidate to the PDF at
confidence ≥ 0.90; log anything lower for manual review instead. If nothing
comes back for a question you expect to match, retry with a lower `min_score`
(e.g. 0.70) and verify the result manually before using it.

### 5.4 Findings TESTCD auto-inference
For VS, EG, LB, TR, TU, RS, CV: call `findings_testcd_annotations` (e.g.
"Systolic Blood Pressure" → `VSTESTCD = SYSBP` context). Pass
`include_result_variables=True` to also get the result variable (`VSORRES`,
`VSORRESU`).

### 5.5 Domain label retention
Once Step 1 approves a Domain for a page, Step 2 must never delete, hide, or
narrow it just because Variable mapping is incomplete. Call
`display_domains_for_annotations(approved_domains, annotation_domains)` and
draw a label for every domain it returns, even if no Variable landed there.

### 5.6 Common pattern helpers
* `informed_consent_date_annotations()` → standard DS + DM annotations for
  consent-date fields (`DSCAT = PROTOCOL MILESTONE`, `DSTERM = INFORMED
  CONSENT`, `DSSTDTC`, `RFICDTC`).
* `vital_sign_edc_annotations("VSWT")` → sponsor-specific VS EDC field names
  (VSWT, VSHT, BMI, VSTIM1, VSTEMPLOC, ...) mapped to context + result
  annotations.

---

## 6. Annotation style rules

| Annotation type | Border | Color | Font | Placement |
|---|---|---|---|---|
| Domain label | Solid | Page-order: 1st blue, 2nd yellow, 3rd green, 4th orange | 8.5pt bold black | Top blank area; never over the title/first question |
| Variable | Solid | Parent domain color | 8pt regular black | As close as possible to the field without covering CRF text |
| Context/constant/when/derived | Dashed | Parent domain color | 8pt regular black | Near the related Variable/result; may wrap |
| RELREC | Dashed | Parent domain color | 8pt regular black | Near the collected link field (see 5.1) |
| `[NOT SUBMITTED]` | Dashed | Related domain color | 8pt regular black | Near the item; keep compact for one-line text |

Fixed page-order colors: 1st blue `RGB(191,255,255)`, 2nd yellow
`RGB(255,255,150)`, 3rd green `RGB(150,255,150)`, 4th orange
`RGB(255,190,155)`.

---

## 7. Placement and drawing

### 7.1–7.3, 7.6 — call the cloud tools for the math
Coordinates are PDF points, origin top-left, x right, y down (convert first if
your extraction library uses a different origin, e.g. PyMuPDF's default is
bottom-left). Don't use one fixed box size for everything:

1. `estimate_annotation_box_size(annotation, style_type)` — check
   `clipped_risk`; if true, widen/heighten or split only that box.
2. `recommend_domain_box(...)` for the Domain label — prioritizes the top
   blank band; may return `needs_manual_or_second_pass_placement`.
3. `recommend_annotation_box(...)` for Variable/context boxes — tries right,
   above, below, left, then diagonal relative to the source question.

Pass the word bboxes you extracted locally (Section 0) as
`pdf_text_bboxes`/`existing_annotation_bboxes`/`source_bbox` — plain
coordinate lists, never the PDF itself.

### 7.4 — Source text bounding boxes (you do this locally)
Use word-level extraction (`page.get_text("words")` or
`page.extract_words()`), not full-string search alone — short labels like
`Sex`, `Age`, `Race`, `Date` often fail a plain search even when visible.
Normalize text, match exact labels first then fuzzy/partial, and record a
missing source box as a placement issue, not a mapping failure.

**`source_bbox` must be a tight box around only the words that make up the
question's own text — nothing else.** Do not union in trailing whitespace, a
neighboring checkbox/YES-NO column, or the rest of the table row. Here's
exactly why this matters: the placement tools compute the "right" position as
`source_bbox`'s right edge + ~6 points (see the `_candidate_box_from_anchor`
math behind `recommend_annotation_box`, Section 7.6/7.9) — if `source_bbox` is
too wide (e.g. it stretches across the whole row instead of stopping at the
end of the question text), the annotation lands far out past the checkboxes
instead of right next to the question. This exact mistake has happened before
— build `source_bbox` as the union of only the word-level boxes belonging to
that specific question's own text span, and verify visually (render a sample
page) that annotations land immediately next to their question, not pushed to
a far margin.

### 7.5 — Metadata table extraction (you do this locally)
Don't parse metadata tables from plain `splitlines()` text — narrow columns
split words/dates across fragments (`Randomizatio n date`, `DD/MMM/Y YYY`).
Reconstruct rows by y-coordinate and columns by x-range anchored to headers
(`Field Name`, `Data Type`, `Field Label`, `Units`, `Values`, `OID`); repair
common breaks while keeping the raw text for QC; split merged fields before
mapping.

### 7.7 — Placement rules (you do this locally, using the cloud recommendation)
Domain label boxes must contain the full `DOMAIN (Dataset Label)` text — widen
or wrap rather than let text/fill spill outside the border. Pass your
extracted `pdf_text_bboxes` and `existing_annotation_bboxes` to the cloud
tools so they can avoid covering CRF content and avoid overlapping each other.

### 7.8 — Page rotation (you do this locally)
For `/Rotate 90` pages, compute placement in the displayed coordinate system,
convert the final rectangle back to the unrotated PDF coordinate system before
creating the annotation, and set `rotate=90` on the FreeText annotation.
Verify visually with a rendered PNG.

### 7.9 — Implementation: create real annotation objects (you do this locally)

**Whichever runtime actually works in your sandbox, use it — the requirement
is the same either way: every annotation must be a real, independent PDF
annotation object (selectable, movable, editable), never text/shapes drawn
directly onto the page content stream.** A flattened box that merely *looks*
right is a QC failure (see Section 8, item 10) even if the colors and
placement are perfect. Known issue: on Windows, spawning a Python process from
inside Codex's sandbox can fail with `CreateProcessAsUserW failed` regardless
of what's installed — this is a documented Codex-on-Windows sandbox bug, not
something fixable by installing packages. If Python won't launch, don't keep
retrying it — switch to Option B, which runs through the same in-process
JS execution path Codex already uses successfully for other steps.

**Option A — PyMuPDF (Python), when Python execution is available:**

Don't pass `border_color` to `add_freetext_annot()` when `richtext=False`
(PyMuPDF 1.28 raises `ValueError`). Use one FreeText annotation for text +
fill + border, then call `set_border()` on that same object — don't add a
separate Square/Rect border (it becomes a second draggable object in PDF
editors).

```python
def display_to_unrotated_rect(page, rect):
    if page.rotation == 90:
        h = page.cropbox.height
        return fitz.Rect(rect.y0, h - rect.x1, rect.y1, h - rect.x0)
    return rect

pdf_rect = display_to_unrotated_rect(page, display_rect)
rotate = page.rotation if page.rotation in (90, 180, 270) else 0

text_annot = page.add_freetext_annot(
    pdf_rect, annotation_text, fontsize=8, fontname="helv",
    text_color=(0, 0, 0), fill_color=fill_color, rotate=rotate,
)
text_annot.set_border(width=0.7, dashes=[3, 2] if dashed else None)
text_annot.update()
```

**Option B — pdf-lib (Node.js), verified working when Python is not available:**

`pdf-lib`'s own `drawRectangle()`/`drawText()` draw permanently onto the page
content stream — do **not** use them for annotations. Instead, construct the
FreeText annotation dictionary by hand (with a real `/AP` appearance stream
for the fill/border/text so it renders correctly in every viewer, not only
ones that auto-generate appearance from `/DA`), and push it onto the page's
`/Annots` array:

```js
import { PDFName, PDFString } from 'pdf-lib';

function makeAnnot(context, page, { x0, y0, x1, y1, text, dashed, rgbColor, font, fontSize = 8 }) {
  const w = x1 - x0, h = y1 - y0;
  const [r, g, b] = rgbColor;
  const dashOp = dashed ? '[3 2] 0 d' : '[] 0 d';
  const content =
    `q\n${r} ${g} ${b} rg\n0 0 ${w} ${h} re f\n` +
    `0 0 0 RG ${dashOp} 0.7 w\n0.35 0.35 ${w - 0.7} ${h - 0.7} re S\n` +
    `0 0 0 rg\nBT /Helv ${fontSize} Tf 2 ${h - fontSize - 1} Td (${text}) Tj ET\nQ`;

  const apStream = context.stream(content, {
    Type: 'XObject', Subtype: 'Form', BBox: [0, 0, w, h],
    Resources: { Font: { Helv: font.ref } },
  });
  const apRef = context.register(apStream);

  const bs = dashed
    ? { W: 0.7, S: PDFName.of('D'), D: [3, 2] }
    : { W: 0.7, S: PDFName.of('S') };

  const dict = context.obj({
    Type: PDFName.of('Annot'), Subtype: PDFName.of('FreeText'),
    Rect: [x0, y0, x1, y1], Contents: PDFString.of(text),
    DA: PDFString.of('/Helv 8 Tf 0 g'), BS: bs, F: 4, AP: { N: apRef },
  });
  const ref = context.register(dict);

  let annots = page.node.lookup(PDFName.of('Annots'));
  if (!annots) { annots = context.obj([]); page.node.set(PDFName.of('Annots'), annots); }
  annots.push(ref);
}
```

Fill color for `rgbColor` follows the page-order Domain colors (Section 6).
Y-coordinates: `pdf-lib` pages are bottom-left origin like raw PDF, so if your
extracted coordinates are top-left origin, convert with
`y_pdf = page.getHeight() - y_top_left` before calling this.

**Verify before reporting done (either option):** after saving, re-open the
output and count real annotation objects — PyMuPDF:
`sum(len(list(p.annots())) for p in doc)`; pdf-lib:
sum of `page.node.lookup(PDFName.of('Annots'))` array lengths across pages.
This count must be roughly equal to the number of annotations you placed. If
it's 0, you flattened instead of annotating — do not report success.

Fallback only: if a rotated page's rendered appearance is missing the border,
add a same-bbox Square/Rect border for that page only, and note that it
creates two editable objects. After writing annotations, render representative
pages and confirm the border encloses the full fill+text, and that dragging
one annotation in a PDF editor moves text/fill/border together.

---

## 8. QC checklist (you run this locally, as the final pass)

1. Every in-scope page reviewed, including continuation pages.
2. Skipped pages have a documented reason (cover, TOC, schedule, metadata,
   blank/footer-only, no submitted data).
3. Every represented Domain has a `DOMAIN (Dataset Label)` label from
   `domain_label`.
4. Every Variable belongs to its approved Domain and the SDTMIG v3.4
   whitelist (enforced by the tools — spot-check anyway).
5. No annotation covers original PDF text/checkboxes/radio buttons/entry
   boxes/table content; no border clips or crowds its own text.
6. Variable annotations sit close to their CRF question/field.
7. Domain labels sit in the top blank area; every border fully encloses its
   fill + text.
8. Constants/when-then/RELREC/`[NOT SUBMITTED]` are dashed; submitted
   Variables are solid.
9. Findings context and result annotations are split, never combined.
10. Annotations are real, independent PDF annotation objects — visible,
    searchable, and individually selectable/movable/editable in a PDF viewer.
    Count them programmatically (Section 7.9) before reporting success; a
    non-zero count close to the number of annotations placed is required.
    Text/shapes drawn directly onto the page content stream ("flattened") do
    not satisfy this — that is a failure, not an acceptable fallback.
11. RELREC only where explicitly collected/displayed (5.1).

---

## 9. Common issues

| Issue | Cause | Fix |
|---|---|---|
| Text clipped/hidden in the box | Size not estimated | Call `estimate_annotation_box_size`; widen/split if `clipped_risk` |
| Annotation covers CRF text | Didn't pass extracted bboxes | Pass `pdf_text_bboxes` to `recommend_annotation_box`/`recommend_domain_box` |
| Variable annotation too far from the question | Used fixed coordinates | Pass `source_bbox` so the tool can anchor to the source field |
| Domain label not at the top | Treated like a normal Variable | Use `recommend_domain_box` |
| Cross-domain Variable forced into current Domain | Whitelist check skipped | Remove it, map to SUPP, mark `[NOT SUBMITTED]`, or add another Domain if justified |
| RELREC overused | Added without an explicit collected/displayed relationship | Follow 5.1 |

---

## 10. Smoke test

Call `map_crf_item(form_name="Concomitant Medications", question="Medication
Name", approved_domains=["CM"])` and confirm it returns `CM.CMTRT`. If that
works, the cloud tools are reachable and the knowledge base loaded correctly.
