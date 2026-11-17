from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "semantic_fabric"
    postgres_user: str = "fabric_admin"
    postgres_password: str = "change_me_in_production"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "mistral"

    enable_hitl_approval: bool = True
    allow_write_queries: bool = False
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
