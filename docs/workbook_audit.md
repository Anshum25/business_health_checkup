# Workbook audit — Business Health Checkup System

| | |
|---|---|
| File audited | `~/frappe-bench/Business_Health_Checkup_System.xlsx` (406,532 bytes) |
| SHA-256 | `e342438260134a3f9de84cb0586e6a2b271d3b4d35bedb5b097499c47d0e22fc` |
| Audit date | 2026-10-27 |
| Method | Every sheet read with openpyxl twice: once for formulas, once for the values Excel cached at its last calculation. Data validation, conditional formatting, defined names, merged and hidden ranges, sheet protection, charts (`xl/charts/*.xml`) and hyperlinks inspected. Formulas that repeat across rows or sheets were compared programmatically, not by sampling. |
| Independent check | The scoring was re-implemented in Python from the formulas (`business_health_checkup/scoring.py`) and reproduces every cached department score, maturity label, the overall score and the gap ranking of the sample answers exactly (`tests/test_scoring.py::test_workbook_sample_answers`). |

**File name.** The brief names `Business_Health_Checkup_System(2).xlsx`. No file with `(2)` exists on this machine; the only copy is `Business_Health_Checkup_System.xlsx` in the bench directory, dated 27 Oct 2026 10:10. This audit is of that file. If a different “(2)” version exists, it must be compared against the hash above (see Q-01 in [open_questions.md](open_questions.md)).

**Terms not found.** “IOC” and “MSE” (and “MSME”) do not appear anywhere in the workbook — not in cell text, sheet names, defined names or comments. Their meaning is not assumed here (Q-02).

**Sample data in the file.** The workbook is not empty: Assessment 1 has 5 answers (`STRATEGY!G7:G9` = YES, PARTIALLY, NO; `KPI!G16:G17` = NO, NO) and `ACTION PLAN!O8` holds a status `Open`. Company Profile is blank except `C21` = “Advice Consultancy”. Excel last calculated the file with `TODAY()` = 24 Oct 2026 (cached `COMPANY PROFILE!C32`). Cached values quoted below come from that state.

Notation: `SHEET!A1` = cell; ranges are inclusive; “row pattern” means the formula is identical on every row with only the row number changing (verified for all rows).

---

## 1. Workbook inventory

27 sheets, all visible (none hidden or very-hidden). 88 workbook-level defined names, no sheet-level names, no Excel tables, no macros (`.xlsx`).

| # | Sheet | Role | Inputs | Notes |
|---|---|---|---|---|
| 1 | COVER | Title page, navigation, headline score | none | Shows `OverallScore`, `OverallMaturity`, company/assessment/consultant text. 11-step workflow list (B13:D24) with hyperlinks. Protected. |
| 2 | COMPANY PROFILE | Business being assessed; assessment schedule; current assessment selector | C4:C21, C25:E28, C30 | See §2.1. Protected (inputs unlocked). |
| 3 | INSTRUCTIONS | Written procedure, scoring rules, priority rules, limits | none | The only narrative statement of the rules; matches the formulas except where noted in §8. |
| 4 | ASSESSMENT | “Assessment Hub”: per-department completion, score, maturity, gap counts | none | All cells mirror `SCORE CALCULATION!B5:L15`. Data bar F8:F18; score colours G8:G18. |
| 5–14 | STRATEGY, KPI, HR, MARKETING, SALES, PURCHASE, PRODUCTION, QUALITY, MAINTENANCE, INVENTORY | Question sheets, one per department | B7:B26 (question ID), G7:J26 (answers for assessments 1–4), S7:S26 (evidence/remarks) | All 10 sheets have byte-identical formulas (428 each). 15 questions + 5 spare rows (22–26). Helper columns T:AA hidden. Autofilter A6:S26. See §2.2. |
| 15 | SCORE CALCULATION | Calculation engine: department summary (rows 5–15), trend (17–21), consolidated question table (25–224) | none | 5,633 formulas. Every dashboard/report reads from here. See §3. |
| 16 | GAP ANALYSIS | Ranked list of all gaps; per-department gap counts | none | Rank 1–200 in A19:A218. See §5. |
| 17 | ACTION PLAN | One row per question slot (200), showing priority/phase/suggested dates; tracking inputs | K8:P207 | StatusList validation O8:O207; date validation L8:M207 (*greater than* 36526, i.e. after 1-Jan-2000; corrected in Phase 4, Phase 1 said ≥). See §6. |
| 18 | 90 DAY PLAN | Gaps split into 3 phases, max 50 rows each | none | Rows 11–60 / 66–115 / 121–170. |
| 19 | BUSINESS GROWTH PLAN | Department ranking with growth/strength status; per-department growth programme | none | Uses GrowthThreshold / StrengthThreshold and RECOMMENDATION MASTER. See §6.3. |
| 20 | OWNER DASHBOARD | KPI cards, heat map, trend table, 3 charts, Owner’s 10-Number dashboard | D39:E48, K39:K48 | Charts: bar + radar of A9:B18, line of trend. See §5. |
| 21 | MANAGEMENT REPORT | Printable consultant report, 10 sections, 2 charts | B109:H111 (remarks) | See §5. |
| 22 | KPI CALCULATOR | Single-period plant numbers → calculated KPIs | C5:C17, C28:C31, C38:C45, G5:G15, G28:G39, G47:G49 | Feeds OWNER DASHBOARD F39:F48. See §3.6. |
| 23 | QUESTION MASTER | Question bank (source of truth for question text, criticality, recommendation, KPI, risk) | A4:K203 | 150 questions in rows 4–153; rows 154–203 spare. Not protected. |
| 24 | KPI MASTER | Reference list of 45 KPI definitions (rows 4–48) + a 150-row mirror of question KPIs (rows 53–202) | A4:F48 | Rows 4–48 are not used by any formula. |
| 25 | RECOMMENDATION MASTER | 7 growth recommendations per department (rows 4–73) + 1 risk statement per department (rows 77–86) | E4:E73, E77:E86 | Not protected. |
| 26 | SETTINGS | All scoring parameters and lists | all | Not protected. See §3.1 and §4. |
| 27 | Sheet1 | Empty | — | No content; nothing references it. |

**Protection.** Sheets 1–22 are protected; formula cells are locked and input cells unlocked. The password (`ADVICE`) is written in plain text in `SETTINGS!B30` and `INSTRUCTIONS!C17`. It prevents accidental edits only and is not a security control. QUESTION MASTER, KPI MASTER, RECOMMENDATION MASTER, SETTINGS and Sheet1 are unprotected.

**Hidden content.** Only columns T:AA on each department sheet are hidden (per-assessment earned/max helpers). No hidden rows, no hidden sheets.

**Colour convention** (`SETTINGS!A54:A55`, `INSTRUCTIONS!C18`): yellow cell with blue text = input; white = formula.

### 1.1 Defined names

