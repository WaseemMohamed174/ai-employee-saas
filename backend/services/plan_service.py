"""Plan service — business logic for listing plans (public catalog)."""
from __future__ import annotations

from backend.schemas.plan import PlanResponse, plan_to_response
from database.connection import platform_session
from database.queries import plans as plans_q


# ============== LIST PLANS ==============

def list_plans() -> list[PlanResponse]:
    """Returns all plans ordered by price ascending (free_trial first)."""
    with platform_session() as conn:
        rows = plans_q.get_all_plans(conn)
    return [plan_to_response(dict(row)) for row in rows]
