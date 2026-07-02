from fastapi import APIRouter

from app.api.routes.analytics import router as analytics_router
from app.api.routes.chat import router as chat_router
from app.api.routes.datasets import router as datasets_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.search import router as search_router
from app.api.routes.system import router as system_router
from app.api.routes.video_search import router as video_search_router
from app.api.routes.videos import router as videos_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(chat_router)
api_router.include_router(system_router)
api_router.include_router(documents_router)
api_router.include_router(search_router)
api_router.include_router(videos_router)
api_router.include_router(video_search_router)
api_router.include_router(datasets_router)
api_router.include_router(analytics_router)