| Group | Names → range |
|---|---|
| Company / assessment | `CompanyName` C4, `ContactPerson` C5, `ContactDesignation` C6, `CompanyIndustry` C9, `CompanyLocation` C11, `Employees` C13, `AnnualTurnover` C14, `ConsultantName` C20, `CurrentAssessment` C30, `AssessmentLabel` C31, `AssessmentDate` C32 (all on COMPANY PROFILE) |
| Settings lists | `AnswerList` A5:A8, `ScorePct` B5:B8, `CritList` D5:D8, `CritWeight` E5:E8, `MatLower` A12:A16, `MatLabel` C12:C16, `MatShort` D12:D16, `PrioCrit` A20:A23, `PrioAns` B19:C19, `PrioMatrix` B20:C23, `PrioList` E20:E22, `PrioScore` F20:F22, `PrioPhase` G20:G22, `PrioStart` H20:H22, `PrioDue` I20:I22, `GrowthThreshold` B27, `StrengthThreshold` B28, `KpiTolerance` B29, `StatusList` A34:A37, `AssessNoList` D34:D37, `IndustryList` G34:G51, `DeptCode` A41:A50, `DeptName` C41:C50, `DeptLabel` D41:D50 (all on SETTINGS) |
| Question master | `QM_ID` A, `QM_Sub` D, `QM_Q` E, `QM_Crit` F, `QM_W` G, `QM_Rec` H, `QM_KPI` I, `QM_Risk` J — rows 4:203 |
| Recommendation master | `RM_Key` A4:A73, `RM_Rec` E4:E73, `RM_RiskCode` B77:B86, `RM_Risk` E77:E86 |
| Consolidated table (`SCORE CALCULATION` rows 25:224) | `C_Code` A, `C_Dept` B, `C_ID` C, `C_Sub` D, `C_Q` E, `C_Crit` F, `C_W` G, `C_Ans` H, `C_Earned` I, `C_Max` J, `C_Gap` K, `C_Prio` L, `C_Rec` M, `C_KPI` N, `C_Risk` O, `C_Rank` R, `C_Phase` S, `C_Start` T, `C_Due` U, `C_Resp` V, `C_StartIn` W, `C_Target` X, `C_Measure` Y, `C_Status` Z, `C_Remarks` AA |
| Results | `DeptScore` SCORE CALCULATION!H5:H14, `DeptRank` U5:U14, `OverallScore` H15, `OverallMaturity` I15; `GapTotal/GapHigh/GapMedium/GapLow` GAP ANALYSIS!B4:E4; `ActTotal/ActOpen/ActInProg/ActDone/ActHold/ActOverdue/ActPct` ACTION PLAN!A4:G4 |
| Unused | `OK_First` (OWNER DASHBOARD!A39) is defined but not referenced by any formula. |

---

## 2. Assessment structure

### 2.1 Business profile and assessment schedule (COMPANY PROFILE)

Business fields (inputs C4:C21): Company Name, Contact Person, Designation, Mobile, Email, Industry (dropdown `IndustryList`, 18 values incl. “Other”), Product Category, Location (City, State), Year Established, Number of Employees, Annual Turnover (Rs Lakh), Export %, Number of Customers, Major Customers, Number of Plants, Production Processes, Consultant Name, Consultancy Firm (pre-filled “Advice Consultancy”). Only Industry has validation; the rest are free cells (no email/number checks).

Assessment schedule (B24:F28): 4 fixed rows, Assessment No. 1–4, with Label (“Assessment 1 - Baseline”, “Assessment 2 - Quarter 2”, “… Quarter 3”, “… Quarter 4”), Assessment Date (input), Consultant (input), Status (formula, e.g. `F25: =IF('SCORE CALCULATION'!B20>0,"Answered "&…B20&" of "&…C15&"  |  Score "&TEXT(…B18,"0%"),"Not started")`).

- `C30` **Current Assessment No.** (dropdown 1–4, `AssessNoList`) “drives all dashboards”.
- `C31` `=INDEX($C$25:$C$28,CurrentAssessment)`.
- `C32` `=IF(INDEX($D$25:$D$28,CurrentAssessment)="",TODAY(),INDEX($D$25:$D$28,CurrentAssessment))` — a blank date means *today*.
- The per-assessment Consultant column (E25:E28) is not read by any formula; reports use the single `ConsultantName` (C20).

### 2.2 Departments

`SETTINGS!A41:D50`. Codes and sheet names are “structural and must not be changed”; names and labels are editable (`SETTINGS!A51`).

| Order | Code | Sheet | Department | Chart label |
|---|---|---|---|---|
| 1 | STR | STRATEGY | Business Strategy & Goals | Strategy |
| 2 | KPI | KPI | KPI & Management Review | KPI |
| 3 | HR | HR | Human Resources | HR |
| 4 | MKT | MARKETING | Marketing | Marketing |
| 5 | SAL | SALES | Sales | Sales |
| 6 | PUR | PURCHASE | Purchase & Supplier Management | Purchase |
| 7 | PRD | PRODUCTION | Production | Production |
| 8 | QA | QUALITY | Quality | Quality |
| 9 | MNT | MAINTENANCE | Maintenance | Maintenance |
| 10 | INV | INVENTORY | Inventory & Stores | Inventory |

### 2.3 Question bank (QUESTION MASTER)

Columns: A Question ID, B Dept Code (validation `DeptCode`), C Department (`=IFERROR(INDEX(DeptName,MATCH(B4,DeptCode,0)),"")`), D Sub-Category, E Question, F Criticality (validation `CritList`), G Weightage (`=IFERROR(INDEX(CritWeight,MATCH(F4,CritList,0)),"")`), H Recommendation (if gap), I KPI, J Business Risk if Unresolved, K Seq.

Checks run on rows 4–153 (all passed):

- 150 questions, 15 per department, IDs `STR-01` … `INV-15`; Seq 1–15 per department.
- No duplicate IDs, no duplicate question texts, no duplicate recommendations; no blank field in any of the 150 rows.
- Every ID prefix matches its Dept Code.
- Every department sheet lists exactly its 15 IDs in B7:B21, in QUESTION MASTER order; no sheet references an ID missing from the master, and no ID is used twice.
- Each department has exactly 15 distinct sub-categories (one per question).

Criticality mix: Important 66, Critical 56, Standard 28, **Basic 0** (Basic is defined in SETTINGS but unused).

| Dept | Critical | Important | Standard | Max points |
|---|---|---|---|---|
| STR | 9 | 5 | 1 | 118 |
| KPI | 8 | 6 | 1 | 113 |
| HR | 3 | 7 | 5 | 80 |
| MKT | 3 | 6 | 6 | 78 |
| SAL | 8 | 6 | 1 | 113 |
| PUR | 6 | 7 | 2 | 101 |
| PRD | 6 | 7 | 2 | 101 |
| QA | 6 | 7 | 2 | 101 |
| MNT | 4 | 7 | 4 | 87 |
| INV | 3 | 8 | 4 | 82 |
| **All** | **56** | **66** | **28** | **974** |

