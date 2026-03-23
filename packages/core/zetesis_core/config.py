from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    database_url: str = "postgresql+asyncpg://zetesis:zetesis_dev@localhost:5432/zetesis"
    inference_backend: str = "mlx"
    inference_model: str = "mlx-community/Qwen2.5-7B-Instruct-4bit"
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    hf_token: str | None = None
    brave_search_api_key: str | None = None


settings = Settings()
