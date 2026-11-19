# DataForge Workflow Selection Instructions

Use these instructions after accepting Job Setup during DataForge initialization to choose the
workflows that support the project's complete data lifecycle. Base the selection
on processing complexity, team ownership, upstream dependencies, and release
timelines.

## Data Lifecycle And Team Responsibilities

A complete data process has three stages:

| Stage | Typical owner | Responsibility |
| --- | --- | --- |
| Ingestion | Data engineers | Ingest data from source systems, preserve it in the raw zone of the data lake, and load standardized tables in Unity Catalog. |
| Curation | Business data analysts | Apply business curation logic to standardized data and write curated tables in Unity Catalog. |
| Integration | Data engineers | Disseminate curated data to downstream consumers such as the AE time-series system, internal systems such as SAP, or external systems such as Stanscan. |

## Available Workflows

DataForge provides four workflow definitions:

- `DATAFLOW` is optional and can implement ingestion, curation, and integration
  in one staged workflow.
- `CURATION` is optional and can implement curation, integration, or both under
  an independent job identity and release lifecycle.
- `OPERATION` is optional and supports general single-task operational work.
- `SERVICE` provides project release and maintenance utilities. Enable it for
  every project with Job Setup enabled, regardless of optional workflow selections.

After Job Setup is accepted, the agent discovers `resources/jobs/*.yml` except
`common.yml`, which supplies shared variables. SERVICE is required and locked;
optional workflows can be selected individually. Declining Job Setup skips this
selection and excludes all job YAML, including common.yml. Choose `DATAFLOW`, `CURATION`, and `OPERATION` according
to the project design; any combination of these optional processing workflows
is valid.

## Recommended Project Patterns

Use one of these three common patterns.

### 1. One Dataflow Bundle

Use one bundle with `DATAFLOW` when curation is straightforward, depends mainly
on the current dataset, and can share the ingestion release timeline. Implement
ingestion, curation, and integration as stages of the same workflow.

### 2. Separate Dataflow And Curation Bundles

Keep ingestion and standardization in a Dataflow bundle, and put complex or
multi-dataset curation in a separately released bundle with `CURATION`. This
supports a business data analyst release timeline. Integration normally stays
with the curation it consumes, allowing data engineers and business data
analysts to own different tasks in the same Curation bundle.

### 3. Legacy Curation With An Integration-Focused Curation Bundle

When curation remains in standalone legacy notebooks, create a separate bundle
with `CURATION` for integration. The legacy curation logic can later be migrated
into the same workflow so curation and integration share one lifecycle.

## Selection Checklist

Before confirming the workflow selection:

- Identify the owner and release timeline for ingestion, curation, and
  integration.
- Determine whether curation depends only on the current dataset or on multiple
  standardized datasets.
- Keep integration with the curation it consumes unless a legacy or operational
  constraint requires a separate implementation.
- Enable only the optional processing workflows required by the selected
  project pattern.
- Always enable `SERVICE`.
