from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Groq
    groq_api_key: str = ""

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Sales transfer
    sales_phone_number: str = "+1234567890"

    # Business hours
    business_hours_start: str = "09:00"
    business_hours_end: str = "17:00"
    business_timezone: str = "America/New_York"

    # Dashboard auth (set in .env to protect config edits)
    dashboard_token: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Database (Neon PostgreSQL)
    database_url: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
