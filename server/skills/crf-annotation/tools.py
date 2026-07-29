"""Code tools for the `crf-annotation` skill — run on the server.

Thin @mcp.tool() wrappers around crf_annotation_mapper.py (which in turn uses
domain_mapping_guide.py, crf_variable_question_patterns.py, and
sdtmig_metadata.py — all in this same folder). None of these files touch PDF
files; they only decide Domain/Variable/box-placement from plain text and
coordinate numbers. Extracting text from the CRF PDF and physically drawing
the annotations both happen locally on the caller's side (see SKILL.md) - this
server only ever returns the *decision*, never the PDF itself.
"""

from __future__ import annotations

from typing import Any

from app import mcp

import crf_annotation_mapper as mapper


@mcp.tool()
def map_form_to_domains(
    form_name: str,
    concept_min_confidence: float = 0.55,
    guide_min_confidence: float = 0.35,
    page_text: str | None = None,
) -> dict[str, Any]:
    """Step 1: map a CRF form/page title to candidate SDTM Domain(s).

    Call this alone first and show the candidates to the user for approval
    before mapping any Variables on that page.
    """
    return mapper.map_form_to_domains(
        form_name,
        concept_min_confidence=concept_min_confidence,
        guide_min_confidence=guide_min_confidence,
        page_text=page_text,
    )


@mcp.tool()
def map_crf_item(
    form_name: str,
    question: str,
    approved_domains: list[str] | None = None,
    min_variable_score: float = 0.82,
    page_text: str | None = None,
    metadata_field_name: str | None = None,
) -> dict[str, Any]:
    """Map one CRF question/label to its SDTM Domain + Variable.

    Pass approved_domains after Step 1 review/approval. If omitted, the mapper
    infers the domain itself instead of waiting for approval - only do this
    when the caller explicitly does not need the Step 1 checkpoint.
    """
    return mapper.map_crf_item(
        form_name,
        question,
        approved_domains=approved_domains,
        min_variable_score=min_variable_score,
        page_text=page_text,
        metadata_field_name=metadata_field_name,
    )


@mcp.tool()
def map_crf_page(
    form_name: str,
    questions: list[str],
    approved_domains: list[str] | None = None,
    min_variable_score: float = 0.82,
    page_text: str | None = None,
    metadata_field_names: dict[str, str] | list[str] | None = None,
) -> dict[str, Any]:
    """Map every question/label on one CRF page/form.

    Pass approved_domains after Step 1 review/approval (same rule as
    map_crf_item). Returns items, display_domains, domain_color_plan, and
    display_domain_qc - see SKILL.md Section 3.3 for the field meanings.
    """
    return mapper.map_crf_page(
        form_name,
        questions,
        approved_domains=approved_domains,
        min_variable_score=min_variable_score,
        page_text=page_text,
        metadata_field_names=metadata_field_names,
    )


@mcp.tool()
def map_question_to_variables(
    domain: str,
    question: str,
    min_score: float = 0.82,
    metadata_whitelist: bool = True,
    max_candidates: int = 10,
) -> dict[str, Any]:
    """Step 2: map one CRF question to Variable candidates within an approved Domain.

    Stays inside the given domain - never forces a cross-domain variable.
    Lower min_score (e.g. 0.70) to surface weaker candidates for manual review
    when nothing scores above the default threshold.
    """
    return mapper.map_question_to_variables(
        domain,
        question,
        min_score=min_score,
        metadata_whitelist=metadata_whitelist,
        max_candidates=max_candidates,
    )


@mcp.tool()
def domain_label(domain: str) -> dict[str, Any]:
    """Return the `DOMAIN (Dataset Label)` text for a Domain, from SDTMIG v3.4 metadata."""
    return mapper.domain_label(domain)


@mcp.tool()
def display_domains_for_annotations(
    approved_domains: list[str] | None,
    annotation_domains: list[str] | None,
    include_unapproved_annotation_domains: bool = True,
) -> list[str]:
    """Domain-label retention rule: Step 1 approved domains must stay visible
    even if Step 2 didn't map a Variable into every one of them."""
    return mapper.display_domains_for_annotations(
        approved_domains,
        annotation_domains,
        include_unapproved_annotation_domains=include_unapproved_annotation_domains,
    )


