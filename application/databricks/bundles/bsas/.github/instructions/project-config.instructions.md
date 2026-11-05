---
applyTo: "conf/oeds/config/**/*"
---

# Project Configuration

Before modifying project configuration:

1. Follow the [DataForge instructions](../../AGENTS.md).
2. Read the [configuration catalog](../../conf/oeds/config/README.md).
3. Read the developer guide linked for the affected configuration area.
4. Inspect the utility that loads the configuration and its current callers.

## Layout and ownership

- Keep configuration under `conf/oeds/config/<area>` and import it through
  `oeds.config.<area>`.
- Keep `conf/oeds` as a namespace package without an `__init__.py`.
- Put reusable behavior under `src/oeds/domain/utils`; configuration modules
  may define project-specific schemas, mappings, transforms, and declarative
  resources but must not become a parallel utility library.
- Keep JSON, HTML, and other static resources beside the package that loads
  them.

## Validation and documentation

- Validate the complete configuration contract before execution where
  possible, and preserve useful error context when validation fails.
- Never store or log secrets, credentials, tokens, or sensitive payload
  contents.
- Update `conf/oeds/config/README.md`, the owning developer guide, examples,
  and affected tests when a configuration area or contract changes.
- Preserve valid package imports and relative documentation links.
