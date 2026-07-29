"""
Unified CRF annotation mapper.

Runtime purpose:
- Step 1: infer page/form SDTM domain(s) from the approved domain guide.
- Step 2: infer SDTM variable(s) from Domain + CRF question/label patterns.
- QC: validate domains and variables against embedded SDTMIG v3.4 metadata.

This file is a runtime mapper only. It does not rebuild knowledge from Word,
Excel, or annotated CRF PDFs.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import crf_variable_question_patterns as question_patterns
import domain_mapping_guide
import sdtmig_metadata


SDTMIG_VERSION = "SDTMIG v3.4"
NOT_SUBMITTED = "[NOT SUBMITTED]"
ANNOTATION_FONT_FAMILY = "Arial"
ANNOTATION_PDF_FONT = "helv"
ANNOTATION_FONT_SIZE = 8.0
DOMAIN_FONT_SIZE = 8.5
DOMAIN_PDF_FONT = "hebo"
DOMAIN_RICH_TEXT_WIDTH_MULTIPLIER = 1.1
DOMAIN_RICH_TEXT_HORIZONTAL_PADDING = 8
DOMAIN_RICH_TEXT_MIN_WIDTH = 72
DOMAIN_RICH_TEXT_MIN_HEIGHT = 16
DOMAIN_COMMENT_RENDER_MODE = "compact_movable_freetext"
FREETEXT_BORDER_RENDER_MODE = "single_freetext_border_annotation"

# Word instruction: page-order colors for represented domains on the same page.
PAGE_DOMAIN_COLORS: list[dict[str, Any]] = [
    {"name": "blue", "rgb": (191, 255, 255), "usage": "first domain on page"},
    {"name": "yellow", "rgb": (255, 255, 150), "usage": "second domain on page"},
    {"name": "green", "rgb": (150, 255, 150), "usage": "third domain on page"},
    {"name": "orange", "rgb": (255, 190, 155), "usage": "fourth domain on page"},
]

# CRF outline/bookmark handling. In the blank CRFs this mapper supports,
# pages under an "Annotations" bookmark are operational annotation/reference
# pages and should not receive SDTM Domain or Variable mapping.
OPERATIONAL_BOOKMARK_TITLES = {"ANNOTATIONS"}
OPERATIONAL_PAGE_KEYWORDS = {
    "EDC ONLY",
    "DERIVED",
    "DERIVED FOR PROGRAMMING",
    "COMPLETION GUIDELINES",
    "QUERY",
    "AUDIT",
}

ANNOTATION_STYLE_GUIDE: dict[str, dict[str, Any]] = {
    "domain": {
        "annotation_object": "movable FreeText comment",
        "rich_text": True,
        "rich_text_template": (
            '<span style="font-family:Helvetica; font-size:{font_size}pt; '
            'font-weight:bold;">{text}</span>'
        ),
        "rich_text_width_multiplier": DOMAIN_RICH_TEXT_WIDTH_MULTIPLIER,
        "rich_text_horizontal_padding": DOMAIN_RICH_TEXT_HORIZONTAL_PADDING,
        "rich_text_min_width": DOMAIN_RICH_TEXT_MIN_WIDTH,
        "rich_text_min_height": DOMAIN_RICH_TEXT_MIN_HEIGHT,
        "border": "solid",
        "border_width": 1.0,
        "font": ANNOTATION_FONT_FAMILY,
        "font_size": DOMAIN_FONT_SIZE,
        "bold": True,
        "text_color": "black",
        "pdf_fontname": DOMAIN_PDF_FONT,
    },
    "variable": {
        "annotation_object": "movable FreeText comment",
        "rich_text": False,
        "border": "solid",
        "border_width": 0.5,
        "font": ANNOTATION_FONT_FAMILY,
        "font_size": ANNOTATION_FONT_SIZE,
        "bold": False,
        "text_color": "black",
        "pdf_fontname": ANNOTATION_PDF_FONT,
    },
    "context": {
        "annotation_object": "movable FreeText comment",
        "rich_text": False,
        "border": "dashed",
        "border_width": 0.5,
        "font": ANNOTATION_FONT_FAMILY,
        "font_size": ANNOTATION_FONT_SIZE,
        "bold": False,
        "text_color": "black",
        "pdf_fontname": ANNOTATION_PDF_FONT,
    },
}

ANNOTATION_PLACEMENT_GUIDE: dict[str, Any] = {
    "domain": {
        "preferred_position": "top blank area of the page/form section",
        "avoid_covering": [
            "form title",
            "generated-on text",
            "first question",
            "response options",
            "page rules",
            "page content",
        ],
        "box_sizing": "size box to visible text; keep short labels compact",
    },
    "variable": {
        "preferred_position": "as close as possible to the source question, field, option, or table cell",
        "avoid_covering": [
            "CRF text",
            "checkboxes",
            "radio buttons",
            "entry boxes",
            "answer options",
            "table content",
            "operational instructions",
        ],
        "box_sizing": "short variables should use short, low-height boxes",
    },
    "context": {
        "preferred_position": (
            "near the relevant question/result field, or near the domain/variable "
            "when it explains constants, conditions, RELREC, derived data, or non-submitted data"
        ),
        "avoid_covering": [
            "CRF text",
            "checkboxes",
            "radio buttons",
            "entry boxes",
            "answer options",
            "table content",
            "operational instructions",
        ],
        "box_sizing": "long constants or explanatory notes may wrap in a taller box",
    },
    "multi_domain": {
        "rule": (
            "Use separate domain labels and page-order colors for each collected domain on the page. "
            "Every variable/context annotation for a domain must use the same color as that domain label "
            "on the same page."
        ),
        "color_order": PAGE_DOMAIN_COLORS,
    },
    "rotation": {
        "rule": (
            "Check page rotation before annotation. If the PDF page has no /Rotate, "
            "do not add annotation /Rotate. If /Rotate 90 displays incorrectly, add "
            "FreeText /Rotate 90 and verify visually."
        )
    },
    "searchability": {
        "rule": (
            "Use searchable, movable PDF FreeText comments for annotation text. "
            "For PyMuPDF output, use the FreeText annotation itself for fill, "
            "text, and border so the label remains one movable object. If visual "
            "QA shows the FreeText border is missing on a rotated page, use the "
            "separate Square/Rect border fallback only for that page and record "
            "that it creates two editable annotation objects."
        )
    },
}

ANNOTATION_RENDERING_GUIDE: dict[str, Any] = {
    "recommended_pdf_objects": [
        {
            "object": "FreeText",
            "purpose": "searchable annotation text, background fill, and visible border",
            "border": "solid for variables/domain labels, including QNAM in SUPPxx; dashed for context/constants",
            "fill": "domain/page-order color",
        },
    ],
    "pymupdf_border_rule": (
        "Create one FreeText annotation and call set_border() on that annotation "
        "for the visible border. Do not add a routine Square/Rect border layer, "
        "because PDF editors expose it as a separate draggable object. If visual "
        "QA shows FreeText borders are missing on a rotated page, a same-bbox "
        "Square/Rect fallback is allowed only for that failing page."
    ),
    "rotation_rule": (
        "When page.rotation is 90, compute placement in displayed page coordinates, "
        "convert displayed rectangles back to unrotated PDF coordinates before "
        "creating annotations, and set FreeText rotate=90."
    ),
}

# PDF annotation layout defaults in PDF points. These are conservative because
# FreeText can render slightly differently across PDF engines.
BOX_LAYOUT_DEFAULTS: dict[str, Any] = {
    "page_margin": 18,
    "min_gap_from_source": 3,
    "preferred_gap_from_source": 6,
    "min_gap_from_pdf_text": 2,
    "min_gap_between_annotations": 3,
    "line_height_multiplier": 1.08,
    "average_char_width_multiplier": 0.72,
    "freetext_wrap_safety_multiplier": 1.0,
    "horizontal_padding": 3.5,
    "vertical_padding": 1.0,
    "domain_horizontal_padding": 4,
    "domain_vertical_padding": 1.2,
    "min_width": {"domain": 54, "variable": 24, "context": 54},
    "max_width": {"domain": 360, "variable": 150, "context": 260},
    "min_height": {"domain": 13, "variable": 10, "context": 11},
    "max_height": {"domain": 36, "variable": 24, "context": 80},
    "domain_top_band_height": 72,
    "max_distance_from_source": 150,
    "nearby_search_offsets": [
        "right",
        "above",
        "below",
        "left",
        "above_right",
        "below_right",
        "above_left",
        "below_left",
    ],
}

WORD_INSTRUCTION_RULES: dict[str, Any] = {
    "workflow": [
        "Step 1 is page-level domain mapping only.",
        "Step 2 is variable mapping after domain review/approval.",
        "Review every page, including continuation pages.",
        "Do not map operational-data pages or pages under an Annotations bookmark.",
    ],
    "page_exclusion_rule": (
        "Pages under an 'Annotations' bookmark, and pages/fields that are operational only "
        "(for example EDC-only, IRT-only, derived-for-programming, completion guidelines, "
        "query/audit/helper content), should not receive SDTM Domain or Variable mapping. "
        f"Use {NOT_SUBMITTED} only for collected form items that are reviewed in scope but "
        "not submitted to SDTM; do not use it to annotate skipped operational pages."
    ),
    "domain_label_rule": "Display domain labels as DOMAIN (Dataset Label) from sdtmig_metadata.py.",
    "variable_whitelist_rule": (
        "Before mapping a main-domain variable, confirm it belongs to a represented "
        "page domain and appears in SDTMIG v3.4 metadata for that domain."
    ),
    "not_submitted_rule": (
        "Collected data that will not be submitted to SDTM should be annotated as "
        f"{NOT_SUBMITTED}."
    ),
    "findings_rule": (
        "For Findings domains, keep --TESTCD context separate from result variables "
        "such as --ORRES or --ORRESU."
    ),
    "combined_shorthand_rule": (
        "Do not use combined shorthand such as LBTESTCD/LBTEST or VSORRES/VSORRESU "
        "as one final annotation."
    ),
    "relrec_rule": (
        "Add RELREC only when a link/relationship is explicitly collected or displayed."
    ),
    "appearance_and_placement": {
        "style_guide": ANNOTATION_STYLE_GUIDE,
        "placement_guide": ANNOTATION_PLACEMENT_GUIDE,
        "page_domain_colors": PAGE_DOMAIN_COLORS,
        "box_layout_defaults": BOX_LAYOUT_DEFAULTS,
    },
}

# These custom/sponsor-defined domains may appear in the approved guide or examples.
# They are allowed as candidates but flagged for confirmation if absent from SDTMIG.
CUSTOM_OR_CONFIRMATION_DOMAINS = {"APMH", "OE", "PC", "IS", "FT"}

FINDINGS_DOMAINS = {
    "BS",
    "CV",
    "DA",
    "DD",
    "EG",
    "FA",
    "FT",
    "IE",
    "IS",
    "LB",
    "MB",
    "MI",
    "MK",
    "MS",
    "NV",
    "OE",
    "PE",
    "QS",
    "RE",
    "RP",
    "RS",
    "SC",
    "SS",
    "TR",
    "TU",
    "UR",
    "VS",
}

NOISE_ONLY_RE = re.compile(r"^[\W_]+$")
BBox = tuple[float, float, float, float]


@lru_cache(maxsize=1)
def metadata_domain_codes() -> set[str]:
    return {
        str(row["Dataset Name"])
        for row in sdtmig_metadata.DATASETS
        if row.get("Version") == SDTMIG_VERSION and row.get("Dataset Name")
    }


@lru_cache(maxsize=None)
def dataset_metadata(domain: str) -> dict[str, Any] | None:
    domain = normalize_domain_code(domain)
    try:
        return sdtmig_metadata.get_dataset(domain, version=SDTMIG_VERSION)
    except (KeyError, ValueError):
        return None


@lru_cache(maxsize=None)
def allowed_variables(domain: str) -> set[str]:
    domain = normalize_domain_code(domain)
    try:
        return {
            str(row["Variable Name"])
            for row in sdtmig_metadata.get_variables(domain, version=SDTMIG_VERSION)
            if row.get("Variable Name")
        }
    except (KeyError, ValueError):
        return set()


def normalize_domain_code(domain: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", str(domain or "")).upper()


def normalize_page_domains(domains: list[str] | tuple[str, ...] | None) -> list[str]:
    normalized: list[str] = []
    for domain in domains or []:
        code = normalize_domain_code(domain)
        if code and code not in normalized:
            normalized.append(code)
    return normalized


def domain_order_index_for_page(domain: str, page_domains: list[str] | tuple[str, ...] | None) -> int:
    """Return the page-local color index for a domain.

    Color coding is page-local, not domain-global: the first domain shown on a
    page is blue, the second is yellow, etc. All annotations for that domain on
    that page must reuse the same index.
    """
    code = normalize_domain_code(domain)
    normalized = normalize_page_domains(page_domains)
    if code in normalized:
        return normalized.index(code)
    return 0


def domain_color_for_page(domain: str, page_domains: list[str] | tuple[str, ...] | None) -> dict[str, Any]:
    index = domain_order_index_for_page(domain, page_domains)
    return PAGE_DOMAIN_COLORS[min(index, len(PAGE_DOMAIN_COLORS) - 1)]


def validate_page_domain_annotation_coverage(
    page_domains: list[str] | tuple[str, ...] | None,
    annotation_domains: list[str] | tuple[str, ...] | None,
) -> dict[str, Any]:
    """QC displayed domains against variable/context annotation domains.

    Approved page domains remain visible. Missing annotation domains are reported
    for audit, but they do not hide the approved page-level domain label.
    """
    page_codes = normalize_page_domains(page_domains)
    annotation_codes = normalize_page_domains(annotation_domains)
    missing = [domain for domain in page_codes if domain not in annotation_codes]
    unexpected = [domain for domain in annotation_codes if domain not in page_codes]
    return {
        "ok": not unexpected,
        "page_domains": page_codes,
        "annotation_domains": annotation_codes,
        "display_domains_without_variable_annotations": missing,
        "unexpected_annotation_domains": unexpected,
    }


def display_domains_for_annotations(
    approved_domains: list[str] | tuple[str, ...] | None,
    annotation_domains: list[str] | tuple[str, ...] | None,
    include_unapproved_annotation_domains: bool = True,
) -> list[str]:
    """Return domains that should receive visible page-level labels.

    Approved domain order is preserved for page-local colors. Approved domains
    stay visible even when item-level mapping falls back to review/SUPP logic.

    If an actual annotation maps to an additional domain, for example DM.DTHDTC
    on a death page, that domain is appended so its annotation can still have a
    label and color.
    """
    approved = normalize_page_domains(approved_domains)
    annotated = normalize_page_domains(annotation_domains)
    displayed = list(approved)
    if include_unapproved_annotation_domains:
        displayed.extend(domain for domain in annotated if domain not in displayed)
    return displayed


def qc_display_domain_plan(
    approved_domains: list[str] | tuple[str, ...] | None,
    display_domains: list[str] | tuple[str, ...] | None,
    annotation_domains: list[str] | tuple[str, ...] | None,
) -> dict[str, Any]:
    """QC the displayed-domain plan used for page-level domain labels."""
    approved = normalize_page_domains(approved_domains)
    displayed = normalize_page_domains(display_domains)
    annotated = normalize_page_domains(annotation_domains)
    hidden_approved = [domain for domain in approved if domain not in displayed]
    coverage = validate_page_domain_annotation_coverage(displayed, annotated)
    return {
        **coverage,
        "approved_domains": approved,
        "hidden_approved_domains_without_annotations": hidden_approved,
    }


def informed_consent_date_annotations(
    include_demographics_reference: bool = True,
    consent_term: str = "INFORMED CONSENT",
) -> list[dict[str, Any]]:
    """Standard annotations for an informed-consent date field.

    Informed consent is a DS protocol milestone. The same collected date often
    also supports DM.RFICDTC, so both mappings are returned by default.
    """
    normalized_term = clean_question_text(consent_term).upper() or "INFORMED CONSENT"
    annotations = [
        {
            "annotation": "DSCAT = PROTOCOL MILESTONE",
            "domain": "DS",
            "source_kind": "context",
            "reason": "Consent is a protocol milestone.",
        },
        {
            "annotation": f"DSTERM = {normalized_term}",
            "domain": "DS",
            "source_kind": "context",
            "reason": "Protocol milestone term for informed consent.",
        },
        {
            "annotation": "DSSTDTC",
            "domain": "DS",
            "source_kind": "variable",
            "reason": "Date/time of the DS protocol milestone.",
        },
    ]
    if include_demographics_reference:
        annotations.append(
            {
                "annotation": "RFICDTC",
                "domain": "DM",
                "source_kind": "variable",
                "reason": "Reference informed consent date in Demographics.",
            }
        )
    return annotations


def is_primary_informed_consent_date_field(form_name: str, question: str) -> bool:
    """Return true for the main informed-consent date, excluding optional sub-consents."""
    lowered_form = clean_question_text(form_name).casefold()
    lowered_question = clean_question_text(question).casefold()
    if not is_informed_consent_date_field(form_name, question):
        return False
    optional_context_terms = (
        "future research",
        "sample",
        "blood",
        "bone marrow",
        "optional",
    )
    return not any(term in lowered_question for term in optional_context_terms)


def is_informed_consent_date_field(form_name: str, question: str) -> bool:
    """Return true for informed-consent date fields on the consent form."""
    lowered_form = clean_question_text(form_name).casefold()
    lowered_question = clean_question_text(question).casefold()
    return (
        "informed consent" in lowered_form
        and "consent" in lowered_question
        and "date" in lowered_question
    )


def prior_infections_mh_context_annotations() -> list[dict[str, Any]]:
    """Standard MH category context for prior infection history forms."""
    return [
        {
            "annotation": "MHCAT = MEDICAL HISTORY",
            "domain": "MH",
            "source_kind": "context",
            "reason": "Prior infections are categorized as medical history.",
        },
        {
            "annotation": "MHSCAT = PRIOR INFECTIONS",
            "domain": "MH",
            "source_kind": "context",
            "reason": "Subcategory identifies the prior infections form.",
        },
    ]


def prior_infections_mh_direct_annotations(
    form_name: str,
    question: str,
    domains: list[str] | tuple[str, ...] | None,
) -> list[dict[str, Any]]:
    """Direct MH mappings for prior infection history forms."""
    if "MH" not in normalize_page_domains(domains):
        return []
    if clean_question_text(form_name).casefold() != "prior infections":
        return []

    text = clean_question_text(question).casefold()
    variable = None
    if "had any infections" in text:
        variable = "MHOCCUR"
    elif "type of infection" in text:
        variable = "MHTERM"
    elif "start date" in text and "hospitalization" not in text:
        variable = "MHSTDTC"
    elif "stop date" in text and "hospitalization" not in text:
        variable = "MHENDTC"
    if not variable:
        return []

    annotations = [
        {
            "annotation": variable,
            "domain": "MH",
            "source_kind": "variable",
            "variable_name": variable,
            "variable_label": (variable_metadata("MH", variable) or {}).get("Variable Label"),
            "score": 1.0,
            "match_type": "approved_domain_direct_rule",
            "metadata_check": validate_variable("MH", variable),
            "reason": "Direct MH mapping for prior infection history form.",
        }
    ]
    if variable == "MHOCCUR":
        annotations.extend(prior_infections_mh_context_annotations())
    return annotations


def rp_pregnancy_test_annotations(
    form_name: str,
    question: str,
    domains: list[str] | tuple[str, ...] | None,
    page_text: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Curated RP mappings for pregnancy-test fields with short CRF labels."""
    if "RP" not in normalize_page_domains(domains):
        return [], None
    form_lower = clean_question_text(form_name).casefold()
    page_lower = clean_question_text(page_text or "").casefold()
    question_lower = clean_question_text(question).casefold()
    if "childbearing potential" not in form_lower and "pregnancy test" not in page_lower:
        return [], None
    if "pregnancy test" not in page_lower and "pregnancy test" not in question_lower:
        return [], None

    pregnancy_context = [
        {
            "annotation": "RPTESTCD = PREG",
            "domain": "RP",
            "source_kind": "context",
            "variable_name": "RPTESTCD",
            "variable_label": "Short Name of Reproductive Test",
            "score": 1.0,
            "match_type": "curated_rp_pregnancy_test_context",
            "metadata_check": validate_variable("RP", "RPTESTCD"),
            "reason": "Pregnancy test context for the RP finding record.",
        },
        {
            "annotation": "RPTEST = Pregnancy Test",
            "domain": "RP",
            "source_kind": "context",
            "variable_name": "RPTEST",
            "variable_label": "Name of Reproductive Test",
            "score": 1.0,
            "match_type": "curated_rp_pregnancy_test_context",
            "metadata_check": validate_variable("RP", "RPTEST"),
            "reason": "Pregnancy test context for the RP finding record.",
        },
    ]

    if question_lower == "result":
        result_annotation = {
            "annotation": "RPORRES",
            "domain": "RP",
            "source_kind": "variable",
            "variable_name": "RPORRES",
            "variable_label": "Result or Finding in Original Units",
            "score": 1.0,
            "match_type": "curated_rp_pregnancy_test_result",
            "metadata_check": validate_variable("RP", "RPORRES"),
            "reason": "Short label 'Result' appears in a pregnancy-test block on the Childbearing Potential page.",
        }
        return pregnancy_context + [result_annotation], result_annotation

    if question_lower == "type":
        specimen_annotation = {
            "annotation": "SPECIMEN in SUPPRP",
            "domain": "RP",
            "source_kind": "context",
            "variable_name": "SPECIMEN",
            "variable_label": "Generated Supplemental Qualifier Name",
            "score": None,
            "match_type": "curated_rp_pregnancy_test_specimen",
            "qnam": "SPECIMEN",
            "qnam_review_flag": "Review supplemental specimen QNAM against sponsor naming conventions.",
            "metadata_check": {
                "domain": "RP",
                "variable_name": "SPECIMEN",
                "in_sdtmig_domain": False,
                "domain_in_sdtmig": bool(dataset_metadata("RP")),
                "supplemental_qualifier": True,
            },
            "reason": "Urine/Serum choices describe pregnancy-test specimen type; RP has no SDTMIG v3.4 RPSPEC/RPMETHOD variable.",
        }
        return pregnancy_context + [specimen_annotation], specimen_annotation

    return [], None


