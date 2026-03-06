"""Work item response models."""

from pydantic import BaseModel


class WorkItemResponse(BaseModel):
    work_item_id: str
    project_id: str
    title: str
    description: str = ""
    work_type: str = "task"
    status: str = "open"
    assignee_agent_role: str = ""
    thread_ref_str: str = ""
    branch_name: str = ""
    pr_url: str = ""
