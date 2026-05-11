"""Пакет хендлеров"""

from .start import router as start_router
from .duel import router as duel_router
from .profile import router as profile_router
from .shop import router as shop_router
from .referral import router as referral_router
from .admin import router as admin_router

__all__ = ["start_router", "duel_router", "profile_router", "shop_router", "referral_router", "admin_router"]
