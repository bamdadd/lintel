# lintel-frontend-targets-api

Multi-frontend target management for Lintel projects. Register and manage web, iOS, Android, and Electron frontend targets within a single project.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/frontend-targets` | Register a target platform |
| GET | `/frontend-targets` | List targets (filter by `project_id`, `platform`) |
| GET | `/frontend-targets/{id}` | Get a specific target |
| PATCH | `/frontend-targets/{id}` | Update a target |
| DELETE | `/frontend-targets/{id}` | Remove a target |

## Supported Platforms

- `web` — Web applications
- `ios` — iOS mobile apps
- `android` — Android mobile apps
- `electron` — Desktop Electron apps
