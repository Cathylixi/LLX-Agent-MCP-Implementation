# CRF Annotation Mapper Instructions (Revised)

**Purpose:** enable a new account or new operator to use the Python mapper for SDTM Domain and Variable annotation of a blank CRF.

## 0. PDF Text Extraction and Audit

Before Step 1 Domain mapping, extract and audit the CRF PDF text using a two-pass approach:

1. **Primary extraction: PyMuPDF.** Use PyMuPDF (`fitz`) as the main extraction engine for word-level and line-level text with coordinates. PyMuPDF coordinates are the source of truth for source-label bounding boxes and downstream annotation placement.
2. **Secondary audit extraction: pdfplumber.** Use pdfplumber as an independent review pass for text, table, row, and metadata-page reconstruction. pdfplumber should not silently replace PyMuPDF output; it should identify extraction gaps, row/column reconstruction issues, and labels that PyMuPDF extracted but the candidate-filter logic dropped.
3. **Compare extraction outputs before mapping.** Create an extraction audit output, such as `crf_extraction_audit.csv`, listing page number, form name, PyMuPDF line text and bbox, pdfplumber text or table row text, whether the text entered the Step 2 question list, whether it received an SDTM mapping, suspected omission reason, and suggested action.
4. **Use metadata pages as a field dictionary.** When metadata/table-definition pages contain field names, OIDs, or field labels such as `SITEID`, `SUBJID`, or `USUBJID`, reconstruct those rows with pdfplumber or PyMuPDF word coordinates and cross-check them against the visible data-collection page labels. Do not annotate metadata pages themselves unless they collect submitted SDTM data.
5. **Do not over-filter real CRF fields.** Broad skip rules such as `site`, `subject`, `date`, or `visit` must not remove real field labels like `Site Identifier`, `Subject Identifier`, `Visit Date`, or `Date of Collection`. Skip only true repeated headers/footers, page controls, response choices, format hints, and operational-only text.
6. **Resolve audit findings before final aCRF output.** If PyMuPDF or pdfplumber sees a likely CRF field that is missing from Step 2, either map it, document why it is not submitted, or send it to manual review. Do not treat it as successfully reviewed merely because it was absent from the candidate question list.

***

## 1. Objective and Required Files

The mapper is designed to support new blank CRFs. It first identifies the SDTM Domain for each page/form, then maps each CRF question or field label to an SDTM Variable within the approved Domain. It also returns annotation style, color, border type, placement, box-size, and QC guidance for PDF annotation.

| File                                 | Purpose                                                                                                                              | Should a new operator edit it?                            |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------- |
| crf\_annotation\_mapper.py           | Main runtime entry point. Calls the Domain guide, Variable pattern library, SDTMIG metadata, and annotation style/placement helpers. | Usually no.                                               |
| domain\_mapping\_guide.py            | Step 1: maps form/page titles to likely SDTM Domain(s) by concept rather than exact match.                                           | Only when the approved Domain guide changes.              |
| crf\_variable\_question\_patterns.py | Step 2: reverse knowledge base. Maps Domain + CRF question/label patterns to SDTM Variables.                                         | Only when the question-pattern knowledge base is updated. |
| sdtmig\_metadata.py                  | Embedded SDTMIG v3.4 metadata. Provides Domain labels, Variable whitelist, and metadata checks.                                      | Normally no. The Excel file is not required at runtime.   |

### 1.1 Directory Setup

All four Python files must reside in the same directory (the "local workspace"). Before starting any annotation work, copy the blank CRF PDF into this same directory. Do not read from or write to the source or network-drive file.

***

## 2. Standard Workflow

