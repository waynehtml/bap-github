# Logging

## When to use this capability

Use `log_utils` at a notebook or job entry point to establish a consistent root logging level and format. Library modules should retrieve a named logger and let the entry point own configuration.

## Choose the public API

- Call `setup_logger` once near startup when the workload should configure root logging.
- Call `get_logger` for a required named logger, or use Python's `logging.getLogger(__name__)` directly.

## Restrictions and side effects

`setup_logger` changes global process logging. It keeps existing handlers, adds a stream handler only when none exist, and can replace the formatter on every compatible existing handler. It also forces the `py4j` logger to `WARNING`. An unknown level name falls back to `INFO`.

Avoid logging credentials, tokens, email bodies, sensitive DataFrame samples, storage payloads, or internal identifiers. Several I/O utilities already log lifecycle details; choose the root level with those messages in mind.

## Short example

```python
from oeds.core.log_utils import get_logger, setup_logger

setup_logger(level="INFO")
logger = get_logger(__name__)
logger.info("Starting input validation")
```

## Related examples

- [Logging example](../../examples/log_utils/configure_logging.py)
