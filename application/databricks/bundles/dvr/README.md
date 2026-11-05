# DVR Bundle — SWIFT vs HABS Reconciliation

## Overview

Automated Daily Verification Reporting (DVR) pipeline for SWIFT message reconciliation.
Replaces the manual process where ARM team downloads files from SWIFT.com, uploads to FMBODW,
and manually triggers the reconciliation.

## Components

### Databricks App: `swift-file-upload`
- Dash web app for ARM team to upload DVR Excel files to the landing volume
- Source: `src/swift-file-upload/`
- App URL: `https://swift-file-upload-1700301391505163.3.azure.databricksapps.com`

### Pipeline Notebooks: `src/dvr-pipeline/`
| Notebook | Description |
|---|---|
| `01_validate_swift_files` | Validates filename, worksheet, dates, required fields |
| `02_parse_load_swift` | Parses DVR Excel, FI dim lookups, writes `tbl_swift_message_fact` |
| `03_load_habs_message` | Extracts HABS messages, CLOB parsing, writes `tbl_habs_message_fact` |
| `04_reconcile` | Three-way FULL OUTER JOIN, Warning/Success logic |
| `05_notify` | Email notifications (4 outcome scenarios) |

### Jobs (defined in `resources/jobs.yml`)
- **DVR Swift Pipeline** — started by the Swift File Upload app after ARM uploads a file (no schedule): validate → parse → HABS → reconcile → reports → notify

The Swift job now passes validation and reconciliation results between tasks,
copies validated files to the configured legacy R: drive, and writes retained
CSV and HTML reports under the configured reports volume.

The DVR first release reads HABS data from the existing BAP raw table populated through the
environment-specific HABS foreign catalog. Direct Oracle connectivity and SMM
ingestion are not required for this release. The confirmed legacy drop path is
`/home/asd/datastg/secured/FCRMS/SWIFTDVR_Inbox`.

### DataBridge R-drive transfer

The legacy transfer now follows the DataForge/DataBridge pattern. The copy task
submits `conf/oeds/config/ingest/default.json` through `run_ingest()` and uses
the `oedis.handler.smb.upload` handler. The custom `pysmb` implementation is no
longer used. DataBridge connection details and secret key names remain deployment
parameters until Wei confirms the shared DataBridge configuration.

## Release

The independent DVR release is `release-2.0.0`, defined under
`releases/release-2.0.0/`. Both DVR jobs expose this release through their
`release_version` parameter. Work Package 1's `release-1.0.0` and Julian's
separate release are outside this bundle's release scope.

### Target Tables
#### Derived tables (`${var.catalog}.derived_db`)
> In dev: `dev_banking_and_payments_cat.derived_db`
- `tbl_swift_message_fact` — parsed SWIFT DVR file data
- `tbl_swift_habs_recon_results_fact` — reconciliation results
- `tbl_dvr_file_processing_log` — file lifecycle audit trail

#### Curated/reference tables (`${var.catalog}.curated_db`)
> HABS and shared reference data remain in `dev_banking_and_payments_cat.curated_db` in dev.
- `tbl_habs_message_fact` — transformed HABS data for reconciliation
- `tbl_swift_message_status_dim` — message status dimension

## Pre-Go-Live Checklist

- [x] **Volume GRANT**: Granted for the Swift upload service principal
  ```sql
  GRANT READ VOLUME, WRITE VOLUME
    ON VOLUME dev_banking_and_payments_cat.reference_db.vol_bap_land
    TO `8131d8f0-22ef-4c2b-af25-73e71def7ece`;
  ```
- [ ] **ARM AD Group**: Ask Geneviève to create AD group, then:
  1. Open App → Share → Add group with `CAN_USE`
  2. This restricts file upload to authorized ARM team members only
- [ ] **EMAIL_SERVICE_URL**: Configure the email endpoint in job parameters
  - Sender: `FMBODW_Support_Noreply@bank-banque-canada.ca`
  - Recipients: `FBD-Accountriskmanagement@bank-banque-canada.ca`, `FBSDSOS@bank-banque-canada.ca`
- [ ] **Unpause jobs**: Once volume GRANT and email are configured, set schedule to UNPAUSED
- [ ] **PR**: Merge `feature/dvr-swift-upload` → `develop`

The volume grant and ARM AD group are intentionally external prerequisites and
are not changed by this bundle. HABS Oracle/foreign-catalog connectivity, SMM
source/schema confirmation, the approved email endpoint, and PDF rendering
service must be supplied by the platform/data owners before go-live. Direct
Oracle connectivity is not required by the DVR first release, and SMM
ingestion is deferred.

## Escalation Flow

ARM → SOS (Barton Loutit / Devin Blackmore) → PSO → CIRP

## Bundle Targets

| Target | Catalog | Mode |
|---|---|---|
| `dev` (default) | `dev_banking_and_payments_cat` | development |
| `stg` | `stg_banking_and_payments_cat` | production |
| `prd` | `prd_banking_and_payments_cat` | production |

Volume path pattern: `/Volumes/${var.catalog}/reference_db/vol_bap_land/swift/`
