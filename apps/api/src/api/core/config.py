from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]
    app_env: str = "development"  # used by api/main.py

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
