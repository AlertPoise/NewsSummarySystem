"""应用配置加载。"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从环境变量读取已冻结的应用配置。"""

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_name: str = "news_summary"
    db_user: str = "news_app"
    db_password: str = ""
    db_charset: str = "utf8mb4"
    bert_model_name: str = "CHANGE_ME"
    summarizer_model_name: str = "CHANGE_ME"
    model_dir: str = "../runtime/models"
    dataset_dir: str = "../runtime/datasets"
    hf_home: str = "../runtime/hf_cache"
    log_dir: str = "../runtime/logs"
    model_version: str = "CHANGE_ME"
    summarizer_max_input_tokens: str = "CHANGE_ME"
    summarizer_max_new_tokens: str = "CHANGE_ME"

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        """生成 SQLAlchemy 使用的 MySQL 连接地址。"""
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}?charset={self.db_charset}"
        )


@lru_cache
def get_settings() -> Settings:
    """返回进程内唯一的配置对象。"""
    return Settings()