The full text of all 150 questions is in `business_health_checkup/workbook_v1/questions.json`, each with its source row.

**Adding questions** (`INSTRUCTIONS!C16`, `QUESTION MASTER!A2`): fill a spare master row (154–203) and type the new ID in a spare department-sheet row (22–26). Limit: 20 questions per department (`INSTRUCTIONS!C19`).

### 2.4 Answer capture (department sheets)

Layout of every department sheet (row 6 headers, rows 7–26 questions):

| Col | Content | Formula / input |
|---|---|---|
| A | No. | `=IF(B7="","",ROW()-6)` |
| B | Question ID | input (unlocked) |
| C, D, E, F | Sub-category, Question, Criticality, Weight | lookups into `QM_Sub`, `QM_Q`, `QM_Crit`, `QM_W`; D shows “ID not found in Question Master” for an unknown ID; F falls back to 0 |
| G, H, I, J | Assessment 1–4 answers | input, dropdown `AnswerList` (YES / PARTIALLY / NO / N/A), blank allowed |
| K | Current Answer | `=IF($B7="","",T(INDEX($G7:$J7,1,CurrentAssessment)))` |
| L | Earned | `=IF(OR($B7="",K7="",K7="N/A"),0,$F7*IFERROR(INDEX(ScorePct,MATCH(K7,AnswerList,0)),0))` |
| M | Max | `=IF(OR($B7="",K7="",K7="N/A"),0,$F7)` |
| N | Gap | `=M7-L7` |
| O | Priority | `=IF(N7<=0,"",IFERROR(INDEX(PrioMatrix,MATCH(E7,PrioCrit,0),MATCH(K7,PrioAns,0)),""))` |
| P | Recommendation (if gap) | `=IF(N7<=0,"",IFERROR(INDEX(QM_Rec,…),""))` |
| Q | KPI | always shown, `QM_KPI` |
| R | Business Risk (if gap) | `=IF(N7<=0,"",IFERROR(INDEX(QM_Risk,…),""))` |
| S | Evidence / Remarks | input, **one column shared by all four assessments** |
| T:AA (hidden) | E1, M1 … E4, M4 | same as L/M but for G, H, I, J respectively |

Header block row 5: `B5` score `=IF(SUM(M7:M26)=0,0,SUM(L7:L26)/SUM(M7:M26))`; `C5` maturity `=IF(SUM(M7:M26)=0,"Not Assessed",INDEX(MatLabel,MATCH(B5,MatLower,1)))`; `E5` questions `=SUMPRODUCT(--(B7:B26<>""))`; `F5` answered `=SUMPRODUCT((B7:B26<>"")*(K7:K26<>""))`; `G5` “earned / max” text; `I5:K5` `COUNTIF(O7:O26,"HIGH"|"MEDIUM"|"LOW")`.

Conditional formatting highlights the active assessment column (`G6`… `CurrentAssessment=1` …) and blank answers in it (`AND(CurrentAssessment=1,G7="",$B7<>"")`).

Answer meaning (`INSTRUCTIONS!C6`): YES = practice defined, implemented and used by management, evidence available; PARTIALLY = exists but informal, incomplete or not reviewed; NO = not in place; N/A = not applicable to this business, excluded from the score, “use sparingly”.

Intended procedure (`INSTRUCTIONS!C3`): business owners / MDs / plant heads with a consultant, a facilitated review with department heads, 2–3 hours for 150 questions. There is no self-service respondent role in the workbook.

---

## 3. Scoring formulas and dependencies

Dependency chain: SETTINGS + QUESTION MASTER → department sheets (per question) → SCORE CALCULATION (department and overall totals, consolidated table, ranking) → ASSESSMENT, GAP ANALYSIS, ACTION PLAN, 90 DAY PLAN, BUSINESS GROWTH PLAN, OWNER DASHBOARD, MANAGEMENT REPORT, COVER. KPI CALCULATOR → OWNER DASHBOARD (10-number dashboard) → MANAGEMENT REPORT §8. The consolidated table also reads back the tracking inputs from ACTION PLAN (`SCORE CALCULATION!V25:AA224` ← `ACTION PLAN!K8:P207`).

### 3.1 Parameters (SETTINGS)

| Rule | Cells | Value |
|---|---|---|
| Answer → share of weight earned | A5:B8 | YES 1, PARTIALLY 0.5, NO 0, N/A 0 |
| N/A handling | A9 + department sheet L7/M7 | N/A excluded from earned **and** max (hard-coded `K7="N/A"` test, not driven by B8) |
| Criticality → weight | D5:E8 | Critical 10, Important 5, Standard 3, Basic 1 |
| Maturity bands | A12:E16 | see §4.1 |
| Priority matrix | A19:C23 | see §4.2 |
| Priority → rank, phase, start/due offsets | E19:I22 | see §4.2 |
| Growth Plan trigger | B27 | department score **below** 0.6 |
| Strength | B28 | department score **at or above** 0.75 |
| KPI “Watch” tolerance | B29 | adverse variance up to 10 % of target |

### 3.2 Question score

For a question with weight `w` (from its criticality) and current answer `a`:

- unanswered or N/A → earned 0, max 0 (excluded);
- otherwise earned = `w × ScorePct(a)`, max = `w`;
- gap = max − earned;
- priority = `PrioMatrix(criticality, a)` when gap > 0, otherwise blank.

Values: Critical YES 10/10, PARTIALLY 5/10, NO 0/10; Important 5/5, 2.5/5, 0/5; Standard 3/3, 1.5/3, 0/3; Basic 1/1, 0.5/1, 0/1.

### 3.3 Department score (SCORE CALCULATION rows 5–14, one per department)

| Col | Meaning | Formula (row 5 = STR) |
|---|---|---|
| C | Questions | `=SUMPRODUCT(--(STRATEGY!B7:B26<>""))` |
| D | Answered (includes N/A) | `=SUMPRODUCT((STRATEGY!B7:B26<>"")*(STRATEGY!K7:K26<>""))` |
| E | Completion % | `=IF(C5=0,0,D5/C5)` |
| F | Earned | `=SUM(STRATEGY!L7:L26)` |
| G | Max (applicable) | `=SUM(STRATEGY!M7:M26)` |
| H | Score (current) | `=IF(G5=0,0,F5/G5)` |
| I | Maturity | `=IF(G5=0,"Not Assessed",INDEX(MatLabel,MATCH(H5,MatLower,1)))` |
| J:L | HIGH / MEDIUM / LOW gaps | `=COUNTIF(STRATEGY!O7:O26,"HIGH")` … |
| M | Total gaps | `=SUM(J5:L5)` |
| N:Q | Score of assessment 1–4 | `=IF(SUM(STRATEGY!U7:U26)=0,0,SUM(STRATEGY!T7:T26)/SUM(STRATEGY!U7:U26))` (V/W, X/Y, Z/AA for 2–4) |
| R | Previous score | `=IF(CurrentAssessment=1,"",INDEX(N5:Q5,1,CurrentAssessment-1))` |
| S | Change vs previous | `=IF(R5="","",H5-R5)` |
| T | Tie score | `=H5+ROW()/1000000` |
| U | Rank (1 = weakest) | `=RANK(T5,$T$5:$T$14,1)` |

