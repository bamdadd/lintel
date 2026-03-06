"""Sandbox response models."""


from pydantic import BaseModel


class CreateSandboxResponse(BaseModel):
    sandbox_id: str


class SandboxStatusResponse(BaseModel):
    sandbox_id: str
    status: str


class ExecuteResponse(BaseModel):
    exit_code: int
    stdout: str
    stderr: str


class FileResponse(BaseModel):
    path: str
    content: str = ""
    status: str = ""
