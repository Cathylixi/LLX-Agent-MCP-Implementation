---
name: cost-estimation
description: Build a clinical study's full cost-estimate page from its protocol. Given only the protocol, produce the complete itemized cost table — every project section laid out, with SDTM and ADaM calculated and the rest listed as placeholders. Use when the user asks for a cost estimate, effort estimate, bid, or quote for a clinical data project.
---

## What this skill does
The **only required input is the study protocol.** Given the protocol, produce the
**complete cost-estimate page** exactly like the tool's Excel output: every project
section is laid out in order. Only **SDTM** and **ADaM** are actually calculated
(their units are derived from the protocol); every other section is **listed as a
placeholder** — its rows/subtotal are shown but left blank for the estimator to
fill in later.

**Input:** the study **protocol** (with its Schedule of Assessments). Optionally the
study **endpoints** and an **hourly rate** (to turn hours into money).

**Output:** the full 7-column cost page — **Task | Unit | Cost Per Hour | Hours Per
Unit | Cost Per Unit | Estimated Cost | Notes** — with all sections (Step 4), a
Subtotal per section, and a Grand Total. SDTM and ADaM are filled in and totaled;
the rest are blank placeholders. Values are in hours (Cost Per Hour = 1); if an
hourly rate is given, multiply to get money.

If no protocol / Schedule of Assessments is provided, STOP and ask for the
protocol — do not invent procedures.

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
2. **High overrides Medium** (a domain in both goes to High only; mutually exclusive).
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

## Step 4 — Build the full cost page (all sections, in this order)
Use these 7 columns for every row:

| Task | Unit | Cost Per Hour | Hours Per Unit | Cost Per Unit | Estimated Cost | Notes |

Row math (used for the CALCULATED sections): **Cost Per Hour** = 1 (or the user's
rate); **Cost Per Unit** = Cost Per Hour × Hours Per Unit; **Estimated Cost** = Unit
× Cost Per Hour × Hours Per Unit (round to 2 decimals). Each section ends with a
**Subtotal** = sum of its Estimated Cost cells. Lay the sections out in THIS order:

### 1. Statistical Analysis Plan and Shells Development  *(listed only — leave Unit and Estimated Cost blank)*
| Task | Hours Per Unit |
|---|---|
| Statistical Analysis Plan Draft 1 | 40 |
| Statistical Analysis Plan Draft 2 | 30 |
| Statistical Analysis Plan Final | 20 |
| Analysis Shells Development | 60 |
| Mock Tables, Listings, and Figures | 40 |
Then a blank **Subtotal**.

### 2. SDTM Datasets Production and Validation  *(CALCULATED)*
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
Notes: High domain names on Specs (High) (joined by "/"), Medium names on Specs
(Medium), all domain names on the xpt row. Then a **Subtotal** = sum.

### 3. ADaM Datasets Production and Validation  *(CALCULATED)*
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
domain names on the xpt and txt rows. Then a **Subtotal** = sum.

### 4–10. The remaining projects  *(listed only — a title row + a blank Subtotal each)*
Add each of these as a titled section with an empty Subtotal (no line items, nothing
calculated):
4. Tables, Figures, and Listings Development
5. Interim Analysis
6. Final Analysis
7. DSUR First Time
8. DSUR Rerun
9. DSMB/IDMC First Time
10. DSMB Rerun

### Fixed trailing sections  *(always listed — title + blank Subtotal each)*
- License Fees
- Adhoc Analysis
- Project Management/Administration (12 Months)

## Step 5 — Grand Total and presentation
- **Grand Total** = the sum of every section's Subtotal (only SDTM and ADaM have
  values; the placeholder sections contribute nothing until filled in).
- Present the entire 7-column page with every section above, each subtotal, and the
  grand total. Keep the blank placeholder sections visible so the estimator can fill
  them in.
- Values are in **hours** (Cost Per Hour = 1). If the user gave an hourly rate,
  multiply to show dollars.

---

## Optional: Data Transfer sub-blocks (only if the user gives a transfer count N)
Inside the SDTM or ADaM section, if the user specifies "Data Transfer Times = N":
- **SDTM Dataset Transfer (N times)**: first 2 times (Unit 2 × 25h) + last (N−2)
  times (Unit N−2 × 12.5h), with its own Subtotal.
- **ADAM Dataset Transfer (N times)**: first 2 times (Unit 2 × 15h) + last (N−2)
  times (Unit N−2 × 7.5h), with its own Subtotal.
