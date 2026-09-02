from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def find_root() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        if (p / "contracts" / "AgriChain.sol").exists():
            return p
        if (p / "app" / "main.py").exists() and (p / "requirements.txt").exists():
            return p
    return here.parents[3]


ROOT = find_root()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ROOT / ".env"), extra="ignore")

    app_name: str = "AgriChain"
    secret_key: str = "change-me-in-production-agrichain-hackathon"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12
    database_url: str = f"sqlite:///{ROOT / 'data' / 'agrichain_v2.db'}"
    chain_path: str = str(ROOT / "data" / "chain_v2.json")
    uploads_dir: str = str(ROOT / "uploads")
    qr_dir: str = str(ROOT / "data" / "qr")
    frontend_url: str = "http://127.0.0.1:5173"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8080,http://localhost:8080"
    blockchain_mode: str = "python"  # python | ethereum
    pow_difficulty: int = 2
    ethereum_rpc: str = "http://127.0.0.1:8545"
    contract_address: str = ""
    max_upload_mb: int = 5

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
Path(settings.uploads_dir).mkdir(parents=True, exist_ok=True)
Path(settings.qr_dir).mkdir(parents=True, exist_ok=True)
Path(ROOT / "data").mkdir(parents=True, exist_ok=True)
