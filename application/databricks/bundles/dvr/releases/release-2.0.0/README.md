# DVR release-2.0.0

This directory identifies the independent DVR release.

## Scope

- Swift DVR `.xlsx` upload through the `swift-file-upload` Databricks App.
- Swift file validation, parsing, and curated fact loading.
- Copy of validated Swift files to the legacy DataStage drop path.
- HABS Swift-message loading from the existing BAP raw HABS table.
- Swift-versus-HABS reconciliation.
- CSV/HTML report generation and notification orchestration.
- Weekday 7:00 AM pipeline and 2:00 PM missing-file check.

## Release boundaries

- This release belongs to the `dvr` bundle only.
- Work Package 1 `release-1.0.0` is not modified or reused.
- Julian's separate release is outside this release directory and deployment scope.
- Runtime schedules remain paused until the external prerequisites are complete.

## Deployment

Deploy this release through the DVR bundle using the `release_version` job parameter:

```text
release-2.0.0
```

Required external prerequisites include Unity Catalog volume permissions, ARM App
`CAN_USE` access, the approved email endpoint, and confirmation that the Databricks
job runtime can reach the legacy drop path.