Rows 6–14 follow the same pattern for KPI … INVENTORY (verified for all 10 rows).

**Unanswered and N/A questions are excluded from both numerator and denominator.** `INSTRUCTIONS!C11` warns: “check ‘Answered’ before trusting a score”.

### 3.4 Overall score (row 15, “ALL”)

- `C15:G15` and `J15:M15` are sums of rows 5–14.
- `H15` (`OverallScore`) `=IF(G15=0,0,F15/G15)` — **total earned ÷ total applicable max across all departments**. It is weighted by applicable points, not an average of department percentages: with the full bank a fully answered STR counts 118 points and MKT 78.
- `I15` (`OverallMaturity`) same lookup as I5.
- `N15:Q15` overall score per assessment 1–4 (sum of every sheet’s T…AA columns).
- `R15`, `S15` previous / change as in rows 5–14.

Trend block rows 17–21: `B18:E18` overall score per assessment; `B19:E19` dates from `COMPANY PROFILE!D25:D28`; `B20:E20` questions answered per assessment (count of non-blank G/H/I/J cells); `B21:E21` chart series `=IF(B20=0,NA(),B18)` so the trend line stops at the last answered assessment.

Cached results for the sample: STR 8 / 23 = 34.78 %, KPI 0 / 10 = 0 %, 8 departments “Not Assessed”; overall 8 / 33 = 24.24 %, “CRITICAL IMPROVEMENT REQUIRED”; 5 of 150 answered (3.33 %).

### 3.5 Consolidated question table and gap ranking (SCORE CALCULATION rows 25–224)

200 rows = 10 departments × 20 slots (row `25 + 20·d + i` ↔ department sheet row `7 + i` ↔ ACTION PLAN row `8 + 20·d + i`; verified for all 200 rows × 27 columns). Columns A–O copy the department sheet; further columns:

| Col | Meaning | Formula (row 25) |
|---|---|---|
| P | Priority rank score | `=IF(L25="",0,IFERROR(INDEX(PrioScore,MATCH(L25,PrioList,0)),0))` |
| Q | Sort key | `=IF(K25>0,P25*10000000+K25*10000+(1000-ROW()),0)` |
| R | Gap rank (`C_Rank`) | `=IF(Q25>0,COUNTIF($Q$25:$Q$224,">"&Q25)+1,"")` |
| S | Phase | `=IF(L25="","",IFERROR(INDEX(PrioPhase,MATCH(L25,PrioList,0)),""))` |
| T | Suggested start | `=IF(L25="","",AssessmentDate+IFERROR(INDEX(PrioStart,MATCH(L25,PrioList,0)),0))` |
| U | Suggested due | `=IF(L25="","",AssessmentDate+IFERROR(INDEX(PrioDue,MATCH(L25,PrioList,0)),0))` |
| V:AA | Responsible, Start, Target date, Target / measure, Status, Remarks | copied back from ACTION PLAN K:P |

Ranking: every question with a gap is ranked by priority (HIGH 3 > MEDIUM 2 > LOW 1), then by points lost, then by position (department order, then question order). The key cannot collide: `K×10000 ≤ 100000` stays below one priority step (`10,000,000`) and `1000−ROW()` (776…975) below one gap step of 0.5 point (5,000).

### 3.6 KPI calculations (KPI CALCULATOR → OWNER DASHBOARD)

KPI CALCULATOR holds **one set of numbers for one period** (inputs in C and G). Calculated values, each blank when its denominator is 0 or blank:

| KPI | Cell | Formula |
|---|---|---|
| RFQ conversion % | C18 | `C7/C5` (orders won / RFQs) |
| Quotation conversion % | C19 | `C7/C6` |
| Sales growth % | C20 | `(C9-C8)/C8` |
| New customer % | C21 | `C10/C11` |
| Order book (months) | C22 | `C12/C13` |
| Pipeline value | C23 | `C14` |
| Top-1 / top-3 customer concentration % | C24 / C25 | `C15/C17`, `C16/C17` |
| EBITDA margin % | C32 | `C29/C28` |
| Debtor days | C33 | `C30/(C28/30)` |
| Employee productivity (Rs Lakh / employee / month) | C34 | `C28/C31` |
| Monthly turnover | C35 | `C28` |
| Total inventory | C46 | `C38+C39+C40` |
| Inventory days | C47 | `(C38+C39+C40)/(C41/30)` |
| Inventory turnover | C48 | `C41*12/(C38+C39+C40)` |
| Slow-moving % / dead stock % | C49 / C50 | `C42/total`, `C43/total` |
| Stock accuracy % | C51 | `C45/C44` |
| Availability % | G16 | `(G5-G6)/G5` |
| Performance % | G17 | `(G7*G8/3600)/(G5-G6)` (not capped at 100 %) |
| Quality % | G18 | `G9/G8` |
| OEE % | G19 | `G16*G17*G18` |
| Production achievement % | G20 | `G8/G12` |
| Rejection % / rework % | G21 / G22 | `G10/G8`, `G11/G8` |
| Machine utilisation % | G23 | `G14/G13` |
| Productivity (pcs / man-hour) | G24 | `G9/G15` |
| Downtime % | G25 | `G6/G5` |
| Customer PPM / supplier PPM | G40 / G41 | `G29/G28×10⁶`, `G31/G30×10⁶` |
| On-time delivery % | G42 | `G33/G32` |
| COPQ (Rs Lakh) / COPQ % | G43 / G44 | `G34+…+G38`, same ÷ `G39` |
| MTBF / MTTR | G50 / G51 | `G47/G48`, `G49/G48` |
| Machine availability % | G52 | `MTBF/(MTBF+MTTR)` |

**Owner’s 10-Number Dashboard** (`OWNER DASHBOARD!A38:L48`). KPIs, units and directions are hard-coded text in A:C: Turnover (monthly) ← C35; EBITDA % ← C32×100; Debtor Days ← C33; Order Book ← C22; RFQ Pipeline ← C23; On-Time Delivery ← G42×100; Customer PPM ← G40; OEE ← G19×100; Inventory Days ← C47; Employee Productivity ← C34. Inputs: Target D, manual Actual E, Previous period K.

- `G39` actual used `=IF(E39<>"",E39,IF(F39<>"",F39,""))` — a manual entry overrides the calculated value.
- `H39` variance `=IF(OR(G39="",D39=""),"",1*(G39-D39))`; the factor is `-1` on the “Lower is better” rows (41, 45, 47).
- `I39` variance % `=IF(OR(H39="",D39=0,D39=""),"",H39/ABS(D39))`.
- `J39` status `=IF(H39="","",IF(H39>=0,"On Track",IF(ABS(I39)<=KpiTolerance,"Watch","Off Track")))`.
- `L39` trend vs previous: “▲ Improving” / “▼ Declining” / “► Stable”, direction-adjusted.

