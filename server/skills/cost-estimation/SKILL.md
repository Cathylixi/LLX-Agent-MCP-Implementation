---
name: cost-estimation
description: Build a clinical study's cost/effort estimate from its protocol. Given only the protocol, directly produce an itemized SDTM + ADaM effort table (in hours). Use when the user asks for a cost estimate, effort estimate, bid, or quote for a clinical data project.
---

## What this skill does
The **only required input is the study protocol.** Given the protocol, directly
produce the cost estimate — no need to ask the user anything else. By default the
estimate covers the two protocol-driven deliverables, **SDTM** and **ADaM**: work
out how many domains are needed and how complex each is, then apply the fixed
effort tables and total it up.

**Input:** the study **protocol** (with its Schedule of Assessments). Optionally,
the study **endpoints** and an **hourly rate** (to turn hours into money).

**Output:** a 7-column effort table — **Task | Unit | Cost Per Hour | Hours Per
Unit | Cost Per Unit | Estimated Cost | Notes** — with an SDTM section and an ADaM
section, a Subtotal for each, and a Grand Total. Values are in hours (Cost Per Hour
= 1); if an hourly rate is given, multiply to get money.

If no protocol / Schedule of Assessments is provided, STOP and ask for the
protocol — do not invent procedures.

> Only produce the extra project sections in the last section ("Optional extra
> projects") if the user explicitly asks for them. Otherwise just do SDTM + ADaM.

---

## Step 1 — Extract the list of procedures (from the protocol)
From the protocol's **Schedule of Assessments**, read the **first column** of each
row (the procedure name). Filters:
- **Skip the header row** — a first cell containing procedure / assessment /
  activity / visit / evaluation / test AND shorter than 50 characters.
- **Keep** a cell only if: length 4–149; not a pure number; not a single letter
  followed by digits (e.g. "A1"); not "-"; not "N/A".
- **Drop** timepoint/visit labels (Day N Pre/Post-dose, Visit N, Week N, Month N,
  Screening, Baseline, Follow-up, End of Study, EOS, Cycle N).
- **Drop** overly descriptive text (>100 chars containing ":").
- **De-duplicate.**

## Step 2 — Map procedures to SDTM domains + rate complexity
Map every procedure to the most appropriate SDTM domain(s) per CDISC SDTMIG v3.4
(never skip a procedure). Common domains: AE, CM, DM, EG, EX, LB, MB, PE, QS, SC,
VS, DA, DS, MH, SU, FA, IE.

Rate complexity:
- **High**: complex lab tests, multi-parameter biomarkers, complex questionnaires,
  special medical examinations.
- **Medium**: standard physical exams, basic vital signs, routine labs, standard
  drug administration.

Normalize at the domain level:
1. **SV is always High** (move it to High, or add it as High if missing).
2. **High overrides Medium** (a domain in both goes to High only; the sets are
   mutually exclusive).
3. **Always add these 6 trial-design domains as Medium** if not present: TA, TE,
   TI, TV, TS, SE.
4. Produce **sdtmHighCount**, **sdtmMediumCount**, **sdtmTotalDomains** (= unique domains).

## Step 3 — Map SDTM domains to ADaM + rate complexity
From the unique SDTM domains, decide the ADaM datasets needed per CDISC ADaM v1.2.
**ADSL is mandatory.** Use endpoints if given: primary → efficacy ADaM (ADTTE,
ADRS); safety → ADAE, ADCM. Common ADaM: ADAE, ADCM, ADEG, ADLB, ADQS, ADVS (plus
ADSL, ADTTE, ADRS).

Rate complexity:
- **High**: needs multiple SDTM datasets; efficacy-related ADaM.
- **Medium**: needs only a single SDTM merged with ADSL; safety-related ADaM.

Normalize: **ADSL is always High** (add if missing); **High overrides Medium**.
Produce **adamHighCount**, **adamMediumCount**, **adamTotalDomains**.

## Step 4 — Build the effort table
Use these 7 columns for every row:

| Task | Unit | Cost Per Hour | Hours Per Unit | Cost Per Unit | Estimated Cost | Notes |

For every detail row:
- **Cost Per Hour** = 1 (unless the user gave a rate — then use it).
- **Hours Per Unit** = the fixed value from the tables below.
- **Cost Per Unit** = Cost Per Hour × Hours Per Unit.
- **Estimated Cost** = Unit × Cost Per Hour × Hours Per Unit (round to 2 decimals; a
  blank Unit counts as 0).
Each section ends with a **Subtotal** = sum of its rows' Estimated Cost.

### SDTM section
| Task | Unit | Hours Per Unit |
|---|---|---|
| SDTM Annotated CRFs (aCRF) | 1 | 32 |
| SDTM Dataset Specs (High Complexity) | sdtmHighCount | 3 |
| SDTM Dataset Specs (Medium Complexity) | sdtmMediumCount | 2 |
| SDTM Production and Validation: Programs and Datasets (High Complexity) | sdtmHighCount | 16 |
| SDTM Production and Validation: Programs and Datasets (Medium Complexity) | sdtmMediumCount | 10 |
| SDTM Pinnacle 21 Report Creation and Review | 2 | 6 |
| SDTM Reviewer's Guide | 1 | 32 |
| SDTM Define.xml | 1 | 32 |
| SDTM Dataset File xpt Conversion and Review | sdtmTotalDomains | 0.2 |

Notes: High domain names on the Specs (High) row (joined by "/"), Medium names on
Specs (Medium), all domain names on the xpt row.

### ADaM section
| Task | Unit | Hours Per Unit |
|---|---|---|
| ADaM Dataset Specs (High Complexity) | adamHighCount | 4 |
| ADaM Dataset Specs (Medium Complexity) | adamMediumCount | 3 |
| ADaM Production and Validation: Programs and Datasets (High Complexity) | adamHighCount | 20 |
| ADaM Production and Validation: Programs and Datasets (Medium Complexity) | adamMediumCount | 12 |
| ADaM Pinnacle 21 Report Creation and Review | 2 | 8 |
| ADaM Reviewer's Guide | 1 | 40 |
| ADaM Define.xml | 1 | 40 |
| ADaM Dataset Program xpt Conversion and Review | adamTotalDomains | 0.3 |
| ADaM Program txt Conversion and Review | adamTotalDomains | 0.2 |

Notes: High domain names on Specs (High), Medium names on Specs (Medium), all ADaM
domain names on the xpt and txt rows.

## Step 5 — Grand Total and presentation
- **Grand Total** = SDTM Subtotal + ADaM Subtotal (plus any optional sections).
- Present the whole 7-column table with both sections, their subtotals, and the
  grand total.
- Values are in **hours** (Cost Per Hour = 1). If the user gave an hourly rate,
  multiply to show dollars.

---

## Optional extra projects (only if the user explicitly asks)
The protocol does not drive these — include a section only when the user requests
it. Each ends with its own Subtotal (added into the Grand Total).

- **Statistical Analysis Plan and Shells Development** — line items (Hours Per Unit,
  Unit 1 each): SAP Draft 1 = 40, SAP Draft 2 = 30, SAP Final = 20, Analysis Shells
  Development = 60, Mock Tables/Listings/Figures = 40.
- **SDTM Data Transfer (N times)** — Production and Validation: first 2 times (Unit
  2 × 25h) + last (N−2) times (Unit N−2 × 12.5h).
- **ADaM Data Transfer (N times)** — first 2 times (Unit 2 × 15h) + last (N−2) times
  (Unit N−2 × 7.5h).
- **Tables, Figures, and Listings Development / Interim Analysis / Final Analysis /
  DSUR First Time / DSMB(IDMC) First Time / DSUR Rerun (N times) / DSMB Rerun (N
  times)** — no predefined line items; add a titled section with a Subtotal to be
  filled in manually.
- **Fixed trailing sections** (add only if the user wants the full quote layout):
  License Fees, Adhoc Analysis, Project Management/Administration (12 Months) — each
  a titled section with a manual Subtotal.
