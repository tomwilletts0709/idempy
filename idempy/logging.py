"""Logging configuration for idempy.

As a library, idempy follows the standard Python convention of adding a
``NullHandler`` to its root logger so that log records are silently discarded
unless the *application* configures a handler.  This means idempy never
pollutes an application's log output without the application's consent.

All internal loggers use the ``idempy.*`` namespace so callers can target them
precisely::

    import logging
    logging.getLogger("idempy").setLevel(logging.DEBUG)

For applications that want idempy's logs written to stdout during development,
:func:`configure_logging` is provided as a convenience helper.  Call it once
at application startup — not imported automatically::

    from idempy.logging import configure_logging
    configure_logging(level=logging.DEBUG)
"""

import logging

# Silence "No handlers could be found for logger 'idempy'" warnings in
# applications that have not configured any handlers.
logging.getLogger("idempy").addHandler(logging.NullHandler())


def configure_logging(
    level: int = logging.INFO,
    fmt: str = "%(asctime)s  %(name)-30s  %(levelname)-8s  %(message)s",
) -> None:
    """Attach a ``StreamHandler`` to the ``idempy`` logger.

    Intended for use in applications and development scripts, not in
    production library code.

    Args:
        level: Logging level, e.g. ``logging.DEBUG`` or ``logging.WARNING``.
            Defaults to ``logging.INFO``.
        fmt: Log format string. Defaults to a timestamped, aligned format.
    """
    logger = logging.getLogger("idempy")
    if logger.handlers and not all(
        isinstance(h, logging.NullHandler) for h in logger.handlers
    ):
        return  # already configured — don't add a second handler

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt))
    logger.addHandler(handler)
    logger.setLevel(level)
