"""Framework middleware adapters for idempy.

Each adapter is in its own module to keep framework-specific imports isolated —
importing ``idempy.middleware.flask`` will not pull in FastAPI or Django, and
vice versa.

Available adapters::

    from idempy.middleware.flask import IdemMiddleware    # Flask
    from idempy.middleware.fastapi import IdemMiddleware  # FastAPI / Starlette
    from idempy.middleware.django import IdemMiddleware   # Django
"""
