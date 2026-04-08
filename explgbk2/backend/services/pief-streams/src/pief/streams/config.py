from pydantic_settings import BaseSettings, SettingsConfigDict


class StreamSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9094"
    CDC_TOPIC: str = "elog-v1-cdc-raw"


settings = StreamSettings()
