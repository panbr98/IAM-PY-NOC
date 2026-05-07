from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn

from server_app.core.bootstrap import initialize_database
from server_app.service.api.governance_routes import router as governance_router
from server_app.service.api.phase_routes import router as phase_router
from server_app.service.api.routes import router
from shared.config.settings import get_settings

settings = get_settings()

@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title=settings.product_name, lifespan=lifespan)
app.include_router(router, prefix=settings.api_base_path)
app.include_router(governance_router, prefix=settings.api_base_path)
app.include_router(phase_router, prefix=settings.api_base_path)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def main() -> None:
    uvicorn.run(
        "server_app.service.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