KPI MASTER rows 4–48 (45 KPI definitions with formula text, unit, frequency, direction) are reference only; no formula reads them, and the KPI text on each question (QUESTION MASTER col I) is free text with no key into KPI MASTER.

---

## 4. Thresholds and classifications

### 4.1 Maturity levels (SETTINGS!A12:E16)

| Lower bound (≥) | Upper bound (display) | Level | Short label | Meaning |
|---|---|---|---|---|
| 0 | 0.3999 | CRITICAL IMPROVEMENT REQUIRED | Critical | Basic management systems missing; business at risk |
| 0.40 | 0.5999 | DEVELOPING | Developing | Systems partly in place; results depend on individuals |
| 0.60 | 0.7499 | MANAGED | Managed | Systems defined and mostly followed; improvement possible |
| 0.75 | 0.8999 | STRONG MANAGEMENT | Strong | Well-managed function; focus on optimisation |
| 0.90 | 1 | ADVANCED | Advanced | Best-practice level; sustain and benchmark |

Lookup: `INDEX(MatLabel, MATCH(score, MatLower, 1))` — the band with the largest lower bound ≤ score, using the **unrounded** score. The upper-bound column B is not used by any formula. When applicable max = 0 the label is the literal “Not Assessed” (“-” in MANAGEMENT REPORT D17, “Not assessed” in OWNER DASHBOARD C9).

Score colours (conditional formatting on every score cell): red 0–0.3999, orange 0.4–0.5999, yellow 0.6–0.7499, light green 0.75–0.8999, green 0.9–1.0001. These limits are literals in the rules, not links to SETTINGS.

### 4.2 Gap priority and 90-day phase (SETTINGS!A19:I24)

| Criticality \ Answer | NO | PARTIALLY |
|---|---|---|
| Critical | HIGH | MEDIUM |
| Important | MEDIUM | MEDIUM |
| Standard | LOW | LOW |
| Basic | LOW | LOW |

| Priority | Rank score | 90-day phase | Suggested start | Suggested due |
|---|---|---|---|---|
| HIGH | 3 | 0-30 Days | assessment date + 0 | + 30 |
| MEDIUM | 2 | 31-60 Days | + 31 | + 60 |
| LOW | 1 | 61-90 Days | + 61 | + 90 |

Stated rule (`SETTINGS!A24`, `INSTRUCTIONS!C12`): Critical NO = HIGH; Important NO or any Critical/Important PARTIALLY = MEDIUM; Standard/Basic gaps = LOW. The matrix matches the statement.

### 4.3 Department classification (BUSINESS GROWTH PLAN)

| Condition | E8:E17 (ranking table) | F22, F32 … F112 (programme header) |
|---|---|---|
| score < `GrowthThreshold` (0.6) | “PRIORITY - GROWTH PLAN” | “GROWTH PROGRAMME REQUIRED” |
| score ≥ `StrengthThreshold` (0.75) | “STRENGTH - LEVERAGE” | “Strength - sustain and use as internal benchmark” |
| otherwise | “MAINTAIN & IMPROVE” | “Maintain - close remaining gaps via Action Plan” |

The 0.6 / 0.75 thresholds coincide with the MANAGED and STRONG MANAGEMENT lower bounds, but are separate parameters.

### 4.4 Other classifications

| Classification | Source | Rule |
|---|---|---|
| “Repeated problem area?” | GAP ANALYSIS!H7:H16 | `=IF(C7>=3,"YES - 3+ HIGH gaps: systemic weakness",IF(F7>=8,"YES - many gaps in one function",""))` — thresholds 3 and 8 are hard-coded, not in SETTINGS |
| KPI status | OWNER DASHBOARD!J39:J48 | On Track (variance ≥ 0) / Watch (adverse, ≤ 10 % of target) / Off Track |
| Action overdue | ACTION PLAN!Q8:Q207 | `=IF(AND(E8<>"",O8<>"Completed",M8<>"",M8<TODAY()),"OVERDUE","")` |

---

## 5. Report and dashboard inventory

All outputs are formula-driven views of the current assessment (`CurrentAssessment`) except where stated.

| Output | Sheet / range | Content | Inputs on the sheet |
|---|---|---|---|
| Cover | COVER | Company, assessment label + date, consultant, health score + maturity | — |
| Assessment hub | ASSESSMENT!A7:K18 | Per department: questions, answered, completion %, score, maturity, HIGH/MEDIUM/LOW; overall row | — |
| Gap analysis | GAP ANALYSIS | Summary B4:G4 (total gaps, HIGH, MEDIUM, LOW, points lost `=SUM(C_Gap)`, overall score); per-department counts + score + “repeated problem area” (rows 7–16); ranked list rows 19–218 (dept, ID, question, criticality, weight, answer, earned points, gap points, priority, recommendation, KPI, risk, phase) | — |
| Action plan | ACTION PLAN | Counters A4:G4; 200 rows in department order | Responsible, Start, Target date, Target/measure, Status, Remarks |
| 90-day plan | 90 DAY PLAN | Plan start = assessment date, end = +90; three phase tables (HIGH, MEDIUM, LOW), 50 rows each, from rank order; start/due = user date else suggested; status blank → “Open” | — |
| Business growth plan | BUSINESS GROWTH PLAN | Overall score/maturity; 10 departments weakest first with score, gaps, status, department risk (risk only when < threshold); per-department programme (7 RECOMMENDATION MASTER items, shown only when < threshold) | — |
| Owner dashboard | OWNER DASHBOARD | 8 cards (score, maturity, answered, HIGH/MEDIUM/LOW gaps, actions open = Open+In Progress+Hold, actions completed + %); heat map A8:F19 with previous and change; trend table A23:D27 and department improvement K23:O33; charts: bar and radar of department scores, line of overall trend; 10-number KPI dashboard | KPI target, manual actual, previous period |
| Management report | MANAGEMENT REPORT | §1 company profile; §2 overall health + one-sentence position (“This is the baseline assessment.” or change vs previous); §3 department table + radar + bar chart; §4 “major strengths” = 3 highest-ranked departments + count of Critical practices answered YES; §5 top 10 gaps; §6 3 weakest departments + risk; §7 top 15 actions with responsible (“(to be assigned)”) and due date; §8 the 10 KPIs; §9 up to 5 weakest departments below threshold with first three growth steps + count “Departments in growth programme: n of 10”; §10 consultant remarks (3 free-text lines) + “Next re-assessment recommended: assessment date + 90”; signature lines for Consultant and Management | Remarks B109:H111 |

“Printing” is the only distribution mechanism described (`INSTRUCTIONS!C9`: “MANAGEMENT REPORT is a printable consultant report - add remarks in section 10 and print”). The workbook defines exactly one formal report; there is no report-selection step and no other report format.