1. Place all four .py files and the blank CRF PDF in the same local directory (see Section 1.1).
2. Extract PDF text using PyMuPDF and run a pdfplumber-based audit pass before mapping (see Section 0). Resolve or document likely field-label omissions before producing the final aCRF.
3. Step 1 â€” perform page/form-level Domain mapping only. Output form/title, data collection status, proposed Domain(s), confidence, evidence/rationale, and uncertainties. Every in-scope data-collection page must receive a proposed Domain. If no historical, override, or content-understanding candidate is found, assign the best available low-confidence fallback Domain and flag it for reviewer confirmation; do not leave Step 1 blank.
4. **Stop after Step 1 and deliver the Domain map for reviewer approval. Do not run Step 2, create Variable annotations, or generate the final annotated PDF until the user explicitly approves the Domain map.**
5. Step 2 â€” within the approved Domain(s), map each CRF question/label to an SDTM Variable. Step 2 must not remove, hide, or narrow any Step 1 approved Domain unless the reviewer explicitly changes the Domain map.
6. Validate each main-domain Variable against the SDTMIG v3.4 whitelist for the current Domain.
7. When creating PDF annotations, use the mapper output for style, color, border, placement, and bounding-box recommendations.
8. Perform QC for overlap, clipping, distance from source question, Domain label placement, extraction-audit omissions, and metadata validity.

***

## 3. Quick Start Code

### 3.1 Single-item mapping (after Step 1 approval)

Pass the approved Domain(s) explicitly. If `approved_domains` is omitted (`None`), the mapper will fall back to Step 1 and auto-infer Domain(s) from the form/page title before running Variable mapping.

```python
import crf_annotation_mapper as mapper
result = mapper.map_crf_item(
    form_name='Adverse Events',
    question='Dose Reduced',
    approved_domains=['AE'],
)
print(result['recommended'])
```

### 3.2 Page-level mapping (multiple questions)

```python
page_result = mapper.map_crf_page(
    form_name='Demographics',
    questions=['Birth Year', 'Age', 'Sex',
              'Date informed consent signed'],
    approved_domains=['DM', 'DS'],
)
```

### 3.3 Key output fields of map\_crf\_page

The return value of `map_crf_page` is a dict with the following keys:

| Key                             | Description                                                                                                                     |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| items                           | List of map\_crf\_item results, one per non-noise question.                                                                     |
| approved\_or\_inferred\_domains | The approved domains passed in, or domains inferred from the form title if not supplied.                                        |
| display\_domains                | Domains that should receive a visible page-level label. This must preserve the Step 1 approved Domain(s); Step 2 Variable results must not remove approved Domain labels (see Section 5.5). |
| domain\_color\_plan             | Page-order color assignments for each display domain (blue â†’ yellow â†’ green â†’ orange).                                          |
| display\_domain\_qc             | QC result checking whether domain labels match actual annotations on the page.                                                  |

***

## 4. Step 1: Domain Mapping

If the Domain has not yet been approved, use the mapper to propose candidate Domain(s) from the form or page title.

```python
domain_result = mapper.map_form_to_domains('12-Lead ECG')
print(domain_result['best_mapping'])
```

Domain labels must be shown as `DOMAIN (Dataset Label)`, with Dataset Label sourced from sdtmig\_metadata.py.

```python
mapper.domain_label('EG')  # EG (ECG Test Results)
```

* If a Domain is not present in SDTMIG metadata (e.g., a sponsor-defined or custom Domain), list it for user confirmation.
* If a page legitimately collects multiple Domains, list all represented Domains and explain why. Do not force a single Domain.
* If no historical, override, or content-understanding Domain candidate is found for an in-scope data-collection page, Step 1 must still propose a best-effort fallback Domain. Mark the fallback as low-confidence / needs review, explain why it was selected, and keep it visible in the review output and PDF domain labels.
* Operational, metadata, codelist, audit/query, EDC-only, and true gateway pages may still be skipped when they do not collect submitted SDTM data.

***

## 5. Step 2: Variable Mapping

Variable mapping must stay within the approved Domain(s). The mapper prioritizes metadata-valid Variable candidates.

```python
mapper.map_question_to_variables(domain='AE', question='Dose Reduced')
```

### 5.1 Core rules

