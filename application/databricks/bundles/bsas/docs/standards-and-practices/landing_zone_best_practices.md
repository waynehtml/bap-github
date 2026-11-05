# Landing Zone Best Practices

## 0. Access Landing Zone Through Unity Catalog Volumes

Landing zone storage should be accessed through approved Unity Catalog volumes, for example:

```text
/Volumes/<catalog>/<schema>/<volume>/
```

Example:

```text
/Volumes/dev_financial_market_cat/reference_db/vol-triton-land/
```

Using volumes provides a governed access path with Unity Catalog permissions, instead of having pipelines directly access the underlying cloud storage path.

---

## 1. Recommended Folder Structure

Downloaded files should be organized by provider, dataset, and ingestion date or timestamp.

Recommended pattern:

```text
{provider}/{dataset}/{date_or_timestamp}/{data_files}
```

Example:

```text
vol-triton-land/
  paycan/
    daily_transactions/
      2026-05-15/
        transactions_001.csv
        transactions_002.csv
```

This structure makes the landing zone easy to navigate, audit, reload, and troubleshoot.

---

## 2. Redownload and Overwrite

If files need to be downloaded again for the same provider, dataset, and date/timestamp, the ingestion process may overwrite the existing files.

This is acceptable when the rerun is intentional and the same landing folder represents the same logical ingestion batch.

Recommended behavior:

```text
If redownload is required:
  overwrite files in the same landing folder
```

This avoids creating duplicate copies of the same logical data delivery.

---

## 3. Do Not Clean Up Landing Files in Pipelines

Pipelines should not delete landing-zone files after processing.

Landing files should remain available for:

```text
reload
reprocessing
audit
debugging
reconciliation
incident investigation
downstream validation
```

Cleanup of landing-zone files should be managed by the storage retention policy.

Current retention expectation:

```text
Storage retention policy manages cleanup.
Files will be Soft deleted in 7 days.
```

Pipelines may clean up temporary staging or working folders, but they should not clean up durable landing-zone data.

---

## 4. Why Pipelines Should Not Delete Landing Files

Landing-zone files are the handoff point between ingestion and downstream processing. They are also the recovery point if something goes wrong later.

A pipeline run can succeed technically, but the data may still need to be reviewed or reloaded later due to issues such as:

```text
incorrect downstream mapping
schema validation failure
business rule issue
duplicate handling issue
partial downstream load
incident investigation
manual reconciliation
```

If the pipeline deletes the landing files immediately, the team may need to request the source system or vendor to resend the data. This creates operational risk and increases support effort.

Keeping files in the landing zone also improves auditability. Teams can verify exactly what was received, when it was received, and what data was used for downstream processing.

Therefore, the recommended pattern is:

```text
Landing-zone cleanup: storage retention policy
```

This keeps pipeline logic simple, protects reload capability, and provides a consistent enterprise data ingestion pattern.
