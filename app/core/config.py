from typing import List, Union
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    from pydantic import BaseSettings  # type: ignore
    SettingsConfigDict = None  # type: ignore
from pydantic import AnyHttpUrl, field_validator
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "HauSort API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    
    # CORS
    BACKEND_CORS_ORIGINS: List[Union[str, AnyHttpUrl]] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ]

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "hausort"
    DATABASE_URL: Optional[str] = None

    # Scraper Configuration
    SCRAPER_ENABLED: bool = True
    SCRAPER_ALLOWED_HOSTS: List[str] = [
        "example.org",
        "example.com",
        "wg-gesucht.de",
        "www.wg-gesucht.de",
        "immobilienscout24.de",
        "www.immobilienscout24.de",
        "immowelt.de",
        "www.immowelt.de",
        "kleinanzeigen.de",
        "www.kleinanzeigen.de",
    ]
    SCRAPER_REQUEST_TIMEOUT_SECONDS: int = 15
    SCRAPER_MAX_RESPONSE_BYTES: int = 5_000_000  # 5 MB
    SCRAPER_MAX_REDIRECTS: int = 5
    SCRAPER_MAX_URLS_PER_BATCH: int = 10
    SCRAPER_USER_AGENT: str = "HauSortBot/0.1 (+https://github.com/hausort/hausort)"
    SCRAPER_BROWSER_FALLBACK_ENABLED: bool = False
    SCRAPER_BROWSER_TIMEOUT_SECONDS: int = 20

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            if self.DATABASE_URL.startswith("postgresql://"):
                return self.DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
            elif self.DATABASE_URL.startswith("postgres://"):
                return self.DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
            return self.DATABASE_URL
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    if SettingsConfigDict is not None:
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=True,
            extra="ignore",
        )
    else:
        class Config:
            env_file = ".env"
            case_sensitive = True
            extra = "ignore"


settings = Settings()
