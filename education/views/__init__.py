"""
education.views package (phase 7 — god-file reduction).

Structure
---------
helpers.py   Shared permission/tenant helpers (extracted).
courses.py   Course templates + expense create (extracted).
legacy.py    Remaining large surface (still being split).

Public API is unchanged for callers::

    from education import views
    from education.views import create_payment, course_list

New code should import from the domain module when possible::

    from education.views.courses import course_list
    from education.views.helpers import get_active_center
"""
from __future__ import annotations

# Domain modules first (explicit, preferred).
from education.views.helpers import (  # noqa: F401
    get_active_center,
)
from education.views.courses import (  # noqa: F401
    expense_create,
    course_list,
    course_create,
    course_edit,
    course_delete,
    course_price_api,
)
from education.views.exam_hub import (  # noqa: F401
    exam_hub,
    exam_annual_grades,
    exam_questions,
)

# Legacy monolit — to'liq orqaga moslik (urls, tests, ichki importlar).
from education.views.legacy import *  # noqa: F403, F401