---

## 6. Action-plan rules

### 6.1 What the workbook does automatically

- Every question with a gap (NO or PARTIALLY) gets a priority, a phase and suggested start/due dates (§3.5, §4.2).
- ACTION PLAN always shows all 200 question slots; rows with a priority are the actions. The user is told to “filter the Priority column to hide non-gap rows” (`ACTION PLAN!A2`, `INSTRUCTIONS!C8`).
- The recommended action text is the question’s Recommendation from QUESTION MASTER; the KPI is the question’s KPI text.
- Counters (`ACTION PLAN!A4:G4`): Total = rows with a priority; Open = priority and status Open **or blank** (“Blank status on a gap counts as Open”, A6); In Progress; Completed; Hold (labelled “On Hold”); Overdue; Completion % = Completed / Total.
- 90 DAY PLAN and MANAGEMENT REPORT §7 use the user’s Start / Target date when entered, otherwise the suggested dates (“your own dates in ACTION PLAN override them”, `INSTRUCTIONS!C14`).

### 6.2 What is left to people

- Responsible person (free text), start date, target date, target / measure, status (Open / In Progress / Completed / Hold), remarks.
- Whether to act on a gap at all: the workbook lists every gap as an action but has no field to accept, reject or defer one; filtering is manual.
- No approval, sign-off or review step for actions. No link between an action and a KPI result.

### 6.3 Business growth plan

- Explicit rule: a department whose current score is below `GrowthThreshold` (0.6) is labelled “PRIORITY - GROWTH PLAN” / “GROWTH PROGRAMME REQUIRED” and shown its 7 standard growth recommendations and department risk (`BUSINESS GROWTH PLAN!E8:F17`, `F22`, `B23`, `A24:B30` … `A114:B120`; MANAGEMENT REPORT §9).
- `INSTRUCTIONS!C9`: “BUSINESS GROWTH PLAN shows the improvement programme for every department below the threshold.”
- The workbook therefore *labels* a growth programme as required by threshold. It does not record whether management accepted it, nor create any action from the growth recommendations.

---

## 7. Reassessment rules

- Up to 4 assessments per workbook, “save a copy per company” (`INSTRUCTIONS!C19`). Assessment 1 is the baseline; 2–4 are labelled Quarter 2–4.
- Procedure (`INSTRUCTIONS!C10`, `COVER!D23`): “After ~90 days: in COMPANY PROFILE set Current Assessment No. = 2, enter the date, and answer in the ‘Assessment 2’ column of each department sheet. Previous answers stay in column ‘Assessment 1’.”
- The suggested date is `AssessmentDate + 90` (`MANAGEMENT REPORT!B113`, “Next re-assessment recommended … (after completion of the 90-day plan)”). It is a recommendation; nothing enforces it.
- Previous vs current: “Previous” is always the assessment number immediately before the current one (`SCORE CALCULATION!R5:R15`), shown on OWNER DASHBOARD and MANAGEMENT REPORT. The trend uses each assessment’s overall score (§3.4).
- The same 150 questions are answered in every assessment; there is no per-assessment question list.

---

## 8. Unclear or conflicting requirements

Findings are numbered for reference from [open_questions.md](open_questions.md) and [data_model.md](data_model.md). None of them was “fixed” in the workbook; they are recorded as found.

| # | Finding | Where | Effect |
|---|---|---|---|
| W-01 | **Unassessed departments are treated as score 0.** Department score is `0` when nothing applicable was answered; the label says “Not Assessed”, but ranking, growth status and reports use the 0. | SCORE CALCULATION!H5:H14, T5:U14; BUSINESS GROWTH PLAN!C8:F17, F22…F112; MANAGEMENT REPORT §4, §6, §9, B106 | With the sample data, 8 unanswered departments rank as “weakest”, are marked “PRIORITY - GROWTH PLAN”, two of them appear under “Major strengths” (§4 lists the top 3 ranks), and §9 says “Departments in growth programme: 10 of 10”. |
| W-02 | **Past scores are recomputed with today’s masters.** Scores of assessments 1–4 use the weights in QUESTION MASTER and SETTINGS as they are now; question text, recommendation and risk are also looked up live. | department sheets F, T:AA; SCORE CALCULATION!N5:Q15 | Editing a criticality, weight or band rewrites every earlier assessment’s score and the trend. |
| W-03 | **One evidence/remarks column for four assessments.** | department sheets S7:S26 | Evidence of assessment 1 is overwritten or mixed with later ones. |
| W-04 | **Action tracking is stored per question slot, not per assessment.** Responsible, dates, status and remarks belong to the row of the question. | ACTION PLAN!K8:P207 ↔ SCORE CALCULATION!V25:AA224 | After switching to assessment 2, old statuses attach to the new gaps; an action whose gap was closed loses its priority and drops out of all counters, so its history disappears. |
| W-05 | **“Previous” means the preceding number, even if it was never answered** (its score then reads 0). | SCORE CALCULATION!R5:S15 | “Change vs previous” can show a large false improvement. |
| W-06 | **Blank assessment date means today.** | COMPANY PROFILE!C32 | Suggested action dates, the 90-day plan and the recommended re-assessment date move every day until a date is entered. |
| W-07 | Hard-coded thresholds outside SETTINGS: “repeated problem area” (3 HIGH / 8 gaps); score colour limits; INSTRUCTIONS text quoting the bands. | GAP ANALYSIS!H7:H16; all score conditional formats; INSTRUCTIONS!C13, C18 | Editing SETTINGS does not update them. Scores between 0.3999 and 0.4 (etc.) get no colour. |
| W-08 | Report sections disagree on “strength”: §4 “Major strengths” = top 3 by rank, ignoring `StrengthThreshold`; BUSINESS GROWTH PLAN uses the threshold. | MANAGEMENT REPORT!B45:D47 vs BUSINESS GROWTH PLAN!E8:E17 | A department at 0 % can be printed as a major strength. |
| W-09 | Department rank ties are broken by sheet order (`H + ROW()/1e6`). Because the offset (at most 9e-6 between departments) is added to the score, two scores closer than that would be ordered by sheet row rather than by score. With the workbook’s weights (≤ 10 points, half points, ≤ 20 questions per department) distinct scores are at least 1/(2·200·199) ≈ 1.3e-5 apart, so this cannot happen today; it could with much larger weights in a future scoring model. | SCORE CALCULATION!T5:T14 | Deterministic, but arbitrary for equal or nearly equal scores. Reproduced exactly by `scoring.rank_departments` (Q-21). |
| W-10 | Report length limits are fixed: top 10 gaps, 3 weakest, 3 strengths, 15 actions, 5 roadmap rows, 50 actions per 90-day phase, 4 assessments, 20 questions per department. | MANAGEMENT REPORT; 90 DAY PLAN; INSTRUCTIONS!C19 | Unclear whether these are business requirements or spreadsheet limits. |
| W-11 | KPI data covers a single period with no history and no link to an assessment; “Previous period” is typed in by hand. | KPI CALCULATOR; OWNER DASHBOARD!D39:L48 | No KPI trend can be reproduced later. |
| W-12 | KPI MASTER is not used by any formula, and question KPIs are free text unrelated to it. The 10 dashboard KPIs are hard-coded. | KPI MASTER!A4:F48; QUESTION MASTER!I; OWNER DASHBOARD!A39:C48 | Its role (reference only, or a list to pick from) is undefined. |
| W-13 | “Basic” criticality (weight 1) is defined and in the priority matrix, but no question uses it. | SETTINGS!D8:E8, A23:C23 | Must be kept for completeness, but is untested by real data. |
| W-14 | Mislabelled trend headers: M23 “Current” sits over the previous score (`=R5`), N23 “Improvement” over the current score (`=H5`), and column O (change) has no header. | OWNER DASHBOARD!K23:O33 | Display only; intended labels are likely “Previous / Current / Improvement”. |
| W-15 | Blank company name shows as `0`. | 90 DAY PLAN!C3; BUSINESS GROWTH PLAN!B3; MANAGEMENT REPORT!C5:F7 | Display only. |
| W-16 | Answers outside the dropdown (possible by pasting) are counted as answered with 0 points and no priority; an unknown question ID scores with weight 0. | department sheets L, O, D, F | Silent mis-scoring; data validation is the only guard. |
| W-17 | “Answered” and completion count N/A as answered; “Critical practices in place: x of y answered” counts N/A in y. | SCORE CALCULATION!D5; MANAGEMENT REPORT!G45 | Consistent, but should be confirmed. |
| W-18 | The per-assessment Consultant column is never used; reports print the single `ConsultantName`. | COMPANY PROFILE!E25:E28 vs C20 | Re-assessments by another consultant are attributed to the current name. |
| W-19 | GAP ANALYSIS column H is headed “Score” but shows earned points, not a percentage; ACTION PLAN “On Hold” header vs “Hold” status value. | GAP ANALYSIS!H18; ACTION PLAN!E3 | Labels only. |
| W-20 | Business profile values (employees, turnover, customers …) are stored once, not per assessment. | COMPANY PROFILE!C4:C21 | A later re-assessment cannot show what the business looked like at the baseline. |
| W-21 | A status `Open` is typed on a row that has no gap (STR-01, answered YES). | ACTION PLAN!O8 | Harmless (counters ignore rows without a priority); sample-data residue. |
| W-22 | The sheet protection password is stored in clear text. | SETTINGS!B30; INSTRUCTIONS!C17 | Not to be carried into the system; access control must be real permissions. |
| W-23 | The 90 DAY PLAN’s Start Date and Due Date columns show the agreed ACTION PLAN date when one was typed and otherwise the suggested one, without saying which. “Overdue” (ACTION PLAN!Q8) uses only the typed Target Date. | 90 DAY PLAN!G11:H170; ACTION PLAN!Q8 | A suggested date can look like a commitment. The system keeps them in separate columns (Phase 4). |

