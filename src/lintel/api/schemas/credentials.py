"""Credential response models."""


from pydantic import BaseModel


class CredentialResponse(BaseModel):
    credential_id: str
    credential_type: str
    name: str
    repo_ids: list[str] = []
    secret_preview: str = ""