def lb_pregnancy_test_annotations(
    form_name: str,
    question: str,
    domains: list[str] | tuple[str, ...] | None,
    page_text: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Curated LB mappings for laboratory pregnancy-test forms."""
    if "LB" not in normalize_page_domains(domains):
        return [], None
    form_lower = clean_question_text(form_name).casefold()
    page_lower = clean_question_text(page_text or "").casefold()
    question_lower = clean_question_text(question).casefold()
    if "pregnancy test" not in form_lower and "pregnancy test" not in page_lower:
        return [], None

    pregnancy_context = [
        {
            "annotation": "LBTESTCD = HCG",
            "domain": "LB",
            "source_kind": "context",
            "variable_name": "LBTESTCD",
            "variable_label": "Lab Test or Examination Short Name",
            "score": 1.0,
            "match_type": "curated_lb_pregnancy_test_context",
            "metadata_check": validate_variable("LB", "LBTESTCD"),
            "reason": "Pregnancy test context for the LB laboratory finding record.",
        },
        {
            "annotation": "LBTEST = Choriogonadotropin",
            "domain": "LB",
            "source_kind": "context",
            "variable_name": "LBTEST",
            "variable_label": "Lab Test or Examination Name",
            "score": 1.0,
            "match_type": "curated_lb_pregnancy_test_context",
            "metadata_check": validate_variable("LB", "LBTEST"),
            "reason": "Pregnancy test context for the LB laboratory finding record.",
        },
    ]

    if question_lower == "result":
        result_annotation = {
            "annotation": "LBORRES",
            "domain": "LB",
            "source_kind": "variable",
            "variable_name": "LBORRES",
            "variable_label": "Result or Finding in Original Units",
            "score": 1.0,
            "match_type": "curated_lb_pregnancy_test_result",
            "metadata_check": validate_variable("LB", "LBORRES"),
            "reason": "Short label 'Result' appears in a laboratory pregnancy-test form.",
        }
        return pregnancy_context + [result_annotation], result_annotation

    if question_lower == "type":
        specimen_annotation = {
            "annotation": "LBSPEC",
            "domain": "LB",
            "source_kind": "variable",
            "variable_name": "LBSPEC",
            "variable_label": "Specimen Type",
            "score": 1.0,
            "match_type": "curated_lb_pregnancy_test_specimen",
            "metadata_check": validate_variable("LB", "LBSPEC"),
            "reason": "Urine/Serum choices identify the specimen type for the laboratory pregnancy test.",
        }
        return pregnancy_context + [specimen_annotation], specimen_annotation

    return [], None


def filter_contextually_invalid_annotations(
    form_name: str,
    question: str,
    annotations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Remove over-broad fuzzy/context matches that conflict with the exact label."""
    form_lower = clean_question_text(form_name).casefold()
    question_lower = clean_question_text(question).casefold()
    if form_lower == "pregnancy test":
        annotations = [
            row
            for row in annotations
            if normalize_domain_code(row.get("domain")) != "RP"
        ]
    if question_lower == "creatinine":
        return [
            row
            for row in annotations
            if clean_question_text(row.get("annotation")).upper() != "LBTESTCD = CREATCLR"
        ]
    return annotations


VS_EDC_TESTCD_RULES: dict[str, dict[str, str | None]] = {
    "VSWT": {"testcd": "WEIGHT", "orresu": "kg"},
    "WT": {"testcd": "WEIGHT", "orresu": "kg"},
    "WEIGHT": {"testcd": "WEIGHT", "orresu": "kg"},
    "VSHT": {"testcd": "HEIGHT", "orresu": "cm"},
    "HT": {"testcd": "HEIGHT", "orresu": "cm"},
    "HEIGHT": {"testcd": "HEIGHT", "orresu": "cm"},
    "BMI": {"testcd": "BMI", "orresu": "kg/m^2"},
    "TEMP": {"testcd": "TEMP", "orresu": "C"},
    "SYSBP": {"testcd": "SYSBP", "orresu": "mmHg"},
    "DIABP": {"testcd": "DIABP", "orresu": "mmHg"},
    "HR": {"testcd": "HR", "orresu": "beats/min"},
    "RESP": {"testcd": "RESP", "orresu": "breaths/min"},
    "SPO2": {"testcd": "SPO2", "orresu": "%"},
    "VSRESU": {"testcd": "INTP", "orresu": None},
}


VS_EDC_TIMEPOINT_RULES: dict[str, str] = {
    "VSTIM1": "SEATING START",
    "VSTIM2": "SEATED VITAL SIGN",
    "VSTIM4": "STANDING START",
    "VSTIM5": "STANDING VITAL SIGN",
}


MAX_TESTCD_VALUE_LENGTH = 8

FINDINGS_TESTCD_QUESTION_RULES: dict[str, list[dict[str, Any]]] = {
    "VS": [
        {"patterns": [r"\bheight\b"], "testcd": "HEIGHT", "result_variables": ["VSORRES"]},
        {"patterns": [r"\bweight\b"], "testcd": "WEIGHT", "result_variables": ["VSORRES"]},
        {"patterns": [r"\bbsa\b", r"body surface area"], "testcd": "BSA", "result_variables": ["VSORRES"]},
        {"patterns": [r"\bbmi\b", r"body mass index"], "testcd": "BMI", "result_variables": ["VSORRES"]},
        {"patterns": [r"\bbody temperature\b", r"\btemperature\b"], "testcd": "TEMP", "result_variables": ["VSORRES"]},
        {"patterns": [r"\brespiratory rate\b", r"\brespiration rate\b"], "testcd": "RESP", "result_variables": ["VSORRES"]},
        {"patterns": [r"\bpulse\b", r"\bheart rate\b"], "testcd": "PULSE", "result_variables": ["VSORRES"]},
        {"patterns": [r"\bsystolic blood pressure\b", r"\bsystolic\b"], "testcd": "SYSBP", "result_variables": ["VSORRES"]},
        {"patterns": [r"\bdiastolic blood pressure\b", r"\bdiastolic\b"], "testcd": "DIABP", "result_variables": ["VSORRES"]},
        {"patterns": [r"vital signs collected", r"were vital signs collected", r"vital signs assessed"], "testcd": "VSALL", "result_variables": []},
    ],
    "EG": [
        {"patterns": [r"\bheart rate\b", r"\bventricular rate\b"], "testcd": "EGHRMN", "result_variables": ["EGORRES", "EGORRESU"]},
        {"patterns": [r"\bpr interval\b", r"\bpr\b"], "testcd": "PRAG", "result_variables": ["EGORRES", "EGORRESU"]},
        {"patterns": [r"\bqrs duration\b", r"\bqrs\b"], "testcd": "QRSAG", "result_variables": ["EGORRES", "EGORRESU"]},
        {"patterns": [r"\bqtcf\b", r"\bqtc[f ]"], "testcd": "QTCFAG", "result_variables": ["EGORRES", "EGORRESU"]},
        {"patterns": [r"\bqt interval\b", r"\bqt\b"], "testcd": "QTAG", "result_variables": ["EGORRES", "EGORRESU"]},
        {"patterns": [r"\brr interval\b", r"\brr\b"], "testcd": "RRAG", "result_variables": ["EGORRES", "EGORRESU"]},
        {"patterns": [r"overall interpretation", r"\binterpretation\b", r"\becg evaluation\b"], "testcd": "INTP", "result_variables": ["EGORRES", "EGCLSIG"]},
    ],
    "CV": [
        {"patterns": [r"\blvef\b", r"left ventricular ejection fraction"], "testcd": "LVEF", "result_variables": ["CVORRES", "CVORRESU"]},
        {"patterns": [r"overall interpretation", r"\binterpretation\b"], "testcd": "INTP", "result_variables": ["CVORRES"]},
    ],
    "LB": [
        {"patterns": [r"\bwbc\b", r"white blood cell"], "testcd": "WBC", "result_variables": ["LBORRES", "LBORRESU"]},
        {"patterns": [r"\brbc\b", r"red blood cell"], "testcd": "RBC", "result_variables": ["LBORRES", "LBORRESU"]},
        {"patterns": [r"\bhemoglobin\b", r"\bhgb\b"], "testcd": "HGB", "result_variables": ["LBORRES", "LBORRESU"]},
        {"patterns": [r"\bhematocrit\b", r"\bhct\b"], "testcd": "HCT", "result_variables": ["LBORRES", "LBORRESU"]},
        {"patterns": [r"\bplatelets?\b", r"\bplt\b"], "testcd": "PLAT", "result_variables": ["LBORRES", "LBORRESU"]},
        {"patterns": [r"\bneutrophils?\s*\(%\)", r"\bneutrophils?\s*percent"], "testcd": "NEUTLE", "result_variables": ["LBORRES", "LBORRESU"]},
        {"patterns": [r"\bneutrophils?\s*\(absolute\)", r"\bneutrophils?,\s*absolute\b", r"\babsolute neutrophils?\b", r"\bneutrophil count\b", r"\banc\b"], "testcd": "NEUT", "result_variables": ["LBORRES", "LBORRESU"]},
        {"patterns": [r"\blymphocytes?\s*\(%\)", r"\blymphocytes?\s*percent"], "testcd": "LYMLE", "result_variables": ["LBORRES", "LBORRESU"]},
        {"patterns": [r"\blymphocytes?\s*\(absolute\)", r"\blymphocytes?,\s*absolute\b", r"\babsolute lymphocytes?\b", r"\blymphocyte count\b", r"\balc\b"], "testcd": "LYM", "result_variables": ["LBORRES", "LBORRESU"]},
        {"patterns": [r"\bmonocytes?\s*\(%\)", r"\bmonocytes?\s*percent"], "testcd": "MONOLE", "result_variables": ["LBORRES", "LBORRESU"]},
        {"patterns": [r"\bmonocytes?\s*\(absolute\)", r"\bmonocytes?,\s*absolute\b", r"\babsolute monocytes?\b", r"\bmonocyte count\b", r"\bamc\b"], "testcd": "MONO", "result_variables": ["LBORRES", "LBORRESU"]},
        {"patterns": [r"\beosinophils?\s*\(%\)", r"\beosinophils?\s*percent"], "testcd": "EOSLE", "result_variables": ["LBORRES", "LBORRESU"]},
        {"patterns": [r"\beosinophils?\s*\(absolute\)", r"\beosinophils?,\s*absolute\b", r"\babsolute eosinophils?\b"], "testcd": "EOS", "result_variables": ["LBORRES", "LBORRESU"]},
        {"patterns": [r"\bbasophils?\s*\(%\)", r"\bbasophils?\s*percent"], "testcd": "BASOLE", "result_variables": ["LBORRES", "LBORRESU"]},
        {"patterns": [r"\bbasophils?\s*\(absolute\)", r"\bbasophils?,\s*absolute\b", r"\babsolute basophils?\b"], "testcd": "BASO", "result_variables": ["LBORRES", "LBORRESU"]},
        {"patterns": [r"pregnancy"], "testcd": "HCG", "result_variables": ["LBORRES"]},
        {"patterns": [r"drug.*screen", r"drug/alcohol/cotinine"], "testcd": "DRUGSCR", "result_variables": ["LBORRES"]},
        {"patterns": [r"cotinine"], "testcd": "COTININE", "result_variables": ["LBORRES"]},
        {"patterns": [r"alcohol|ethanol"], "testcd": "ETHANOL", "result_variables": ["LBORRES"]},
        {"patterns": [r"\bfsh\b"], "testcd": "FSH", "result_variables": ["LBORRES"]},
    ],
    "TR": [
        {"patterns": [r"longest diameter", r"\bmeasurement\b"], "testcd": "LDIAM", "result_variables": ["TRORRES", "TRORRESU"]},
        {"patterns": [r"short axis"], "testcd": "LPERP", "result_variables": ["TRORRES", "TRORRESU"]},
        {"patterns": [r"tumou?r state", r"lesion state"], "testcd": "TUMSTATE", "result_variables": ["TRORRES"]},
        {"patterns": [r"new lesion"], "testcd": "NEWCONF", "result_variables": ["TRORRES"]},
    ],
    "TU": [
        {"patterns": [r"lesion identification", r"lesion number", r"lesion id"], "testcd": "TUMIDENT", "result_variables": ["TUORRES"]},
        {"patterns": [r"target lesion"], "testcd": "TIND", "result_variables": ["TUORRES"]},
        {"patterns": [r"non[- ]target lesion"], "testcd": "NTIND", "result_variables": ["TUORRES"]},
    ],
    "RS": [
        {"patterns": [r"\bbest response\b"], "testcd": "BESTRESP", "result_variables": ["RSORRES"]},
        {"patterns": [r"overall response", r"recist"], "testcd": "OVRLRESP", "result_variables": ["RSORRES"]},
        {"patterns": [r"target lesion response"], "testcd": "TRGRESP", "result_variables": ["RSORRES"]},
        {"patterns": [r"non[- ]target lesion response"], "testcd": "NTRGRESP", "result_variables": ["RSORRES"]},
        {"patterns": [r"new lesion"], "testcd": "NEWLPROG", "result_variables": ["RSORRES"]},
    ],
}


DIRECT_VARIABLE_QUESTION_RULES: dict[str, list[dict[str, Any]]] = {
    "DM": [
        {"patterns": [r"\bsite id\b", r"\bsite identifier\b", r"\bsite number\b"], "annotations": ["SITEID"]},
        {"patterns": [r"^(?!.*\bfull\b).*\bparticipant number\b", r"^(?!.*\bfull\b).*\bsubject number\b", r"^(?!.*\bfull\b).*\bpatient number\b", r"^subject identifier$"], "annotations": ["SUBJID"]},
        {"patterns": [r"\bparticipant id\b", r"\bsubject id\b", r"\bpatient id\b", r"\bfull patient number\b", r"\bfull subject number\b", r"\bunique subject identifier\b"], "annotations": ["USUBJID"]},
        {"patterns": [r"\bbirth year\b", r"\byear of birth\b"], "annotations": ["BRTHDTC"]},
        {"patterns": [r"\bage\b"], "annotations": ["AGE", "AGEU = YEARS"]},
        {"patterns": [r"\bsex\b"], "annotations": ["SEX"]},
        {"patterns": [r"\bethnicity\b"], "annotations": ["ETHNIC"]},
        {"patterns": [r"\bspecify\s+other\s+race\b", r"\bother\s+race\b"], "annotations": ["RACEOTH in SUPPDM"]},
        {"patterns": [r"\brace\b"], "annotations": ["RACE"]},
        {"patterns": [r"\bcountry code\b", r"^country$"], "annotations": ["COUNTRY"]},
        {"patterns": [r"\binformed consent signed\b"], "annotations": ["RFICDTC"]},
        {"patterns": [r"\bdate of death\b"], "annotations": ["DTHDTC", "DTHFL"]},
        {"patterns": [r"\bscreen failure date\b"], "annotations": ["DMDTC"]},
        {"patterns": [r"\bscreen failure reason\b"], "annotations": ["ARMNRS"]},
    ],
    "DS": [
        {"patterns": [r"\bparticipant status\b", r"\bsubject status\b"], "annotations": ["DSCAT = SUBJECT STATUS", "DSTERM"]},
        {"patterns": [r"\binformed consent\b"], "annotations": ["DSCAT = PROTOCOL MILESTONE", "DSTERM", "DSSTDTC"]},
        {"patterns": [r"\breconsent\b"], "annotations": ["DSCAT = PROTOCOL MILESTONE", "DSTERM", "DSSTDTC"]},
        {"patterns": [r"\brandomization date\b", r"\brandomized\b"], "annotations": ["DSCAT = PROTOCOL MILESTONE", "DSTERM = RANDOMIZED", "DSSTDTC"]},
        {"patterns": [r"\bcompletion\b", r"\bdiscontinuation\b", r"\bend of study\b", r"\bend of treatment\b"], "annotations": ["DSCAT = DISPOSITION EVENT", "DSTERM"]},
        {"patterns": [r"\bprimary reason\b", r"\breason for discontinu"], "annotations": ["DSDECOD"]},
    ],
    "IE": [
        {"patterns": [r"\beligibility criteria\b", r"\binclusion\b", r"\bexclusion\b", r"\bcriteria\b", r"\bcriterion\b"], "annotations": ["IETESTCD", "IEORRES"]},
        {"patterns": [r"\beligibility assessment\b", r"\bdate of eligibility\b", r"\bassessment date\b"], "annotations": ["IEDTC"]},
    ],
    "FA": [
        {"patterns": [r"\borgan of origin\b"], "annotations": ["FATESTCD = ORIGIN", "FAORRES"]},
        {"patterns": [r"\bhistology\b", r"\btumou?r histology\b"], "annotations": ["FATESTCD = HISTOL", "FAORRES"]},
        {"patterns": [r"\bstage\b", r"\bstaging\b"], "annotations": ["FATESTCD = STAGE", "FAORRES"]},
        {"patterns": [r"\bmetastatic\b", r"\bmetastasis\b"], "annotations": ["FATESTCD = METAST", "FAORRES"]},
    ],
    "MH": [
        {"patterns": [r"\bmedical history term\b", r"^mh term$"], "annotations": ["MHTERM"]},
        {"patterns": [r"\bmedical history condition\b", r"\bcondition/event\b"], "annotations": ["MHTERM"]},
        {"patterns": [r"\bonset date\b", r"\bstart date\b"], "annotations": ["MHSTDTC"]},
        {"patterns": [r"\bend date\b"], "annotations": ["MHENDTC"]},
        {"patterns": [r"\bongoing\b"], "annotations": ["MHENRF"]},
    ],
    "SV": [
        {"patterns": [r"\bwas\b.*\bvisit\b.*\bperformed\b", r"\bvisit\b.*\bperformed\b", r"\bwas\b.*\bvisit\b.*\bcompleted\b", r"\bdid\b.*\bvisit\b.*\boccur\b", r"\bvisit\s+not\s+done\b", r"\bvisit\s+not\s+performed\b"], "annotations": ["SVOCCUR"]},
        {"patterns": [r"\bvisit date\b", r"\bdate of visit\b", r"\bunscheduled visit date\b"], "annotations": ["SVSTDTC"]},
        {"patterns": [r"\bvisit reason\b", r"\breason\b", r"\breason not performed\b", r"\breason not completed\b"], "annotations": ["SVREASOC"]},
    ],
    "VS": [
        {"patterns": [r"\bdate of assessment\b", r"\bdate of measurement\b"], "annotations": ["VSDTC"]},
        {"patterns": [r"\bheight\b"], "annotations": ["VSTESTCD = HEIGHT", "VSORRES", "VSORRESU = cm"]},
        {"patterns": [r"\bweight\b"], "annotations": ["VSTESTCD = WEIGHT", "VSORRES", "VSORRESU = kg"]},
        {"patterns": [r"\bbsa\b", r"body surface area"], "annotations": ["VSTESTCD = BSA", "VSORRES"]},
        {"patterns": [r"\bbmi\b"], "annotations": ["VSTESTCD = BMI", "VSORRES"]},
        {"patterns": [r"\bsystolic\b"], "annotations": ["VSTESTCD = SYSBP", "VSORRES", "VSORRESU = mmHg"]},
        {"patterns": [r"\bdiastolic\b"], "annotations": ["VSTESTCD = DIABP", "VSORRES", "VSORRESU = mmHg"]},
        {"patterns": [r"\bpulse\b"], "annotations": ["VSTESTCD = PULSE", "VSORRES", "VSORRESU = bpm"]},
    ],
    "PE": [
        {"patterns": [r"\bphysical examination performed\b"], "annotations": ["PESTAT"]},
        {"patterns": [r"\bdate of examination\b"], "annotations": ["PEDTC"]},
        {"patterns": [r"^test$"], "annotations": ["PETESTCD"]},
        {"patterns": [r"^result$"], "annotations": ["PEORRES"]},
    ],
    "EG": [
        {"patterns": [r"\belectrocardiogram performed\b", r"\becg performed\b"], "annotations": ["EGSTAT"]},
        {"patterns": [r"\bdate of ecg\b"], "annotations": ["EGDTC"]},
    ],
    "LB": [
        {"patterns": [r"\bpregnancy\b"], "annotations": ["LBTESTCD = HCG", "LBORRES"]},
        {"patterns": [r"\bcollection date\b", r"\bdate of collection\b"], "annotations": ["LBDTC"]},
        {"patterns": [r"\bnot done reason\b", r"\bif no.*reason\b"], "annotations": ["LBREASND"]},
        {"patterns": [r"\bfsh\b"], "annotations": ["LBTESTCD = FSH", "LBORRES"]},
        {"patterns": [r"\burine drug screen\b", r"\bdrug screen\b"], "annotations": ["LBTESTCD = DRUGSCR", "LBORRES"]},
    ],
    "IS": [
        {"patterns": [r"\bimmunogenicity sample collected\b"], "annotations": ["ISSTAT"]},
        {"patterns": [r"\b(?:biomarker|protein)\s+expression\b", r"\bclaudin\b.*\bexpression\b"], "annotations": ["ISTESTCD = CLAUDIN", "ISORRES"]},
        {"patterns": [r"\bintensity\b.*\bimmunostain\b", r"\bimmunostain\b.*\bintensity\b"], "annotations": ["ISTESTCD = INTENS", "ISORRES"]},
        {"patterns": [r"\bpercent\b.*\bpositive\b.*\bstaining\b"], "annotations": ["ISTESTCD = PCTPOS", "ISORRES"]},
        {"patterns": [r"^no result$"], "annotations": ["ISSTAT = NOT DONE"]},
        {"patterns": [r"\bcollection date\b", r"\bcollection time\b"], "annotations": ["ISDTC"]},
        {"patterns": [r"\breason\b"], "annotations": ["ISREASND"]},
    ],
    "PC": [
        {"patterns": [r"\btimepoint\b"], "annotations": ["PCTPT"]},
        {"patterns": [r"\bcollection date\b", r"\bcollection time\b"], "annotations": ["PCDTC"]},
        {"patterns": [r"\bnot done reason\b"], "annotations": ["PCREASND"]},
    ],
    "EC": [
        {"patterns": [r"\bwas\b.*\badministered\b", r"\bdid\b.*\breceive\b"], "annotations": ["ECOCCUR"]},
        {"patterns": [r"\blot number\b"], "annotations": ["ECLOT"]},
        {"patterns": [r"^date$", r"\bdose date\b", r"\badministration date\b"], "annotations": ["ECSTDTC"]},
        {"patterns": [r"\bstart time\b"], "annotations": ["ECSTDTC"]},
        {"patterns": [r"\bend time\b"], "annotations": ["ECENDTC"]},
        {"patterns": [r"\bdose\b", r"\bdose level\b"], "annotations": ["ECDOSE"]},
    ],
    "EX": [
        {"patterns": [r"\blot number\b"], "annotations": ["EXLOT"]},
        {"patterns": [r"^date$", r"\bdose date\b", r"\badministration date\b"], "annotations": ["EXSTDTC"]},
        {"patterns": [r"\bstart time\b"], "annotations": ["EXSTDTC"]},
        {"patterns": [r"\bend time\b"], "annotations": ["EXENDTC"]},
        {"patterns": [r"\bdose\b", r"\bdose level\b"], "annotations": ["EXDOSE"]},
    ],
    "AE": [
        {"patterns": [r"^adverse event$"], "annotations": ["AETERM"]},
        {"patterns": [r"\b(?:adverse event|ae)\b.*\bongoing\b", r"\bongoing\b.*\b(?:adverse event|ae)\b", r"^ongoing\??$"], "annotations": ["AEENRTPT = \"ONGOING\""]},
        {"patterns": [r"\bstart date\b", r"\bstart time\b"], "annotations": ["AESTDTC"]},
        {"patterns": [r"\bend date\b", r"\bend time\b"], "annotations": ["AEENDTC"]},
        {"patterns": [r"^grade$"], "annotations": ["AETOXGR"]},
        {"patterns": [r"\bpattern of (?:the )?event\b", r"\bevent pattern\b"], "annotations": ["AEPATT"]},
        {"patterns": [r"\brelationship\b"], "annotations": ["AEREL"]},
        {"patterns": [r"\bother action taken\b", r"\bother action\b"], "annotations": ["AEACNOTH"]},
        {"patterns": [r"\baction taken\b"], "annotations": ["AEACN"]},
        {"patterns": [r"\bserious\b"], "annotations": ["AESER"]},
        {"patterns": [r"\bdeath\b"], "annotations": ["AESDTH"]},
        {"patterns": [r"\blife-threatening\b"], "annotations": ["AESLIFE"]},
        {"patterns": [r"\bhospitalization\b"], "annotations": ["AESHOSP"]},
        {"patterns": [r"\boutcome\b"], "annotations": ["AEOUT"]},
    ],
    "CM": [
        {"patterns": [r"^medication$"], "annotations": ["CMTRT"]},
        {"patterns": [r"\bstart date\b", r"\bstart time\b"], "annotations": ["CMSTDTC"]},
        {"patterns": [r"\bend date\b", r"\bend time\b"], "annotations": ["CMENDTC"]},
        {"patterns": [r"\broute\b"], "annotations": ["CMROUTE"]},
        {"patterns": [r"\bfrequency\b"], "annotations": ["CMDOSFRQ"]},
        {"patterns": [r"\bdose unit\b"], "annotations": ["CMDOSU"]},
        {"patterns": [r"^dose$"], "annotations": ["CMDOSE"]},
        {"patterns": [r"\bindication\b"], "annotations": ["CMINDC"]},
    ],
    "PR": [
        {"patterns": [r"\bwhole body planar scintigraphy\b"], "annotations": ["PRTRT = WHOLE BODY PLANAR SCINTIGRAPHY"]},
        {"patterns": [r"\bspect/ct\b", r"\bspect\b"], "annotations": ["PRTRT = SPECT/CT"]},
        {"patterns": [r"\bprocedure\b", r"\bcounseling\b", r"\bbiopsy\b", r"\bscintigraphy\b", r"\bscan\b", r"\bimaging\b"], "annotations": ["PRTRT"]},
        {"patterns": [r"\bwas\b.*\bperformed\b", r"\bwere\b.*\bperformed\b", r"\bwas\b.*\bcollected\b", r"\bwere\b.*\bcollected\b"], "annotations": ["PROCCUR"]},
        {"patterns": [r"\bvoid after\b.*\bscan\b", r"\bvoid after\b.*\binjection\b"], "annotations": ["PRTRT = VOIDING", "PROCCUR"]},
        {"patterns": [r"\btreatment site\b", r"\bprocedure site\b", r"\banatomical site\b"], "annotations": ["PRLOC"]},
        {"patterns": [r"\bother site\b.*\bspecify\b"], "annotations": ["PRLOCOTH in SUPPPR"]},
        {"patterns": [r"\btreatment intent\b"], "annotations": ["PRINDC"]},
        {"patterns": [r"\bstart date\b", r"\bdate of counseling\b", r"\bdate performed\b", r"\bdate collected\b"], "annotations": ["PRSTDTC"]},
        {"patterns": [r"\btime performed\b", r"\btime collected\b"], "annotations": ["PRSTDTC"]},
        {"patterns": [r"\bend date\b"], "annotations": ["PRENDTC"]},
        {"patterns": [r"\bindication\b"], "annotations": ["PRINDC"]},
        {"patterns": [r"\btotal urine volume\b", r"\burine sample volume\b", r"\burine radioactivity count\b"], "annotations": ["PRDOSE", "PRDOSU"]},
    ],
    "QS": [
        {"patterns": [r"\b(?:assessment|questionnaire|performance status)\b.*\b(?:performed|completed|done|assessed)\b"], "annotations": ["QSSTAT"]},
        {"patterns": [r"\b(?:if\s+)?not\s+done\b.*\b(?:reason|specify)\b", r"\breason\b.*\bnot\s+done\b"], "annotations": ["QSREASND"]},
    ],
    "OE": [
        {"patterns": [r"\b(?:ophthalmologic|ophthalmic|ocular)\b.*\b(?:examination|exam)\b.*\bperformed\b"], "annotations": ["OESTAT"]},
        {"patterns": [r"\breason not done\b"], "annotations": ["OEREASND"]},
        {"patterns": [r"\bdate of examination\b", r"\bdate of exam\b"], "annotations": ["OEDTC"]},
    ],
    "DD": [
        {"patterns": [r"\bdate of death\b"], "annotations": ["DDDTC"]},
        {"patterns": [r"\bcause of death\b", r"\bautopsy\b"], "annotations": ["DDTESTCD", "DDORRES"]},
    ],
    "SS": [
        {"patterns": [r"\bcontinue to next visit\b"], "annotations": ["SSTESTCD", "SSORRES"]},
    ],
}

def validate_testcd_value(testcd: str) -> dict[str, Any]:
    """Validate a --TESTCD value against SDTM's 8-character limit."""
    normalized = re.sub(r"[^A-Za-z0-9_]", "", str(testcd or "")).upper()
    return {
        "testcd": normalized,
        "max_length": MAX_TESTCD_VALUE_LENGTH,
        "length": len(normalized),
        "valid": bool(normalized) and len(normalized) <= MAX_TESTCD_VALUE_LENGTH,
        "issues": [] if normalized and len(normalized) <= MAX_TESTCD_VALUE_LENGTH else [
            f"--TESTCD value must be 1-{MAX_TESTCD_VALUE_LENGTH} characters."
        ],
    }


def testcd_context_annotation(domain: str, testcd: str) -> dict[str, Any] | None:
    """Build a dashed context annotation for a Findings --TESTCD value."""
    domain = normalize_domain_code(domain)
    check = validate_testcd_value(testcd)
    if not domain or not check["valid"]:
        return None
    return {
        "annotation": f"{domain}TESTCD = {check['testcd']}",
        "domain": domain,
        "source_kind": "context",
        "reason": f"Findings test context; --TESTCD value length {check['length']} <= {MAX_TESTCD_VALUE_LENGTH}.",
        "testcd": check["testcd"],
    }


def findings_testcd_annotations(
    domain: str,
    question: str,
    include_result_variables: bool = False,
) -> list[dict[str, Any]]:
    """Return Findings --TESTCD context annotations inferred from a CRF question."""
    domain = normalize_domain_code(domain)
    normalized_question = clean_question_text(question).casefold()
    annotations: list[dict[str, Any]] = []
    seen: set[str] = set()

    for rule in FINDINGS_TESTCD_QUESTION_RULES.get(domain, []):
        if not any(re.search(pattern, normalized_question) for pattern in rule["patterns"]):
            continue
        context = testcd_context_annotation(domain, str(rule["testcd"]))
        if context and context["annotation"] not in seen:
            annotations.append(context)
            seen.add(context["annotation"])
        if include_result_variables:
            for variable in rule.get("result_variables", []):
                if variable in allowed_variables(domain) and variable not in seen:
                    annotations.append(
                        {
                            "annotation": variable,
                            "domain": domain,
                            "source_kind": "variable",
                            "reason": f"Result variable for {context['annotation'] if context else domain + 'TESTCD'}.",
                        }
                    )
                    seen.add(variable)
    return annotations


def normalize_repeating_edc_variable(variable_name: str) -> str:
    """Strip EDC repeat suffixes while keeping standard SDTM variable names intact."""
    variable = re.sub(r"[^A-Za-z0-9_]", "", str(variable_name or "")).upper()
    if variable in VS_EDC_TIMEPOINT_RULES:
        return variable
    return re.sub(r"\d+$", "", variable)


def vital_sign_edc_annotations(
    edc_variable_name: str,
    include_units: bool = True,
) -> list[dict[str, Any]]:
    """Map common custom VS EDC field names to SDTM VS annotations.

    EDC systems often encode collected vital sign concepts as sponsor-specific
    field names such as VSWT, VSHT, BMI, SYSBP2, or VSTIM5. These are not SDTMIG
    variables, but they should usually map to VS findings using separate
    Findings context and result annotations.
    """
    variable = re.sub(r"[^A-Za-z0-9_]", "", str(edc_variable_name or "")).upper()
    if variable in {"VSTEMPLOC", "TEMPLOC"}:
        return [
            {
                "annotation": "VSLOC",
                "domain": "VS",
                "source_kind": "variable",
                "reason": "Temperature measurement location.",
            }
        ]
    if variable in VS_EDC_TIMEPOINT_RULES:
        return [
            {
                "annotation": f"VSTPT = {VS_EDC_TIMEPOINT_RULES[variable]}",
                "domain": "VS",
                "source_kind": "context",
                "reason": "Collected vital-sign timepoint context.",
            },
            {
                "annotation": "VSDTC",
                "domain": "VS",
                "source_kind": "variable",
                "reason": "Collected vital-sign date/time.",
            },
        ]

    base_variable = normalize_repeating_edc_variable(variable)
    rule = VS_EDC_TESTCD_RULES.get(base_variable)
    if not rule:
        return []

    annotations = [
        {
            "annotation": f"VSTESTCD = {rule['testcd']}",
            "domain": "VS",
            "source_kind": "context",
            "reason": "Vital-sign finding test context.",
        },
        {
            "annotation": "VSORRES",
            "domain": "VS",
            "source_kind": "variable",
            "reason": "Vital-sign original result.",
        },
    ]
    if include_units and rule.get("orresu"):
        annotations.append(
            {
                "annotation": f"VSORRESU = {rule['orresu']}",
                "domain": "VS",
                "source_kind": "context",
                "reason": "Visible fixed unit for the vital-sign result.",
            }
        )
    return annotations


def clean_question_text(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def is_noise_text(value: str) -> bool:
    text = clean_question_text(value)
    if not text:
        return True
    if NOISE_ONLY_RE.match(text):
        return True
    return not re.search(r"[A-Za-z0-9]", text)


RESPONSE_CHOICE_LABELS = {
    "yes",
    "no",
    "not done",
    "not applicable",
    "unknown",
    "recovered/resolved",
    "recovered/resolved with",
    "sequelae",
    "recovering/resolving",
    "not recoved/not resolved",
    "not recovered/not resolved",
    "(ongoing)",
    "fatal",
    "positive",
    "negative",
    "other",
    "male",
    "female",
    "liquid",
    "powder",
    "serum",
    "urine",
    "white",
    "black or african american",
    "native hawaiian or other pacific islander",
    "american indian or alaska native",
    "asian",
    "hispanic or latino",
    "not hispanic or latino",
    "not reported",
    "in clinic",
    "phone contact",
    "virtual",
    "phone contact/virtual",
    "combination of in clinic",
    "combination of in clinic and virtual",
    "mild",
    "moderate",
    "severe",
    "life-threatening",
    "life threatening",
    "death",
}

CONTEXTUAL_RESPONSE_CHOICE_LABELS = {
    "completed as per protocol",
    "adverse event",
    "progressive disease",
    "clinical progression",
    "lost to follow-up",
    "lost to follow up",
    "associated study drug",
    "discontinued",
    "physician decision",
    "patient decision to",
    "discontinue treatment",
    "protocol deviation",
    "pregnancy",
    "study terminated by",
    "sponsor",
}

RESPONSE_CHOICE_PATTERNS = [
    r"^grade\s*[1-5]\s*[-:]\s*(mild|moderate|severe|life[- ]threatening|death)\b",
    r"^[1-5]\s*[-:]\s*(mild|moderate|severe|life[- ]threatening|death)\b",
    r"^check all that apply$",
    r"^select all that apply$",
    r"^fixed unit:",
    r"^\(?x+[.)x]*\)?$",
    r"^\(?24-hour clock\)?$",
    r"^protocol version \d",
    r"^(mild|moderate|severe|life[- ]threatening)\s*/\s*ctcae\b",
    r"^grade\s*4$",
]

INDEPENDENT_FIELD_LABEL_PATTERNS = [
    r"^protocol\s+version$",
    r"^protocol\s+version\s+at\b",
    r"\bconsent\s+date\b",
    r"\bmedical\s+history\s+term\b",
    r"^visit\s+date\b",
    r"^intensity\s+of\s+immunostain\b",
    r"^percent\s+positive\s+staining\b",
    r"\bwhite\s+blood\s+cells?\b",
]

RESPONSE_CHOICE_PROMPT_KEYWORDS = {
    "category",
    "ethnicity",
    "grade",
    "intent",
    "location",
    "method",
    "outcome",
    "race",
    "reason",
    "relationship",
    "result",
    "sex",
    "site",
    "status",
    "timepoint",
    "type",
}


def is_question_prompt(value: str) -> bool:
    text = clean_question_text(value)
    lower = text.casefold()
    return "?" in text or bool(re.match(r"^(did|was|were|is|are|does|do|has|have|how|if)\b", lower))


def opens_response_choice_block(value: str) -> bool:
    """Return True when a label is likely followed by checkbox/radio choices."""
    text = clean_question_text(value)
    lower = text.casefold()
    if is_question_prompt(text):
        return True
    tokens = set(re.findall(r"[A-Za-z0-9]+", lower))
    if tokens & RESPONSE_CHOICE_PROMPT_KEYWORDS:
        return True
    return any(
        phrase in lower
        for phrase in (
            "check all that apply",
            "select all that apply",
            "choose one",
            "mark all that apply",
            "applicable / not applicable",
        )
    )


def is_response_choice_label(value: str, after_prompt: bool = False) -> bool:
    """Return True for displayed answer choices, not independent CRF fields."""
    text = clean_question_text(value)
    lower = text.casefold()
    if any(re.search(pattern, lower) for pattern in INDEPENDENT_FIELD_LABEL_PATTERNS):
        return False
    if lower in RESPONSE_CHOICE_LABELS or lower.startswith("and "):
        return True
    if any(re.search(pattern, lower) for pattern in RESPONSE_CHOICE_PATTERNS):
        return True
    if not after_prompt:
        return False
    if lower in CONTEXTUAL_RESPONSE_CHOICE_LABELS:
        return True
    tokens = set(re.findall(r"[A-Za-z0-9]+", lower))
    if tokens & RESPONSE_CHOICE_PROMPT_KEYWORDS:
        return False
    if is_question_prompt(text):
        return False
    if re.match(
        r"^(date|time|start|end|onset|specify|provide|number|amount|dose|lot|term|actual|planned|"
        r"ongoing|outcome|reason|comment|description|physician|patient|visit)\b",
        lower,
    ):
        return False
    if len(tokens) <= 8:
        return True
    return False


def is_unit_hint_label(value: str) -> bool:
    """Return True for non-collected unit hints that should not swallow later fields."""
    return bool(re.match(r"^fixed unit:", clean_question_text(value).casefold()))


def is_field_sequence_marker(value: str) -> bool:
    """Return True for CRF item numbers that separate fields from choices."""
    return bool(re.fullmatch(r"\(?\d+\)?", clean_question_text(value)))


def is_explicit_response_choice_label(value: str) -> bool:
    """Return True for choices that are self-contained and should not extend a block."""
    lower = clean_question_text(value).casefold()
    return lower in RESPONSE_CHOICE_LABELS or lower.startswith("and ")


def filter_response_choice_labels(labels: list[str]) -> list[str]:
    """Keep field/question prompts and drop their visible checkbox/radio choices."""
    filtered: list[str] = []
    after_prompt = False
    for label in labels:
        text = clean_question_text(label)
        if not text:
            after_prompt = False
            continue
        if is_field_sequence_marker(text):
            after_prompt = False
            continue
        if is_response_choice_label(text, after_prompt):
            after_prompt = False if (is_unit_hint_label(text) or is_explicit_response_choice_label(text)) else True
            continue
        filtered.append(text)
        after_prompt = opens_response_choice_block(text)
    return filtered


def is_crf_field_label_candidate(value: str) -> bool:
    """Return True for CRF prompts/fields that should enter variable mapping."""
    text = clean_question_text(value)
    lowered = text.casefold()
    if len(lowered) < 2 or len(lowered) > 180:
        return False
    if lowered.startswith("("):
        return False
    if lowered.endswith("is chosen)"):
        return False
    if not re.search(r"[a-z]", lowered):
        return False
    if any(re.search(pattern, lowered) for pattern in RESPONSE_CHOICE_PATTERNS):
        return False
    if any(re.search(pattern, lowered) for pattern in INDEPENDENT_FIELD_LABEL_PATTERNS):
        return True
    skip_patterns = [
        r"^crf\s+\d",
        r"^generated on:",
        r"^page \d+",
        r"^protocol\b",
        r"^version\b",
        r"^field name\b",
        r"^data type$",
        r"^field label$",
        r"^units$",
        r"^values$",
        r"^pre-filled$",
        r"^include$",
        r"^oid$",
        r"^yes$",
        r"^no$",
        r"^not done$",
        r"^unknown$",
        r"^select all that apply$",
        r"^dd/mmm/yyyy$",
        r"^\d+ of \d+$",
    ]
    if any(re.search(pattern, lowered) for pattern in skip_patterns):
        return False
    if "(derived)" in lowered:
        return False
    return True


def should_map_to_supplemental(label: str) -> bool:
    """Return True only for collected fields/questions that need SUPP fallback."""
    text = clean_question_text(label)
    lower = text.casefold()
    tokens = re.findall(r"[A-Za-z0-9]+", lower)
    if not tokens or is_operational_only_text(text):
        return False
    if is_response_choice_label(text, after_prompt=False):
        return False
    if re.match(r"^v\d+(\.\d+)?\b", lower):
        return False
    if re.match(r"^(phase\s+\d|cohort\s+\d|use this form|information for|form\.?$|sponsor$|beam$)", lower):
        return False
    if re.fullmatch(r"(adverse event|withdrawal by patient|lost to follow-up|physician decision|covid-19)", lower):
        return False
    if text[:1].islower() and not re.match(r"^(if|date|time|reason|specify|provide|check)\b", lower):
        return False
    if supplemental_qnam_candidate(text)["method"] == "specific_text_rule":
        return True

    starts_like_question = bool(re.match(r"^(did|was|were|is|are|does|do|has|have|how|what|which)\b", lower))
    if starts_like_question:
        return True
    if lower.startswith("if ") and any(word in lower for word in ("specify", "provide", "indicate", "reason", "date", "number")):
        return True
    if re.match(r"^(date|time|reason|specify|provide|check if|check the box)", lower):
        return True

    field_tokens = {
        "age",
        "amount",
        "assessment",
        "category",
        "comment",
        "collection",
        "condition",
        "count",
        "date",
        "description",
        "detail",
        "details",
        "duration",
        "grade",
        "id",
        "identifier",
        "location",
        "method",
        "number",
        "origin",
        "reason",
        "research",
        "result",
        "sample",
        "samples",
        "specification",
        "specimen",
        "status",
        "term",
        "text",
        "time",
        "type",
    }
    return len(tokens) <= 10 and any(token in field_tokens for token in tokens)


QNAM_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "be",
    "box",
    "by",
    "check",
    "crf",
    "did",
    "do",
    "does",
    "for",
    "form",
    "has",
    "have",
    "if",
    "in",
    "is",
    "mark",
    "of",
    "on",
    "or",
    "patient",
    "provide",
    "question",
    "subject",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
    "yes",
}


QNAM_TOKEN_ABBREVIATIONS = {
    "additional": "ADD",
    "administered": "ADM",
    "administration": "ADM",
    "adverse": "AE",
    "allowed": "ALLOW",
    "allows": "ALLOW",
    "assessment": "ASS",
    "baseline": "BASE",
    "biomarker": "BIO",
    "biomarkers": "BIO",
    "cancer": "CAN",
    "classification": "CLAS",
    "clinical": "CLIN",
    "collection": "COLL",
    "collected": "COLL",
    "comment": "COMM",
    "comments": "COMM",
    "completed": "COMP",
    "completion": "COMP",
    "consent": "CNS",
    "date": "DT",
    "decision": "DEC",
    "description": "DESC",
    "details": "DET",
    "diagnosis": "DIAG",
    "disease": "DIS",
    "event": "EVT",
    "future": "FUT",
    "history": "HIST",
    "identifier": "ID",
    "initial": "INIT",
    "leftover": "LEFT",
    "medical": "MED",
    "method": "METH",
    "number": "NUM",
    "ongoing": "ONG",
    "other": "OTH",
    "performed": "PERF",
    "previous": "PREV",
    "procedure": "PROC",
    "progression": "PROG",
    "reason": "REAS",
    "research": "RSH",
    "result": "RES",
    "sample": "SAMP",
    "samples": "SAMP",
    "specify": "SPEC",
    "specimen": "SPC",
    "status": "STAT",
    "surgery": "SURG",
    "testing": "TEST",
    "treatment": "TRT",
    "tumor": "TUM",
    "type": "TYP",
    "visit": "VISIT",
}


def supplemental_qnam_candidate(question: str, domain: str | None = None) -> dict[str, Any]:
    """Generate a reviewable 1-8 character SUPP QNAM candidate from CRF text."""
    text = clean_question_text(question)
    tokens = [
        token.upper()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9]*", text)
        if token.casefold() not in QNAM_STOPWORDS
    ]
    if not tokens:
        tokens = ["SUPP"]

    normalized = " ".join(token.casefold() for token in tokens)
    explicit_patterns = [
        (r"\bscreen\b.*\bfailure\b.*\bdate\b", "SCRFDT"),
        (r"\bscreen\b.*\bfailure\b.*\breason\b", "SCRFREAS"),
        (r"\bprotocol\b.*\bversion\b", "PROTVER"),
        (r"\bversion\b.*\bprotocol\b", "PROTVER"),
        (r"\bleftover\b.*\bspecimen\b.*\bfuture\b.*\bresearch\b", "FUTRSH"),
        (r"\bfuture\b.*\bresearch\b", "FUTRSH"),
        (r"\bre[- ]?screen\b", "RESCRN"),
        (r"\bprevious\b.*\bunique\b.*\bsubject\b.*\bidentifier\b", "PREVUSUB"),
        (r"\bprevious\b.*\bpicf\b.*\bsignature\b.*\bdate\b", "PREVPICF"),
        (r"\bnyha\b.*\bclassification\b", "NYHACLS"),
        (r"\bclinically\b.*\bsignificant\b", "CLINSIG"),
        (r"\bnot\b.*\bdone\b.*\breason\b", "NDREAS"),
        (r"\bcollection\b.*\btime\b", "COLLTM"),
        (r"\bcollection\b.*\bdate\b", "COLLDT"),
    ]
    for pattern, qnam in explicit_patterns:
        if re.search(pattern, normalized):
            return {
                "qnam": qnam,
                "method": "specific_text_rule",
                "review_flag": "Review generated supplemental QNAM against sponsor naming conventions.",
            }

    abbreviated = [QNAM_TOKEN_ABBREVIATIONS.get(token.casefold(), token[:4]) for token in tokens]
    if len(abbreviated) == 1:
        qnam = abbreviated[0][:8]
    elif len(abbreviated) == 2:
        qnam = (abbreviated[0][:4] + abbreviated[1][:4])[:8]
    else:
        qnam = "".join(piece[:3] for piece in abbreviated[:3])[:8]
    qnam = re.sub(r"[^A-Z0-9]", "", qnam.upper())
    if not qnam or not qnam[0].isalpha():
        qnam = f"Q{qnam}"[:8] if qnam else "SUPPVAR"
    return {
        "qnam": qnam[:8],
        "method": "generated_from_field_text",
        "review_flag": "Review generated supplemental QNAM against sponsor naming conventions.",
    }


