from .common import router as common_router
from .group_leader import router as group_leader_router
from .regular_member import router as group_member_router
from .topics import router as topics_router

def register_handlers(dp):
    dp.include_router(common_router)
    dp.include_router(group_leader_router)
    dp.include_router(group_member_router)
    dp.include_router(topics_router)