---

## 9. Implementation implications

1. **Scoring is fully specified** by SETTINGS + criticality and is deterministic. It is implemented and tested in `business_health_checkup/scoring.py` (question score, department and overall totals, maturity, priority, gap ranking, suggested dates), reproducing the workbook to full floating-point precision.
2. **Historical integrity needs snapshots the workbook does not have** (W-02, W-03, W-04, W-20): each assessment must store its answers, evidence, the question text / criticality / weight it was asked with, the rule values it was scored with, and its computed results. A finalised assessment must not be re-scored by master edits.
3. **Each re-assessment becomes its own record** linked to the previous one, instead of four columns. That removes the 4-assessment and “previous = number − 1” limits (W-05, W-10), but how “previous” is chosen must be confirmed.
4. **Actions belong to an assessment’s gap**, not to a question slot (W-04). Whether an action is created for every gap or only for those the manager selects is open (Q-07).
5. **“Not Assessed” must be handled explicitly** in ranking, growth status and reports (W-01, W-08). The engine exposes `Summary.assessed`; ranking and growth status are deliberately not implemented until Q-04/Q-05 are answered.
6. **Reports to rebuild**: gap analysis, action plan / 90-day plan, growth plan, owner dashboard, management report (print format), trend across assessments. Their exact content is in §5; their length limits are to be confirmed (W-10).
7. **KPI tracking is a separate concern** (single-period calculator + 10-number dashboard). Whether it is in scope, and whether it should keep history per period or per assessment, is open (Q-10, W-11, W-12).
8. **Thresholds in formulas** (W-07) should become parameters only if management wants them editable; until then they are documented constants.
9. **No approval workflow, respondent portal, notifications or report selection exist in the workbook.** They are not designed in until confirmed (Q-06, Q-08, Q-09).
10. The workbook is industry-specific (manufacturing: title “Manufacturing Business Health Checkup”, industry list, OEE/PPM KPIs). The data model keeps the question bank as data so another bank could be added later, but nothing beyond the supplied bank is built.

---

## 10. Questions that require manager confirmation

These are listed with context, options and impact in [open_questions.md](open_questions.md). Summary:

| # | Question |
|---|---|
| Q-01 | Is `Business_Health_Checkup_System.xlsx` (hash above) the authoritative “(2)” version? |
| Q-02 | What do “IOC” and “MSE” refer to? Neither term is in the workbook. |
| Q-03 | Who is “the manager”, and what does the manager approve or decide? |
| Q-04 | How should unassessed departments be ranked and reported (W-01, W-08)? |
| Q-05 | Is “GROWTH PROGRAMME REQUIRED” (score < 0.6) a decision, or a recommendation the manager accepts or rejects? |
| Q-06 | Is a review / approval step needed before results are final? Who signs (consultant, management)? |
| Q-07 | Should every gap automatically become an action, or only gaps the manager selects? |
| Q-08 | Which reports are required, and in what format? Is the Management Report the only formal report? |
| Q-09 | Do clients (respondents) enter answers themselves, or only the consultant? |
| Q-10 | Is KPI tracking (calculator + 10-number dashboard) in scope? Per period or per assessment? |
| Q-11 | Which assessment is “previous” for comparison? Is re-assessment always ~90 days? |
| Q-12 | Should the scoring parameters stay editable, and who may change them? |
| Q-13 | Should the business record be an ERPNext Customer? |
| Q-14 | Is the “Responsible” person a system user or free text? |
| Q-15 | Are the report limits (top 10, 15, 50 …) requirements? |
| Q-16 | Confirm N/A counts as answered for completion. |
| Q-17 | Evidence/remarks per assessment; are attachments wanted? |
| Q-18 | Who may see which businesses and assessments? |

---

## 11. Phase 5 audit — Management Report and Owner Dashboard (2026-10-27)

