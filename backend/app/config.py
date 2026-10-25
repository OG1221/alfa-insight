from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
ALLOWED_MODELS = {'Gemma 4 26B A4B', 'GLM-5.3-Flash', 'Qwen3.6 35B A3B', 'DeepSeek-V4.1-Flash', 'Qwen3-VL-30B-A3B-Instruct', 'Kimi-K2.6'}

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    database_url: str = 'postgresql+psycopg://alfa@127.0.0.1:55432/alfa_insight'
    demo_mode: bool = True
    demo_token: str = 'alfa-local-demo'
    admin_token: str = 'alfa-local-admin'
    llm_mode: str = 'disabled'
    llm_api_key: str = ''
    llm_base_url: str = ''
    llm_model: str = ''
    llm_approved_name: str = ''
    llm_protocol: str = ''
    llm_max_tokens: int = 1800
    llm_timeout: int = 35
    llm_daily_budget_rub: float = 500
    llm_input_rub_per_million: float = 0
    llm_output_rub_per_million: float = 0
    agent_max_steps: int = 24
    agent_timeout: int = 90
    news_hosts: str = 'www.cbr.ru,cbr.ru,www.interfax.ru,interfax.ru,tass.ru,www.rbc.ru'

settings = Settings()
