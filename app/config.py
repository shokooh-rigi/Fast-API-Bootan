import os


class Settings:
    def __init__(self) -> None:
        self.database_url = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://pricing_user:pricing_pass@localhost:5432/pricing",
        )
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.default_commission_rate_bps = 1000
        self.currency = "IRR"


settings = Settings()
