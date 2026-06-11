import sqlalchemy
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .config import settings

metadata = MetaData(schema="pricing")
engine: AsyncEngine = create_async_engine(settings.database_url, future=True)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
