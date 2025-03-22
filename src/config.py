from pydantic import PostgresDsn, RedisDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Config(BaseSettings):
    """Application configuration settings loaded from environment variables"""
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    # Database settings
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str

    # Redis settings
    redis_host: str
    redis_port: int
    redis_db: int
    
    # Application settings
    log_level: str = "INFO"
    log_file: str | None = None


    @computed_field
    def database_url(self) -> PostgresDsn:
        return PostgresDsn.build(
                scheme="postgresql",
                username=self.postgres_user,
                password=self.postgres_password,
                host=self.postgres_host,
                port=self.postgres_port,
                path=self.postgres_db
            )

    @computed_field
    def redis_url(self) -> RedisDsn:
        return RedisDsn.build(
                scheme="redis",
                host=self.redis_host,
                port=self.redis_port,
                path=f"/{self.redis_db}"
            )

@lru_cache()
def get_config() -> Config:
    """Get cached application config"""
    return Config()
