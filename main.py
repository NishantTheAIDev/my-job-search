import os

import uvicorn

if __name__ == "__main__":
    # Configure logging before uvicorn starts so early startup messages are captured.
    # backend/app.py also calls this on import; the second call is idempotent.
    from backend.config import settings
    from backend.logging_config import configure_logging

    configure_logging(settings.log_level)

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "true").lower() == "true"
    uvicorn.run("backend.app:app", host=host, port=port, reload=reload)
