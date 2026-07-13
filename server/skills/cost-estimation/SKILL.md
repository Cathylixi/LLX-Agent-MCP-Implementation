---
name: cost-estimation
description: Build a clinical study's cost/effort estimate — an itemized table (in hours) for the selected deliverables (SDTM, ADaM, SAP, TFL, analyses, DSUR/DSMB, etc.). Use when the user asks for a cost estimate, effort estimate, bid, or quote for a clinical data project.
---

## What this skill does
Produce a full **cost-estimate table** for a clinical study. The estimator first
picks which deliverables (projects) the study needs; for the SDTM and ADaM
deliverables the effort is derived automatically from the protocol (by counting
domains and their complexity); the other deliverables are listed with their known
effort rates or left for manual entry. Everything is totaled into subtotals and a
grand total.

**Input:**
1. **Which projects to include** — the estimator selects from the 10 projects in
   Step 1 below (plus a count for any Data-Transfer or Rerun items).
2. The study **protocol** (its Schedule of Assessments) — needed only if SDTM
   and/or ADaM is selected, to work out the domains.
3. (Optional) study **endpoints**, and an **hourly rate** (to turn hours into money).

**Output:** a 7-column cost table — **Task | Unit | Cost Per Hour | Hours Per Unit
| Cost Per Unit | Estimated Cost | Notes** — with one section per selected project,
a Subtotal per section, three fixed trailing sections, and a Grand Total. Values
are in hours (Cost Per Hour defaults to 1); if an hourly rate is given, multiply to
get money.

---

## Step 1 — Choose the projects to include
Ask the estimator which of these 10 deliverables the study needs (any combination):

1. **Statistical Analysis Plan and Shells Development** (2 Drafts and 1 Final)
2. **SDTM Datasets Production and Validation** — also ask **Data Transfer Times** (a number, optional)
3. **ADaM Datasets Production and Validation** — also ask **Data Transfer Times** (a number, optional)
4. **Tables, Figures, and Listings Development**
5. **Interim Analysis**
6. **Final Analysis**
7. **DSUR First Time**
8. **DSUR Rerun** — also ask **Rerun Times** (a number)
9. **DSMB/IDMC First Time**
10. **DSMB Rerun** — also ask **Rerun Times** (a number)

Only build sections for the projects that were selected. Regardless of selection,
always add the three fixed trailing sections in Step 5.

---

## Step 2 — (only if SDTM is selected) Determine SDTM domains and complexity
### 2a. Extract procedures
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

### 2b. Map to SDTM domains + rate complexity
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
4. Produce **sdtmHighCount**, **sdtmMediumCount**, **sdtmTotalDomains** (= unique
   domains).

---

## Step 3 — (only if ADaM is selected) Determine ADaM domains and complexity
From the unique SDTM domains, decide the ADaM datasets needed per CDISC ADaM v1.2.
**ADSL is mandatory.** Use endpoints if given: primary → efficacy ADaM (ADTTE,
ADRS); safety → ADAE, ADCM. Common ADaM: ADAE, ADCM, ADEG, ADLB, ADQS, ADVS (plus
ADSL, ADTTE, ADRS).

Rate complexity:
- **High**: needs multiple SDTM datasets; efficacy-related ADaM.
- **Medium**: needs only a single SDTM merged with ADSL; safety-related ADaM.

Normalize: **ADSL is always High** (add if missing); **High overrides Medium**.
Produce **adamHighCount**, **adamMediumCount**, **adamTotalDomains**.

---

## Step 4 — Build the cost table (one section per selected project)
Use these 7 columns for every row:

| Task | Unit | Cost Per Hour | Hours Per Unit | Cost Per Unit | Estimated Cost | Notes |

Rules for every detail row:
- **Cost Per Hour** = 1 (unless the user gave a rate — then use it).
- **Hours Per Unit** = the fixed value from the tables below.
- **Cost Per Unit** = Cost Per Hour × Hours Per Unit.
- **Estimated Cost** = Unit × Cost Per Hour × Hours Per Unit.
- Round money to 2 decimals; a blank Unit counts as 0.
Each project section ends with a **Subtotal** = sum of its rows' Estimated Cost.

### If "SDTM Datasets Production and Validation" is selected
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

Notes column: put the High domain names on the Specs (High) row (joined by "/"),
the Medium domain names on the Specs (Medium) row, and all domain names on the xpt
row.

**If Data Transfer Times = N (N > 0)**, add a "SDTM Dataset Transfer (N times)"
sub-block with its own Subtotal:
| Task | Unit | Hours Per Unit |
|---|---|---|
| Production and Validation, the first 2 times | 2 | 25 |
| Production and Validation, the last (N−2) times | N−2 | 12.5 |

### If "ADaM Datasets Production and Validation" is selected
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

Notes column: High domain names on Specs (High), Medium names on Specs (Medium),
all ADaM domain names on the xpt and txt rows.

**If Data Transfer Times = N (N > 0)**, add an "ADAM Dataset Transfer (N times)"
sub-block with its own Subtotal:
| Task | Unit | Hours Per Unit |
|---|---|---|
| Production and Validation, the first 2 times | 2 | 15 |
| Production and Validation, the last (N−2) times | N−2 | 7.5 |

### If "Statistical Analysis Plan and Shells Development" is selected
| Task | Unit | Hours Per Unit |
|---|---|---|
| Statistical Analysis Plan Draft 1 | 1 | 40 |
| Statistical Analysis Plan Draft 2 | 1 | 30 |
| Statistical Analysis Plan Final | 1 | 20 |
| Analysis Shells Development | 1 | 60 |
| Mock Tables, Listings, and Figures | 1 | 40 |

### If any of these are selected: TFL, Interim Analysis, Final Analysis, DSUR First Time, DSMB/IDMC First Time
These have no predefined line items in the tool. Add just a **bold section title**
(the project name) and an empty **Subtotal** row — the estimator fills in the
line items and units manually.

### If "DSUR Rerun" or "DSMB Rerun" is selected (with Rerun Times = N)
Add a bold title "DSUR Rerun (N times)" / "DSMB Rerun (N times)" and an empty
**Subtotal** row (line items entered manually).

---

## Step 5 — Always add three fixed trailing sections
Whatever was selected, always append these three, each as a bold title + an empty
**Subtotal** row (filled manually):
1. **License Fees**
2. **Adhoc Analysis**
3. **Project Management/Administration (12 Months)**

## Step 6 — Grand Total and presentation
- **Grand Total** = the sum of every section's Subtotal.
- Present the whole 7-column table with all sections, subtotals, and the grand total.
- Values are in **hours** (Cost Per Hour = 1). If the user gave an hourly rate,
  multiply the Estimated Cost / totals by that rate to show dollars.
