"""Application entry point: creates the FastAPI app, middleware and routers."""

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from slowapi.errors import RateLimitExceeded

from src.api import auth, contacts, users, utils
from src.conf.config import settings
from src.services.limiter import limiter

app = FastAPI(
    title="Contacts API",
    description="REST API for storing and managing contacts",
    version="0.3.0",
)

app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Return 429 with a JSON body when a rate limit is exceeded."""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Too many requests. Try again later."},
    )


@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
async def root():
    """Redirect the site root to the interactive API documentation."""
    return RedirectResponse(url="/docs")


app.include_router(utils.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(contacts.router, prefix="/api")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
