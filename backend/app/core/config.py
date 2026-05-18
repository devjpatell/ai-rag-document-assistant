from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    hf_api_token: str
    pinecone_api_key: str
    pinecone_index_name: str = "rag-documents-free"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"
    cors_origins: str = "http://localhost:3000"

    class Config:
        env_file = ".env"


settings = Settings()