Workbook unchanged (SHA-256 `e3424382…0e22fc`, dump identical to Phase 1). Specifications: **MANAGEMENT REPORT!A1:H115** (print area A1:H115, portrait; two charts: radar and bar of C17:C26) and **OWNER DASHBOARD!A1:P50** (no print area; three charts: bar and radar of A9:B18, line of SCORE CALCULATION!B17:E21).

### 11.1 Q-08 and Q-15

- **Q-08 — “Which reports are required?”** *“The workbook has one formal report (MANAGEMENT REPORT, printed) and on-screen views: Assessment Hub, Gap Analysis, Action Plan, 90-Day Plan, Business Growth Plan, Owner Dashboard (workbook §5). Need: confirm which of these are needed, which must be printable/PDF, and whether the manager chooses between report types (the brief mentions this; the workbook has no such choice).”* Workbook evidence: MANAGEMENT REPORT is the only sheet with a print area and signature lines (B114, F114); INSTRUCTIONS!C9 “MANAGEMENT REPORT is a printable consultant report - add remarks in section 10 and print”; OWNER DASHBOARD has no print area and is described as the on-screen dashboard (INSTRUCTIONS!C7, COVER!D17). **Specified**: one printable report per assessment, one on-screen dashboard. **Undecided**: other report formats, report selection by a manager, distribution. **Handling**: the Management Report becomes a printable (and PDF) print format of BHC Assessment, the Owner Dashboard an on-screen desk page; no report-selection step, no distribution or e-mail.
- **Q-15 — “Are the report limits requirements?”** *“Top 10 gaps, 15 actions, 3 strengths, 3 weakest, 5 growth rows, 50 actions per 90-day phase (W-10). Need: keep as is, or show everything?”* Workbook evidence: MANAGEMENT REPORT!A51:A60 (ranks 1–10), A70:A84 (1–15), B45:B47 (ranks 10, 9, 8), B64:B66 (ranks 1–3), B101:B105 (ranks 1–5) and D101 (“first three steps”). **Specified**: the limits themselves are in the formulas. **Undecided**: whether they are business requirements. **Handling**: the printed report keeps the workbook limits (constants in `management.py`, each citing its cells) and every section says where the full list is (Gap Analysis, 90 Day Plan, Department Results). Reversible by changing the constants.

### 11.2 Management Report content (MANAGEMENT REPORT)

| § | Workbook | Source in the system |
|---|---|---|
| title, A2 | “Prepared by {consultant}, {firm} \| {assessment label} \| {date}” | assessment consultant (user name), business consultancy firm, label, date |
| 1 B5:F7 | company, contact person (designation), industry, location, employees, annual turnover | BHC Business **as it is now** (the workbook also stores one profile, W-20, Q-13) |
| 2 B11:H11, B13 | score, maturity, “answered / questions”, gaps H / M / L; “Current position: … scores {0%} - maturity level …. This is the baseline assessment. / Change since previous assessment: {+0%}.” | stored overall results; change from `get_comparison` (only when both sides have applicable answers, Q-11) |
| 3 B16:F26 + charts | department label, score, maturity short label (“-” when max = 0, D17), previous, change; radar and bar chart | stored department results, scoring model short labels, comparison |
| 4 B45:D47, G45 | departments ranked 10, 9, 8 (score, maturity); “Critical-weight practices fully in place: {Critical and YES} of {Critical and answered} answered” | workbook rank (Phase 3); stored responses |
| 5 A51:H60 | top 10 gaps: department, question, priority, recommendation, risk | stored responses by gap rank |
| 6 B64:E66 | departments ranked 1, 2, 3: score, gaps, department risk | workbook rank; department risk from BHC Department **master (current)** |
| 7 A70:H84 | top 15 gaps: department, action (= recommendation), phase, responsible or “(to be assigned)”, due (target date, else suggested due) | stored gaps + BHC Improvement Action (Phase 4) |
| 8 B88:G97 | Owner’s 10 KPIs | **not available**: KPI tracking is not built (Q-10) |
| 9 B101:D106 | ranks 1–5 with score < growth threshold: score and first three growth steps; “Departments in growth programme: n of 10. …” / “No department is below the growth threshold …” | workbook rank, the assessment’s scoring model threshold, growth recommendations from BHC Department **master (current)** |
| 10 B109:H113, B114:F114 | consultant remarks (input), “Next re-assessment recommended: {date + 90} (after completion of the 90-day plan)”, signature lines Consultant / Management | `consultant_remarks`, stored `suggested_reassessment_date`; printed lines only, no sign-off workflow |

Workbook behaviour kept and flagged rather than changed: §4/§6/§9 use the workbook rank, in which unassessed departments rank as weakest (W-01, W-08, Q-04) — they are printed with “not assessed”; §2/§3 show no change when a side has no applicable answers (Phase 3 rule); §7 distinguishes the recommendation from an agreed action and a suggested from an agreed due date (W-23). The workbook’s §10 instruction “Change Current Assessment No. in COMPANY PROFILE” is replaced by the system’s *Create → Re-assessment*.

### 11.3 Owner Dashboard content (OWNER DASHBOARD)

| Block | Workbook | Source in the system |
|---|---|---|
| A1:A2 | company; label, date, industry, consultant | assessment + business |
| A4:P5 cards | score, maturity, answered, HIGH / MEDIUM / LOW gaps, actions open (= Open + In Progress + Hold), actions completed “n (pct)” | stored results; ACTION PLAN!A4:G4 counters over the **created** actions (in the workbook every gap is an action; here also “gaps with an action”) |
| A8:F19 heat map | label, score, status (MatShort or “Not assessed”, C9), previous, change, gaps; colours by band (A20) | stored results, scoring model bands, comparison |
| A22:D27 trend + chart | assessment, overall score (“-” when nothing answered, B24), answered, date | non-cancelled assessments of the same business the user may read, by date (the workbook’s four columns become separate records) |
| K23:O33 | department previous / current / change | the same values as the heat map (identical formulas R5, H5, S5); not repeated |
| charts | bar, radar of department scores; overall trend line (blank after the last answered assessment, B21) | SVG drawn on the server |
| A36:L48 | Owner’s 10-number dashboard | **not available** (Q-10) |
| A50:H50 | navigation links | links to the reports, the form and the Management Report |

**“Owner”**: the workbook uses it for the business owner / MD who reviews results with the consultant (INSTRUCTIONS!C3, OWNER DASHBOARD!A36 “Owner’s 10-Number …”); it defines no access rule and the system has no owner role or client login (Q-09). The dashboard is therefore available to the existing BHC roles under the existing Assigned Users rule; an owner sees it only if given a BHC role and an assignment.

### 11.4 Blocking decisions

None block the implementation above. Open: Q-08 (other formats / distribution), Q-15 (limits), Q-10 (KPI section stays empty), Q-04 (unassessed in strengths / priorities / roadmap), Q-27 (new: department risks and growth steps come from the current master, not a snapshot).
