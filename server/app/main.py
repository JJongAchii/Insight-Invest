from fastapi import FastAPI
from sqlalchemy.orm import Session

from .routers import meta

app = FastAPI()

app.include_router(meta.router)