def is_operational_bookmark(title: str) -> bool:
    """Return True for PDF outline/bookmark sections that should not be mapped."""
    return clean_question_text(title).upper() in OPERATIONAL_BOOKMARK_TITLES


def is_operational_only_text(value: str) -> bool:
    """Return True for labels/pages that are operational-only rather than SDTM data."""
    text = clean_question_text(value).upper()
    if not text:
        return False
    return any(keyword in text for keyword in OPERATIONAL_PAGE_KEYWORDS)


def should_map_crf_page(
    page_title: str | None = None,
    bookmark_title: str | None = None,
    page_text: str | None = None,
) -> dict[str, Any]:
    """Decide whether a CRF page should enter Domain/Variable mapping.

    This helper is for downstream PDF extraction code. The mapper itself does
    not read PDF outlines, but when outline/bookmark metadata is available,
    pages under an "Annotations" bookmark and operational-only pages should be
    skipped before Step 1 domain mapping.
    """
    reasons: list[str] = []
    if bookmark_title and is_operational_bookmark(bookmark_title):
        reasons.append("Page is under an Annotations bookmark.")
    if is_operational_only_text(page_title or ""):
        reasons.append("Page title is operational-only.")
    if is_operational_only_text(page_text or ""):
        reasons.append("Page text appears operational-only.")
    return {
        "should_map": not reasons,
        "page_title": clean_question_text(page_title or ""),
        "bookmark_title": clean_question_text(bookmark_title or ""),
        "reasons": reasons,
    }


