---
name: trial-design-SDTM-domains-generation
description: Generate the trial design domains (TA, TE, TV, TS, TI) from clinical study protocols, it must comply with CDISC SDTMIG V3.4 and applicable CDISC controlled terminology.
---


## Required Inputs
### Different version of protocols or one single version

## Required Outputs
### An excel file with multiple tabs. The 1st tab name is "TA", the 2nd tab name is "TE", the 3rd tab name is "TV", the 4th tab name is "TS", the 5th tab name is "TI", all these 5 tabs use variable names as column headers. The 6th tab name is "TI_Version", should contain 2 columns, the 1st is TIVERS, the 2nd is the list of all the protocol versions. They should have the corresponding relationship.

## Global Validation Requirements
### Naming Standards
- Ensure domain-level consistency.
- ARMCD and ETCD must be uppercase.
- No special characters except underscore.
- Length restrictions must be enforced.

### Consistency Checks
- TA → TE mapping must be exact.
- Epoch definitions must be consistent across domains.
- Visit structure must align with trial arms and elements.
- Inclusion and exclusion criteria must preserve protocol intent.

---

### Step 1: Generate TA (Trial Arms)

#### Rules
1. Follow SDTMIG v3.4.
2. Include only:
   - STUDYID
   - DOMAIN
   - ARMCD
   - ARM
   - TAETORD
   - ETCD
   - ELEMENT
   - TABRANCH
   - TATRANS
   - EPOCH
3. EPOCH must use controlled terminology.
4. ARMCD:
   - Maximum 20 characters
   - Uppercase only
   - Letters, numbers, and underscores only
5. ETCD:
   - Maximum 8 characters
   - Uppercase only
   - Letters, numbers, and underscores only
6. ARM and ELEMENT should be concise, meaningful phrases.
7. TATRANS must be readable text without arrows, hyphens, or special symbols.
8. One record per occurrence of an element within each arm.
9. Arms must represent complete planned subject paths.
10. TABRANCH:
    - Represents branching decisions creating separate arms.
    - No IF statements.
11. TATRANS:
    - Represents choices within an arm.
    - May contain conditional logic.
12. Populate TABRANCH and TATRANS only where required.

---

### Step 2: Generate TE (Trial Elements)

#### Inputs
- TA domain
- Study Design

#### Rules
1. Follow SDTMIG v3.4.
2. Include only:
   - STUDYID
   - DOMAIN
   - ETCD
   - ELEMENT
   - TESTRL
   - TEENRL
   - TEDUR
3. ETCD and ELEMENT must exactly match TA.
4. Each unique element appears once only.
5. TEDUR must use ISO 8601 duration format.
6. TESTRL must not reference arms.
7. TESTRL must not reference epochs.
8. At least one of TEENRL or TEDUR must be populated.

---

### Step 3: Generate TV (Trial Visits)

#### Rules
1. Follow SDTMIG v3.4.
2. Derive visits from:
   - Schedule of Activities
   - Visit Schedule
   - Study Design
3. Generate planned visits in chronological order.
4. Use controlled terminology where applicable.
5. Ensure consistency with:
   - TA
   - TE
   - Epoch definitions
6. Include visit timing, visit windows, and visit numbering when available.
7. Represent all planned protocol visits including:
   - Screening
   - Randomization
   - Treatment visits
   - Follow-up visits
   - End-of-treatment
   - End-of-study

---

### Step 4: Generate TS (Trial Summary)

#### Rules
1. Follow SDTMIG v3.4.
2. Include:
   - STUDYID
   - DOMAIN
   - TSSEQ
   - TSPARMCD
   - TSPARM
   - TSVAL
   - TSVALNF
   - TSVALCD
   - TSVCDREF
   - TSVCDVER
   - TSVAL1–TSVALn (when required)
3. If TSVAL exceeds 200 characters:
   - Split into TSVAL1–TSVALn
   - Each segment ≤200 characters
   - Split at word boundaries
4. When a CDISC codelist exists:
   - Use CDISC submission value in TSVAL
   - Use code in TSVALCD
5. When ISO 8601 is required:
   - Use ISO 8601 format in TSVAL
6. TSSEQ:
   - Single-record parameter → TSSEQ=1
   - Multi-record parameter → sequence from 1 upward

#### Example Parameter
- TSPARMCD = ADAPT
- TSPARM = Adaptive Design

---

### Step 5: Generate TI (Trial Inclusion/Exclusion Criteria)

#### Rules
1. Follow SDTMIG v3.4.
2. Must include the Req and Exp variables, the Perm variable can be included based on your judgement
3. IECAT must use controlled terminology.
4. Avoid using special characters in IETEST, e.g. use ">=" instead of "≥", use "<=" instead of "≤"
4. Inclusion criteria:
   - IETESTCD begins with INCL01
   - Maximum 8 characters
5. Exclusion criteria:
   - IETESTCD begins with EXCL01
   - Maximum 8 characters
6. If criterion text <=200 characters:
   - Use full text in IETEST.
7. If criterion text >200 characters:
   - Use meaningful summary in IETEST.
8. Criteria with separately enumerated subcriteria (a, b, c or i, ii, iii):
   - Consider them as one criteria, do not generate separate IETESTCD values.
9. Please search all the versions of protocol in the folder:
   - Use TIVERS to indicate The number of this version of the Inclusion/Exclusion criteria. When it is pure number, add "Version" to make TIVERS a character format variable. May be omitted if there is only 1 version.
   - If inclusion/exclusion criteria were amended during the trial, then each complete set of criteria must be included in the TI domain. TIVERS is used to distinguish between the versions.
   - Protocol version numbers should be used to identify criteria versions, although there may be more versions of the protocol than versions of the inclusion/exclusion criteria. For example, a protocol might have versions 1, 2, 3, and 4, but if the inclusion/exclusion criteria in version 1 were unchanged through versions 2 and 3, and changed only in version 4, then there would be 2 sets of inclusion/exclusion criteria in TI: one for version 1 and one for version 4.
   - Individual criteria do not have versions. If a criterion changes, it should be treated as a new criterion, with a new value for IETESTCD. If criteria have been numbered and values of IETESTCD are generally of the form INCL00n or EXCL00n, and new versions of a criterion have not been given new numbers, separate values of IETESTCD might be created by appending letters (e.g., INCL003A, INCL003B). The original set of criterion should end with number without appending letters, example INCL001, EXCL001. The appending letters should be used from the criteria modification.
10. Do not infer additional logical splits beyond protocol structure.

---
