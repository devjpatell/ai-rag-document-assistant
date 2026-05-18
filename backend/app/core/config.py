from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    hf_api_token: str = ""
    cors_origins: str = "*"


settings = Settings()