def normalize_bbox(bbox: tuple[float, float, float, float] | list[float]) -> BBox:
    x0, y0, x1, y1 = [float(value) for value in bbox]
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def bbox_intersects(left: BBox, right: BBox, padding: float = 0) -> bool:
    lx0, ly0, lx1, ly1 = left
    rx0, ry0, rx1, ry1 = right
    return not (
        lx1 + padding <= rx0
        or rx1 + padding <= lx0
        or ly1 + padding <= ry0
        or ry1 + padding <= ly0
    )


def bbox_inside_page(bbox: BBox, page_size: tuple[float, float], margin: float | None = None) -> bool:
    margin = BOX_LAYOUT_DEFAULTS["page_margin"] if margin is None else margin
    page_width, page_height = page_size
    x0, y0, x1, y1 = bbox
    return x0 >= margin and y0 >= margin and x1 <= page_width - margin and y1 <= page_height - margin


def estimate_annotation_box_size(
    annotation: str,
    style_type: str,
    font_size: float | None = None,
) -> dict[str, Any]:
    """
    Estimate a FreeText box size that avoids clipped text.

    This intentionally overestimates a little because Acrobat can clip tight
    boxes, especially for wrapped constants/context annotations.
    """
    style = ANNOTATION_STYLE_GUIDE[style_type]
    raw_font_size = font_size or style["font_size"]
    size = ANNOTATION_FONT_SIZE if isinstance(raw_font_size, str) else float(raw_font_size)
    if style_type == "domain":
        size = max(size, DOMAIN_FONT_SIZE)

    raw_text = str(annotation or "").strip()
    explicit_lines = [
        clean_question_text(line)
        for line in re.split(r"\r\n|\r|\n|<br\s*/?>", raw_text, flags=re.I)
    ]
    explicit_lines = [line for line in explicit_lines if line]
    if not explicit_lines:
        explicit_lines = [clean_question_text(raw_text)]
    text = " ".join(explicit_lines)
    max_width = BOX_LAYOUT_DEFAULTS["max_width"][style_type]
    min_width = BOX_LAYOUT_DEFAULTS["min_width"][style_type]
    min_height = BOX_LAYOUT_DEFAULTS["min_height"][style_type]
    max_height = BOX_LAYOUT_DEFAULTS["max_height"][style_type]
    char_width = size * BOX_LAYOUT_DEFAULTS["average_char_width_multiplier"]
    padding_x = (
        BOX_LAYOUT_DEFAULTS["domain_horizontal_padding"]
        if style_type == "domain"
        else BOX_LAYOUT_DEFAULTS["horizontal_padding"]
    )
    padding_y = (
        BOX_LAYOUT_DEFAULTS["domain_vertical_padding"]
        if style_type == "domain"
        else BOX_LAYOUT_DEFAULTS["vertical_padding"]
    )
    line_height = size * BOX_LAYOUT_DEFAULTS["line_height_multiplier"]

    horizontal_padding = padding_x * 2
    vertical_padding = padding_y * 2

    longest_explicit_line = max(explicit_lines, key=len) if explicit_lines else text
    unwrapped_width = (len(longest_explicit_line) * char_width) + horizontal_padding
    width = max(min_width, min(max_width, unwrapped_width))
    available_text_width = max(char_width, width - horizontal_padding)
    effective_text_width = available_text_width
    if style_type == "context":
        # PyMuPDF/Acrobat FreeText wraps conservatively around spaces and "=".
        # Without this safety factor, "EGTESTCD = RRAG" can render on two
        # lines inside a box sized as one line, clipping the second line.
        effective_text_width *= BOX_LAYOUT_DEFAULTS["freetext_wrap_safety_multiplier"]
    chars_per_line = max(1, int((effective_text_width / max(char_width, 1)) + 0.001))
    wrapped_line_counts = [
        max(1, (len(line) + chars_per_line - 1) // chars_per_line)
        for line in explicit_lines
    ]
    line_count = max(1, sum(wrapped_line_counts))
    if style_type == "context" and re.search(r"\b[A-Z]{2,4}TESTCD\s*=", text.upper()):
        line_count = max(line_count, 2)
    raw_height = (line_count * line_height) + vertical_padding
    height = max(min_height, min(max_height, raw_height))
    return {
        "width": round(width, 1),
        "height": round(height, 1),
        "font_size": size,
        "line_count": line_count,
        "explicit_line_count": len(explicit_lines),
        "wrapped_line_counts": wrapped_line_counts,
        "chars_per_line": chars_per_line,
        "clipped_risk": raw_height > max_height,
    }


def _candidate_box_from_anchor(
    source_bbox: BBox,
    width: float,
    height: float,
    position: str,
    gap: float,
) -> BBox:
    x0, y0, x1, y1 = source_bbox
    if position == "right":
        return x1 + gap, y0, x1 + gap + width, y0 + height
    if position == "left":
        return x0 - gap - width, y0, x0 - gap, y0 + height
    if position == "above":
        return x0, y0 - gap - height, x0 + width, y0 - gap
    if position == "below":
        return x0, y1 + gap, x0 + width, y1 + gap + height
    if position == "above_right":
        return x1 + gap, y0 - gap - height, x1 + gap + width, y0 - gap
    if position == "below_right":
        return x1 + gap, y1 + gap, x1 + gap + width, y1 + gap + height
    if position == "above_left":
        return x0 - gap - width, y0 - gap - height, x0 - gap, y0 - gap
    if position == "below_left":
        return x0 - gap - width, y1 + gap, x0 - gap, y1 + gap + height
    raise ValueError(f"Unknown annotation position: {position}")


def _box_collision_reasons(
    bbox: BBox,
    page_size: tuple[float, float],
    pdf_text_bboxes: list[BBox] | None = None,
    existing_annotation_bboxes: list[BBox] | None = None,
    allow_pdf_text_overlap: bool = False,
) -> list[str]:
    reasons: list[str] = []
    if not bbox_inside_page(bbox, page_size):
        reasons.append("outside page margin")
    if not allow_pdf_text_overlap:
        for text_bbox in pdf_text_bboxes or []:
            if bbox_intersects(bbox, text_bbox, BOX_LAYOUT_DEFAULTS["min_gap_from_pdf_text"]):
                reasons.append("overlaps original PDF text/content")
                break
    for annotation_bbox in existing_annotation_bboxes or []:
        if bbox_intersects(
            bbox,
            annotation_bbox,
            BOX_LAYOUT_DEFAULTS["min_gap_between_annotations"],
        ):
            reasons.append("overlaps existing annotation")
            break
    return reasons


def bbox_center_distance(left: BBox, right: BBox) -> float:
    """Distance between two bbox centers in PDF points."""
    lx = (left[0] + left[2]) / 2
    ly = (left[1] + left[3]) / 2
    rx = (right[0] + right[2]) / 2
    ry = (right[1] + right[3]) / 2
    return ((lx - rx) ** 2 + (ly - ry) ** 2) ** 0.5


SOURCE_MATCH_SKIP_TOKENS = {
    "x",
    "xx",
    "xxx",
    "mmm",
    "yyyy",
    "hh",
    "nn",
    "24",
    "hour",
    "clock",
}

SOURCE_MATCH_STOP_WORDS = {
    "a",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "if",
    "in",
    "is",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
}


def source_match_tokens(text: str) -> list[str]:
    """Tokenize CRF source text for word-coordinate matching."""
    tokens = []
    for token in re.findall(r"[A-Za-z0-9]+", str(text or "").casefold()):
        if token in SOURCE_MATCH_SKIP_TOKENS:
            continue
        tokens.append(token)
    return tokens


def locate_source_text_bbox(
    pdf_words: list[tuple[Any, ...]],
    label: str,
    *,
    header_y_max: float = 115,
    allow_header_match: bool = False,
    min_fuzzy_overlap: float = 0.55,
) -> dict[str, Any]:
    """Locate the visible CRF field label bbox from PyMuPDF word output.

    PyMuPDF words are tuples like ``(x0, y0, x1, y1, text, block, line, word)``.
    This helper deliberately ignores exact matches in the page header by
    default, because form titles can repeat field labels such as "Visit Date"
    and would otherwise pull annotations to the header.
    """
    label_tokens = source_match_tokens(label)
    if not label_tokens:
        return {
            "bbox": None,
            "method": "no_label_tokens",
            "matched_header_candidate": False,
        }

    sorted_words = sorted(
        pdf_words or [],
        key=lambda word: (round(float(word[1]), 1), round(float(word[0]), 1)),
    )
    word_tokens: list[str] = []
    word_items: list[tuple[Any, ...]] = []
    for word in sorted_words:
        for token in source_match_tokens(str(word[4] if len(word) > 4 else "")):
            word_tokens.append(token)
            word_items.append(word)

    if not word_tokens:
        return {
            "bbox": None,
            "method": "no_pdf_words",
            "matched_header_candidate": False,
        }

    def union_bbox(items: list[tuple[Any, ...]]) -> BBox:
        return (
            min(float(item[0]) for item in items),
            min(float(item[1]) for item in items),
            max(float(item[2]) for item in items),
            max(float(item[3]) for item in items),
        )

    def is_header_bbox(bbox: BBox) -> bool:
        return bbox[1] < header_y_max

    matched_header_candidate = False
    max_exact_len = min(len(label_tokens), 16)
    min_exact_len = max(1, min(4, max_exact_len))
    for length in range(max_exact_len, min_exact_len - 1, -1):
        sequence = label_tokens[:length]
        for index in range(0, len(word_tokens) - length + 1):
            if word_tokens[index:index + length] != sequence:
                continue
            bbox = union_bbox(word_items[index:index + length])
            if is_header_bbox(bbox) and not allow_header_match:
                matched_header_candidate = True
                continue
            return {
                "bbox": bbox,
                "method": f"exact_first_{length}_tokens",
                "matched_header_candidate": matched_header_candidate,
            }

    useful_tokens = [
        token for token in label_tokens
        if token not in SOURCE_MATCH_STOP_WORDS
    ] or label_tokens
    useful_set = set(useful_tokens)
    best: tuple[int, int] | None = None
    best_score = 0.0
    window_min = max(2, min(5, len(useful_tokens)))
    window_max = max(window_min, min(12, len(label_tokens) + 2))
    for window_size in range(window_min, window_max + 1):
        for index in range(0, max(0, len(word_tokens) - window_size + 1)):
            chunk = word_tokens[index:index + window_size]
            score = len(useful_set.intersection(chunk)) / max(1, len(useful_set))
            if score <= best_score:
                continue
            bbox = union_bbox(word_items[index:index + window_size])
            if is_header_bbox(bbox) and not allow_header_match:
                matched_header_candidate = True
                continue
            best_score = score
            best = (index, window_size)

    if best and best_score >= min_fuzzy_overlap:
        index, window_size = best
        return {
            "bbox": union_bbox(word_items[index:index + window_size]),
            "method": f"fuzzy_overlap_{best_score:.2f}",
            "matched_header_candidate": matched_header_candidate,
        }

    return {
        "bbox": None,
        "method": "not_found",
        "matched_header_candidate": matched_header_candidate,
    }


def extract_domain_codes(text: str) -> list[str]:
    """Extract domain codes from guide text while avoiding variable names."""
    valid = metadata_domain_codes() | CUSTOM_OR_CONFIRMATION_DOMAINS
    found: list[str] = []
    for token in re.findall(r"\b[A-Z]{2,4}\b", str(text or "")):
        if token in valid and token not in found:
            found.append(token)
    return found


def domain_label(domain: str) -> dict[str, Any]:
    domain = normalize_domain_code(domain)
    dataset = dataset_metadata(domain)
    if dataset:
        label = str(dataset["Dataset Label"])
        return {
            "domain": domain,
            "dataset_label": label,
            "annotation": f"{domain} ({label})",
            "in_sdtmig": True,
            "needs_confirmation": False,
        }
    return {
        "domain": domain,
        "dataset_label": None,
        "annotation": f"{domain} (CONFIRM DATASET LABEL)",
        "in_sdtmig": False,
        "needs_confirmation": True,
    }


def normalize_domain_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    approach = str(
        candidate.get("domain")
        or candidate.get("preferred_domain_approach")
        or candidate.get("preferred_domain")
        or ""
    )
    domains = extract_domain_codes(approach)
    return {
        **candidate,
        "domains": domains,
        "domain_labels": [domain_label(domain) for domain in domains],
    }


def map_form_to_domains(
    form_name: str,
    concept_min_confidence: float = 0.55,
    guide_min_confidence: float = 0.35,
    page_text: str | None = None,
) -> dict[str, Any]:
    """Map a CRF form/page title to candidate SDTM domain(s)."""
    candidates = [
        normalize_domain_candidate(row)
        for row in domain_mapping_guide.map_form_candidates(
            form_name,
            concept_min_confidence=concept_min_confidence,
            guide_min_confidence=guide_min_confidence,
            page_text=page_text,
        )
    ]
    best = candidates[0] if candidates else None
    return {
        "form_name": form_name,
        "best_mapping": best,
        "all_candidates": candidates,
        "instruction_step": "Step 1 domain mapping",
    }


def validate_variable(domain: str, variable_name: str) -> dict[str, Any]:
    domain = normalize_domain_code(domain)
    variable_name = str(variable_name or "").strip().upper()
    allowed = allowed_variables(domain)
    return {
        "domain": domain,
        "variable_name": variable_name,
        "in_sdtmig_domain": variable_name in allowed,
        "domain_in_sdtmig": bool(dataset_metadata(domain)),
    }


def variable_metadata(domain: str, variable_name: str) -> dict[str, Any] | None:
    domain = normalize_domain_code(domain)
    variable_name = str(variable_name or "").strip().upper()
    try:
        for row in sdtmig_metadata.get_variables(domain, version=SDTMIG_VERSION):
            if row.get("Variable Name") == variable_name:
                return row
    except (KeyError, ValueError):
        return None
    return None


def _pattern_is_high_value(row: dict[str, Any]) -> bool:
    pattern = clean_question_text(str(row.get("question_pattern", "")))
    if is_noise_text(pattern):
        return False
    normalized = question_patterns.normalize_question(pattern)
    tokens = [token for token in normalized.split() if re.search(r"[a-z]", token)]
    return len(tokens) >= 1


def _support_sort_key(row: dict[str, Any]) -> tuple[float, float, int, int]:
    return (
        1.0 if row.get("exact_question_match") else 0.0,
        float(row.get("score", 0.0)),
        int(row.get("supporting_crf_count", 0) or 0),
        int(row.get("row_count", 0) or 0),
    )


def extract_testcd_value_from_pattern_row(row: dict[str, Any], domain: str) -> str | None:
    """Extract a valid --TESTCD value from pattern evidence annotations."""
    domain = normalize_domain_code(domain)
    testcd_var = f"{domain}TESTCD"
    for annotation in row.get("example_variable_annotations", []):
        match = re.search(rf"\b{re.escape(testcd_var)}\s*=?\s*\"?([A-Z0-9_]+)", str(annotation).upper())
        if not match:
            continue
        testcd = match.group(1).strip("_")
        if validate_testcd_value(testcd)["valid"]:
            return testcd
    return None


def variable_name_from_annotation(annotation: str) -> str:
    """Return the main SDTM variable name represented by an annotation string."""
    text = clean_question_text(annotation).upper()
    text = re.split(r"\s*=", text, maxsplit=1)[0]
    text = re.split(r"\s+IN\s+SUPP[A-Z]{2,4}\b", text, maxsplit=1)[0]
    return re.sub(r"[^A-Z0-9_]", "", text)


def direct_variable_question_candidates(domain: str, question: str) -> list[dict[str, Any]]:
    """Return approved-domain direct mappings before fuzzy pattern matching.

    Step 2 is driven by the approved SDTM domain. These rules catch standard
    labels such as Enrollment identifiers (DM.SITEID/SUBJID/USUBJID) even when
    the historical pattern library has no form-name-specific evidence for them.
    """
    domain = normalize_domain_code(domain)
    normalized_question = clean_question_text(question).casefold()
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    for rule in DIRECT_VARIABLE_QUESTION_RULES.get(domain, []):
        if not any(re.search(pattern, normalized_question, flags=re.I) for pattern in rule["patterns"]):
            continue
        added_for_rule = False
        for annotation in rule["annotations"]:
            variable_name = variable_name_from_annotation(annotation)
            validation = validate_variable(domain, variable_name)
            is_supp_annotation = bool(re.search(r"\bIN\s+SUPP[A-Z]{2,4}\b", annotation, flags=re.I))
            if not validation["in_sdtmig_domain"] and not is_supp_annotation:
                continue
            if annotation in seen:
                continue
            metadata = variable_metadata(domain, variable_name)
            seen.add(annotation)
            candidates.append(
                {
                    "domain": domain,
                    "variable_name": variable_name,
                    "annotation": clean_question_text(annotation),
                    "variable_label": metadata.get("Variable Label") if metadata else "Supplemental Qualifier",
                    "score": 1.01,
                    "question_pattern": "; ".join(rule["patterns"]),
                    "supporting_crf_frequency": "direct",
                    "supporting_crf_count": 999,
                    "row_count": 999,
                    "matched_terms": [],
                    "example_questions": [question],
                    "example_variable_annotations": [annotation],
                    "exact_question_match": True,
                    "metadata_check": validation,
                    "annotation_style": classify_annotation(annotation, domain=domain),
                    "match_type": "approved_domain_direct_rule",
                }
            )
            added_for_rule = True
        if added_for_rule:
            break
    return candidates


def map_question_to_variables(
    domain: str,
    question: str,
    min_score: float = 0.82,
    metadata_whitelist: bool = True,
    max_candidates: int = 10,
) -> dict[str, Any]:
    """
    Map one CRF question/label to variable candidates within an approved domain.

    The mapper stays inside the supplied domain. It does not force cross-domain
    variables into the page domain.
    """
    domain = normalize_domain_code(domain)
    question = clean_question_text(question)
    if is_noise_text(question):
        return {
            "domain": domain,
            "question": question,
            "candidates": [],
            "best_mapping": None,
            "issues": ["Question/label is empty or symbol-only."],
        }
    if is_response_choice_label(question):
        return {
            "domain": domain,
            "question": question,
            "candidates": [],
            "best_mapping": None,
            "issues": ["Skipped displayed response choice; annotate the parent CRF question instead."],
        }
    matches = question_patterns.match_variable_question_patterns(
        domain=domain,
        question=question,
        min_score=min_score,
    )

    candidates: list[dict[str, Any]] = direct_variable_question_candidates(domain, question)
    candidate_keys = {
        (candidate["domain"], candidate["variable_name"], candidate["annotation"])
        for candidate in candidates
    }
    pattern_matches = [] if candidates else matches
    for row in pattern_matches:
        if not _pattern_is_high_value(row):
            continue
        variable_name = str(row.get("variable_name", "")).upper()
        validation = validate_variable(domain, variable_name)
        if metadata_whitelist and not validation["in_sdtmig_domain"]:
            continue
        metadata = variable_metadata(domain, variable_name)
        annotation = variable_name
        example_annotations = [str(value or "").strip() for value in row.get("example_variable_annotations", [])]
        constant_annotation = next((value for value in example_annotations if "=" in value), "")
        if constant_annotation and variable_name_from_annotation(constant_annotation) == variable_name:
            annotation = clean_question_text(constant_annotation)
        if re.fullmatch(r"[A-Z]{2,4}TESTCD", variable_name):
            testcd = extract_testcd_value_from_pattern_row(row, domain)
            if testcd:
                annotation = f"{variable_name} = {testcd}"
        normalized_question = question_patterns.normalize_question(question)
        normalized_examples = {
            question_patterns.normalize_question(str(example))
            for example in [row.get("question_pattern"), *row.get("example_questions", [])]
        }
        exact_question_match = normalized_question in normalized_examples
        candidate = (
            {
                "domain": domain,
                "variable_name": variable_name,
                "annotation": annotation,
                "variable_label": metadata.get("Variable Label") if metadata else None,
                "score": row.get("score"),
                "question_pattern": row.get("question_pattern"),
                "supporting_crf_frequency": row.get("supporting_crf_frequency"),
                "supporting_crf_count": row.get("supporting_crf_count"),
                "row_count": row.get("row_count"),
                "matched_terms": row.get("matched_terms", []),
                "example_questions": row.get("example_questions", []),
                "example_variable_annotations": row.get("example_variable_annotations", []),
                "exact_question_match": exact_question_match,
                "metadata_check": validation,
                "annotation_style": classify_annotation(annotation, domain=domain),
                "match_type": "question_pattern",
            }
        )
        key = (candidate["domain"], candidate["variable_name"], candidate["annotation"])
        if key in candidate_keys:
            continue
        candidate_keys.add(key)
        candidates.append(candidate)

    candidates = sorted(candidates, key=_support_sort_key, reverse=True)[:max_candidates]
    issues = qc_variable_candidates(domain, question, candidates)
    return {
        "domain": domain,
        "question": question,
        "candidates": candidates,
        "best_mapping": candidates[0] if candidates else None,
        "issues": issues,
    }


def is_non_collected_context_annotation(annotation: str, domain: str | None = None) -> bool:
    """Return True for annotations that describe context rather than collected data.

    These should use dashed annotation borders per the aCRF instruction. Examples
    include Findings test-code constants, unit constants, RELREC notes, and
    explicit conditional/derived annotations. Supplemental qualifier annotations
    like ``QNAM in SUPPxx`` are collected variables and use solid borders.
    """
    text = clean_question_text(annotation)
    upper = text.upper()
    domain_code = normalize_domain_code(domain)

    if upper == NOT_SUBMITTED:
        return True
    if "=" in upper or re.search(r"\bWHEN\b|\bIF\b", upper):
        return True
    if "RELREC" in upper:
        return True
    if re.fullmatch(r"[A-Z]{2,4}(?:TESTCD|TEST)", upper):
        return True
    if upper in {"AGEU"}:
        return True
    return False


def classify_annotation(annotation: str, domain: str | None = None) -> dict[str, Any]:
    """Classify annotation wording using the Word instruction appearance rules."""
    text = clean_question_text(annotation)
    upper = text.upper()
    style_type = "variable"
    reasons: list[str] = []

    if re.fullmatch(r"[A-Z]{2,4}\s+\([^)]+\)", text):
        style_type = "domain"
        reasons.append("domain label")
    elif is_non_collected_context_annotation(text, domain=domain):
        style_type = "context"
        reasons.append("not collected / context annotation")

    if domain and normalize_domain_code(domain) in FINDINGS_DOMAINS:
        if re.search(r"(TESTCD|TEST)\s*/\s*|/\s*(ORRES|ORRESU|STRESC|STRESN)", upper):
            reasons.append("combined Findings shorthand should be split")

    return {
        "style_type": style_type,
        "style": ANNOTATION_STYLE_GUIDE[style_type],
        "placement": ANNOTATION_PLACEMENT_GUIDE[style_type],
        "reasons": reasons,
    }


def annotation_instruction(
    annotation: str,
    domain: str,
    domain_order_index: int = 0,
    source_kind: str | None = None,
    page_domains: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """
    Return the style, border, color, and placement instruction for one annotation.

    source_kind can be "domain", "variable", or "context" when the caller already
    knows the annotation type. Otherwise the type is inferred from wording.
    """
    classified = classify_annotation(annotation, domain=domain)
    style_type = source_kind or classified["style_type"]
    if source_kind != "domain" and is_non_collected_context_annotation(annotation, domain=domain):
        style_type = "context"
    if page_domains is not None:
        domain_order_index = domain_order_index_for_page(domain, page_domains)
    color = PAGE_DOMAIN_COLORS[min(domain_order_index, len(PAGE_DOMAIN_COLORS) - 1)]
    return {
        "annotation": clean_question_text(annotation),
        "domain": normalize_domain_code(domain),
        "annotation_object": ANNOTATION_STYLE_GUIDE[style_type]["annotation_object"],
        "style_type": style_type,
        "border": ANNOTATION_STYLE_GUIDE[style_type]["border"],
        "border_width": ANNOTATION_STYLE_GUIDE[style_type]["border_width"],
        "font": ANNOTATION_STYLE_GUIDE[style_type]["font"],
        "pdf_fontname": ANNOTATION_STYLE_GUIDE[style_type]["pdf_fontname"],
        "font_size": ANNOTATION_STYLE_GUIDE[style_type]["font_size"],
        "bold": ANNOTATION_STYLE_GUIDE[style_type]["bold"],
        "text_color": ANNOTATION_STYLE_GUIDE[style_type]["text_color"],
        "background_color": color,
        "domain_order_index": domain_order_index,
        "placement": ANNOTATION_PLACEMENT_GUIDE[style_type],
        "rendering": ANNOTATION_RENDERING_GUIDE,
        "reasons": classified["reasons"],
    }


def recommend_domain_box(
    annotation: str,
    domain: str,
    page_size: tuple[float, float],
    pdf_text_bboxes: list[tuple[float, float, float, float] | list[float]] | None = None,
    existing_annotation_bboxes: list[tuple[float, float, float, float] | list[float]] | None = None,
    domain_order_index: int = 0,
    page_domains: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Place domain labels in the top blank band whenever possible."""
    instruction = annotation_instruction(
        annotation,
        domain=domain,
        domain_order_index=domain_order_index,
        source_kind="domain",
        page_domains=page_domains,
    )
    size = estimate_annotation_box_size(annotation, "domain")
    width = size["width"]
    height = size["height"]
    page_width, _page_height = page_size
    margin = BOX_LAYOUT_DEFAULTS["page_margin"]
    top_band = BOX_LAYOUT_DEFAULTS["domain_top_band_height"]
    gap = BOX_LAYOUT_DEFAULTS["min_gap_between_annotations"]
    pdf_text = [normalize_bbox(bbox) for bbox in pdf_text_bboxes or []]
    existing = [normalize_bbox(bbox) for bbox in existing_annotation_bboxes or []]
    attempted: list[dict[str, Any]] = []

    y_positions = [margin, margin + height + gap, margin + (2 * (height + gap))]
    x_start = margin
    while x_start + width <= page_width - margin:
        for y_start in y_positions:
            if y_start + height > top_band:
                continue
            candidate = (x_start, y_start, x_start + width, y_start + height)
            reasons = _box_collision_reasons(candidate, page_size, pdf_text, existing)
            attempted.append({"position": "top_band", "bbox": candidate, "blocked_by": reasons})
            if not reasons:
                return {
                    **instruction,
                    "bbox": candidate,
                    "placement_status": "placed_top_blank_area",
                    "relative_position": "top_band",
                    "box_size": size,
                    "attempted_positions": attempted,
                }
        x_start += width + gap

    return {
        **instruction,
        "bbox": None,
        "placement_status": "needs_manual_or_second_pass_placement",
        "relative_position": None,
        "box_size": size,
        "attempted_positions": attempted,
        "issues": ["Could not place domain label in top blank area without overlap."],
    }


def recommend_annotation_box(
    annotation: str,
    domain: str,
    page_size: tuple[float, float],
    source_bbox: tuple[float, float, float, float] | list[float] | None = None,
    pdf_text_bboxes: list[tuple[float, float, float, float] | list[float]] | None = None,
    existing_annotation_bboxes: list[tuple[float, float, float, float] | list[float]] | None = None,
    domain_order_index: int = 0,
    source_kind: str | None = None,
    page_domains: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """
    Recommend a non-overlapping FreeText box.

    Coordinate assumption: PDF points with origin at top-left, x increasing
    rightward and y increasing downward. Convert coordinates first if your PDF
    library uses a different coordinate system.
    """
    instruction = annotation_instruction(
        annotation,
        domain=domain,
        domain_order_index=domain_order_index,
        source_kind=source_kind,
        page_domains=page_domains,
    )
    style_type = instruction["style_type"]

    if style_type == "domain":
        return recommend_domain_box(
            annotation=annotation,
            domain=domain,
            page_size=page_size,
            pdf_text_bboxes=pdf_text_bboxes,
            existing_annotation_bboxes=existing_annotation_bboxes,
            domain_order_index=domain_order_index,
            page_domains=page_domains,
        )

    if source_bbox is None:
        raise ValueError("source_bbox is required for variable/context annotation placement.")

    size = estimate_annotation_box_size(annotation, style_type)
    width = size["width"]
    height = size["height"]
    source = normalize_bbox(source_bbox)
    pdf_text = [normalize_bbox(bbox) for bbox in pdf_text_bboxes or []]
    existing = [normalize_bbox(bbox) for bbox in existing_annotation_bboxes or []]
    attempted: list[dict[str, Any]] = []

    for position in BOX_LAYOUT_DEFAULTS["nearby_search_offsets"]:
        candidate = _candidate_box_from_anchor(
            source,
            width,
            height,
            position,
            BOX_LAYOUT_DEFAULTS["preferred_gap_from_source"],
        )
        reasons = _box_collision_reasons(candidate, page_size, pdf_text, existing)
        attempted.append({"position": position, "bbox": candidate, "blocked_by": reasons})
        if not reasons:
            return {
                **instruction,
                "bbox": candidate,
                "placement_status": "placed_near_source",
                "relative_position": position,
                "box_size": size,
                "attempted_positions": attempted,
            }

    for attempted_position in attempted:
        reasons = [
            reason
            for reason in attempted_position["blocked_by"]
            if reason != "overlaps original PDF text/content"
        ]
        if reasons:
            continue
        return {
            **instruction,
            "bbox": attempted_position["bbox"],
            "placement_status": "placed_near_source_relaxed_content_overlap",
            "relative_position": attempted_position["position"],
            "box_size": size,
            "attempted_positions": attempted,
            "issues": [
                "No fully blank nearby placement found; placed near source while allowing non-text CRF content overlap. Pass word-level text bboxes so original text remains protected."
            ],
        }

    return {
        **instruction,
        "bbox": None,
        "placement_status": "unplaced_no_nearby_space",
        "relative_position": None,
        "box_size": size,
        "attempted_positions": attempted,
        "issues": [
            "Could not place annotation near the source without going outside the page or overlapping another annotation."
        ],
    }


def recommend_annotation_boxes_for_question(
    annotations: list[dict[str, Any]],
    source_bbox: tuple[float, float, float, float] | list[float],
    page_size: tuple[float, float],
    pdf_text_bboxes: list[tuple[float, float, float, float] | list[float]] | None = None,
    existing_annotation_bboxes: list[tuple[float, float, float, float] | list[float]] | None = None,
    page_domains: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    """
    Place every annotation for one CRF question.

    Preferred order is same-line horizontal placement to the right of the
    question, then horizontal lanes above the question. If space is tight, keep
    adding lanes instead of dropping annotations.
    """
    source = normalize_bbox(source_bbox)
    page_width, _page_height = page_size
    margin = BOX_LAYOUT_DEFAULTS["page_margin"]
    gap = BOX_LAYOUT_DEFAULTS["min_gap_between_annotations"]
    pdf_text = [normalize_bbox(bbox) for bbox in pdf_text_bboxes or []]
    existing = [normalize_bbox(bbox) for bbox in existing_annotation_bboxes or []]
    placed: list[dict[str, Any]] = []
    lane_next_x: dict[int, float] = {0: source[2] + BOX_LAYOUT_DEFAULTS["preferred_gap_from_source"]}

    def lane_y(lane: int, height: float) -> float:
        if lane == 0:
            return source[1]
        if lane < 0:
            return max(margin, source[1] + (lane * (height + gap)))
        return min(source[3] + gap + ((lane - 1) * (height + gap)), _page_height - margin - height)

    for row in annotations:
        annotation = clean_question_text(str(row.get("annotation") or ""))
        domain = normalize_domain_code(row.get("domain"))
        if not annotation:
            continue
        style_type = str(row.get("annotation_type") or classify_annotation(annotation, domain=domain)["style_type"])
        size = estimate_annotation_box_size(annotation, style_type)
        width = min(float(size["width"]), max(24.0, page_width - (2 * margin)))
        height = float(size["height"])
        lanes = [0, -1, -2, -3, -4, 1, 2, 3, 4]
        chosen_bbox: BBox | None = None
        chosen_lane: int | None = None
        attempted: list[dict[str, Any]] = []

        for lane in lanes:
            y = lane_y(lane, height)
            x_start = lane_next_x.get(lane, source[2] + BOX_LAYOUT_DEFAULTS["preferred_gap_from_source"])
            if x_start + width > page_width - margin:
                x_start = margin
            candidate = (x_start, y, min(x_start + width, page_width - margin), y + height)
            reasons = _box_collision_reasons(candidate, page_size, pdf_text, existing)
            attempted.append({"lane": lane, "bbox": candidate, "blocked_by": reasons})
            if not reasons:
                chosen_bbox = candidate
                chosen_lane = lane
                break

        if chosen_bbox is None:
            lane = -1
            while True:
                y = lane_y(lane, height)
                x_start = lane_next_x.get(lane, source[2] + BOX_LAYOUT_DEFAULTS["preferred_gap_from_source"])
                if x_start + width > page_width - margin:
                    x_start = margin
                candidate = (x_start, y, min(x_start + width, page_width - margin), y + height)
                reasons = _box_collision_reasons(candidate, page_size, [], existing)
                attempted.append({"lane": lane, "bbox": candidate, "blocked_by": reasons, "pass": "forced_lane"})
                if not reasons or lane <= -12:
                    chosen_bbox = candidate
                    chosen_lane = lane
                    break
                lane -= 1

        lane_next_x[chosen_lane or 0] = chosen_bbox[2] + gap
        existing.append(chosen_bbox)
        placed.append(
            {
                **annotation_instruction(
                    annotation,
                    domain=domain,
                    source_kind=row.get("source_kind"),
                    page_domains=page_domains,
                ),
                "annotation": annotation,
                "domain": domain,
                "bbox": chosen_bbox,
                "placement_status": "placed_question_lane" if not any(
                    attempt.get("pass") == "forced_lane" for attempt in attempted[-1:]
                ) else "forced_question_lane",
                "relative_position": f"question_lane_{chosen_lane}",
                "box_size": size,
                "attempted_positions": attempted,
                "source_row": row,
            }
        )

    return placed


def qc_variable_candidates(
    domain: str,
    question: str,
    candidates: list[dict[str, Any]],
) -> list[str]:
    issues: list[str] = []
    domain = normalize_domain_code(domain)
    if not dataset_metadata(domain):
        issues.append(f"{domain} is not present in SDTMIG v3.4 metadata; confirm custom domain.")
    if is_noise_text(question):
        issues.append("Question/label is empty or symbol-only.")
    if not candidates:
        issues.append("No high-confidence metadata-valid variable candidate found.")
    for candidate in candidates:
        variable_name = candidate.get("variable_name", "")
        if "/" in variable_name:
            issues.append(f"{variable_name} looks like combined shorthand; split final annotations.")
        validation = candidate.get("metadata_check", {})
        if not validation.get("in_sdtmig_domain"):
            issues.append(f"{variable_name} is not in SDTMIG v3.4 {domain} variable list.")
    return sorted(set(issues))


PDF_ANNOTATION_MIN_SCORE = 0.82


def candidate_is_safe_for_pdf_annotation(
    candidate: dict[str, Any],
    min_score: float = PDF_ANNOTATION_MIN_SCORE,
) -> bool:
    """Return True when a candidate is safe enough to write on the PDF.

    Direct rules are curated mappings and do not depend on fuzzy score.
    Pattern-derived mappings must meet the PDF annotation confidence threshold.
    """
    if candidate.get("match_type") == "approved_domain_direct_rule":
        return True
    try:
        score = float(candidate.get("score") or 0)
    except (TypeError, ValueError):
        score = 0.0
    return score >= min_score


def annotations_from_variable_results(variable_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build the authoritative item annotation list from PDF-safe candidates."""
    annotations: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for result in variable_results:
        for candidate in result.get("candidates", []):
            if not candidate_is_safe_for_pdf_annotation(candidate):
                continue
            domain = normalize_domain_code(candidate.get("domain"))
            annotation = clean_question_text(candidate.get("annotation") or candidate.get("variable_name") or "")
            if not domain or not annotation:
                continue
            key = (domain, annotation)
            if key in seen:
                continue
            seen.add(key)
            style_type = (
                candidate.get("annotation_style", {}).get("style_type")
                or classify_annotation(annotation, domain=domain)["style_type"]
            )
            annotations.append(
                {
                    "annotation": annotation,
                    "domain": domain,
                    "source_kind": style_type,
                    "variable_name": candidate.get("variable_name"),
                    "variable_label": candidate.get("variable_label"),
                    "score": candidate.get("score"),
                    "match_type": candidate.get("match_type"),
                    "metadata_check": candidate.get("metadata_check"),
                    "reason": "PDF-safe metadata-valid mapper candidate.",
                }
            )
    return annotations


def supplemental_fallback_annotation(question: str, domains: list[str] | tuple[str, ...] | None) -> dict[str, Any] | None:
    """Map a real collected field to a generated, reviewable SUPPxx QNAM."""
    domain = next(iter(normalize_page_domains(domains)), "")
    if not domain or not should_map_to_supplemental(question):
        return None
    qnam_result = supplemental_qnam_candidate(question, domain=domain)
    qnam = qnam_result["qnam"]
    annotation = f"{qnam} in SUPP{domain}"
    return {
        "annotation": annotation,
        "domain": domain,
        "source_kind": "context",
        "variable_name": qnam,
        "variable_label": "Generated Supplemental Qualifier Name",
        "score": None,
        "match_type": qnam_result["method"],
        "qnam": qnam,
        "qnam_review_flag": qnam_result["review_flag"],
        "metadata_check": {
            "domain": domain,
            "variable_name": qnam,
            "in_sdtmig_domain": False,
            "domain_in_sdtmig": True,
            "supplemental_qualifier": True,
        },
        "reason": "No reliable main-domain SDTM variable; generated a reviewable supplemental qualifier in the Step 1 domain.",
    }


def demographic_context_supplemental_override(
    form_name: str,
    question: str,
    domains: list[str] | tuple[str, ...] | None,
    page_text: str | None = None,
) -> dict[str, Any] | None:
    """Use page context for generic Demographics supplemental fields.

    Some CRFs display a generic label such as "If Other, please specify" under
    a Race codelist. Without nearby field metadata, the generic SUPP fallback
    would create an artificial QNAM. Prefer the established DM race-other QNAM
    when the page context clearly shows the Race block.
    """
    normalized_domains = normalize_page_domains(domains)
    if "DM" not in normalized_domains:
        return None
    text = clean_question_text(question).casefold()
    if not re.fullmatch(r"if\s+other,\s*please\s+specify|other,\s*please\s+specify", text):
        return None
    context = clean_question_text(" ".join([form_name or "", page_text or ""])).casefold()
    if "race" not in context:
        return None
    annotation = "RACEOTH in SUPPDM"
    return {
        "annotation": annotation,
        "domain": "DM",
        "source_kind": "context",
        "variable_name": "RACEOTH",
        "variable_label": "Race Other, Specify",
        "score": 1.0,
        "match_type": "curated_demographics_context_override",
        "qnam": "RACEOTH",
        "qnam_review_flag": "",
        "metadata_check": {
            "domain": "DM",
            "variable_name": "RACEOTH",
            "in_sdtmig_domain": False,
            "domain_in_sdtmig": True,
            "supplemental_qualifier": True,
        },
        "reason": "Generic Other/specify field appears in the Demographics Race block; use reviewed RACEOTH supplemental qualifier.",
    }


METADATA_VARIABLE_ALIASES: dict[str, dict[str, str]] = {
    "LB": {
        "LBDAT": "LBDTC",
        "LBTIM": "LBDTC",
        "LBORRES": "LBORRES",
        "LBTEST": "LBTEST",
        "LBSTAT": "LBSTAT",
        "SER_LBSTR": "LBORRES",
    },
    "AE": {
        "AESTDAT": "AESTDTC",
        "AEENDAT": "AEENDTC",
    },
    "EC": {
        "ECSTDAT": "ECSTDTC",
        "ECENDAT": "ECENDTC",
    },
    "EX": {
        "EXSTDAT": "EXSTDTC",
        "EXENDAT": "EXENDTC",
    },
    "CM": {
        "CMSTDAT": "CMSTDTC",
        "CMENDAT": "CMENDTC",
    },
    "MH": {
        "MHSTDAT": "MHSTDTC",
        "MHENDAT": "MHENDTC",
    },
}


METADATA_SUPPLEMENTAL_ALIASES: dict[str, dict[str, str]] = {
    "MH": {
        "MHGRAD": "MHGRAD",
    },
}


def valid_supplemental_qnam(value: str | None) -> str | None:
    """Return a standards-shaped QNAM from a metadata field/OID, if possible."""
    qnam = clean_question_text(value or "").upper()
    if re.fullmatch(r"[A-Z][A-Z0-9]{0,7}", qnam):
        return qnam
    return None


def metadata_supplemental_override(
    domain: str,
    question: str,
    metadata_field_name: str | None,
) -> dict[str, Any] | None:
    """Map non-SDTMIG metadata fields to SUPPxx when the field is collected."""
    domain = normalize_domain_code(domain)
    field = clean_question_text(metadata_field_name or "").upper()
    qnam = METADATA_SUPPLEMENTAL_ALIASES.get(domain, {}).get(field)
    if not qnam:
        qnam = valid_supplemental_qnam(field)
    if not qnam:
        return None
    if not should_map_to_supplemental(question):
        return None

    annotation = f"{qnam} in SUPP{domain}"
    return {
        "annotation": annotation,
        "domain": domain,
        "source_kind": "context",
        "variable_name": qnam,
        "variable_label": "Supplemental Qualifier Name from CRF metadata field/OID",
        "score": 1.0,
        "match_type": f"metadata_oid_supplemental:{field}->{qnam}",
        "qnam": qnam,
        "qnam_review_flag": "Review supplemental QNAM against sponsor naming conventions.",
        "metadata_check": {
            "domain": domain,
            "variable_name": qnam,
            "in_sdtmig_domain": False,
            "domain_in_sdtmig": True,
            "supplemental_qualifier": True,
        },
        "reason": "CRF annotation-page field name/OID maps to a reviewable supplemental qualifier.",
    }


def metadata_generic_datetime_aliases(domain: str, field: str) -> list[str]:
    """Return domain-valid datetime aliases implied by common CRF metadata OIDs."""
    domain = normalize_domain_code(domain)
    candidates: list[str] = []
    if field == f"{domain}DAT":
        candidates.append(f"{domain}DTC")
    if field == f"{domain}TIM":
        candidates.append(f"{domain}DTC")
    if field == f"{domain}STDAT":
        candidates.append(f"{domain}STDTC")
    if field == f"{domain}ENDAT":
        candidates.append(f"{domain}ENDTC")
    return [
        candidate
        for candidate in candidates
        if validate_variable(domain, candidate).get("in_sdtmig_domain")
    ]


def metadata_variable_override(
    domains: list[str] | tuple[str, ...] | None,
    question: str,
    metadata_field_name: str | None = None,
) -> dict[str, Any] | None:
    """Use CRF annotation-page field names/OIDs to correct weak text-only mappings.

    The override is intentionally narrow: it only returns SDTMIG-valid main-domain
    variables, plus a few label-based LB normal-range corrections.
    """
    normalized_domains = normalize_page_domains(domains)
    field = clean_question_text(metadata_field_name or "").upper()
    text = clean_question_text(question).casefold()

    for domain in normalized_domains:
        alias = METADATA_VARIABLE_ALIASES.get(domain, {}).get(field)
        if alias and validate_variable(domain, alias).get("in_sdtmig_domain"):
            return {
                "annotation": alias,
                "domain": domain,
                "source_kind": "variable",
                "variable_name": alias,
                "variable_label": (variable_metadata(domain, alias) or {}).get("Variable Label"),
                "score": 1.0,
                "match_type": f"metadata_oid_alias:{field}->{alias}",
                "metadata_check": validate_variable(domain, alias),
                "reason": "CRF annotation-page field name/OID maps to an SDTMIG-valid variable.",
            }
        generic_aliases = metadata_generic_datetime_aliases(domain, field)
        if generic_aliases:
            alias = generic_aliases[0]
            return {
                "annotation": alias,
                "domain": domain,
                "source_kind": "variable",
                "variable_name": alias,
                "variable_label": (variable_metadata(domain, alias) or {}).get("Variable Label"),
                "score": 1.0,
                "match_type": f"metadata_oid_datetime_alias:{field}->{alias}",
                "metadata_check": validate_variable(domain, alias),
                "reason": "CRF annotation-page date/time field name/OID maps to an SDTMIG-valid datetime variable.",
            }
        if field and validate_variable(domain, field).get("in_sdtmig_domain"):
            return {
                "annotation": field,
                "domain": domain,
                "source_kind": "variable",
                "variable_name": field,
                "variable_label": (variable_metadata(domain, field) or {}).get("Variable Label"),
                "score": 1.0,
                "match_type": f"metadata_oid_exact:{field}",
                "metadata_check": validate_variable(domain, field),
                "reason": "CRF annotation-page field name/OID is an SDTMIG-valid variable.",
            }
        supplemental = metadata_supplemental_override(domain, question, field)
        if supplemental:
            return supplemental

    if "LB" in normalized_domains and "lower limit of normal" in text:
        variable = "LBORNRLO"
        return {
            "annotation": variable,
            "domain": "LB",
            "source_kind": "variable",
            "variable_name": variable,
            "variable_label": (variable_metadata("LB", variable) or {}).get("Variable Label"),
            "score": 1.0,
            "match_type": "label_override:lower_limit_of_normal",
            "metadata_check": validate_variable("LB", variable),
            "reason": "Visible LB label indicates original normal-range lower limit.",
        }
    if "LB" in normalized_domains and "upper limit of normal" in text:
        variable = "LBORNRHI"
        return {
            "annotation": variable,
            "domain": "LB",
            "source_kind": "variable",
            "variable_name": variable,
            "variable_label": (variable_metadata("LB", variable) or {}).get("Variable Label"),
            "score": 1.0,
            "match_type": "label_override:upper_limit_of_normal",
            "metadata_check": validate_variable("LB", variable),
            "reason": "Visible LB label indicates original normal-range upper limit.",
        }
    return None


GENERIC_DOMAIN_DATE_VARIABLES: dict[str, dict[str, str]] = {
    "AE": {"start": "AESTDTC", "end": "AEENDTC", "generic": "AESTDTC"},
    "CE": {"start": "CESTDTC", "end": "CEENDTC", "generic": "CESTDTC"},
    "CM": {"start": "CMSTDTC", "end": "CMENDTC", "generic": "CMSTDTC"},
    "EG": {"generic": "EGDTC"},
    "FA": {"generic": "FADTC"},
    "IS": {"generic": "ISDTC"},
    "LB": {"generic": "LBDTC"},
    "MH": {"start": "MHSTDTC", "end": "MHENDTC", "generic": "MHSTDTC"},
    "OE": {"generic": "OEDTC"},
    "PC": {"generic": "PCDTC"},
    "PE": {"generic": "PEDTC"},
    "PR": {"start": "PRSTDTC", "end": "PRENDTC", "generic": "PRSTDTC"},
    "QS": {"generic": "QSDTC"},
    "VS": {"generic": "VSDTC"},
}


def generic_domain_datetime_annotation(
    question: str,
    domains: list[str] | tuple[str, ...] | None,
) -> dict[str, Any] | None:
    """Map broad date labels to the approved domain's main datetime variable.

    This catches labels such as "Date (DD/MMM/YYYY)" on QS pages and
    "Date of ultrasound" on FA pages before non-standard EDC OIDs fall to SUPP.
    """
    text = clean_question_text(question)
    lowered = text.casefold()
    if not re.search(r"\b(date|dtc|datetime|time)\b", lowered):
        return None
    if re.search(r"\b(protocol version|birth|consent|randomi[sz]ation)\b", lowered):
        return None

    date_kind = "generic"
    if re.search(r"\b(start|begin|first)\b", lowered):
        date_kind = "start"
    elif re.search(r"\b(stop|end|last)\b", lowered):
        date_kind = "end"

    for domain in normalize_page_domains(domains):
        variable_by_kind = GENERIC_DOMAIN_DATE_VARIABLES.get(domain, {})
        variable = variable_by_kind.get(date_kind) or variable_by_kind.get("generic")
        if not variable:
            continue
        validation = validate_variable(domain, variable)
        if not validation.get("in_sdtmig_domain"):
            continue
        return {
            "annotation": variable,
            "domain": domain,
            "source_kind": "variable",
            "variable_name": variable,
            "variable_label": (variable_metadata(domain, variable) or {}).get("Variable Label"),
            "score": 1.0,
            "match_type": f"generic_domain_datetime:{date_kind}",
            "metadata_check": validation,
            "reason": "Generic date label maps to the approved domain's main datetime variable before SUPP fallback.",
        }
    return None


def protocol_version_annotation(question: str, domains: list[str] | tuple[str, ...] | None) -> dict[str, Any] | None:
    """Map collected protocol-version fields to SUPP before DS protocol milestone rules."""
    text = clean_question_text(question)
    if not (
        re.fullmatch(r"protocol\s+version(?:\s+at\b.*)?", text, flags=re.I)
        or re.search(r"\bversion\b.*\bprotocol\b", text, flags=re.I)
        or re.search(r"\bprotocol\b.*\bversion\b", text, flags=re.I)
    ):
        return None
    return supplemental_fallback_annotation(text, domains)


def annotation_domains_from_items(items: list[dict[str, Any]]) -> list[str]:
    """Return page annotation domains from all PDF-safe candidates, preserving order."""
    domains: list[str] = []
    for item in items:
        for annotation in item.get("annotations", []):
            domain = normalize_domain_code(annotation.get("domain"))
            if domain and domain not in domains:
                domains.append(domain)
    return domains


def qc_domain_mapping(mapping: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    best = mapping.get("best_mapping")
    if not best:
        return ["No domain candidate found for form/title."]
    for label in best.get("domain_labels", []):
        if not label["in_sdtmig"]:
            issues.append(f"{label['domain']} needs domain-label confirmation.")
        if label["annotation"].endswith(f"({label['domain']})"):
            issues.append(f"{label['domain']} has fallback label; correct before delivery.")
    return issues


def expand_domains_with_strong_page_content(
    domains: list[str] | tuple[str, ...] | None,
    page_text: str | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Append very high-confidence page-content domains to base/approved domains."""
    expanded_domains = normalize_page_domains(domains)
    expansions = domain_mapping_guide.strong_content_domain_expansions(
        page_text,
        "; ".join(expanded_domains),
    )
    for expansion in expansions:
        domain = normalize_domain_code(expansion.get("domain"))
        if domain and domain not in expanded_domains:
            expanded_domains.append(domain)
    return expanded_domains, expansions


def map_crf_item(
    form_name: str,
    question: str,
    approved_domains: list[str] | None = None,
    min_variable_score: float = 0.82,
    page_text: str | None = None,
    metadata_field_name: str | None = None,
) -> dict[str, Any]:
    """
    Map one CRF item.

    Use approved_domains after Step 1 review. If not provided, the mapper will
    infer domains from the form/page title first.
    """
    cleaned_question = clean_question_text(question)
    if is_response_choice_label(cleaned_question):
        return {
            "form_name": form_name,
            "question": cleaned_question,
            "domain_mapping": {},
            "variable_results": [],
            "recommended": {
                "domain": None,
                "domain_label": None,
                "variable_name": None,
                "variable_label": None,
                "score": None,
            },
            "annotations": [],
            "qc_issues": ["Skipped displayed response choice; annotate the parent CRF question instead."],
            "skipped": True,
            "skip_reason": "response_choice",
        }

    if approved_domains:
        domains, domain_expansions = expand_domains_with_strong_page_content(
            approved_domains,
            page_text=page_text or question,
        )
        expansion_rationale = ""
        if domain_expansions:
            expansion_rationale = "Strong page-content evidence appended secondary domain(s): " + "; ".join(
                f"{expansion['domain']} from {', '.join(expansion.get('evidence', []))}"
                for expansion in domain_expansions
            )
        domain_mapping = {
            "form_name": form_name,
            "best_mapping": {
                "domains": domains,
                "domain_labels": [domain_label(domain) for domain in domains],
                "match_type": "approved_domain_with_strong_content_expansion"
                if domain_expansions
                else "approved_domain",
                "confidence": 1.0,
                "multiple_domain_rationale": expansion_rationale,
            },
            "all_candidates": [],
            "instruction_step": "Step 1 domain mapping already approved",
        }
    else:
        domain_mapping = map_form_to_domains(form_name, page_text=page_text)
        best = domain_mapping.get("best_mapping") or {}
        domains = list(best.get("domains", []))

    protocol_annotation = protocol_version_annotation(cleaned_question, domains)
    if protocol_annotation:
        recommended_domain = protocol_annotation["domain"]
        return {
            "form_name": form_name,
            "question": cleaned_question,
            "domain_mapping": domain_mapping,
            "variable_results": [],
            "recommended": {
                "domain": recommended_domain,
                "domain_label": domain_label(recommended_domain),
                "variable_name": protocol_annotation.get("variable_name"),
                "variable_label": protocol_annotation.get("variable_label"),
                "score": protocol_annotation.get("score"),
            },
            "annotations": [protocol_annotation],
            "qc_issues": qc_domain_mapping(domain_mapping)
            + [protocol_annotation.get("qnam_review_flag", "")],
        }

    variable_results = [
        map_question_to_variables(
            domain=domain,
            question=question,
            min_score=min_variable_score,
        )
        for domain in domains
    ]
    best_variable = next(
        (result["best_mapping"] for result in variable_results if result["best_mapping"]),
        None,
    )
    annotations = annotations_from_variable_results(variable_results)
    lowered_form = clean_question_text(form_name).casefold()
    lowered_question = cleaned_question.casefold()
    if is_informed_consent_date_field(form_name, cleaned_question):
        annotations = informed_consent_date_annotations(
            include_demographics_reference=is_primary_informed_consent_date_field(
                form_name,
                cleaned_question,
            )
        )
    elif prior_infections_annotations := prior_infections_mh_direct_annotations(
        form_name,
        cleaned_question,
        domains,
    ):
        annotations = prior_infections_annotations
    else:
        lb_pregnancy_annotations, curated_best_variable = lb_pregnancy_test_annotations(
            form_name,
            cleaned_question,
            domains,
            page_text=page_text,
        )
        if lb_pregnancy_annotations:
            annotations = lb_pregnancy_annotations
            if curated_best_variable:
                best_variable = curated_best_variable
        else:
            rp_pregnancy_annotations, curated_best_variable = rp_pregnancy_test_annotations(
                form_name,
                cleaned_question,
                domains,
                page_text=page_text,
            )
            if rp_pregnancy_annotations:
                annotations = rp_pregnancy_annotations
                if curated_best_variable:
                    best_variable = curated_best_variable
            else:
                findings_domain = None
                if best_variable and best_variable.get("domain") in FINDINGS_DOMAINS:
                    findings_domain = best_variable["domain"]
                else:
                    findings_domain = next(
                        (
                            normalize_domain_code(domain)
                            for domain in domains
                            if normalize_domain_code(domain) in FINDINGS_DOMAINS
                        ),
                        None,
                    )
                findings_annotations = []
                if findings_domain:
                    findings_annotations = findings_testcd_annotations(
                        domain=findings_domain,
                        question=question,
                        include_result_variables=True,
                    )
                if findings_annotations:
                    annotations = findings_annotations
    if not annotations:
        datetime_annotation = generic_domain_datetime_annotation(cleaned_question, domains)
        if datetime_annotation:
            best_variable = datetime_annotation
            annotations = [datetime_annotation]
    if not annotations:
        supplemental_annotation = supplemental_fallback_annotation(cleaned_question, domains)
        if supplemental_annotation:
            annotations = [supplemental_annotation]
    demographics_override_annotation = demographic_context_supplemental_override(
        form_name,
        cleaned_question,
        domains,
        page_text=page_text,
    )
    if demographics_override_annotation:
        best_variable = demographics_override_annotation
        annotations = [demographics_override_annotation]
    override_annotation = metadata_variable_override(
        domains,
        cleaned_question,
        metadata_field_name=metadata_field_name,
    )
    if override_annotation:
        override_is_supplemental = override_annotation.get("metadata_check", {}).get("supplemental_qualifier")
        if not (annotations and override_is_supplemental):
            best_variable = override_annotation
            annotations = [override_annotation]
    annotations = filter_contextually_invalid_annotations(form_name, cleaned_question, annotations)
    recommended_domain = best_variable.get("domain") if best_variable else (domains[0] if domains else None)
    recommended_label = domain_label(recommended_domain) if recommended_domain else None
    recommended_variable = best_variable.get("variable_name") if best_variable else (
        annotations[0].get("variable_name") if annotations else None
    )
    recommended_variable_label = best_variable.get("variable_label") if best_variable else (
        annotations[0].get("variable_label") if annotations else None
    )
    recommended_score = best_variable.get("score") if best_variable else (
        annotations[0].get("score") if annotations else None
    )
    return {
        "form_name": form_name,
        "question": cleaned_question,
        "domain_mapping": domain_mapping,
        "variable_results": variable_results,
        "recommended": {
            "domain": recommended_domain,
            "domain_label": recommended_label,
            "variable_name": recommended_variable,
            "variable_label": recommended_variable_label,
            "score": recommended_score,
        },
        "annotations": annotations,
        "qc_issues": qc_domain_mapping(domain_mapping)
        + [
            issue
            for result in variable_results
            for issue in result.get("issues", [])
            if issue != "No high-confidence metadata-valid variable candidate found."
        ],
    }


def map_crf_page(
    form_name: str,
    questions: list[str],
    approved_domains: list[str] | None = None,
    min_variable_score: float = 0.82,
    page_text: str | None = None,
    metadata_field_names: dict[str, str] | list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Map all question/label strings for one CRF page/form."""
    filtered_questions = filter_response_choice_labels(questions)
    inferred_page_text = page_text or " ".join(filtered_questions)
    items = []
    for index, question in enumerate(filtered_questions):
        if is_noise_text(question):
            continue
        metadata_field_name = None
        if isinstance(metadata_field_names, dict):
            metadata_field_name = (
                metadata_field_names.get(question)
                or metadata_field_names.get(clean_question_text(question))
            )
        elif metadata_field_names is not None and index < len(metadata_field_names):
            metadata_field_name = metadata_field_names[index]
        items.append(
            map_crf_item(
                form_name=form_name,
                question=question,
                approved_domains=approved_domains,
                min_variable_score=min_variable_score,
                page_text=inferred_page_text,
                metadata_field_name=metadata_field_name,
            )
        )
    approved_or_inferred_domains = (
        expand_domains_with_strong_page_content(
            approved_domains,
            page_text=inferred_page_text,
        )[0]
        if approved_domains
        else (
            items[0]["domain_mapping"]["best_mapping"].get("domains", [])
            if items and items[0]["domain_mapping"].get("best_mapping")
            else []
        )
    )
    annotation_domains = annotation_domains_from_items(items)
    display_domains = display_domains_for_annotations(
        approved_or_inferred_domains,
        annotation_domains,
    )
    has_mappable_content = any(item.get("recommended", {}).get("variable_name") for item in items)
    meaningful_page_domain_qc = {
        "ok": bool(not has_mappable_content or (approved_or_inferred_domains and display_domains)),
        "approved_or_inferred_domains": approved_or_inferred_domains,
        "display_domains": display_domains,
        "annotation_domains": annotation_domains,
        "has_mappable_content": has_mappable_content,
        "issues": [],
    }
    if has_mappable_content and not approved_or_inferred_domains:
        meaningful_page_domain_qc["issues"].append("Meaningful CRF content page has no supported Domain.")
    if has_mappable_content and not display_domains:
        meaningful_page_domain_qc["issues"].append("Meaningful CRF content page has no visible annotation Domain.")
    return {
        "form_name": form_name,
        "approved_domains": approved_domains,
        "items": items,
        "approved_or_inferred_domains": approved_or_inferred_domains,
        "pdf_annotation_domains": annotation_domains,
        "display_domains": display_domains,
        "domain_color_plan": build_domain_color_plan(display_domains),
        "display_domain_qc": qc_display_domain_plan(
            approved_or_inferred_domains,
            display_domains,
            annotation_domains,
        ),
        "meaningful_page_domain_qc": meaningful_page_domain_qc,
    }


def build_domain_color_plan(domains: list[str]) -> list[dict[str, Any]]:
    plan = []
    for index, domain in enumerate(domains):
        color = PAGE_DOMAIN_COLORS[min(index, len(PAGE_DOMAIN_COLORS) - 1)]
        plan.append(
            {
                "domain": normalize_domain_code(domain),
                "domain_label": domain_label(domain),
                "color": color,
                "domain_annotation_instruction": annotation_instruction(
                    domain_label(domain)["annotation"],
                    domain=domain,
                    domain_order_index=index,
                    source_kind="domain",
                ),
            }
        )
    return plan


def summarize_mapping(item: dict[str, Any]) -> str:
    """Compact human-readable summary for quick review."""
    recommended = item.get("recommended", {})
    domain = recommended.get("domain") or "UNMAPPED"
    variable = recommended.get("variable_name") or "UNMAPPED"
    score = recommended.get("score")
    score_text = f" score={score}" if score is not None else ""
    return f"{item.get('question', '')} -> {domain}.{variable}{score_text}"


if __name__ == "__main__":
    examples = [
        ("Demographics", "Date informed consent signed", ["DM", "DS"]),
        ("Adverse Events", "Dose Reduced", ["AE"]),
        ("Concomitant Medications", "Medication Name", ["CM"]),
        ("12-Lead ECG", "Was ECG performed?", ["EG"]),
    ]
    for form_name, question, approved_domains in examples:
        result = map_crf_item(
            form_name=form_name,
            question=question,
            approved_domains=approved_domains,
        )
        print(summarize_mapping(result))
