from typing import Any

from pydantic import PostgresDsn, RedisDsn, Field
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, EnvSettingsSource
from functools import lru_cache
import os

class Config(BaseSettings):
    """Application configuration settings loaded from environment variables"""

    # Database settings
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    database_url: PostgresDsn

    # Redis settings
    redis_host: str
    redis_port: int
    redis_db: int
    redis_url: RedisDsn
    
    # Application settings
    debug: bool
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Build DATABASE_URL if not provided
        if not self.database_url:
            self.database_url = PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                path=f"/{self.postgres_db}"
            )
            
        # Build REDIS_URL if not provided
        if not self.redis_url:
            self.redis_url = RedisDsn.build(
                scheme="redis",
                host=self.redis_host,
                port=self.redis_port,
                path=f"/{self.redis_db}"
            )


@lru_cache()
def get_config() -> Config:
    """Get cached application config"""
    return Config()
