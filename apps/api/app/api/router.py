from fastapi import APIRouter

from app.api.routes import analysis, auth, contacts, health, imports, qa, reply_coach, vault

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(contacts.router, prefix="/contacts", tags=["contacts"])
api_router.include_router(imports.router, prefix="/contacts", tags=["imports"])
api_router.include_router(analysis.router, prefix="/contacts", tags=["analysis"])
api_router.include_router(qa.router, prefix="/contacts", tags=["qa"])
api_router.include_router(reply_coach.router, prefix="/contacts", tags=["reply-coach"])
api_router.include_router(vault.router, prefix="/contacts", tags=["vault"])
