"""
Clean CRF form-name to SDTM domain mapper.

Source of truth:
- outputs/acrf_form_name_domain_mapping.xlsx
- Sheet: Consolidated Form Names

This module contains a compact historical aCRF form-name mapping guide plus
page-text validation. Historical form matches are treated as candidates; the
visible CRF text can prune unsupported domains or provide a conservative
fallback when no historical match is available.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any


HISTORICAL_FORM_DOMAIN_GUIDE: list[tuple[str, str]] = [('12-Lead ECG', 'EG'),
 ('12-Lead ECG (Timepoint)', 'EG'),
 ('12-Lead ECG - Central', 'EG'),
 ('12-Lead Electrocardiogram', 'EG'),
 ('12-Lead Electrocardiogram - Triplicate', 'EG'),
 ('12-Lead Electrocardiogram - Triplicate - Predose', 'EG'),
 ('12-Lead Electrocardiogram - Triplicate - Timepoints', 'EG'),
 ('12-Lead Electrocardiogram Single', 'EG'),
 ('Administrative Protocol Deviation', 'DV'),
 ('Adverse Event', 'AE'),
 ('Adverse Events Question', 'AE; PR'),
 ('Adverse Events Y/N', 'AE'),
 ('Adverse Events Y/N?', 'AE'),
 ('Adverse Events YN', 'AE; PR'),
 ('Adverse Events YN?', 'AE'),
 ('Aflibercept Treatment (Week 8 and prior)', 'CM'),
 ('ALK Alterations', 'MH'),
 ('ALL Cytogenetic and Molecular Studies', 'FA'),
 ('ALL Disease History', 'MH; SE'),
 ('ALL Overall Response', 'RS'),
 ('AML Cytogenetic and Molecular Studies', 'FA'),
 ('AML Disease History', 'MH'),
 ('AML Overall Response', 'RS'),
 ('AMT-130 Administration', 'EC; CO; RE'),
 ('AMT-130 Cannula Depth Changes', 'EC'),
 ('AMT-130 Infusion Rate Changes', 'EC'),
 ('AMT-130 Thaw Dates and Times', 'FA'),
 ('Anesthesia Worksheet', 'PR; EX; CO'),
 ('Anti-Cancer Therapy', 'CM; PR'),
 ('Anticancer Therapies', 'PR'),
 ('Anticancer Therapy - Other', 'PR'),
 ('Anticancer Therapy - Radiation', 'PR'),
 ('Anticancer Therapy - Surgery', 'PR'),
 ('Anticancer Therapy - Systemic Treatment', 'CM'),
 ('Archival Tumor', 'PR'),
 ('Archival Tumor Tissue Biopsy', 'BE; PR'),
 ('Archival/Fresh tumor sample and Fine needle aspirates', 'PR'),
 ('Assent form', 'PR; DS'),
 ('Atopic Comorbid Conditions', 'FA; PR'),
 ('Baseline Clinical Subject Profile', 'CE'),
 ('Best Corrected Visual Acuity - ETDRS', 'OE'),
 ('Biomarker', 'LB'),
 ('Blood Collection', 'LB'),
 ('Blood Sample for Centralized Flow Cytometry', 'LB'),
 ('Blood samples - Central processing', 'LB'),
 ('Blood Samples for ADA', 'IS; LB'),
 ('Blood Samples for Biomarkers', 'PR; LB'),
 ('Blood Samples for Genomics', 'PR; LB'),
 ('Blood Samples for Pd/Biomarkers', 'LB; PR'),
 ('Blood Samples for Pd/Biomarkers - Unscheduled', 'PR; LB'),
 ('Blood Samples for PK/ADA - 30-Day Follow-Up', 'LB; PC'),
 ('Blood Samples for PK/ADA - C1 & C3', 'LB; PC'),
 ('Blood Samples for PK/ADA - C2, C4, C5 & C6', 'LB; PC'),
 ('Blood Samples for PK/ADA - EOT', 'LB; PC'),
 ('Blood Samples for PK/ADA - Unscheduled', 'LB; PC'),
 ('Blood Sampling for Concordance Study (BCT)', 'MI'),
 ('Body Composition', 'VS; PR'),
 ('Bone Marrow Aspirate for Genomics', 'PR; LB'),
 ('Bone Marrow Aspirate for Pd/Biomarkers', 'PR; LB'),
 ('Bone Marrow Assessment', 'MI; CM'),
 ('BPDCN Cytogenetic and Molecular Studies', 'FA'),
 ('BPDCN Disease History', 'MH; SE'),
 ('BPDCN Overall Response', 'RS'),
 ('Brain MRI', 'PR'),
 ('Buccal Swab for FCyR', 'GF; LB'),
 ('C-SSRS Screening', 'QS'),
 ('C-SSRS Since Last Visit', 'QS'),
 ('CA125', 'LB'),
 ('Cancer Diagnosis', 'MH'),
 ('Cancer History', 'PR; MH; CO'),
 ('Capacity to Consent', 'QS'),
 ('Central ECG', 'EG'),
 ('Central Lab - Safety Laboratory Samples', 'LB'),
 ('Central Laboratory - FSH', 'LB; PR'),
 ('Central Laboratory - Safety', 'LB'),
 ('Central Laboratory - Serum Pregnancy', 'LB; PR'),
 ('Central Laboratory Category 1', 'LB'),
 ('Central Laboratory Category 2', 'LB'),
 ('Central Laboratory Samples', 'LB; PR'),
 ('Central Laboratory: Chemistry, Hematology, Coagulation, Thyroid and Urinalysis', 'LB'),
 ('Central Laboratory: Chemistry, Hematology, Coagulation, Thyroid and Urinalysis (C1D1)', 'LB'),
 ('Chair Sit-to-Stand Test', 'FT; FA; PR'),
 ('Chemistry', 'LB'),
 ('Chemistry Local Lab', 'LB'),
 ('Chemistry-Central Laboratory', 'LB'),
 ('Clinical Activity Assessment list', 'QS; PR; SC'),
 ('Clinical Laboratory Evaluations', 'LB'),
 ('Clinical Status Related to Brain Metastasis', 'RS'),
 ('CNS Disease Assessment', 'MI; MH'),
 ('CNS Disease Assessment - Screening', 'MH'),
 ('Coagulation', 'LB'),
 ('Coagulation Local Lab', 'LB'),
 ('Coagulation-Central Laboratory', 'LB'),
 ('Color Fundus Photography', 'OE'),
 ('Compliance and Reconciliation', 'DA'),
 ('Concomitant Medical Procedures', 'PR'),
 ('Concomitant Medications', 'CM; MH; PR'),
 ('Concomitant Medications Question', 'CM; PR'),
 ('Concomitant Medications Y/N?', 'CM'),
 ('Concomitant Procedure', 'PR; CM'),
 ('Concomitant Procedure Questionnaire', 'PR; CM'),
 ('Concomitant Procedures', 'PR; MH; AE'),
 ('Concomitant Procedures Y/N', 'PR'),
 ('Concomitant Procedures Y/N?', 'PR; CM'),
 ('Concomitant Procedures/Surgeries', 'PR'),
 ('Consent', 'PR; DM; DS'),
 ('Continuation Form', 'CO'),
 ('Continuation Status', 'PR'),
 ('Corticosteroid and Lubricating Eye Drop Compliance', 'CM'),
 ('Corticosteroids/Anti-Convulsant Medications', 'CM'),
 ('COVID-19 IMPACT', 'SV; CO'),
 ('COVID-19 Status', 'FA; CO'),
 ('COVID-19 Test', 'LB'),
 ('Creatinine Clearance Calculated by Cockcroft-Gault', 'LB'),
 ('Crossover', 'DS; DM'),
 ('Crossover Arm Eligibility', 'DS; IE'),
 ('Crossover IP Accountability', 'FA; CO'),
 ('Crossover Neurosurgical Procedure', 'PR; DS'),
 ('Crossover Study Drug Dispensation', 'DM'),
 ('Crossover Subject Re-Consent', 'DS'),
 ('Crossover Subject Transfer', 'DM; TR'),
 ('CSF Local Laboratory', 'LB; FA'),
 ('CSF Local Laboratory Gram Stain, Culture, Sensitivity', 'MB; LB; SE'),
 ('CSF Sample', 'PR'),
 ('CT', 'PR'),
 ('ctDNA blood sample collection', 'PR; LB'),
 ('ctDNA Blood Sampling', 'MI; CO'),
 ('Current Cancer Status', 'FA'),
 ('D-Dimer', 'LB; ML'),
 ('Dark Adaptometry Analysis', 'OE'),
 ('Date of Visit', 'SV; MI'),
 ('Date of Visit at Screening', 'SV'),
 ('Death', 'DM; DS; AE'),
 ('Death Details', 'PR'),
 ('Death Diagnosis', 'DM'),
 ('Death Report', 'DM; DS; PR'),
 ('Death/Autopsy', 'PR; DM'),
 ('Demographics / Informed Consent', 'DM; DS'),
 ('Dermatologic Examination', 'PE'),
 ('Deviations, Violations, and Exceptions', 'DV'),
 ('Diagnosis of AD - Major Criteria', 'FA; PR'),
 ('Diagnosis of AD - Minor Criteria', 'FA; PR'),
 ('Dietary Counseling', 'FA'),
 ('Disease Characteristics', 'MH'),
 ('Disease Characteristics for Screen Failures', 'DM'),
 ('Disease History', 'DM'),
 ('Disposition (End of Study)', 'DS'),
 ('Disposition Pre-Screening', 'DS; DM; PR'),
 ('DM&SC', 'SC; DM; SU'),
 ('Dose Limiting Toxicity', 'FA'),
 ('Drug Dispensation', 'FA; EX; PR'),
 ('ECG', 'EG'),
 ('ECG - Timepoint', 'EG'),
 ('ECHO', 'CV'),
 ('ECHO/MUGA', 'CV'),
 ('echo/MUGA scan', 'CV'),
 ('Echocardiogram or MUGA for LVEF Assessment', 'CV'),
 ('Echocardiogram/MUGA', 'CV'),
 ('ECOG', 'QS'),
 ('ECOG Performance status', 'QS; EC; RS'),
 ('ECOG Performance Status Questionnaire', 'QS; EC'),
 ('ECOG PS', 'QS'),
 ('ECOG Status', 'QS; EC'),
 ('Edema Reflex', 'AE'),
 ('Electrocardiogram', 'EG; PR'),
 ('Eligibility Criteria', 'IE'),
 ('Eligibility Reconfirmation', 'DS; IE'),
 ('End of Crossover', 'DS'),
 ('End of Cycle', 'MI'),
 ('End of Safety Follow-Up Period', 'DS'),
 ('End of Study Treatment: Adagrasib', 'AE'),
 ('End of Study Treatment: Cabozantinib', 'AE'),
 ('End of Study Treatment: Cabozantinib Monotherapy', 'AE'),
 ('End of Study Treatment: KO-2806', 'AE'),
 ('End of Trial', 'DS'),
 ('End of Visit', 'PR; SV'),
 ('End of XTX301 Treatment', 'DS; PR; RE'),
 ('Endocrinologist Consultation', 'FA'),
 ('Endothelial Cell Count', 'OE'),
 ('Enrolled - Treatment', 'DM; SC; EX'),
 ('Enrollment', 'DM; DS; PR'),
 ('Erythrocyte sedimentation rate', 'LB'),
 ('Exploratory Biomarkers - CSF', 'LB'),
 ('Exploratory Biomarkers - Serum', 'LB'),
 ('Exploratory Testing Consent Withdrawal', 'DS'),
 ('Exposure', 'EX; EC; PR'),
 ('FAF General', 'OE'),
 ('FAF Grader 1 Analysis', 'OE'),
 ('FAF Grader 2 Analysis', 'OE'),
 ('FAF Grader 3 Analysis', 'OE'),
 ('FAF Grader 4 Analysis', 'OE'),
 ('Family Hx - Atopic Conditions', 'MH; PR'),
 ('Female Reproductive Status', 'DM; PR; RP'),
 ('Fluorescein Angiography', 'OE; FA'),
 ('Follow-up Drug Therapy - GIST', 'PR'),
 ('Follow-Up Phone Call', 'RS; SV; PE'),
 ('Follow-up Procedures - GIST', 'PR'),
 ('Follow-up Radiotherapy - GIST', 'PR'),
 ('Follow-up Surgery - GIST', 'PR'),
 ('Fresh Tumor Tissue Biopsy', 'BE; PR'),
 ('FSH', 'RP; LB; PR'),
 ('FSH Test', 'LB'),
 ('Fulvestrant Administration', 'EX; EC'),
 ('Fundus Autofluorescence', 'OE'),
 ('Future Research Samples - CSF', 'LB'),
 ('Future Research Samples - Informed Consent', 'DS'),
 ('Future Research Samples - Serum', 'LB'),
 ('FX-909 Administration', 'EX; EC; DM'),
 ('FX-909 Dosing Log', 'EX; EC; DM'),
 ('General', 'OE'),
 ('Genetic Diagnosis', 'FA'),
 ('Genetic Testing HTT', 'LB'),
 ('Genomic DNA blood sample collection', 'PR; LB'),
 ('GIST Cancer History', 'SC'),
 ('HD-CAB', 'FT; TR'),
 ('Health-Related Qualify of Life', 'QS; CO; FA'),
 ('Healthcare Utilization Questionnaire (A)', 'HO'),
 ('Healthcare Utilization Questionnaire (B)', 'HO'),
 ('Healthcare Utilization Questionnaire (C)', 'HO'),
 ('Hematology', 'LB'),
 ('Hematology Local Lab', 'LB'),
 ('Hematology-Central Laboratory', 'LB'),
 ('Hepatitis B Screen', 'LB'),
 ('Hepatitis C Screen', 'LB'),
 ('Holter ECG', 'EG; LB'),
 ('Hospital Anxiety and Depression Scale (HADS)', 'QS'),
 ('Hospitalization Worksheet', 'CO; HO'),
 ('Hospitalization/Hospice/Nursing Home', 'HO; AE'),
 ('Huntington Disease History and Baseline Characteristics', 'MH'),
 ('IgG Level - Local Lab', 'LB'),
 ('Imaging & Psychophysical Testing', 'OE'),
 ('IMGN632 Infusion (Schedule A)', 'EX; EC'),
 ('IMGN632 Infusion (Schedule B)', 'EX; EC'),
 ('Immunogenicity Blood Sample Collection', 'PR; LB'),
 ('Immunogenicity Samples', 'IS'),
 ('Immunogenicity Sampling', 'IS; LB; PR'),
 ('Immunogenicity Testing - Cytokines - Serum', 'LB'),
 ('Immunogenicity Testing - IgG/IgM AAV5 - CSF', 'LB'),
 ('Immunogenicity Testing - IgG/IgM AAV5 - Serum', 'LB'),
 ('Immunogenicity Testing - NAB AAV5 - CSF', 'LB'),
 ('Immunogenicity Testing - Serum NAB AAV5 and ELISpot', 'LB'),
 ('Impact Harmony Data Transfer', 'DS'),
 ('Inclusion & Exclusion', 'IE; DS'),
 ('Inclusion and Exclusion Criteria', 'IE; EX'),
 ('Inclusion/Exclusion Criteria', 'DM; EX; IE'),
 ('Inclusion/Exclusion Criteria - Day 1', 'IE; DS; PR'),
 ('Inclusion/Exclusion Criteria - Day 112', 'IE; DS; PR'),
 ('Informed Consent', 'DM; DS'),
 ('Informed Consent and Inclusion/Exclusion Criteria', 'IE; DS; DM'),
 ('Informed Consent Form', 'DM; DS'),
 ('Infusion Reaction PK', 'LB; PR'),
 ('Intraocular Pressure', 'OE'),
 ('Iris Color', 'SC'),
 ('Iron Studies', 'LB; PR'),
 ('KO-2806 Administration', 'EC; SC; DS'),
 ('L Anterior Putamen Coordinates and Changes in Infusion Rate and', 'CO; FA'),
 ('L Caudate Coordinates and Changes in Infusion Rate and Cannula Depth', 'CO; FA'),
 ('L Posterior Putamen Coordinates and Changes in Infusion Rate and', 'CO; FA'),
 ('Laboratory Assessment: Serology', 'LB'),
 ('Laboratory Assessment: Serology 2', 'LB'),
 ('Laboratory Sample (Urinalysis)', 'LB; PR'),
 ('Laboratory Tests - Coagulation', 'LB'),
 ('Laboratory Tests - Hematology', 'LB'),
 ('Laboratory Tests - Serum Chemistry', 'LB'),
 ('Laboratory Tests - Urinalysis', 'LB; PR'),
 ('Lead ECG - Single', 'EG'),
 ('Lead ECG - Single - Unscheduled', 'EG'),
 ('Lead ECG - Triplicate', 'EG'),
 ('Lead ECG - Triplicate (Pre/Post-Dose)', 'EG'),
 ('Lead ECG - Triplicate - Unscheduled', 'EG'),
 ('Lesion Identification at Crossover', 'SC'),
 ('Lesion Identification at Screening', 'SC'),
 ('Lipid Profile', 'LB'),
 ('LLVA', 'OE'),
 ('Local Chemistry', 'LB; PR'),
 ('Local Coagulation', 'LB; PR'),
 ('Local Hematology', 'LB; PR'),
 ('Local Laboratory - BNP', 'LB'),
 ('Local Laboratory - C-peptide', 'LB; PE'),
 ('Local Laboratory - Chemistry', 'LB; RE'),
 ('Local Laboratory - Coagulation', 'LB'),
 ('Local Laboratory - Hematology', 'LB'),
 ('Local Laboratory - Hemoglobin A1C', 'LB'),
 ('Local Laboratory - Homeostatic Model Assessment for Insulin Resistance', 'LB'),
 ('Local Laboratory - Pregnancy Test', 'LB; SE'),
 ('Local Laboratory - Serology', 'LB'),
 ('Local Laboratory - Urinalysis', 'LB; TR'),
 ('Local Laboratory Results (Ripretinib)', 'LB'),
 ('Local Laboratory Results (Sunitinib)', 'LB'),
 ('Local Laboratory Results: Chemistry', 'LB; PR; TR'),
 ('Local Laboratory Results: Coagulation', 'LB; PR'),
 ('Local Laboratory Results: Hematology', 'LB'),
 ('Local Laboratory Results: Thyroid', 'LB'),
 ('Local Labs', 'LB'),
 ('Local serology', 'MB; LB; PR'),
 ('Local Thyroid Panel', 'LB; PR'),
 ('Log Form', 'AE; CM; PR'),
 ('Long Term Follow-Up Subject Re-Consent', 'DS'),
 ('MacCAT-CR', 'QS'),
 ('Manual Protocol Deviation', 'DV'),
 ('Medical History', 'MH; PR'),
 ('Medical History and Active Symptoms', 'MH'),
 ('Medical History Cardiovascular System', 'MH'),
 ('Medical History Dermatological System', 'MH'),
 ('Medical History Endocrine System', 'MH'),
 ('Medical History Findings', 'MH; PR'),
 ('Medical History Gastrointestinal System', 'MH'),
 ('Medical History Genitourinary System', 'MH'),
 ('Medical History Gynecologic System', 'MH'),
 ('Medical History HEENT System', 'MH'),
 ('Medical History Hematologic System/Malignancy', 'MH'),
 ('Medical History Hepatobiliary System', 'MH'),
 ('Medical History Immune System', 'MH'),
 ('Medical History Musculoskeletal System', 'MH'),
 ('Medical History Neurological System', 'MH'),
 ('Medical History Psychiatric', 'MH'),
 ('Medical History Renal System', 'MH'),
 ('Medical History Respiratory System', 'MH'),
 ('Medical History Surgery', 'PR; MH'),
 ('Medical History Y/N', 'MH'),
 ('Medical History YN', 'PR; MH'),
 ('Medical Monitor Review', 'PR; IE'),
 ('Medical or Surgical Treatment Procedures', 'PR'),
 ('Medical Surgical Treatment Procedures YN', 'PR'),
 ('Medical/Surgical/Ophthalmic History', 'MH'),
 ('Medication History - Atopic Dermatitis', 'CM; PR'),
 ('Microperimetry General', 'OE'),
 ('Microperimetry Review', 'OE'),
 ('Microscopic Urinalysis', 'LB'),
 ('MoCA', 'FT'),
 ('Modified RECIST', 'RS'),
 ('Molecular Markers from Blood', 'MI'),
 ('Month 12 Transition', 'DS'),
 ('NEI-VFQ-25', 'QS'),
 ('Neurological Examination', 'PE'),
 ('Neurological Examination Yes/No', 'PE'),
 ('New Antineoplastic Therapy', 'PR; CM'),
 ('New Lesion', 'TU; TR'),
 ('New Lesion Assessment', 'TU; TR'),
 ('New Lesion Identification', 'TU; TR'),
 ('Next Visit', 'PR'),
 ('Next Visit/Cycle', 'CO'),
 ('Nicotine and Alcohol Usage', 'SU; PR'),
 ('Non-CNS Overall Response (RECIST 1.1)', 'RS'),
 ('Non-Platinum Therapy Choice', 'DM'),
 ('Non-Target Lesion', 'TU; TR'),
 ('Non-Target Lesion / Baseline', 'TU; TR'),
 ('Non-Target Lesion / Post Baseline', 'TU; TR'),
 ('Non-Target Lesion Assessment', 'TU; TR'),
 ('Non-Target Lesion Assessment Screening', 'TU; TR'),
 ('Nutritional Counseling', 'FA; PR'),
 ('NVL-655-01 Study Drug Administration', 'EC; EX'),
 ('Ocular Exam', 'OE'),
 ('Ocular Exam & Characteristics', 'OE'),
 ('Ocular Examination - Dilated Ophthalmoscopy', 'OE'),
 ('Ocular Examination - Slit Lamp Biomicroscopy', 'OE'),
 ('Ocular Imaging Review Main', 'OE'),
 ('Ocular Imaging Review OD', 'OE'),
 ('Ocular Imaging Review OS', 'OE'),
 ('Ocular Symptom Assessment', 'OE'),
 ('Open Ended Questions', 'QS'),
 ('Opening Lumbar Puncture Pressure', 'VS'),
 ('Ophthalmic Exam', 'OE'),
 ('Ophthalmic Examination', 'OE'),
 ('Ophthalmologic Examination', 'OE'),
 ('Ophthalmological Examination', 'OE'),
 ('OS', 'OE'),
 ('Other Hematologic Malignancies Overall Response', 'RS'),
 ('Other Hematologic Malignancy Cytogenetic and Molecular Studies', 'FA'),
 ('Other Hematologic Malignancy Disease History', 'MH; SE'),
 ('Other Prior Cancer Therapy', 'PR'),
 ('Other Prior Cancer Therapy Y/N', 'PR'),
 ('Other TB Screening', 'LB; PR'),
 ('Overall Response', 'RS'),
 ('Overall Response (CNS)', 'RS'),
 ('Overall Survival Follow-Up', 'SS; SV'),
 ('Participant Dose Log', 'EX; PR; EC'),
 ('Patient Enrollment', 'DM'),
 ('Patient Identification', 'DM'),
 ('Patient Status', 'SS'),
 ('PedsQL Child (Parent)', 'QS'),
 ('PedsQL Child (Subject)', 'QS'),
 ('PedsQL Teens (Parent)', 'QS'),
 ('PedsQL Teens (Subject)', 'QS'),
 ('PD Gene Expression Blood Sample Collection', 'PR; LB'),
 ('PD Sample 1', 'PR'),
 ('PD Sample 2', 'PR'),
 ('PD Sample 2 - Timepoint', 'PR; PC; MI'),
 ('PD Sampling', 'PR'),
 ('PET/CT Imaging', 'PR'),
 ('PET/CT Imaging - Screening', 'PR'),
 ('Pharmacodynamic Assessments', 'IS; PE'),
 ('Pharmacodynamic Blood Samples', 'LB'),
 ('Pharmacodynamic Blood Sampling (Timepoint)', 'PR'),
 ('Pharmacodynamics Plasma Sampling', 'IS'),
 ('Pharmacokinetic Blood Samples', 'PC'),
 ('Pharmacokinetic Urine Samples', 'PC'),
 ('Pharmacokinetics Concentration', 'PC'),
 ('Pharmacokinetics Concentration 2', 'PC'),
 ('Pharmacokinetics Sampling', 'PC; PR'),
 ('Pharmacokinetics Sampling (Unscheduled)', 'PC'),
 ('Phone Visit', 'SV'),
 ('Photography', 'PR'),
 ('Physical Exam', 'PR; PE'),
 ('Physical Examination', 'PE; PR'),
 ('Physical Examination - Complete', 'PE'),
 ('Physical Examination - Symptom Driven', 'PE'),
 ('Physical Examination - Symptom-Directed', 'PE'),
 ('Physical Measurements', 'VS; PR'),
 ('Physical/Neurological Exam (Full or Symptom Directed)', 'PE'),
 ('PK', 'LB'),
 ('PK - Multiple Timepoints', 'PC'),
 ('PK - Single Timepoint (Pre-Dose)', 'PC'),
 ('PK Blood Sampling', 'PC; CO'),
 ('PK Dosing and Meal Record', 'CO'),
 ('PK Samples', 'PR; PC'),
 ('PK Samples - Timepoint 1', 'PR; PC; MI'),
 ('PK Samples - Timepoint 2', 'PR; PC; MI'),
 ('PK Samples - Timepoint 3', 'PR; PC'),
 ('PK Sampling', 'PC'),
 ('PK Sampling (Timepoint)', 'PC'),
 ('PK Sampling (Timepoint) 2', 'PC'),
 ('PK Sampling DLT', 'PR'),
 ('Plasma PK Sample Collection', 'PC; PR'),
 ('Post Aflibercept Injection Intraocular Pressure - Week 8', 'OE'),
 ('Post SCT Reflex', 'PR'),
 ('Post-Injection Assessment', 'OE'),
 ('Post-Injection Intraocular Pressure', 'OE'),
 ('Post-study Treatments', 'CM'),
 ('Post-Treatment Cancer Radiation Therapy', 'PR'),
 ('Post-Treatment Cancer Surgery', 'PR'),
 ('Post-Treatment Cancer Therapy', 'CM; PR'),
 ('Post-Treatment Cancer Treatments YN?', 'PR; CM; RP'),
 ('Pre and Post Dose ECG', 'EG'),
 ('Pre-Medications', 'CM'),
 ('Pre-Op Physical & Neurological Exam', 'PE'),
 ('Predose ECG', 'EG'),
 ('Pregnancy Follow-up Consent', 'DS; PR'),
 ('Pregnancy Test', 'LB; RP; PR'),
 ('Pregnancy Test Serum', 'LB'),
 ('Pregnancy Test- Dipstick', 'LB'),
 ('Prescreening (HNSCC)', 'DM; DS; PR'),
 ('Previous IMGN Studies', 'DM'),
 ('Primary Cancer History', 'MH'),
 ('Prior & Concomitant Medications', 'CM; QS'),
 ('Prior & Concomitant Medications YN?', 'CM'),
 ('Prior & Concomitant Non-Drug Therapies or Procedures', 'PR'),
 ('Prior and Concomitant Medication YN', 'CM'),
 ('Prior and Concomitant Medications Y/N', 'CM'),
 ('Prior and Concomitant Medications YN', 'PR; CM'),
 ('Prior and Concomitant Procedures', 'PR; IS'),
 ('Prior and Concomitant Procedures YN', 'PR'),
 ('Prior and Concomitant Therapies', 'PR; AE; MH'),
 ('Prior Anti-Cancer Therapy', 'PR; SE; CM'),
 ('Prior Cancer Radiation Therapy', 'PR; MH'),
 ('Prior Cancer Related Surgeries', 'PR'),
 ('Prior Cancer Surgery', 'PR; MH'),
 ('Prior Cancer Surgery/Biopsy', 'PR'),
 ('Prior Cancer Surgery/Biopsy Y/N', 'PR'),
 ('Prior Cancer Systemic Therapy', 'CM'),
 ('Prior Cancer Therapy', 'CM; PR'),
 ('Prior Cancer treatment history', 'PR; CM'),
 ('Prior Cancer Treatments YN?', 'CM; MH; RP'),
 ('Prior GIST Procedures', 'PR'),
 ('Prior GIST Radiotherapy', 'PR'),
 ('Prior GIST Surgery', 'PR'),
 ('Prior GnRH Administration', 'CM'),
 ('Prior Imatinib Therapy', 'PR'),
 ('Prior Infections', 'MH'),
 ('Prior IVT Injections', 'CM'),
 ('Prior Radiation', 'PR'),
 ('Prior Radiation Y/N', 'PR'),
 ('Prior Radiotherapy', 'PR; AE'),
 ('Prior Surgery for Lung Cancer', 'PR'),
 ('Prior Systemic Anti-Cancer Therapies for Lung Cancer', 'CM'),
 ('Prior Systemic Cancer Therapy', 'CM; PR'),
 ('Prior Systemic Cancer Therapy Y/N', 'MH'),
 ('Prior Systemic Therapy - ALL', 'CM; PR; AE'),
 ('Prior Systemic Therapy - AML', 'CM; PR; AE'),
 ('Prior Systemic Therapy - BPDCN', 'CM; PR; AE'),
 ('Prior Systemic Therapy - Other Hematologic Malignancies', 'CM; PR; AE'),
 ('Prior Therapy Prompts', 'PR; CM'),
 ('Prior Transfusions', 'PR'),
 ('Prior/Concomitant Medications', 'CM; PR'),
 ('Prior/Concomitant Medications YN', 'PR; CM'),
 ('Programmed Protocol Deviation', 'DV'),
 ('Q-Motor Test', 'FT'),
 ('R Anterior Putamen Coordinates and Changes in Infusion Rate and', 'CO; FA'),
 ('R Caudate Coordinates and Changes in Infusion Rate and Cannula Depth', 'CO; FA'),
 ('R Posterior Putamen Coordinates and Changes in Infusion Rate and', 'CO; FA'),
 ('Randomization', 'DS; PR'),
 ('RAS Alterations', 'PR; SC; DS'),
 ('Re-Consent', 'DS; DM'),
 ('Reading Speed', 'OE'),
 ('Reading Speed (MNRead)', 'OE'),
 ('RECIST Non Target Lesions', 'TU; TR'),
 ('RECIST Response', 'RS'),
 ('RECIST Target Lesions', 'TU; TR'),
 ('Reconsent', 'DS'),
 ('Reconsent Form', 'DS; RE'),
 ('Reconsent/Consent Withdrawal', 'DS'),
 ('Registration Form', 'DM; PR'),
 ('Response assessment', 'PR; RS'),
 ('Results of Local Tumor Tissue/ctDNA analysis', 'MI; CO'),
 ('Review of Adverse Events & Concomitant Medications', 'SE'),
 ('Ripretinib Administration Log', 'EC'),
 ('Ripretinib Dosing Log', 'EX'),
 ('Ripretinib Drug Compliance Log', 'DA'),
 ('RLY-2608 Study Drug Administration', 'EX; EC'),
 ('Safety Event Form', 'AE; RE; CO'),
 ('Safety Follow-Up', 'SV'),
 ('Safety Follow-up Drug Therapy - GIST', 'PR'),
 ('Safety Follow-up Procedures - GIST', 'PR'),
 ('Screen Failure', 'DM'),
 ('Screen Failure Prompt', 'DM'),
 ('SD - OCT Assessment', 'OE'),
 ('SD - OCTA Assessment', 'OE'),
 ('SDMT', 'FT; CO'),
 ('Serious Adverse Event', 'AE; RE'),
 ('Serious Adverse Events', 'AE; DM'),
 ('Serology', 'LB'),
 ('Serum based tumor markers', 'LB; PR'),
 ('Serum Central Laboratory Long Term Follow- Up', 'LB; IS; SE'),
 ('Site Participating Assessments', 'PR'),
 ('Skin Biopsy', 'BE; PR'),
 ('Skin Cancer History', 'SC'),
 ('Skin Lesion Assessment', 'PR; PE'),
 ('Skin Lesion Assessment - Screening', 'PR; PE'),
 ('Social History', 'SU'),
 ('Stem Cell Transplant', 'PR; SC'),
 ('Study Completion', 'DM; DS'),
 ('Study Continuation', 'FA; DS'),
 ('Study Drug Administration', 'EC; EX'),
 ('Study Drug Administration - BL/FU', 'EC; EX'),
 ('Study Drug Administration - Week 8', 'EC; EX'),
 ('Study Eligibility', 'DS; IE'),
 ('Study Medication Administration Pemetrexed', 'EC; EX'),
 ('Study Medication Administration Platinum', 'EC; EX'),
 ('Study Medication Administration Zipalertinib', 'EC; EX'),
 ('Study Registration', 'RP'),
 ('Subject', 'DM; DS'),
 ('Subject Continuation', 'PR'),
 ('Subject Enrollment', 'DM'),
 ('Subject Identification', 'DM'),
 ('Subject Re-Consent', 'DS'),
 ('Subsequent Cancer Therapies', 'PR; AE'),
 ('Subsequent New Anticancer Therapy', 'PR; CM'),
 ('Subsequent New Anticancer Therapy Y/N?', 'CM; PR'),
 ('Subsequent Tumor Assessment', 'TU; TR'),
 ('Substance Use', 'SU; CO'),
 ('Sunitinib Administration Log', 'EC'),
 ('Sunitinib Dosing Log', 'EX'),
 ('Sunitinib Drug Compliance Log', 'DA'),
 ('Supplemental Injection Criteria (after Week 8)', 'FA'),
 ('Supplemental Therapy', 'CM'),
 ('Survival Follow-Up', 'SS; DS'),
 ('Survival Status', 'SS; PR'),
 ('Survival Sweep', 'SS'),
 ('T MRI', 'PR'),
 ('T MRS', 'PR'),
 ('Target Lesion', 'TU; TR'),
 ('Target Lesion / Baseline', 'TU; TR'),
 ('Target Lesion / Post Baseline', 'TU; TR'),
 ('Target Lesion Assessment', 'TU; TR'),
 ('Target Lesion Assessment Screening', 'TU; TR'),
 ('TB, Lymphocyte phenotyping, Immunoelectrophoresis and IgG - Central', 'LB; MB; IS'),
 ('Tobacco Use', 'SU'),
 ('Transfusions', 'PR'),
 ('Transfusions Y/N?', 'PR'),
 ('Treatment - Temporary Discontinuation', 'EC; EX; AE'),
 ('Treatment Assignment/Randomization', 'DM; DS'),
 ('Treatment Beyond Progression', 'DM'),
 ('Treatment Schedule', 'EX'),
 ('Trough Sirolimus Concentration - Local Lab', 'PC'),
 ('Tuberculosis Test - Local Lab', 'MB'),
 ('Tumor Assessment', 'TU; TR'),
 ('Tumor Assessment for New Lesions (RECIST 1.1)', 'TU; TR'),
 ('Tumor Assessment for New Lesions (RECIST 1.1) - Post Baseline', 'TU; TR'),
 ('Tumor Assessment for Non-Target Lesions (RECIST 1.1)', 'TU; TR'),
 ('Tumor Assessment for Non-Target Lesions (RECIST 1.1) - Baseline', 'TU; TR'),
 ('Tumor Assessment for Non-Target Lesions (RECIST 1.1) - Post Baseline', 'TU; TR'),
 ('Tumor Assessment for Target Lesions (RECIST 1.1)', 'TU; TR'),
 ('Tumor Assessment for Target Lesions (RECIST 1.1) - Baseline', 'TU; TR'),
 ('Tumor Assessment for Target Lesions (RECIST 1.1) - Post Baseline', 'TU; TR'),
 ('Tumor Assessment Screening', 'TU; TR'),
 ('Tumor Assessment Visit', 'TU; TR'),
 ('Tumor Biopsy', 'PR'),
 ('Tumor Biopsy Markers', 'FA'),
 ('Tumor Evaluations (RECIST 1.1)', 'TU; TR'),
 ('Tumor Mutations', 'FA'),
 ('Tumor Results: New Lesions (RECIST 1.1)', 'TU; TR'),
 ('Tumor Results: New Lesions RANO-BM', 'TU; TR'),
 ('Tumor Results: Non-Target Lesions (RECIST 1.1)', 'TU; TR'),
 ('Tumor Results: Non-Target Lesions RANO-BM', 'TU; TR'),
 ('Tumor Results: Target Lesions (RECIST 1.1)', 'TU; TR'),
 ('Tumor Results: Target Lesions RANO-BM', 'TU; TR'),
 ('Tumor Sample', 'PR'),
 ('Tumor Tissue Sample Consent', 'DS'),
 ('Tumor Tissue Sampling', 'MI; CO'),
 ('UHDRS', 'RS; CO; DS'),
 ('Un-Blinding', 'DS'),
 ('Unblinded 3T MRI', 'PR'),
 ('Unblinded 3T MRS', 'PR'),
 ('Unblinded Adverse Events', 'AE; DM; TR'),
 ('Unblinded Adverse Events YN', 'AE'),
 ('Unblinded AMT-130 Administration', 'EC; CO; RE'),
 ('Unblinded AMT-130 Thaw Dates and Times', 'FA'),
 ('Unblinded Anesthesia Worksheet', 'PR; EX; CO'),
 ('Unblinded Contrast Agent Diluent Preparation - Low Dose Kit', 'CO'),
 ('Unblinded CSF Local Laboratory', 'LB'),
 ('Unblinded CSF Local Laboratory Gram Stain, Culture, Sensitivity', 'MB; LB; SE'),
 ('Unblinded Drug Product Diluent Preparation - Low Dose Kit', 'CO'),
 ('Unblinded Hospitalization Worksheet', 'CO; HO'),
 ('Unblinded IP Accountability', 'FA; CO'),
 ('Unblinded L Anterior Putamen Coordinates and Changes in Infusion Rate', 'CO; FA'),
 ('Unblinded L Caudate Coordinates and Changes in Infusion Rate and', 'CO; FA'),
 ('Unblinded L Posterior Putamen Coordinates and Changes in Infusion Rate', 'CO; FA'),
 ('Unblinded Neurosurgical Procedure', 'PR; DS; SE'),
 ('Unblinded Non-Drug Therapies', 'PR; AE; MH'),
 ('Unblinded Opening Lumbar Puncture Pressure', 'VS'),
 ('Unblinded Prior and Concomitant Medication YN', 'CM'),
 ('Unblinded Prior and Concomitant Medications', 'CM; DS'),
 ('Unblinded R Anterior Putamen Coordinates and Changes in Infusion Rate', 'CO; FA'),
 ('Unblinded R Caudate Coordinates and Changes in Infusion Rate and', 'CO; FA'),
 ('Unblinded R Posterior Putamen Coordinates and Changes in Infusion Rate', 'CO; FA'),
 ('Unblinded Serious Adverse Events', 'AE; DM'),
 ('Unblinded Study Drug Dispensation', 'DM'),
 ('Unblinded Subject Transfer', 'DM; TR'),
 ('Unblinded Surgical Photography Consent', 'DS'),
 ('Unblinded Vector Shedding', 'LB'),
 ('Unscheduled Assessment', 'MI'),
 ('Unscheduled Assessments', 'SV; PR; LB'),
 ('Unscheduled Forms', 'SV; PR; TR'),
 ('Unscheduled Forms Cohort 3', 'SV'),
 ('Unscheduled Forms Crossover', 'SV'),
 ('Unscheduled Forms Crossover Baseline', 'SV'),
 ('Unscheduled Forms Crossover Re Screening', 'SV'),
 ('Unscheduled Forms Long Term Follow-Up', 'SV'),
 ('Unscheduled PK Blood Sampling', 'PC; CO'),
 ('Unscheduled PK Dosing and Meal Record', 'CO'),
 ('Unscheduled Visit', 'SV; PR; CO'),
 ('Urinalysis', 'LB'),
 ('Urinalysis Local Lab', 'LB'),
 ('Urinalysis-Central Laboratory', 'LB'),
 ('Urine Drug Screen', 'LB; PR; CO'),
 ('Urine Pregnancy Test', 'LB; PR'),
 ('Vector Shedding', 'LB'),
 ('Viral Screening', 'LB'),
 ('Viral Tests', 'LB'),
 ('Vision Questionnaires', 'QS'),
 ('Visit', 'SV'),
 ('Visit - Additional Cycle', 'SV'),
 ('Visit - Screening', 'SV'),
 ('Visit Continuation', 'PR'),
 ('Visit Data Records', 'SE'),
 ('Visit Date', 'SV; PR'),
 ('Visit Information', 'SV'),
 ('Visual Acuity', 'OE'),
 ('Vital Signs (Screening/End of Treatment)', 'VS; RE'),
 ('Vital Signs - 30 Day Follow-Up', 'VS; RE'),
 ('Vital Signs - C1D1', 'VS; RE'),
 ('Vital Signs - Infusion Day 4/8', 'VS; RE'),
 ('Vital Signs - Non-Infusion Day', 'VS; RE'),
 ('Vital Signs - Screening', 'VS; RE'),
 ('Vital Signs - Unscheduled', 'VS; RE'),
 ('Vital Signs Day 8 and 15', 'VS; RE'),
 ('Vital Signs-with Height and Weight', 'VS; CO'),
 ('Vitamin A Quiz', 'FA'),
 ('von Willebrand Factor (vWF antigen (Ag))', 'LB'),
 ('Waist Circumference', 'VS; PR'),
 ('Weight', 'VS'),
 ('Withdrawal of Optional Informed Consents', 'DS; PR'),
 ('XTX301 Administration', 'EX; PR; EC'),
 ('Subject Visits', 'SV'),
 ('Findings About Events or Interventions', 'FA'),
 ('Laboratory Test Results', 'LB'),
 ('Reproductive System Findings', 'RP'),
 ('Pharmacokinetics Parameters', 'PP'),
 ('ECG Test Results', 'EG'),
 ('Microscopic Findings', 'MI'),
 ('Pulmonary Function Tests', 'RE'),
 ('Healthcare Encounters', 'HO'),
 ('Protocol Deviations', 'DV'),
 ('Subject Status', 'SS')]

# Compatibility table for existing mapper code.
DOMAIN_MAPPING_GUIDE: list[dict[str, str]] = [
    {
        "crf_content": row[0],
        "preferred_domain_approach": row[1],
    }
    for row in HISTORICAL_FORM_DOMAIN_GUIDE
]

# No legacy hand-written rules in this clean version.
CRF_CONCEPT_DOMAIN_RULES: list[dict[str, Any]] = []
UNDERSTANDING_FALLBACK_DOMAIN_RULES: list[dict[str, Any]] = []

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "by", "for", "from", "if", "in", "into", "is", "of", "on",
    "or", "per", "the", "to", "was", "were", "with", "without", "form", "page", "section", "title",
    "visit", "cycle", "day", "week", "month", "timepoint", "time", "pre", "post", "dose", "predose",
    "postdose", "uns", "unscheduled", "central", "local", "single", "repeat", "repeated", "baseline",
    "screening", "follow", "up", "long", "term", "part", "period", "phase", "version",
}

IMPORTANT_SINGLE_TOKENS = {
    "ae", "cm", "dm", "ds", "ecg", "eg", "lb", "mh", "pe", "pk", "qs", "recist", "vs",
    "demographics", "laboratory", "medications", "consent", "disposition", "eligibility",
}

SYNONYMS = {
    "adverse events": "ae",
    "adverse event": "ae",
    "electrocardiogram": "ecg",
    "electrocardiograms": "ecg",
    "concomitant medication": "concomitant medications",
    "concomitant meds": "concomitant medications",
    "medication": "medications",
    "meds": "medications",
    "demography": "demographics",
    "pharmacokinetic": "pk",
    "pharmacokinetics": "pk",
    "reconsent": "consent",
    "re consent": "consent",
    "re-consent": "consent",
    "tumor": "tumour",
}

TIMING_PAREN_RE = re.compile(
    r"\((?:pre|post|predose|postdose|dose|timepoint|cycle|day|week|month|screening|baseline|uns|unscheduled|phase)[^)]*\)",
    re.IGNORECASE,
)
VERSION_RE = re.compile(r"\s*[-?]\s*\d+(?:\.\d+){1,4}\s*$")
CYCLE_DAY_RE = re.compile(r"\b(?:cycle|c)\s*\d+\s*(?:day|d)\s*\d+\b", re.IGNORECASE)
DAY_RE = re.compile(r"\b(?:day|d)\s*-?\d+\b", re.IGNORECASE)
WEEK_RE = re.compile(r"\b(?:week|wk)\s*-?\d+\b", re.IGNORECASE)


def normalize_form_name(value: str) -> str:
    """Normalize CRF form names before exact/semantic matching."""
    text = str(value or "").casefold().strip()
    text = VERSION_RE.sub(" ", text)
    text = TIMING_PAREN_RE.sub(" ", text)
    text = CYCLE_DAY_RE.sub(" ", text)
    text = DAY_RE.sub(" ", text)
    text = WEEK_RE.sub(" ", text)
    text = text.replace("&", " and ")
    text = re.sub(r"\bnon\s*[- ]\s*target\b", "nontarget", text)
    text = re.sub(r"\b12\s*[- ]?\s*lead\b", "12 lead", text)
    text = re.sub(r"\by\s*/\s*n\b|\byes\s*/\s*no\b", " yn ", text)
    for old, new in SYNONYMS.items():
        text = re.sub(rf"\b{re.escape(old)}\b", new, text)
    text = re.sub(r"\b\d+(?:\.\d+)*\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# Compatibility alias used by existing code.
normalize_text = normalize_form_name


def tokenize(value: str) -> set[str]:
    return {
        token
        for token in normalize_form_name(value).split()
        if len(token) > 1 and token not in STOP_WORDS
    }


def token_similarity(left: str, right: str) -> tuple[float, list[str]]:
    """Return confidence-like similarity and matched normalized tokens."""
    left_norm = normalize_form_name(left)
    right_norm = normalize_form_name(right)
    left_tokens = tokenize(left)
    right_tokens = tokenize(right)
    matched_terms = sorted(left_tokens & right_tokens)

    if not left_norm or not right_norm:
        return 0.0, matched_terms
    if left_norm == right_norm:
        return 0.95, matched_terms
    if not left_tokens or not right_tokens:
        return round(SequenceMatcher(None, left_norm, right_norm).ratio() * 0.60, 3), matched_terms

    overlap = len(matched_terms) / max(len(left_tokens), len(right_tokens))
    containment = len(matched_terms) / min(len(left_tokens), len(right_tokens))
    fuzzy = SequenceMatcher(None, left_norm, right_norm).ratio()
    base_score = (0.55 * overlap) + (0.20 * containment) + (0.25 * fuzzy)

    if matched_terms and left_tokens <= right_tokens:
        subset_score = 0.90 if len(matched_terms) >= 2 else 0.87
        return round(max(subset_score, base_score), 3), matched_terms

    if matched_terms and right_tokens <= left_tokens:
        if len(right_tokens) == 1 and next(iter(right_tokens)) not in IMPORTANT_SINGLE_TOKENS:
            subset_score = 0.70
        else:
            subset_score = 0.87 if len(right_tokens) == 1 else 0.84
        return round(max(subset_score, base_score), 3), matched_terms

    return round(base_score, 3), matched_terms


def domain_codes(value: str | None) -> list[str]:
    """Extract SDTM domain codes while preserving their mapping order."""
    codes: list[str] = []
    for code in re.findall(r"\b[A-Z]{2,8}\b", str(value or "").upper()):
        if code not in codes:
            codes.append(code)
    return codes


def _content_supports_domains(page_text: str | None, domains: str) -> bool:
    """Optional confirmation for lower-confidence fuzzy matches."""
    if not page_text:
        return False
    text = normalize_form_name(page_text)
    for code in domain_codes(domains):
        if _domain_supported_by_text(code, text):
            return True
    return False


DOMAIN_TEXT_SUPPORT_PATTERNS: dict[str, list[str]] = {
    "AE": [r"\badverse event\b", r"\bae\b", r"\bserious\b", r"\bseverity\b", r"\bcausality\b", r"\boutcome\b"],
    "CM": [r"\bconcomitant medication\b", r"\bprior medication\b", r"\bmedications?\b", r"\btherapy\b"],
    "CO": [r"^comments?$", r"^general comments?$", r"^additional comments?$"],
    "DA": [r"\baccountability\b", r"\bdispensed\b", r"\breturned\b", r"\bcompliance\b", r"\bkit\b", r"\bbottle\b"],
    "DD": [r"\bdeath\b", r"\bdied\b", r"\bcause of death\b"],
    "DM": [r"\bdemographics?\b", r"\bsubject id\b", r"\bsubject number\b", r"\bsite number\b", r"\bparticipant id\b", r"\bbirth\b", r"\bage\b", r"\bsex\b", r"\brace\b", r"\bethnicity\b", r"\binformed consent\b"],
    "DS": [r"\bdisposition\b", r"\bend of study\b", r"\bend of treatment\b", r"\bwithdraw", r"\bcompletion\b", r"\binformed consent\b", r"\breconsent\b", r"\bre consent\b", r"\bassent\b", r"\bprotocol version\b", r"\brandomi[sz]"],
    "EC": [r"\bstudy drug\b", r"\bstudy treatment\b", r"\bdose\b", r"\bdosing\b", r"\badministration\b", r"\binfusion\b", r"\binjection\b"],
    "EX": [r"\bstudy drug\b", r"\bstudy treatment\b", r"\bdose\b", r"\bdosing\b", r"\badministration\b", r"\binfusion\b", r"\binjection\b", r"\bexposure\b"],
    "EG": [r"\becg\b", r"\belectrocardiogram\b", r"\bqtc\b", r"\bqrs\b", r"\bpr interval\b"],
    "FA": [r"\bfindings? about\b", r"\bgenetic\b", r"\bmutation\b", r"\bgenotype\b", r"\babnormalit"],
    "HO": [r"\bhospitali[sz]ation\b", r"\badmission\b", r"\bdischarge\b", r"\bicu\b"],
    "IE": [r"\beligib", r"\binclusion\b", r"\bexclusion\b", r"\bcriteria\b", r"\bcriterion\b"],
    "IS": [
        r"\bimmunogenicity\b",
        r"\bimmunogenicity response\b",
        r"\b(?:vaccine|immunotherapy|study treatment|drug)[- ]?specific antibod",
        r"\b(?:antibody|neutralizing antibody|nab)\s+tit(?:er|re)s?\b",
        r"\bada\b",
    ],
    "LB": [r"\blab\b", r"\blaboratory\b", r"\bhematology\b", r"\bchemistry\b", r"\burinalysis\b", r"\bpregnancy\b", r"\bspecimen\b", r"\bsample\b", r"\bresult\b"],
    "MB": [r"\bmicrobiology\b", r"\bculture\b", r"\bswab\b"],
    "MH": [r"\bmedical history\b", r"\bdisease history\b", r"\bhistory of disease\b", r"\bdiagnosis\b", r"\bcondition\b"],
    "MI": [r"\bmicroscopic\b", r"\bhistology\b", r"\bpathology\b", r"\bbiopsy\b"],
    "OE": [r"\bophthalm", r"\bocular\b", r"\beye\b", r"\bvision\b", r"\bretina\b"],
    "PC": [r"\bpk\b", r"\bpharmacokinetic\b", r"\bconcentration\b"],
    "PE": [r"\bphysical examination\b", r"\bexam\b", r"\bbody system\b"],
    "PP": [r"\bauc\b", r"\bcmax\b", r"\btmax\b", r"\bpk parameter\b"],
    "PR": [r"\bprocedure\b", r"\bsurgery\b", r"\bbiopsy\b", r"\bradiation\b", r"\bradiotherapy\b", r"\bscan\b", r"\bimaging\b", r"\bultrasound\b", r"\bx[- ]?ray\b"],
    "QS": [r"\bquestionnaire\b", r"\bquality of life\b", r"\bscore\b", r"\bscale\b", r"\becog\b", r"\bperformance status\b", r"\bpedsql\b", r"\beq 5d\b"],
    "RE": [r"\brespiratory\b", r"\bpulmonary\b", r"\bspirometry\b", r"\bdlco\b", r"\boxygen saturation\b"],
    "RP": [r"\breproductive\b", r"\bchildbearing\b", r"\bpregnancy\b", r"\bmenopaus", r"\bcontraception\b"],
    "RS": [r"\brecist\b", r"\bresponse\b", r"\boverall response\b", r"\bdisease response assessed\b"],
    "SS": [r"\bsubject status\b", r"\bsurvival status\b", r"\balive\b"],
    "SV": [r"\bvisit\b", r"\bvisit date\b", r"\bwas the visit performed\b", r"\bclinic visit\b", r"\bhome health visit\b", r"\bphone contact\b", r"\btelephone\b", r"\bfollow[- ]?up\b", r"\bunscheduled\b"],
    "TR": [r"\blesion\b", r"\btumou?r\b", r"\bmeasurement\b"],
    "TU": [r"\blesion\b", r"\btumou?r\b", r"\btarget\b", r"\bnon[- ]?target\b", r"\bidentification\b"],
    "VS": [r"\bvital\b", r"\bblood pressure\b", r"\bpulse\b", r"\btemperature\b", r"\bheight\b", r"\bweight\b", r"\bbmi\b"],
}


def _domain_supported_by_text(domain: str, normalized_text: str) -> bool:
    return any(re.search(pattern, normalized_text) for pattern in DOMAIN_TEXT_SUPPORT_PATTERNS.get(domain, []))


def _prune_candidate_domains_by_content(candidate: dict[str, Any], page_text: str | None) -> dict[str, Any] | None:
    if not page_text:
        return candidate
    text = normalize_form_name(page_text)
    original_codes = domain_codes(candidate.get("preferred_domain_approach", ""))
    if not original_codes:
        return candidate
    kept_codes = [code for code in original_codes if _domain_supported_by_text(code, text)]
    if not kept_codes:
        return None
    if kept_codes == original_codes:
        return candidate

    pruned = dict(candidate)
    pruned["preferred_domain_approach"] = "; ".join(kept_codes)
    pruned["domains"] = "; ".join(kept_codes)
    pruned["domain_labels"] = ""
    removed = [code for code in original_codes if code not in kept_codes]
    note = f"Historical domains pruned by page text; removed unsupported domain(s): {', '.join(removed)}."
    pruned["rationale"] = note
    pruned["multiple_domain_rationale"] = note
    pruned["match_type"] = f"{candidate.get('match_type', 'historical')}_content_pruned"
    return pruned


def _candidate_from_record(record: tuple[str, str], confidence: float, match_type: str, matched_terms: list[str]) -> dict[str, Any]:
    rationale = f"Historical {match_type} match to {record[0]}."
    return {
        "confidence": round(float(confidence), 3),
        "score": round(float(confidence), 3),
        "match_type": match_type,
        "matched_terms": matched_terms,
        "crf_content": record[0],
        "historical_form": record[0],
        "preferred_domain_approach": record[1],
        "domain_labels": "",
        "multiple_domain_rationale": "",
        "rationale": rationale,
    }


def historical_form_candidates(
    form_name: str,
    page_text: str | None = None,
    fuzzy_min_confidence: float = 0.86,
    supported_fuzzy_min_confidence: float = 0.75,
) -> list[dict[str, Any]]:
    """Return exact, normalized, and fuzzy historical form-name candidates."""
    raw = str(form_name or "").strip()
    normalized = normalize_form_name(raw)
    if not raw and not normalized:
        return []

    exact: list[dict[str, Any]] = []
    normalized_matches: list[dict[str, Any]] = []
    fuzzy: list[dict[str, Any]] = []

    for record in HISTORICAL_FORM_DOMAIN_GUIDE:
        guide_name = record[0]
        if raw.casefold() == guide_name.casefold():
            exact.append(_candidate_from_record(record, 1.0, "historical_exact", sorted(tokenize(raw))))
            continue

        guide_norm = normalize_form_name(guide_name)
        if normalized and normalized == guide_norm:
            normalized_matches.append(
                _candidate_from_record(record, 0.95, "historical_normalized", sorted(tokenize(raw) & tokenize(guide_name)))
            )
            continue

        confidence, matched_terms = token_similarity(raw, guide_name)
        content_supported = confidence >= supported_fuzzy_min_confidence and _content_supports_domains(page_text, record[1])
        if confidence >= fuzzy_min_confidence or content_supported:
            fuzzy.append(_candidate_from_record(record, confidence, "historical_fuzzy", matched_terms))

    sort_key = lambda item: item["confidence"]
    def content_pruned(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        pruned: list[dict[str, Any]] = []
        for item in items:
            candidate = _prune_candidate_domains_by_content(item, page_text)
            if candidate:
                pruned.append(candidate)
        return pruned

    if exact:
        return sorted(content_pruned(exact), key=sort_key, reverse=True)
    if normalized_matches:
        return sorted(content_pruned(normalized_matches), key=sort_key, reverse=True)
    return sorted(content_pruned(fuzzy), key=sort_key, reverse=True)


CRITERIA_FORM_NAME_PATTERNS = [
    r"^eligibility criteria$",
    r"^inclusion criteria$",
    r"^exclusion criteria$",
    r"^inclusion and exclusion criteria$",
    r"^inclusion exclusion criteria$",
]


def criteria_form_candidate(form_name: str) -> dict[str, Any] | None:
    """Criteria pages map to IE even when the criteria mention drugs/procedures."""
    form_text = normalize_form_name(str(form_name or ""))
    if not any(re.search(pattern, form_text) for pattern in CRITERIA_FORM_NAME_PATTERNS):
        return None
    rationale = (
        "Criteria form text supports IE. Do not add EX, CM, PR, or other domains merely "
        "because a criterion mentions treatment, medication, procedure, dose, or study drug."
    )
    return {
        "confidence": 0.99,
        "score": 0.99,
        "match_type": "criteria_form_override",
        "matched_terms": [form_name],
        "crf_content": "Eligibility/Inclusion/Exclusion Criteria",
        "historical_form": "",
        "preferred_domain_approach": "IE",
        "domain_labels": "",
        "multiple_domain_rationale": rationale,
        "rationale": rationale,
    }


DEATH_DETAILS_FORM_NAME_PATTERNS = [
    r"^death$",
    r"^death details?$",
    r"^death report$",
    r"^death/autopsy$",
]

DEATH_DETAILS_CONTENT_PATTERNS = [
    r"\bdate of death\b",
    r"\bprimary cause of death\b",
    r"\bcause of death\b",
    r"\bautopsy\b",
]


def death_details_candidate(form_name: str, page_text: str | None = None) -> dict[str, Any] | None:
    """Protect Death CRF pages from being pruned to AE by conditional AE wording."""
    form_text = normalize_form_name(str(form_name or ""))
    text = normalize_form_name(" ".join([str(form_name or ""), str(page_text or "")]))
    if not any(re.search(pattern, form_text) for pattern in DEATH_DETAILS_FORM_NAME_PATTERNS):
        return None
    matched = [pattern for pattern in DEATH_DETAILS_CONTENT_PATTERNS if re.search(pattern, text)]
    if not matched:
        return None
    rationale = (
        "Death form content supports DD and DM. Conditional adverse-event wording on the page "
        "does not make AE the page domain."
    )
    return {
        "confidence": 0.99,
        "score": 0.99,
        "match_type": "death_details_override",
        "matched_terms": matched,
        "crf_content": "Death details",
        "historical_form": "",
        "preferred_domain_approach": "DD; DM",
        "domain_labels": "",
        "multiple_domain_rationale": rationale,
        "rationale": rationale,
    }


FORM_TITLE_DOMAIN_OVERRIDES: list[tuple[str, str, str]] = [
    (r"^subject enrollment$", "DM", "Subject enrollment identifiers support DM."),
    (r"^date of visit$", "SV", "Visit date pages support SV."),
    (r"^childbearing potential$", "RP", "Childbearing potential pages collect reproductive-system findings; do not infer MH from response-option history wording."),
    (r"^demographics?$", "DM", "Demographics pages support DM."),
    (r"^physical examination$", "PE", "Physical Examination pages support PE only; do not add PR for the exam-performed question."),
    (r"^pk blood sampling(?:\s*-\s*\d+)?$", "PC", "PK blood sampling pages support PC only unless a visible comments field is collected."),
    (r"^unscheduled pk blood sampling$", "PC", "Unscheduled PK blood sampling pages support PC only unless a visible comments field is collected."),
    (r"^medical surgical history unrelated to cancer under investigation yn$", "MH", "Medical/surgical history Y/N pages support MH occurrence/status."),
    (r"^tumou?r molecular genetic testing yn$", "FA", "Tumor molecular/genetic testing Y/N pages support FA."),
    (r"^(adverse events|ae) yn$", "AE", "Adverse event Y/N pages support AE occurrence/status."),
    (r"^gate non cancer prior and concomitant$", "CM; PR", "Prior/concomitant gate pages collect medication/procedure occurrence triggers."),
    (r"^gate prior cancer$", "CM; PR", "Prior cancer gate pages collect prior therapy/procedure occurrence triggers."),
    (r"^gate post(?: post treatment)?$", "CM; PR", "Post-treatment gate pages collect subsequent therapy/procedure occurrence triggers."),
    (r"^(reconsent|consent) form yn$", "DS", "Reconsent Y/N pages support DS protocol milestone disposition."),
    (r".*infection related events?.*", "CE; MB; HO", "Infection-related event pages collect clinical event details first, with microbiology and healthcare encounter details when present."),
    (r"^eligibility$", "IE", "Eligibility status/criteria pages support IE."),
    (r"^eq[- ]?5d[- ]?5l$", "QS", "EQ-5D-5L is a questionnaire/scale assessment and supports QS."),
    (r".*\b(patient|clinician|clinical)\s+global impression\b.*", "QS", "Global impression instruments are questionnaire/scale assessments."),
    (r".*\bpgi[- ]?[cs]\b.*", "QS", "PGI-C/PGI-S instruments are questionnaire assessments."),
    (r".*\bpedsql\b.*", "QS", "PedsQL instruments are pediatric quality-of-life questionnaire assessments and support QS."),
    (r"^cancer history$", "FA; MH", "Cancer history pages are findings about cancer history first (FA), with MH as supporting history."),
    (r"^tumo[u]?r molecular genetic testing results.*$", "FA", "Tumor molecular/genetic testing results are findings about tumor characteristics."),
    (r"^local laboratory .*$", "LB", "Local laboratory result pages support LB."),
    (r"^serum cortisol and adrenocorticotrophic hormone.*$", "LB", "Serum laboratory result pages support LB."),
    (r"^blood for exploratory biomarkers$", "LB", "Biomarker blood result/sample pages support LB."),
    (r"^biomarker collection - serum immunoglobulins$", "LB", "Serum immunoglobulin collection is a conventional quantitative/qualitative laboratory assessment; use LB, not IS."),
    (r".*\b(?:serum )?immunoglobulins?\b.*", "LB", "Routine immunoglobulin measurements are laboratory test results unless the form explicitly collects immunogenicity response, titers, or treatment-specific antibodies."),
    (r".*\b(?:biomarker|protein)\s+expression\b.*", "IS", "Biomarker/protein expression assessments are mapped to IS by project convention."),
    (r".*\b(?:immunostain|immunostaining|staining)\b.*", "IS", "IHC/immunostain expression assessments are mapped to IS by project convention."),
    (r".*\b(?:immunogenicity|vaccine|immunotherapy|study treatment|drug)[- ]?(?:specific )?(?:antibody|antibodies|response|tit(?:er|re)s?)\b.*", "IS", "Immunogenicity response, vaccine/immunotherapy-specific antibodies, and antibody titers support IS."),
    (r".*\b(?:antibody|neutralizing antibody|nab)\s+tit(?:er|re)s?\b.*", "IS", "Antibody titers are immunogenicity specimen assessment results and support IS."),
    (r"^serum for tumo[u]?r biomarkers$", "LB", "Tumor biomarker serum result/sample pages support LB."),
    (r".*questionnaire.*", "QS", "Questionnaire pages support QS."),
    (r"^vital signs$", "VS", "Vital signs pages support VS; respiratory-rate text does not make the page RE."),
    (r"^administration of .*$", "EC; EX", "Study product administration pages support EC/EX."),
    (r"^spect ct dosimetry imaging$", "PR", "Imaging procedure pages support PR."),
    (r"^tumo[u]?r identification.*non[- ]?target lesions.*$", "TU; TR", "Non-target lesion identification pages support TU/TR."),
    (r"^tumo[u]?r identification.*target lesions.*$", "TU; TR", "Target lesion identification pages support TU/TR."),
    (r"^tumo[u]?r identification.*new lesions.*$", "TU; TR", "New lesion identification pages support TU/TR."),
    (r"^tumo[u]?r assessment for target lesions.*$", "TU; TR", "Target lesion assessment pages support TU/TR."),
    (r"^tumo[u]?r assessment for non target lesions.*$", "TU; TR", "Non-target lesion assessment pages support TU/TR."),
    (r"^tumo[u]?r assessment for new lesions.*$", "TU; TR", "New lesion assessment pages support TU/TR."),
    (r"^disease response$", "RS", "Disease response pages collect response assessment results and should retain RS over lesion-identification fallback rules."),
    (r"^response assessment.*$", "RS", "Response assessment pages collect disease response assessment results. Procedure or surgery wording in the title is timing/context, not a submitted PR procedure record."),
    (r"^next visit cycle$", "SV", "Next visit/cycle pages support SV."),
    (r"^end of treatment$", "DS", "End of treatment disposition pages support DS."),
    (r"^adverse events$", "AE", "Adverse event pages support AE."),
    (r"^prior and concomitant blood transfusions$", "PR", "Blood transfusion records are procedure records."),
    (r"^prior and concomitant medical procedures interventions$", "PR", "Medical procedure/intervention records support PR."),
    (r"^unscheduled forms$", "SV", "Unscheduled visit/form pages support SV only."),
]


STRONG_CONTENT_DOMAIN_EXPANSION_RULES: dict[str, list[dict[str, Any]]] = {
    "RP": [
        {
            "patterns": [
                r"\bchildbearing potential\b",
                r"\bpatient of childbearing potential\b",
                r"\bsubject of childbearing potential\b",
                r"\bfemale\b.*\bchildbearing potential\b",
            ],
            "evidence": "childbearing potential",
        },
        {
            "patterns": [
                r"\bpost[- ]?menopausal\b",
                r"\bpre[- ]?menopausal\b",
                r"\bmenopause\b",
                r"\bmenopausal status\b",
            ],
            "evidence": "menopausal status",
        },
        {
            "patterns": [
                r"\bmethod of contraception\b",
                r"\bcontraception \(check all that apply\)",
                r"\bcontraceptive method\b",
            ],
            "evidence": "contraception method",
        },
        {
            "patterns": [
                r"\bhysterectomy\b",
                r"\boophorectomy\b",
                r"\bvasectomized partner\b",
            ],
            "evidence": "reproductive status procedure",
        },
    ],
}


def _domain_codes_text(domains: str | None) -> list[str]:
    return [
        code
        for code in re.split(r"[^A-Za-z0-9]+", str(domains or "").upper())
        if code
    ]


def strong_content_domain_expansions(
    page_text: str | None,
    existing_domains: str | None,
) -> list[dict[str, Any]]:
    """Return only very high-confidence content domains to append to title overrides."""
    text = normalize_form_name(str(page_text or ""))
    if not text:
        return []
    existing = set(_domain_codes_text(existing_domains))
    expansions: list[dict[str, Any]] = []
    for domain, rules in STRONG_CONTENT_DOMAIN_EXPANSION_RULES.items():
        if domain in existing:
            continue
        evidence = [
            rule["evidence"]
            for rule in rules
            if any(re.search(pattern, text) for pattern in rule["patterns"])
        ]
        if evidence:
            expansions.append(
                {
                    "domain": domain,
                    "evidence": sorted(set(evidence)),
                }
            )
    return expansions


def expand_candidate_with_strong_content(
    candidate: dict[str, Any],
    page_text: str | None,
) -> dict[str, Any]:
    expansions = strong_content_domain_expansions(
        page_text,
        str(candidate.get("preferred_domain_approach") or candidate.get("domain") or ""),
    )
    if not expansions:
        return candidate

    updated = dict(candidate)
    existing_domains = _domain_codes_text(str(updated.get("preferred_domain_approach") or ""))
    for expansion in expansions:
        domain = expansion["domain"]
        if domain not in existing_domains:
            existing_domains.append(domain)
    updated["preferred_domain_approach"] = "; ".join(existing_domains)
    evidence_text = "; ".join(
        f"{expansion['domain']} from {', '.join(expansion['evidence'])}"
        for expansion in expansions
    )
    updated["match_type"] = f"{updated.get('match_type', 'candidate')}_with_strong_content_expansion"
    updated["multiple_domain_rationale"] = "Strong page-content evidence appended secondary domain(s): " + evidence_text
    updated["rationale"] = f"{updated.get('rationale', '')} Strong page-content evidence appended secondary domain(s): {evidence_text}".strip()
    return updated


def form_title_override_candidate(form_name: str) -> dict[str, Any] | None:
    """High-confidence form-title mappings that should not be overridden by stray body terms."""
    form_text = normalize_form_name(str(form_name or ""))
    for pattern, domains, rationale in FORM_TITLE_DOMAIN_OVERRIDES:
        if re.search(pattern, form_text):
            return {
                "confidence": 0.99,
                "score": 0.99,
                "match_type": "form_title_override",
                "matched_terms": [form_name],
                "crf_content": form_name,
                "historical_form": "",
                "preferred_domain_approach": domains,
                "domain_labels": "",
                "multiple_domain_rationale": rationale,
                "rationale": rationale,
            }
    return None


def vaccination_context_candidate(form_name: str, page_text: str | None = None) -> dict[str, Any] | None:
    """Context-aware Step 1 mapping for vaccination/immunization forms.

    Vaccinations collected as prior/historical background map to MH. Vaccinations
    collected during the study or concomitant-medication period map to CM. Ambiguous
    vaccination titles intentionally return None so later rules can flag them for
    review instead of relying on a single keyword.
    """
    title = normalize_form_name(str(form_name or ""))
    text = normalize_form_name(" ".join([str(form_name or ""), str(page_text or "")]))
    vaccination_word = r"(?:vaccin\w*|vaccine\w*|immuni[sz]ation\w*)"
    if not re.search(rf"\b{vaccination_word}\b", text):
        return None

    historical_patterns = [
        r"\bvaccin\w*\s+history\b",
        r"\bimmuni[sz]ation\s+history\b",
        rf"\bprior\s+{vaccination_word}\b",
        rf"\bprevious\s+{vaccination_word}\b",
        rf"\bhistory\s+of\s+{vaccination_word}\b",
        r"\bbefore\s+(?:screening|enroll(?:ment)?|study|baseline|first dose)\b",
        r"\bpre[- ]?(?:screening|enroll(?:ment)?|study|baseline|dose)\b",
        r"\bmedical history\b",
        r"\bhistorical background\b",
    ]
    concomitant_patterns = [
        rf"\bconcomitant\s+{vaccination_word}\b",
        r"\bduring\s+(?:the\s+)?study\b",
        r"\bduring\s+(?:treatment|therapy|follow[- ]?up)\b",
        r"\bsince\s+(?:last visit|previous visit|screening|baseline|first dose)\b",
        r"\badminister(?:ed|ation)?\b",
        r"\bongoing\b",
        rf"\bcurrent\s+{vaccination_word}\b",
        r"\bstart date\b",
        r"\bstop date\b",
        r"\bdose\b",
        r"\broute\b",
    ]
    historical_hits = [pattern for pattern in historical_patterns if re.search(pattern, text)]
    concomitant_hits = [pattern for pattern in concomitant_patterns if re.search(pattern, text)]

    if historical_hits and not concomitant_hits:
        domains = "MH"
        rationale = (
            "Vaccination/immunization is collected as prior or historical background; "
            "map to MH unless the SAP treats it as concomitant medication."
        )
        hits = historical_hits
    elif concomitant_hits and not historical_hits:
        domains = "CM"
        rationale = (
            "Vaccination/immunization is collected during the study or concomitant-medication period; "
            "map to CM."
        )
        hits = concomitant_hits
    else:
        return None

    title_specific = re.search(
        rf"\b(vaccin\w*\s+history|immuni[sz]ation\s+history|concomitant\s+{vaccination_word})\b",
        title,
    )
    candidate_confidence = 0.99 if title_specific else 0.88
    return {
        "confidence": candidate_confidence,
        "score": candidate_confidence,
        "match_type": "vaccination_context_rule",
        "matched_terms": hits,
        "crf_content": "Vaccination/immunization context",
        "historical_form": "",
        "preferred_domain_approach": domains,
        "domain_labels": "",
        "multiple_domain_rationale": rationale,
        "rationale": rationale,
    }


def map_form_candidates(
    form_name: str,
    concept_min_confidence: float = 0.55,
    guide_min_confidence: float = 0.35,
    page_text: str | None = None,
) -> list[dict[str, Any]]:
    """Public Step 1 candidate API used by the annotation mapper."""
    if is_operational_or_metadata_form(form_name, page_text):
        return []

    criteria_candidate = criteria_form_candidate(form_name)
    if criteria_candidate:
        return [criteria_candidate]

    death_candidate = death_details_candidate(form_name, page_text=page_text)
    if death_candidate:
        return [death_candidate]

    override_candidate = form_title_override_candidate(form_name)
    if override_candidate:
        return [expand_candidate_with_strong_content(override_candidate, page_text)]

    vaccination_candidate = vaccination_context_candidate(form_name, page_text=page_text)
    if vaccination_candidate:
        return [vaccination_candidate]

    if is_gateway_no_domain_form(form_name, page_text):
        return []

    historical = historical_form_candidates(
        form_name,
        page_text=page_text,
        fuzzy_min_confidence=0.86,
        supported_fuzzy_min_confidence=0.75,
    )
    if historical:
        return historical
    understanding = understanding_fallback_candidates(form_name, page_text=page_text)
    if understanding:
        return understanding
    fallback = best_effort_fallback_candidate(form_name, page_text=page_text)
    return [fallback] if fallback else []


def map_form_to_domain(
    form_name: str,
    concept_min_confidence: float = 0.55,
    guide_min_confidence: float = 0.35,
    page_text: str | None = None,
) -> dict[str, Any] | None:
    """Return the best historical SDTM domain mapping for a CRF form name."""
    candidates = map_form_candidates(
        form_name,
        concept_min_confidence=concept_min_confidence,
        guide_min_confidence=guide_min_confidence,
        page_text=page_text,
    )
    return candidates[0] if candidates else None


def map_forms_to_domains(form_names: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "form_name": form_name,
            "best_mapping": map_form_to_domain(form_name),
            "all_candidates": map_form_candidates(form_name),
        }
        for form_name in form_names
    ]


def concept_candidates(form_name: str, min_confidence: float = 0.55) -> list[dict[str, Any]]:
    """Compatibility wrapper; clean version uses historical candidates only."""
    return historical_form_candidates(form_name, fuzzy_min_confidence=max(min_confidence, 0.86))


def guide_candidates(form_name: str, min_confidence: float = 0.35) -> list[dict[str, Any]]:
    """Compatibility wrapper; clean version uses historical candidates only."""
    return historical_form_candidates(form_name, fuzzy_min_confidence=max(min_confidence, 0.86))


def map_form_candidates_learned_only(
    form_name: str,
    concept_min_confidence: float = 0.55,
    guide_min_confidence: float = 0.35,
) -> list[dict[str, Any]]:
    return map_form_candidates(form_name, concept_min_confidence, guide_min_confidence)


def existing_domain_knowledge_entries() -> list[dict[str, str]]:
    return [
        {
            "crf_content": record[0],
            "preferred_domain_approach": record[1],
            "match_type": "historical_form_name",
        }
        for record in HISTORICAL_FORM_DOMAIN_GUIDE
    ]


def existing_text_candidate(form_name: str) -> dict[str, Any] | None:
    candidates = historical_form_candidates(form_name, fuzzy_min_confidence=0.45, supported_fuzzy_min_confidence=0.45)
    if not candidates:
        return None
    candidate = dict(candidates[0])
    candidate["existing_text"] = candidate["crf_content"]
    candidate["existing_domain"] = candidate["preferred_domain_approach"]
    return candidate


def find_existing_domain_mapping(
    form_name: str,
    concept_min_confidence: float = 0.50,
    guide_min_confidence: float = 0.30,
    similar_min_confidence: float = 0.45,
    strong_pattern_confidence: float = 0.90,
) -> dict[str, Any] | None:
    candidates = historical_form_candidates(
        form_name,
        fuzzy_min_confidence=max(similar_min_confidence, 0.45),
        supported_fuzzy_min_confidence=max(similar_min_confidence, 0.45),
    )
    if not candidates:
        return None
    candidate = dict(candidates[0])
    candidate["existing_text"] = candidate["crf_content"]
    candidate["existing_domain"] = candidate["preferred_domain_approach"]
    return candidate


def is_existing_domain_candidate(
    form_name: str,
    proposed_domain: str | None = None,
    similar_min_confidence: float = 0.45,
) -> bool:
    match = find_existing_domain_mapping(form_name, similar_min_confidence=similar_min_confidence)
    if not match:
        return False
    existing_codes = set(domain_codes(match.get("existing_domain") or match.get("preferred_domain_approach")))
    proposed_codes = set(domain_codes(proposed_domain))
    return not proposed_codes or not existing_codes or proposed_codes == existing_codes


OPERATIONAL_NO_DOMAIN_PATTERNS = [
    r"\boperational\b",
    r"\bmetadata\b",
    r"\bcodelist\b",
    r"\bcode\s*list\b",
    r"\bdata dictionary\b",
    r"\bedit check\b",
    r"\bquery\b",
    r"\baudit trail\b",
    r"\bsystem field\b",
    r"\bhidden field\b",
    r"\bedc only\b",
    r"\bderived\b",
    r"\bnot submitted\b",
]

PAGE_LEVEL_OPERATIONAL_NO_DOMAIN_PATTERNS = [
    r"\bmetadata\b",
    r"\bcodelist\b",
    r"\bcode\s*list\b",
    r"\bdata dictionary\b",
    r"\bedit check\b",
    r"\bquery\b",
    r"\baudit trail\b",
    r"\bcompletion guidelines\b",
]

GATEWAY_NO_DOMAIN_PATTERNS = [
    r"^log forms?\b",
    r"\bselecting yes\b.*\btrigger the appropriate form\b",
]

UNDERSTANDING_DOMAIN_RULES: list[dict[str, Any]] = [
    {"domain": "AE", "concept": "Adverse event", "patterns": [r"\badverse event\b", r"\bserious adverse\b", r"\bae term\b", r"\bseverity\b", r"\bcausality\b"]},
    {"domain": "CM", "concept": "Concomitant/prior medication", "patterns": [r"\bconcomitant medication\b", r"\bprior medication\b", r"\bmedication\b", r"\btherapy\b"]},
    {"domain": "DM", "concept": "Demographics/subject identifiers", "patterns": [r"\bdemograph", r"\bsubject id\b", r"\bsubject number\b", r"\bparticipant id\b", r"\bbirth\b", r"\bsex\b", r"\brace\b", r"\bethnicity\b"]},
    {"domain": "DS", "concept": "Disposition/protocol milestone", "patterns": [r"\bdisposition\b", r"\bend of study\b", r"\bend of treatment\b", r"\bwithdraw", r"\bcompletion\b", r"\brandomi[sz]"]},
    {"domain": "IE", "concept": "Eligibility/inclusion/exclusion", "patterns": [r"\beligib", r"\binclusion\b", r"\bexclusion\b", r"\bcriteria\b", r"\bcriterion\b"]},
    {"domain": "MH", "concept": "Medical history", "patterns": [r"\bmedical history\b", r"\bdisease history\b", r"\bhistory of disease\b", r"\bdiagnosis\b", r"\bcondition\b"]},
    {"domain": "PR", "concept": "Procedure/intervention", "patterns": [r"\bprocedure\b", r"\bsurgery\b", r"\bbiopsy\b", r"\bradiation\b", r"\bradiotherapy\b", r"\bscan\b", r"\bimaging\b"]},
    {"domain": "LB", "concept": "Laboratory/sample/result", "patterns": [r"\blab\b", r"\blaboratory\b", r"\bhematology\b", r"\bchemistry\b", r"\burinalysis\b", r"\bpregnancy\b", r"\bspecimen\b", r"\bsample\b"]},
    {"domain": "VS", "concept": "Vital signs/body measurements", "patterns": [r"\bvital\b", r"\bblood pressure\b", r"\bpulse\b", r"\btemperature\b", r"\bheight\b", r"\bweight\b", r"\bbmi\b"]},
    {"domain": "EG", "concept": "ECG", "patterns": [r"\becg\b", r"\belectrocardiogram\b", r"\bqtc\b", r"\bqrs\b", r"\bpr interval\b"]},
    {"domain": "EC; EX", "concept": "Study treatment administration/exposure", "patterns": [r"\bstudy drug\b", r"\bstudy treatment\b", r"\bdose\b", r"\bdosing\b", r"\badministration\b", r"\binfusion\b", r"\binjection\b"]},
    {"domain": "DA", "concept": "Drug accountability", "patterns": [r"\baccountability\b", r"\bdispensed\b", r"\breturned\b", r"\bcompliance\b", r"\bkit\b", r"\bbottle\b"]},
    {"domain": "SV", "concept": "Subject visit/contact", "patterns": [r"\bvisit\b", r"\bphone contact\b", r"\btelephone\b", r"\bfollow[- ]?up\b", r"\bunscheduled\b"]},
    {"domain": "QS", "concept": "Questionnaire/scale/score", "patterns": [r"\bquestionnaire\b", r"\bquality of life\b", r"\bscore\b", r"\bscale\b", r"\becog\b", r"\bperformance status\b"]},
    {"domain": "RE", "concept": "Respiratory/pulmonary findings", "patterns": [r"\brespiratory\b", r"\bpulmonary\b", r"\bspirometry\b", r"\bdlco\b", r"\boxygen saturation\b"]},
    {"domain": "RS", "concept": "RECIST/tumor response", "patterns": [r"\brecist\b", r"\bresponse\b", r"\boverall response\b", r"\bdisease response assessed\b"]},
    {"domain": "TU; TR", "concept": "Tumor/lesion identification or measurement", "patterns": [r"\btarget lesions?\b", r"\bnon[- ]?target lesions?\b", r"\bnew lesions?\b", r"\blesions?\b", r"\btumo[u]?r identification\b", r"\btumo[u]?r assessment\b", r"\btumo[u]?r result\b", r"\btumo[u]?r measurement\b"]},
    {"domain": "PC", "concept": "PK concentration", "patterns": [r"\bpk\b", r"\bpharmacokinetic\b", r"\bconcentration\b"]},
    {"domain": "PP", "concept": "PK parameter", "patterns": [r"\bauc\b", r"\bcmax\b", r"\btmax\b", r"\bpk parameter\b"]},
    {
        "domain": "IS",
        "concept": "Immunogenicity response",
        "patterns": [
            r"\bimmunogenicity\b",
            r"\bimmunogenicity response\b",
            r"\b(?:biomarker|protein)\s+expression\b",
            r"\b(?:immunostain|immunostaining|staining)\b",
            r"\b(?:vaccine|immunotherapy|study treatment|drug)[- ]?specific antibod",
            r"\b(?:antibody|neutralizing antibody|nab)\s+tit(?:er|re)s?\b",
            r"\bada\b",
        ],
    },
    {"domain": "MB", "concept": "Microbiology", "patterns": [r"\bmicrobiology\b", r"\bculture\b", r"\bswab\b"]},
    {"domain": "MI", "concept": "Microscopic finding", "patterns": [r"\bmicroscopic\b", r"\bhistology\b", r"\bpathology\b"]},
    {"domain": "DV", "concept": "Protocol deviation", "patterns": [r"\bprotocol deviation\b", r"\bdeviation\b"]},
]

COMMENT_FORM_NAME_PATTERNS = [
    r"^comments?$",
    r"^general comments?$",
    r"^additional comments?$",
    r"^other comments?$",
    r"^continuation form$",
]


def is_operational_or_metadata_form(form_name: str, page_text: str | None = None) -> bool:
    """Return True for CRF pages that should not receive an SDTM Domain."""
    form_text = normalize_form_name(str(form_name or ""))
    if any(re.search(pattern, form_text) for pattern in OPERATIONAL_NO_DOMAIN_PATTERNS):
        return True

    # Page text may include hidden/derived EDC helper fields on an otherwise
    # meaningful CRF page. Do not let those helper words suppress Step 1 domain
    # mapping for the whole page; only page-level metadata/reference wording
    # should skip the page here.
    text = normalize_form_name(str(page_text or ""))
    return any(re.search(pattern, text) for pattern in PAGE_LEVEL_OPERATIONAL_NO_DOMAIN_PATTERNS)


def is_gateway_no_domain_form(form_name: str, page_text: str | None = None) -> bool:
    """Return True for Y/N lead-in pages that only open detailed CRF forms."""
    form_text = normalize_form_name(str(form_name or ""))
    text = normalize_form_name(" ".join([str(form_name or ""), str(page_text or "")]))
    return any(re.search(pattern, text) for pattern in GATEWAY_NO_DOMAIN_PATTERNS)


def understanding_fallback_candidates(form_name: str, page_text: str | None = None) -> list[dict[str, Any]]:
    """
    Add a Domain by SDTM/CRF-content understanding when history has no match.

    Pages with real CRF data collection should receive a Domain whenever the
    wording is sufficiently clear. Operational Data, Metadata, and Codelist
    pages intentionally return no Domain.
    """
    if is_operational_or_metadata_form(form_name, page_text) or is_gateway_no_domain_form(form_name, page_text):
        return []

    form_text = normalize_form_name(str(form_name or ""))
    text = normalize_form_name(" ".join([str(form_name or ""), str(page_text or "")]))
    candidates: list[dict[str, Any]] = []
    if any(re.search(pattern, form_text) for pattern in COMMENT_FORM_NAME_PATTERNS):
        candidates.append(
            {
                "confidence": 0.82,
                "match_type": "understanding_fallback",
                "matched_terms": [form_name],
                "crf_content": "Comments form",
                "historical_form": "",
                "preferred_domain_approach": "CO",
                "domain_labels": "",
                "multiple_domain_rationale": "Added only because the form title itself is a comments form.",
                "rationale": "Added only because the form title itself is a comments form.",
            }
        )
    for rule in UNDERSTANDING_DOMAIN_RULES:
        matched_patterns = [pattern for pattern in rule["patterns"] if re.search(pattern, text)]
        if not matched_patterns:
            continue
        confidence = 0.78 + min(0.12, 0.03 * (len(matched_patterns) - 1))
        candidates.append(
            {
                "confidence": round(confidence, 3),
                "score": round(confidence, 3),
                "match_type": "understanding_fallback",
                "matched_terms": matched_patterns,
                "crf_content": rule["concept"],
                "historical_form": "",
                "preferred_domain_approach": rule["domain"],
                "domain_labels": "",
                "multiple_domain_rationale": "Added by SDTM/CRF-content understanding because no historical guide match was found.",
                "rationale": "Added by SDTM/CRF-content understanding because no historical guide match was found.",
            }
        )

    return sorted(candidates, key=lambda item: item["confidence"], reverse=True)


def best_effort_fallback_candidate(form_name: str, page_text: str | None = None) -> dict[str, Any] | None:
    """Return a required Step 1 best-effort Domain when no stronger rule matches.

    Step 1 must produce a reviewable Domain for every in-scope data-collection
    page. This fallback is intentionally low-confidence and review-flagged; it
    is used only after historical, override, and understanding rules fail.
    """
    if is_operational_or_metadata_form(form_name, page_text) or is_gateway_no_domain_form(form_name, page_text):
        return None

    return {
        "confidence": 0.50,
        "score": 0.50,
        "match_type": "best_effort_fallback",
        "matched_terms": [form_name] if form_name else [],
        "crf_content": form_name or "Unclassified data-collection form",
        "historical_form": "",
        "preferred_domain_approach": "FA",
        "domain_labels": "",
        "multiple_domain_rationale": (
            "No historical, override, or content-understanding Domain candidate was found. "
            "Mapped to FA as the broadest reviewable findings-about fallback; requires reviewer confirmation."
        ),
        "rationale": (
            "Required Step 1 best-effort fallback because every in-scope data-collection page must receive "
            "a proposed Domain. Review and replace with a more specific Domain when appropriate."
        ),
        "needs_review": True,
        "review_reason": "Best-effort Step 1 fallback; no stronger Domain evidence found.",
    }


map_crf_text = map_form_candidates
best_crf_mapping = map_form_to_domain


if __name__ == "__main__":
    for example in ["Adverse Event Log", "12-Lead ECG Pre-Dose", "Demography", "Tumor Assessment for Target Lesions"]:
        print(example, "=>", map_form_to_domain(example))
