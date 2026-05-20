# Semantic layer plan: the customer Branch Performance source

Apply these renames, descriptions and hide flags to each table's `nativeFields` when building the data source. Default rule for any field not listed: convert SNAKE_CASE to Title Case for the label, leave description blank, leave visible=true.

## Source-level

- **Name**: `the customer Branch Performance (VDD demo)`
- **Description**: "Demo data source over a local sample of the customer's debit-order data, for building and testing the semantic layer before porting to the the customer tenant."

## Table 1: `branch` → data entity label "Branches"

Entity description: "Merchant branches with status, region, and operational configuration."

| Original | New label | Description | Visible |
|---|---|---|---|
| BRANCH_CD | Branch Code | Primary identifier for a branch | true |
| BILL_CD | Billing Code | Distinct from Branch Code, used for billing routing | true |
| DESCRIPTION | Branch Name | Full branch name for display | true |
| SHORT_NAME | Branch Short Name | Short label for compact displays | true |
| REGION | Region | Geographic region (e.g. WGauteng, KZN) | true |
| STATUS | Branch Status | Active, Suspended, etc. | true |
| GROUP_CD | Branch Group | Group code, "Unassigned" if no group | true |
| ORG_CD | Organisation Code | Parent organisation identifier | true |
| BRANCH_INSTALL_DT | Branch Install Date | Date the branch was activated. Primary time field for branch-level trends. | true |
| PAY_AWAY_ENABLED | Pay-Away Enabled | Y/N flag for the Pay-Away feature | true |
| PAY_AWAY_ACTIVE_DT | Pay-Away Active Date | Date Pay-Away went live for this branch | true |
| IFEE_ENABLED | Internal Fee Enabled | Y/N flag (confirm with customer) | true |
| IFEE_TYPE | Internal Fee Type | | true |
| FEE_PROF | Fee Profile | Which fee schedule applies | true |
| ACCESS_PROF | Access Profile | Operational access tier | true |
| COMM_PROF | Commission Profile | | true |
| NLR_ENABLED | NLR Enabled | National Loan Register flag (confirm) | true |
| ILR_ENABLED | ILR Enabled | Confirm meaning with customer | true |
| INFUSSION_ENABLED | Infusion Enabled | the customer product feature flag (confirm) | true |
| PAY_AWAY_START_EXTRACT | | Internal extract timestamp | **false** |
| PAY_AWAY_EXTRACT | | Internal extract timestamp | **false** |
| FEATURES | | Blob field, noisy | **false** |

## Table 2: `branch_legal_entity` → "Legal Entities"

Entity description: "Legal entity details for each branch including registration, industry and contact data."

| Original | New label | Description | Visible |
|---|---|---|---|
| BRANCH_CD | Branch Code | Join key to Branches | true |
| ORG_CD | Organisation Code | | true |
| REG_ENTITY | Legal Entity Name | | true |
| TRADE_NAME | Trading Name | | true |
| LEGAL_STRUCTURE | Legal Structure | Pty Ltd, CC, Sole Prop, etc. | true |
| INDUSTRY | Industry | Primary industry classification | true |
| REGUL_BODY | Regulatory Body | Which body the entity is registered with | true |
| REGUL_BODY_REG_ACTIVE | Regulatory Registration Active | Y/N flag | true |
| REGUL_BODY_REG_DT | Regulatory Registration Date | | true |

Hide everything else in this table: all BAC_* fields, all PHYS_*, all POST_*, REG_NUMBER, VAT_NUMBER, INCOME_TAX_NUMBER, REGUL_BODY_NUM, PSSF_*, FIC_REG_NUM. Reasons: PII, sensitive identifiers, balloons distinct-value pre-fetches.

## Table 3: `branch_details` → "Branch Details"

Entity description: "Extended attributes for branches including admin programme usage and licensing."

| Original | New label | Description | Visible |
|---|---|---|---|
| BRANCH_CD | Branch Code | Join key | true |
| ORG_CD | Organisation Code | | true |
| TRADE_NAME | Trading Name | | true |
| INDUSTRY | Industry | | true |
| ADM_PROG_USE | Admin Programme Used | | true |
| ADM_PROG_USE_LIC | Admin Programme Licence | | true |
| LAST_VISIT_DT | Last Visit Date | | true |
| DOC_EXPIRY_DT | Document Expiry Date | | true |

