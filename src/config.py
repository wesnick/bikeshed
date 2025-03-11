from pydantic import PostgresDsn, RedisDsn, Field
from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Config(BaseSettings):
    """Application configuration settings loaded from environment variables"""
    
    # Database settings
    POSTGRES_HOST: str = Field("localhost", description="PostgreSQL host")
    POSTGRES_PORT: int = Field(5432, description="PostgreSQL port")
    POSTGRES_DB: str = Field("flibberflow", description="PostgreSQL database name")
    POSTGRES_USER: str = Field("app", description="PostgreSQL username")
    POSTGRES_PASSWORD: str = Field("pass", description="PostgreSQL password")
    DATABASE_URL: PostgresDsn = Field(None, description="Full PostgreSQL connection string")
    
    # Redis settings
    REDIS_HOST: str = Field("localhost", description="Redis host")
    REDIS_PORT: int = Field(6379, description="Redis port")
    REDIS_DB: int = Field(0, description="Redis database number")
    REDIS_URL: RedisDsn = Field(None, description="Full Redis connection string")
    
    # Application settings
    DEBUG: bool = Field(False, description="Debug mode")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Build DATABASE_URL if not provided
        if not self.DATABASE_URL:
            self.DATABASE_URL = PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=str(self.POSTGRES_PORT),
                path=f"/{self.POSTGRES_DB}"
            )
            
        # Build REDIS_URL if not provided
        if not self.REDIS_URL:
            self.REDIS_URL = RedisDsn.build(
                scheme="redis",
                host=self.REDIS_HOST,
                port=str(self.REDIS_PORT),
                path=f"/{self.REDIS_DB}"
            )


@lru_cache()
def get_config() -> Config:
    """Get cached application config"""
    return Config()
