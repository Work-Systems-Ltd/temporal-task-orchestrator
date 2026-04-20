from __future__ import annotations

from fastapi import APIRouter, Depends

from ui.auth.dependencies import require_auth
from ui.views.workflows import WorkflowTableView

router = APIRouter(tags=["workflows_list"], dependencies=[Depends(require_auth)])

# Register the generic table view routes (GET /workflows + GET /api/workflows)
workflow_view = WorkflowTableView()
workflow_view.register(router)
