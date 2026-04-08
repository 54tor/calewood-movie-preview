from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    calewood_api_base_url: str = Field(default="https://calewood.n0flow.io/api", alias="CALEWOOD_API_BASE_URL")
    calewood_api_token: str = Field(alias="CALEWOOD_API_TOKEN")
    calewood_api_timeout_seconds: float = Field(default=30.0, alias="CALEWOOD_API_TIMEOUT_SECONDS")
    calewood_api_verify_tls: bool = Field(default=True, alias="CALEWOOD_API_VERIFY_TLS")
    calewood_api_archived_statuses: str = Field(default="pre_archiving,awaiting_fiche,post_archiving", alias="CALEWOOD_API_ARCHIVED_STATUSES")
    calewood_api_category: str = Field(default="XXX", alias="CALEWOOD_API_CATEGORY")
    calewood_api_per_page: int = Field(default=200, alias="CALEWOOD_API_PER_PAGE")
    calewood_api_single_id: int | None = Field(default=None, alias="CALEWOOD_API_SINGLE_ID")
    calewood_api_pre_archiving_status: str = Field(default="my-pre-archiving", alias="CALEWOOD_API_PRE_ARCHIVING_STATUS")
    hash_field_name: str = Field(default="info_hash", alias="HASH_FIELD_NAME")

    qbittorrent_base_url: str = Field(alias="QBITTORRENT_BASE_URL")
    qbittorrent_username: str = Field(alias="QBITTORRENT_USERNAME")
    qbittorrent_password: str = Field(alias="QBITTORRENT_PASSWORD")
    qbittorrent_timeout_seconds: float = Field(default=30.0, alias="QBITTORRENT_TIMEOUT_SECONDS")
    qbittorrent_verify_tls: bool = Field(default=True, alias="QBITTORRENT_VERIFY_TLS")

    imgbb_api_key: str = Field(alias="IMGBB_API_KEY")
    imgbb_timeout_seconds: float = Field(default=30.0, alias="IMGBB_TIMEOUT_SECONDS")

    image_format: str = Field(default="jpg", alias="IMAGE_FORMAT")
    dry_run: bool = Field(default=True, alias="DRY_RUN")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="text", alias="LOG_FORMAT")
    temp_dir: Path = Field(default=Path("/tmp/movie-preview"), alias="TEMP_DIR")
    requests_retry_count: int = Field(default=2, alias="REQUESTS_RETRY_COUNT")
    preflight_max_items: int = Field(default=9, alias="PREFLIGHT_MAX_ITEMS")
    ffmpeg_bin: str = Field(default="ffmpeg", alias="FFMPEG_BIN")
    ffprobe_bin: str = Field(default="ffprobe", alias="FFPROBE_BIN")
    path_map_source: str | None = Field(default=None, alias="PATH_MAP_SOURCE")
    path_map_target: str | None = Field(default=None, alias="PATH_MAP_TARGET")

    @field_validator("calewood_api_single_id", mode="before")
    @classmethod
    def normalize_single_id(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str) and value.strip().lower() in {"", "none", "null"}:
            return None
        return value

    def archived_statuses(self) -> set[str]:
        return {item.strip() for item in self.calewood_api_archived_statuses.split(",") if item.strip()}