* Select Variables only from the SDTMIG v3.4 whitelist for the current approved Domain.
* Ignore noise-only question text such as `/`, `//`, `---`, or strings with no letters or numbers.
* For Findings domains, split context from result. Example: `VSTESTCD = WEIGHT` as dashed context; `VSORRES` near the result field as solid Variable.
* Do not use combined shorthand such as `LBTESTCD/LBTEST` or `VSORRES/VSORRESU` as one final annotation.
* Add RELREC only when the CRF **explicitly** collects or displays a link/relationship. "Explicit" means a visible field or label on the CRF page â€” for example, a death page that shows "Related AE Number" or "Link to AE" is explicit. A death page that does NOT display any AE reference is not explicit, even if the protocol links death to AE programmatically.
* Mark true operational/helper fields that will not be submitted to SDTM as `[NOT SUBMITTED]`.
* If a real collected CRF question cannot be mapped to a reliable main-domain SDTM variable, map it to a supplemental qualifier in the Step 1 approved Domain instead of using `[NOT SUBMITTED]`. Use a specific, reviewed QNAM when available (for example, `VISITTYP in SUPPSV`). If no specific QNAM can be assigned confidently, use `QNAM in SUPPXX` as the fallback annotation and flag it for supplemental-qualifier review in the audit output. Do not leave a real collected field unmapped merely because a main-domain Variable was not found.
* When a single CRF question has checkbox/radio/dropdown response choices, annotate the collected question once. Do not create separate `SUPPXX` annotations for each displayed response choice unless the CRF explicitly collects separate fields for those choices.
* Do not use `SUPPXX` as a catch-all for every visible text string. Do not map instructions, continuation text, controlled-term response options, protocol version choices, unit labels, or form-list choices to `SUPPXX`.
* For RECIST target-lesion tumor assessment forms, Step 1 should include `RS; TR; TU`: `RS` for response assessment, `TR` for tumor/lesion measurements, and `TU` for tumor/lesion identification.

### 5.2 \[NOT SUBMITTED] â€” when to use

Apply `[NOT SUBMITTED]` only to operational, hidden, derived, or EDC-only helper items that will not appear in any SDTM dataset. Do not use `[NOT SUBMITTED]` merely because a real CRF question lacks a reliable main-domain variable; use `SUPPXX` for those items. Common examples:

* Operational / site-management helper fields (e.g., query flags, page-control flags, workflow triggers).
* CRF-only instructions or helper text that are not data (e.g., "Please initial here").
* Fields whose values are derived programmatically and never submitted as collected (e.g., calculated totals displayed for operator convenience).
* Duplicate or redundant fields that are mapped elsewhere (e.g., a repeated visit date already captured in SV).

### 5.3 Scoring mechanism

The mapper scores each Variable candidate using a weighted formula:

* **score = 0.75 Ã— token\_overlap + 0.25 Ã— fuzzy\_string\_ratio**
* token\_overlap = matched tokens / max(query tokens, pattern tokens)
* An additional boost is applied when overlap â‰¥ 0.66 and â‰¥ 2 tokens match.
* Only candidates scoring â‰¥ `min_score` (default **0.82**) are returned.
* Final PDF annotation should use direct/curated rules or candidates with confidence score â‰¥ **0.90**. Candidates below 0.90 may be listed in audit output for review, but should not be written to the PDF unless manually approved.

The `min_score` parameter is tunable. If the mapper returns no candidates for a question that you believe should match, try lowering min\_score (e.g., 0.70) to surface lower-confidence candidates, then verify manually:

```python
mapper.map_question_to_variables(
    domain='AE', question='Was action taken?',
    min_score=0.70,
)
```

### 5.4 Findings TESTCD auto-inference

For Findings domains (VS, EG, LB, TR, TU, RS, CV), the mapper can automatically infer `--TESTCD` values from CRF question text using built-in rules. For example, "Systolic Blood Pressure" â†’ `VSTESTCD = SYSBP` (context) + `VSORRES` (variable).

```python
mapper.findings_testcd_annotations(domain='VS', question='Systolic Blood Pressure')
```

To also include result variables (e.g., VSORRES, VSORRESU) in the output:

```python
mapper.findings_testcd_annotations(
    domain='VS',
    question='Systolic Blood Pressure',
    include_result_variables=True,
)
```

### 5.5 Domain label retention â€” display\_domains\_for\_annotations

Step 1 approval may list one or more Domains for a page, and Step 2 must preserve those Step 1 Domain labels. Once a Domain is approved in Step 1, Step 2 must not delete, hide, narrow, or filter it out because Variable mapping is incomplete. Missing or low-confidence Variable annotations should be mapped to SUPPXX when they are real collected fields, or recorded in QC/review output when they are not submitted data; they must not be used to remove the Step 1 Domain label.

