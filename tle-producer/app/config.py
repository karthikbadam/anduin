from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ingest_api_url: str = "http://ingest-api:8000"
    anduin_dev_api_key: str = "dev-key-anduin-local-only"

    tle_source: str = "fixture"
    celestrak_group: str = "active"  # `active` is the full 11k catalog (often 403s);
                                     # `stations` (~30 sats) is reliable for dev.
    celestrak_user_agent: str = "anduin/0.1 (contact: unset@example.com)"
    n2yo_api_key: str = ""
    spacetrack_user: str = ""
    spacetrack_password: str = ""

    watchlist_norad_ids: str = "25544,20580,48274"
    propagation_tick_seconds: int = 5
    bulk_cadence_seconds: int = 30
    tle_fetch_interval_minutes: int = 180
    healpix_nside: int = 64

    stub_propagate: bool = True  # Stage 1 default: drift-only positions until SGP4 is implemented

    def watchlist(self) -> list[str]:
        return [s.strip() for s in self.watchlist_norad_ids.split(",") if s.strip()]


settings = Settings()
