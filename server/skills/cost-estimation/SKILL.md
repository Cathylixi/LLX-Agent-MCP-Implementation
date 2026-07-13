---
name: cost-estimation
description: Estimate the programming and validation effort (in hours) for a clinical study's SDTM and ADaM deliverables, based on the study's Schedule of Assessments and endpoints. Use when the user asks for a cost estimate, effort estimate, bid, or quote for a clinical data (SDTM/ADaM) project.
---

## What this skill does
Given a clinical study, work out how much programming + validation effort (in
hours) the SDTM and ADaM deliverables will take, and present an itemized estimate
with subtotals and a grand total. The effort is driven by how many SDTM/ADaM
domains are needed and how complex each one is.

## Required inputs
- The study's **Schedule of Assessments** (the grid listing every procedure/test
  and the visits), from the protocol or CRF.
- (Optional) the study **endpoints** (primary / secondary / safety), which help
  decide the ADaM datasets.

If no Schedule of Assessments or procedure list can be found, STOP and ask the
user to provide the protocol — do not invent procedures.

---

## Step 1 — Extract the list of procedures
From the Schedule of Assessments, read the **first column** of each row (the
procedure/assessment name). Apply these filters:

- **Skip the header row** — a first cell that contains any of
  procedure / assessment / activity / visit / evaluation / test AND is shorter
  than 50 characters.
- **Keep** a cell only if ALL of: length between 4 and 149 characters; not a pure
  number; not a single letter followed by digits (e.g. "A1", "B2"); not "-";
  not "N/A".
- **Drop timepoint / visit labels**, e.g. "Day N Pre/Post-dose", "Visit N",
  "Week N", "Month N", "Screening", "Baseline", "Follow-up", "End of Study",
  "EOS", "Cycle N".
- **Drop overly descriptive text** — longer than 100 characters and containing a
  colon ":".
- **De-duplicate** the final list.

## Step 2 — Map each procedure to SDTM domains, and rate complexity
You are a CDISC SDTM expert. Map based on CDISC SDTMIG **v3.4**. You MUST provide a
mapping for **every** procedure — never skip one; pick the most appropriate domain
even if the procedure looks unusual.

Common SDTM domains: AE, CM, DM, EG, EX, LB, MB, PE, QS, SC, VS, DA, DS, MH, SU,
FA, IE.

Rate each procedure's complexity:
- **High**: complex laboratory tests, multi-parameter biomarkers, complex
  questionnaire assessments, special medical examinations.
- **Medium**: standard physical examinations, basic vital signs, routine
  laboratory tests, standard drug administration.

Then normalize at the **domain** level (this is what the effort table counts):
1. **SV is always High.** If SV ended up as Medium, move it to High. If SV is not
   present at all, add it as High.
2. **High overrides Medium.** If the same domain is rated both High and Medium
   (across different procedures), put it in the High set only. The High and Medium
   sets must be mutually exclusive by domain.
3. **Always add these 6 trial-design domains as Medium** if not already present
   (they don't come from procedures): TA, TE, TI, TV, TS, SE.
4. Produce three counts:
   - **highCount** = number of High-complexity domains
   - **mediumCount** = number of Medium-complexity domains
   - **totalDomains** = number of unique domains (= the union of High + Medium)

## Step 3 — Compute the SDTM effort
Build this table. "Hours each" is fixed; "Quantity" comes from Step 2.

| Task | Quantity | Hours each |
|---|---|---|
| Annotated CRF | 1 | 32 |
| SDTM specs (High complexity) | highCount | 3 |
| SDTM specs (Medium complexity) | mediumCount | 2 |
| Production & validation (High) | highCount | 16 |
| Production & validation (Medium) | mediumCount | 10 |
| Pinnacle 21 report | 2 | 6 |
| Reviewer's Guide | 1 | 32 |
| Define.xml | 1 | 32 |
| XPT conversion | totalDomains | 0.2 |

For each row: **hours = Quantity × Hours each** (round to 2 decimals; a missing
quantity counts as 0). Add all rows = **SDTM subtotal (hours)**.

## Step 4 — Map SDTM domains to ADaM, and rate complexity
You are a CDISC ADaM expert. From the unique SDTM domains, decide which **ADaM
datasets** are needed, per CDISC ADaM **v1.2**. **ADSL is mandatory.** If study
endpoints are provided, use them: primary endpoints → efficacy ADaM (e.g. ADTTE,
ADRS); safety endpoints → safety ADaM (e.g. ADAE, ADCM); time-to-event → ADTTE;
response → ADRS.

Common ADaM domains: ADAE, ADCM, ADEG, ADLB, ADQS, ADVS (plus ADSL, and efficacy
ones like ADTTE / ADRS as needed).

Rate each ADaM domain's complexity:
- **High**: the ADaM dataset needs multiple SDTM datasets; efficacy-related ADaM.
- **Medium**: the ADaM dataset needs only a single SDTM merged with ADSL;
  safety-related ADaM.

Normalize at the domain level:
1. **ADSL is always High** — add it as High if it's missing.
2. **High overrides Medium**; the two sets are mutually exclusive by domain.
3. Produce **highCount**, **mediumCount**, **totalDomains** for ADaM.

## Step 5 — Compute the ADaM effort
| Task | Quantity | Hours each |
|---|---|---|
| ADaM specs (High complexity) | highCount | 4 |
| ADaM specs (Medium complexity) | mediumCount | 3 |
| Production & validation (High) | highCount | 20 |
| Production & validation (Medium) | mediumCount | 12 |
| Pinnacle 21 report | 2 | 8 |
| Reviewer's Guide | 1 | 40 |
| Define.xml | 1 | 40 |
| XPT conversion | totalDomains | 0.3 |
| TXT conversion | totalDomains | 0.2 |

Same math: hours = Quantity × Hours each per row, then add = **ADaM subtotal (hours)**.

## Step 6 — Total and present the estimate
- **Grand total (hours)** = SDTM subtotal + ADaM subtotal.
- Show BOTH tables (each line item with its quantity and hours), the two
  subtotals, and the grand total.
- For each High / Medium row, note which domains it covers (e.g. "SDTM specs
  (High): LB / EG").
- The default rate is **1 hour per unit**, so the result is expressed in **hours**.
  If the user gives an hourly rate (or per-role rates), multiply the hours by the
  rate to produce a dollar figure; otherwise report hours.
