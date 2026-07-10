---
name: TI-domains-generation
description: Generate the TI domain from clinical study protocols, it must comply with CDISC SDTMIG V3.4 and applicable CDISC controlled terminology.
---


## Required Inputs
### Protocols

## Required Outputs
### An excel file, the first tab name is "TI", using variable names as column headers. The second tab name is "TI_Version", should contain 2 columns, the 1st is TIVERS, the 2nd is the list of all the protocol versions. They should have the corresponding relationship.


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