```python
mapper.display_domains_for_annotations(
    approved_domains=['DM', 'DS'],
    annotation_domains=['DM'],
)
# Returns ['DM', 'DS'] â€” DS remains visible as a Step 1 Domain even if no DS variable annotation exists.
```

### 5.6 Common annotation pattern helpers

#### Informed consent date

`informed_consent_date_annotations()` returns standard DS + DM annotations for consent date fields:

```python
mapper.informed_consent_date_annotations()
# Returns: DSCAT = PROTOCOL MILESTONE, DSTERM = INFORMED CONSENT,
#          DSSTDTC, RFICDTC
```

#### Vital signs EDC variable mapping

`vital_sign_edc_annotations()` handles custom EDC field names (e.g., VSWT, VSHT, BMI, VSTIM1, VSTEMPLOC) that are not SDTMIG variables but common sponsor-defined names:

```python
mapper.vital_sign_edc_annotations('VSWT')
# Returns: VSTESTCD = WEIGHT (context), VSORRES (variable),
#          VSORRESU = kg (context)
```

***

## 6. Annotation Style Rules

| Annotation Type                     | Border | Color                                                                | Font                                              | Placement                                                                                                             |
| ----------------------------------- | ------ | -------------------------------------------------------------------- | ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Domain label                        | Solid  | Page-order Domain color: 1st blue, 2nd yellow, 3rd green, 4th orange | Arial/Helvetica-compatible, 8.5 pt, bold, black.  | Top blank area of the page/form. Do not cover the title or first question.                                            |
| Variable                            | Solid  | Use the parent/current Domain color                                  | Arial/Helvetica-compatible, 8 pt, regular, black. | As close as possible to the related question, field, checkbox, radio button, or table cell without covering CRF text. |
| Context / constant / when / derived | Dashed | Use the parent/current Domain color                                  | Arial/Helvetica-compatible, 8 pt, regular, black. | Near the related Variable or result field. Longer text may wrap.                                                      |
| RELREC                              | Dashed | Use the parent/current Domain color                                  | Arial/Helvetica-compatible, 8 pt, regular, black. | Near the collected link variable or relationship statement (see RELREC rule in Section 5.1).                          |
| \[NOT SUBMITTED]                    | Dashed | Usually use the related Domain color                                 | Arial/Helvetica-compatible, 8 pt, regular, black. | Near the non-submitted data item. Keep compact when the text is one line.                                             |

Fixed page-order colors:

```
1st domain: blue   RGB(191, 255, 255)
2nd domain: yellow RGB(255, 255, 150)
3rd domain: green  RGB(150, 255, 150)
4th domain: orange RGB(255, 190, 155)
```

***

## 7. Annotation Placement and Box Size

The mapper includes executable helpers for downstream PDF annotation code. Do not use one fixed box size for all annotations, and do not manually enlarge every annotation box. Short one-line annotations should stay compact; longer annotations should expand only as needed for wrapping.

### 7.1 Coordinate system

