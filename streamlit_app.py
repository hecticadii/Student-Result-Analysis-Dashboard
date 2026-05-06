"""Streamlit Community Cloud entrypoint.

This thin wrapper keeps the deploy target separate from the offline
report-generation script in `app.py`.
"""

import dashboard  # noqa: F401