@mcp.tool()
def findings_testcd_annotations(
    domain: str,
    question: str,
    include_result_variables: bool = False,
) -> list[dict[str, Any]]:
    """Findings-domain --TESTCD auto-inference (VS, EG, LB, TR, TU, RS, CV).

    E.g. "Systolic Blood Pressure" -> VSTESTCD = SYSBP (context). Set
    include_result_variables=True to also get the result variable (e.g. VSORRES).
    """
    return mapper.findings_testcd_annotations(
        domain,
        question,
        include_result_variables=include_result_variables,
    )


@mcp.tool()
def informed_consent_date_annotations(
    include_demographics_reference: bool = True,
    consent_term: str = "INFORMED CONSENT",
) -> list[dict[str, Any]]:
    """Standard DS + DM annotations for an informed-consent date field."""
    return mapper.informed_consent_date_annotations(
        include_demographics_reference=include_demographics_reference,
        consent_term=consent_term,
    )


@mcp.tool()
def vital_sign_edc_annotations(
    edc_variable_name: str,
    include_units: bool = True,
) -> list[dict[str, Any]]:
    """Map a sponsor-specific vital-sign EDC field name (e.g. VSWT, BMI, VSTIM1)
    to SDTM VS context + result annotations."""
    return mapper.vital_sign_edc_annotations(
        edc_variable_name,
        include_units=include_units,
    )


@mcp.tool()
def estimate_annotation_box_size(
    annotation: str,
    style_type: str,
    font_size: float | None = None,
) -> dict[str, Any]:
    """Estimate a FreeText annotation box size that avoids clipped text.

    style_type is one of the annotation types in SKILL.md Section 6 (e.g.
    "domain", "variable", "context"). Check clipped_risk in the result before
    reusing a fixed box size.
    """
    return mapper.estimate_annotation_box_size(annotation, style_type, font_size=font_size)


@mcp.tool()
def recommend_domain_box(
    annotation: str,
    domain: str,
    page_size: list[float],
    pdf_text_bboxes: list[list[float]] | None = None,
    existing_annotation_bboxes: list[list[float]] | None = None,
    domain_order_index: int = 0,
    page_domains: list[str] | None = None,
) -> dict[str, Any]:
    """Recommend where to place a Domain-label box in the page's top blank band.

    page_size, pdf_text_bboxes, and existing_annotation_bboxes are plain
    numbers extracted locally from the PDF (never the PDF file itself) -
    (width, height) and lists of [x0, y0, x1, y1] boxes.
    """
    return mapper.recommend_domain_box(
        annotation,
        domain,
        tuple(page_size),
        pdf_text_bboxes=pdf_text_bboxes,
        existing_annotation_bboxes=existing_annotation_bboxes,
        domain_order_index=domain_order_index,
        page_domains=page_domains,
    )


@mcp.tool()
def recommend_annotation_box(
    annotation: str,
    domain: str,
    page_size: list[float],
    source_bbox: list[float] | None = None,
    pdf_text_bboxes: list[list[float]] | None = None,
    existing_annotation_bboxes: list[list[float]] | None = None,
    domain_order_index: int = 0,
    source_kind: str | None = None,
    page_domains: list[str] | None = None,
) -> dict[str, Any]:
    """Recommend a non-overlapping FreeText box for a Variable/context annotation.

    Coordinates are PDF points, origin top-left, x right, y down - convert
    first if extracted with a bottom-left-origin library (e.g. PyMuPDF's
    default) before calling this.
    """
    return mapper.recommend_annotation_box(
        annotation,
        domain,
        tuple(page_size),
        source_bbox=source_bbox,
        pdf_text_bboxes=pdf_text_bboxes,
        existing_annotation_bboxes=existing_annotation_bboxes,
        domain_order_index=domain_order_index,
        source_kind=source_kind,
        page_domains=page_domains,
    )