Hide everything else: all TEL_*, EMAIL, CONTACT_PERSON, NOTE, all PHYS_*, POST_*, LONGITUDE, LATITUDE, BUREAU_CD, TN_ALIAS, all REG_NUMBER / VAT_NUMBER / REGUL_BODY_* / REGUL_BODY_NUM, CREATE_DT, TERM_DT.

## Table 4: `idm_branch_perf_v1` → "Branch Performance"

Entity description: "Monthly branch performance metrics: dispositions, successes, failures, fees and costs by branch."

Keep all fields visible. Rename labels:

| Original | New label |
|---|---|
| BRANCH_CD | Branch Code |
| ORG_CD | Organisation Code |
| MONTH_DT | Month (primary time field for monthly trends) |
| INDUSTRY | Industry |
| CLASSIFICATION | Classification |
| PMT_STREAM | Payment Stream |
| MSG_TYPE | Message Type |
| TOTAL_AMT | Total Amount |
| INST_AMT | Instalment Amount |
| NUM_SUCCESS | Successful Count |
| NUM_FAIL | Failed Count |
| NUM_DISP | Disputed Count |
| NUM_SUSP | Suspended Count |
| NUM_TRACK | Tracked Count |
| VAL_SUCCESS | Successful Value |
| VAL_FAIL | Failed Value |
| VAL_DISP | Disputed Value |
| FEE_SUCCESS | Fees on Success |
| FEE_FAIL | Fees on Failure |
| FEE_DISP | Fees on Dispute |
| FEE_SUSP | Fees on Suspension |
| FEE_TRACK | Fees on Tracking |
| IFEE_SUCCESS | Internal Fees on Success |
| IFEE_INST_AMT | Internal Fee Instalment Amount |
| COST_SUCCESS | Cost on Success |
| COST_FAIL | Cost on Failure |
| COST_DISP | Cost on Dispute |
| COST_SUSP | Cost on Suspension |
| COST_TRACK | Cost on Tracking |
| LAST_AUTH_MODE | Last Authorisation Mode |
| REPLY_CD | Reply Code |
| REPLY_MSG | Reply Message |

## Table 5: `idm_monthly_due_v2` → "Monthly Dues"

Entity description: "Monthly amounts due to be collected per branch and finance code."

| Original | New label | Description | Visible |
|---|---|---|---|
| BRANCH_CD | Branch Code | Join key | true |
| ORG_CD | Organisation Code | | true |
| MONTH_DT | Month | Primary time field. | true |
| FIN_CD | Finance Code | Finance/funder identifier (e.g. CAPITEC_SO) | true |
| PROM_TYPE | Promise Type | (e.g. RMAN) | true |
| NUM_DUE | Count Due | Number of debit orders due | true |
| AMT_DUE | Amount Due | Total monetary amount due | true |
| CHECK_TS | | Snapshot timestamp, metadata not analytical | **false** |

## Table 6: `idm_fee_stats_v3` → "Fee Statistics"

Entity description: "Monthly fee revenue and transaction statistics by branch and payment stream."

| Original | New label | Description | Visible |
|---|---|---|---|
| BRANCH_CD | Branch Code | Join key | true |
| ORG_CD | Organisation Code | | true |
| MONTH_DT | Month | Primary time field. | true |
| PMT_STREAM | Payment Stream | | true |
| MSG_TYPE | Message Type | | true |
| TRN_DESC | Transaction Description | | true |
| TRN_COUNT | Transaction Count | | true |
| TRN_AMT | Transaction Amount | Total transaction value | true |
| TRN_FEE | Transaction Fee | Total fees on these transactions | true |
| LAST_AUTH_MODE | Last Authorisation Mode | | true |
| STAT_VAL1 | | Generic statistical value, unclear meaning | **false** |
| STAT_VAL2 | | Generic statistical value, unclear meaning | **false** |
| WEB_USER_ID | | Internal user id (PII) | **false** |

## Source-level settings

- **Primary join key across all tables**: `BRANCH_CD`
- **Time bar**: set to off
- **Default time field for trend questions**: `MONTH_DT` in fact tables (`idm_*`), `BRANCH_INSTALL_DT` for branch-level trends