All bounding boxes use PDF points with origin at top-left, x increasing rightward, y increasing downward. If your PDF library uses a bottom-left origin (e.g., PyMuPDF's default), convert coordinates before calling the mapper's placement helpers.

### 7.2 Box size estimation

```python
mapper.estimate_annotation_box_size(
    'DSCAT = PROTOCOL MILESTONE', 'context'
)
```

### 7.3 Domain label placement

```python
mapper.recommend_domain_box(
    annotation='DS (Disposition)', domain='DS',
    page_size=(612, 792),
    pdf_text_bboxes=pdf_text_bboxes,
    existing_annotation_bboxes=annotation_bboxes,
)
```

### 7.4 Source text bounding-box extraction

Before Variable/context placement, build a source-text bounding-box inventory from word-level PDF text extraction. Prefer PyMuPDF `page.get_text("words")` or pdfplumber `page.extract_words()` for locating source labels and questions. Do not rely only on full-string search methods such as PyMuPDF `page.search_for()`, because short CRF labels such as `Sex`, `Age`, `Race`, `Date`, or compact table-cell labels may fail to return a reliable source box even when the text is visible on the page.

Recommended source-box workflow:

1. Extract page text with word-level coordinates.
2. Normalize text for matching (case, whitespace, punctuation, and line breaks).
3. Match exact labels first, then controlled fuzzy/partial labels when needed.
4. Use full-string search only as a fallback, not as the only source-box method.
5. If a field maps successfully but no source box is found, record it as a placement/source-location issue rather than a variable-mapping failure.

### 7.5 Metadata table text extraction

When using CRF annotation/metadata pages to identify field names, data types, and field labels, do not parse the table only from plain text lines such as `page.get_text("text").splitlines()`. Metadata tables often have narrow columns and split words or dates across drawing fragments; examples include `Randomizatio n date`, `DD/MMM/Y YYY`, or adjacent fields being merged into one label. This can cause correct SDTM rules to miss and can also prevent source-box placement.

Recommended metadata-table workflow:

1. Extract annotation/metadata pages with word-level coordinates using PyMuPDF `page.get_text("words")` or pdfplumber `page.extract_words()`.
2. Reconstruct rows by y-coordinate grouping and reconstruct columns by x-coordinate ranges anchored to visible headers such as `Field Name`, `Data Type`, `Field Label`, `Units`, `Values`, and `OID`.
3. Use the field ordinal, field name, and OID as row boundaries; do not rely only on line order.
4. Normalize and repair common PDF extraction breaks before mapping, while preserving the raw extracted text for QC. Examples: `Randomizatio n` -> `Randomization`, `Y YYY` -> `YYYY`, `dd/MMM/yyy y` -> `DD/MMM/YYYY`.
5. Cross-check reconstructed metadata labels against the visible data page text. If metadata extraction is broken but the data page label is clear, use the visible data page label for source-box placement and record the repair in QC.
6. If two fields are merged during extraction, split them before variable mapping; do not map the merged text as one field.

### 7.6 Variable / context placement

```python
mapper.recommend_annotation_box(
    annotation='AEACN', domain='AE',
    page_size=(612, 792),
    source_bbox=question_bbox,
    pdf_text_bboxes=pdf_text_bboxes,
    existing_annotation_bboxes=annotation_bboxes,
)
```

### 7.7 Placement rules

* Domain labels: scan the top blank area first. If there is no safe location, the mapper returns `needs_manual_or_second_pass_placement`.
* Domain label boxes must contain the full `DOMAIN (Dataset Label)` text. For long labels such as `FA (Findings About Events or Interventions)`, widen the domain box up to the available top-band width or wrap to a second line; do not let text or fill extend outside the border.
* Variables/context: the mapper tries right, above, below, left, then diagonal positions relative to the source question.
* Pass original PDF text bounding boxes (`pdf_text_bboxes`) so the mapper can avoid covering CRF text, checkboxes, radio buttons, entry boxes, and table content.
* Pass existing annotation bounding boxes (`existing_annotation_bboxes`) so annotations do not overlap each other.
* If `clipped_risk=True` in the box-size estimate, widen, heighten, or split only that annotation â€” do not apply a large fixed height to all boxes.

### 7.8 Page rotation

Check page rotation before placing annotations. For PDFs with `/Rotate 90`, compute annotation placement in the displayed page coordinate system, convert the final displayed rectangle back to the unrotated PDF coordinate system before creating the annotation object, and set the FreeText annotation `rotate=90`. Verify the rendered PNG visually; do not rely only on extracted annotation coordinates.

### 7.9 PyMuPDF FreeText implementation note

When creating searchable, movable PDF FreeText annotations with PyMuPDF, do not pass `border_color` to `page.add_freetext_annot()` when `richtext=False`. PyMuPDF 1.28 may raise `ValueError: cannot set border_color if rich_text is False`.

Use a single FreeText annotation for the text, background fill, and border. After creating the FreeText annotation, call `set_border()` on that same object. Do not routinely add a separate Square/Rect annotation for the border, because PDF editors expose it as a second draggable object that can be pulled away from the text/fill.

Fallback exception: if visual QA shows that a rotated page omits the FreeText border in the rendered appearance stream, add a same-bbox Square/Rect border only for that failing page and document that the fallback creates two editable annotation objects.

Recommended implementation:

1. Create the FreeText annotation with text color, fill color, font, font size, and page rotation.
2. Call `text_annot.set_border(width=0.7, dashes=[3, 2] if dashed else None)` on the same FreeText annotation.
3. For context/constant annotations, set dashed borders. For variable and domain annotations, use solid borders.
4. Keep `richtext=False` unless rich-text rendering is specifically required and visually verified.

Example:

```python
def display_to_unrotated_rect(page, rect):
    if page.rotation == 90:
        h = page.cropbox.height
        return fitz.Rect(rect.y0, h - rect.x1, rect.y1, h - rect.x0)
    return rect

pdf_rect = display_to_unrotated_rect(page, display_rect)
rotate = page.rotation if page.rotation in (90, 180, 270) else 0

text_annot = page.add_freetext_annot(
    pdf_rect,
    annotation_text,
    fontsize=8,
    fontname="helv",
    text_color=(0, 0, 0),
    fill_color=fill_color,
    rotate=rotate,
)
text_annot.set_border(width=0.7, dashes=[3, 2] if dashed else None)
text_annot.update()
```

After writing annotations, render representative pages with annotations enabled and confirm the border is visible and encloses the full colored fill and text. Also open one annotation in a PDF editor and confirm dragging it moves the text, fill, and border together as one object.

***

## 8. QC Checklist

1. Every page in scope was reviewed, including continuation pages.
2. Pages without annotation have a documented reason: cover, TOC, schedule, metadata, blank/footer-only, or no submitted data.
3. Each represented Domain has a `DOMAIN (Dataset Label)` label sourced from sdtmig\_metadata.py.
4. Variable whitelist check passed â€” each Variable belongs to the approved page Domain and exists in the SDTMIG v3.4 whitelist (see Section 5.1).
5. Annotations do not cover original PDF text, checkboxes, radio buttons, entry boxes, or table content, and annotation borders do not clip or crowd the annotation text.
6. Variable annotations are close to the corresponding CRF question/label/field.
7. Domain annotations are placed in the top available blank area, and every domain-label border fully encloses the label text and colored fill.
8. Constants, when/then notes, RELREC, and \[NOT SUBMITTED] use dashed borders; submitted Variables use solid borders.
9. Findings context and result annotations are split â€” no combined shorthand (see Section 5.1).
10. PDF comments are visible and searchable. If flattened, annotations remain traceable.
11. RELREC rule followed (see Section 5.1) â€” RELREC added only when an explicit relationship is collected/displayed.

***

## 9. Common Issues and Corrections

| Issue                                                    | Likely Cause                                                          | Correction                                                                                                 |
| -------------------------------------------------------- | --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| Text is clipped or hidden inside the annotation box      | Box is too small, or wrapping/font size was not estimated             | Use `estimate_annotation_box_size`. If `clipped_risk=True`, widen/heighten or split only that annotation.  |
| Annotation covers original CRF text                      | PDF text bounding boxes were not provided or overlap was not checked  | Use `recommend_annotation_box` / `recommend_domain_box` and pass `pdf_text_bboxes`.                        |
| Variable annotation is too far from the CRF question     | Fixed coordinates were used                                           | Pass `source_bbox` so the mapper can place near the source field.                                          |
| Domain label is not at the top of the page               | Domain was placed like a normal Variable                              | Use `recommend_domain_box` to prioritize the top blank area.                                               |
| Cross-domain Variable was forced into the current Domain | Metadata whitelist check was skipped                                  | Check `metadata_check`. Remove it, map to SUPP, mark \[NOT SUBMITTED], or add another Domain if justified. |
| RELREC is overused                                       | RELREC was added without an explicit collected/displayed relationship | Follow the RELREC rule in Section 5.1.                                                                     |

***

## 10. Recommended Handoff Test

Before a new operator starts annotation work, confirm that the four Python files are in the same folder (see Section 1.1) and run one smoke test:

```
python crf_annotation_mapper.py
```

Expected output should include examples similar to:

```
Dose Reduced -> AE.AEACN
Medication Name -> CM.CMTRT
```

If the knowledge base needs to be updated, update `domain_mapping_guide.py` or `crf_variable_question_patterns.py` first. Do not edit `sdtmig_metadata.py` unless the SDTMIG version changes.

***

<p style="text-align:center; color:gray; font-size:8pt;">CRF Annotation Mapper Instructions (Revised) | Python runtime workflow</p>

***
