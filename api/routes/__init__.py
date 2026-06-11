from api.routes.auth import router as auth_router
from api.routes.info import router as info_router
from api.routes.leaderboard import router as leaderboard_router
from api.routes.predictions import router as predictions_router
from api.routes.stats import router as stats_router
from api.routes.users import router as users_router


__all__ = ["auth_router", "info_router", "leaderboard_router", "predictions_router", "stats_router", "users_router"]
