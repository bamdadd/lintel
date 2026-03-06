"""Export OpenAPI spec without starting the server."""

import json
from pathlib import Path

from lintel.api.app import create_app

app = create_app()
spec = app.openapi()
Path("openapi.json").write_text(json.dumps(spec, indent=2))
print(f"Exported {len(spec['paths'])} paths to openapi.json")
