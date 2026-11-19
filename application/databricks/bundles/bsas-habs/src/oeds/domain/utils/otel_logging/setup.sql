-- One-time administrator-reviewed setup; neither Python module executes this.
-- https://learn.microsoft.com/en-us/azure/databricks/ingestion/opentelemetry/configure
-- Existing catalog/schema required. Inspect any existing table's actual schema.
CREATE TABLE application.oedataservices_db.otel_logs (
    record_id STRING,
    time TIMESTAMP,
    date DATE,
    service_name STRING,
    event_name STRING,
    trace_id STRING,
    span_id STRING,
    time_unix_nano LONG,
    observed_time_unix_nano LONG,
    severity_number STRING,
    severity_text STRING,
    body VARIANT,
    attributes VARIANT,
    dropped_attributes_count INT,
    flags INT,
    resource STRUCT<attributes: VARIANT, dropped_attributes_count: INT>,
    resource_schema_url STRING,
    instrumentation_scope STRUCT<
        name: STRING, version: STRING, attributes: VARIANT,
        dropped_attributes_count: INT
    >,
    log_schema_url STRING
)
USING DELTA
CLUSTER BY (time, service_name)
TBLPROPERTIES (
    'otel.schemaVersion' = 'v2',
    'delta.checkpointPolicy' = 'classic'
);

-- Replace with the approved Databricks principal's application UUID, not the
-- numeric SCIM ID. Do NOT grant these privileges to the app-local principal.
GRANT USE CATALOG ON CATALOG application TO `<approved-principal-app-id>`;
GRANT USE SCHEMA ON SCHEMA application.oedataservices_db TO `<approved-principal-app-id>`;
GRANT SELECT, MODIFY ON TABLE application.oedataservices_db.otel_logs
TO `<approved-principal-app-id>`;

-- Verification after running example_notebook.py:
SELECT
    time AS timestamp,
    service_name AS application,
    severity_text AS severity,
    body::STRING AS message,
    attributes,
    resource.attributes AS resource_attributes,
    resource.attributes:['deployment.environment.name']::STRING AS environment,
    resource.attributes:['databricks.job.id']::STRING AS job_id,
    resource.attributes:['databricks.job.run_id']::STRING AS job_run_id,
    resource.attributes:['databricks.task.run_id']::STRING AS task_run_id
FROM application.oedataservices_db.otel_logs
WHERE attributes:['smoke_test_id']::STRING = '<printed-smoke-test-marker>'
ORDER BY time;
