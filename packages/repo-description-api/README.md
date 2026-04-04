# lintel-repo-description-api

Project-scoped repository description editor for Lintel. Allows setting, retrieving, listing, and deleting per-repository descriptions within a project.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| PUT | `/projects/{id}/repositories/{repo_id}/description` | Set/update repo description |
| GET | `/projects/{id}/repositories/{repo_id}/description` | Get a single repo description |
| GET | `/projects/{id}/repo-descriptions` | List all descriptions for a project |
| DELETE | `/projects/{id}/repositories/{repo_id}/description` | Remove a repo description |
