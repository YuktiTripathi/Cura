from pathlib import Path

from dotenv import load_dotenv
from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Cura's backend/.env must win over inherited SuperShyft DATABASE_URL values.
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        extra="ignore",
    )

    app_env: str = "development"
    database_url: str = "sqlite:///./cura.db"
    auth_provider: str = "mock"
    health_provider: str = "mock"
    auth_jwt_secret: str = ""
    auth_jwt_algorithm: str = "HS256"
    # Preferred: Supershyft's JWKS endpoint for RS256/ES256 tokens. When set, the shared
    # HS256 secret is not used and exp, iss and aud are required.
    auth_jwks_url: str = ""
    auth_jwt_algorithms: str = "RS256"
    auth_jwt_issuer: str = ""
    auth_jwt_audience: str = ""
    auth_subject_claim: str = "sub"

    # OpenRouter is the only inference gateway (Jev routing + medical LLM).
    llm_provider: str = "openrouter"
    llm_api_key: str = ""
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_http_referer: str = ""
    openrouter_app_title: str = "Cura"
    llm_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = ""
    medical_llm_model: str = "google/gemini-3.8-flash"
    jev_model: str = "typesafe/jev-1.13"
    jev_enabled: bool = True
    jev_timeout_seconds: int = 10
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 1
    llm_max_output_tokens: int = 800
    # Reasoning models (plan 6.6): effort and the output cap that includes hidden reasoning.
    # Reuse a model answer for an identical prompt (same data, question and context). 0 disables.
    answer_cache_ttl_seconds: int = 86400
    # Reuse an identical prompt's answer. Turn off for cold-latency measurement and evals.
    answer_cache_enabled: bool = True
    answer_prompt_compact: bool = False
    # legacy keeps the current system text. modular uses the compact core plus task modules.
    cura_prompt_variant: str = "legacy"
    # Diagnostic package cards and retest suggestions. Off until explicitly enabled.
    cura_test_suggestions_enabled: bool = False
    # CURA_RESPONSE_MODE: "rich" (cards, tables, chips) or "plain" (the conversational answer
    # only). Plain mode debugs answer quality separately from presentation.
    cura_response_mode: str = "rich"
    # Plain mode: value lookups ("what is my LDL?") are answered by the model at minimal
    # density so the reply can say how much the value matters. False keeps the template.
    plain_lookups_use_model: bool = True
    # Skip the Jev router call for unambiguous single-value lookups and short definitions.
    jev_fast_path: bool = True
    # Answer plain definition questions from a reviewed passage without a model (cost lever 4).
    deterministic_definitions_enabled: bool = True
    # Bump to invalidate every cached answer, for example after a prompt or model change.
    answer_cache_version: str = "1"
    llm_reasoning_effort: str = "low"
    llm_reasoning_output_cap: int = 1200
    enable_llm: bool = False
    allow_mock_auth_with_real_health: bool = False
    mock_user_id: str = ""
    allow_mock_header_override: bool = False
    # The three answer tiers (one place). CURA_FAST_MODEL / CURA_STANDARD_MODEL /
    # CURA_DEEP_MODEL are accepted as well as the older ANSWER_MODEL_* names.
    answer_model_fast_reasoning: str = Field(
        "google/gemini-3.8-flash", validation_alias=AliasChoices("CURA_FAST_MODEL", "ANSWER_MODEL_FAST_REASONING", "answer_model_fast_reasoning")
    )
    answer_model_standard_medical: str = Field(
        "openai/gpt-5-mini", validation_alias=AliasChoices("CURA_STANDARD_MODEL", "ANSWER_MODEL_STANDARD_MEDICAL", "answer_model_standard_medical")
    )
    answer_model_deep_medical: str = Field(
        "openai/gpt-5.6-luna", validation_alias=AliasChoices("CURA_DEEP_MODEL", "ANSWER_MODEL_DEEP_MEDICAL", "answer_model_deep_medical")
    )
    # Development only (ignored in production): force every model answer onto one tier
    # (fast | standard | deep) to compare models on the same questions.
    cura_force_answer_tier: str = ""
    # Development only: log a readable routing decision and add it to meta.debug.
    cura_model_routing_debug: bool = False
    # Development only: dump each answer-model request (components, sizes, tokens) to
    # CURA_PROMPT_DEBUG_DIR. Contains health values; never active in production.
    cura_prompt_debug: bool = False
    cura_prompt_debug_dir: str = ".prompt_debug"
    # Per-tier answer-call caps (seconds); always bounded by the request budget.
    answer_timeout_fast_seconds: float = 10.0
    answer_timeout_standard_seconds: float = 18.0
    answer_timeout_deep_seconds: float = 25.0
    answer_model_nano: str = "openai/gpt-5.6-luna"
    answer_model_standard: str = "google/gemini-3.8-flash"
    answer_model_advanced: str = "google/gemini-3.8-flash"
    llm_allowed_providers: str = "openrouter"
    llm_allowed_models: str = (
        "openai/gpt-5.6-luna,openai/gpt-5-mini,google/gemini-3.8-flash,"
        "openai/gpt-4o-mini,typesafe/jev-1.13"
    )
    assistant_quality_v2: bool = True
    llm_json_schema_output: bool = True
    eval_candidate_model: str = "google/gemini-3.8-flash"
    # Request OpenRouter not to use prompts for training. This is not proof of ZDR.
    openrouter_data_collection_deny: bool = True
    # Route via OpenRouter ZDR-eligible endpoints when true. CURA cannot independently
    # verify retention; confirm gateway policy before production personal-health LLM.
    openrouter_zero_data_retention: bool = False
    require_zdr_for_personal_health: bool = False
    # Do not set true unless every answer model is known to support JSON Schema.
    openrouter_require_parameters: bool = False
    cura_openrouter_require_zdr: bool = False
    cura_openrouter_deny_data_collection: bool = True
    cura_openrouter_allowed_models: str = ""
    cura_openrouter_allowed_providers: str = "openai,google,anthropic,typesafe"
    cura_openrouter_prompt_injection_protection: bool = True
    cura_openrouter_dlp_enabled: bool = True
    cura_clinical_safety_enabled: bool = True
    cura_package_safety_enabled: bool = True
    request_timeout_seconds: float = 60
    chat_streaming_mode: str = "complete_only"
    crisis_helpline_text: str = ""
    crisis_helpline_region: str = ""
    # India numbers used by the emergency and self-harm replies and the client call
    # buttons. Defaults are 112 (national emergency) and Tele-MANAS 14416; the clinical
    # safety owner must confirm them before the pilot.
    emergency_number: str = "112"
    crisis_helpline_number: str = "14416"
    # Model-backed safety classifier, combined with the deterministic rules.
    safety_llm_classifier_enabled: bool = True
    safety_classifier_model: str = "openai/gpt-5.6-luna"
    safety_classifier_timeout_seconds: float = 3.0
    # Optional model judge on answers that mention medicines or diagnoses (plan 2.7).
    safety_answer_judge_enabled: bool = False
    # Production /chat responses carry only a small public meta; full meta stays in logs.
    public_meta_only: bool | None = None
    # Consent: chat requires an accepted consent record at this version when enforced.
    consent_version: str = "2026-10-v1"
    consent_required: bool | None = None
    # Languages Cura answers in (English pivot + translation). Plan suggests en,hi for the pilot.
    answer_languages: str = "en,hi,hinglish"
    answer_translation_enabled: bool = True
    translation_model: str = "openai/gpt-5.6-luna"
    translation_timeout_seconds: float = 8.0
    # Serve only reviewed, in-date medical passages (default on outside development).
    medical_require_reviewed: bool | None = None
    # Read-only SuperShyft session guards (defence in depth behind the read-only role).
    supershyft_statement_timeout_ms: int = 5000
    # Reuse a member's Supershyft reads for this long (plan 5.5). 0 disables.
    health_data_cache_seconds: int = 90
    health_data_cache_version: str = "1"
    document_encryption_key: str = ""
    document_retention_days: int = 90
    # Conversations untouched for this many days are purged with their derived rows. 0 disables.
    conversation_retention_days: int = 365
    # Disabled until operations/legal approve explicit policies. When enabled, only
    # terminal document jobs and operational audit rows older than the window are removed.
    processing_job_retention_days: int = 0
    audit_record_retention_days: int = 0
    supershyft_pool_size: int = 5
    supershyft_max_overflow: int = 2
    store_health_fact_values: bool = False
    model_price_nano_input_per_1m: float = 0.25
    model_price_nano_output_per_1m: float = 2.00
    model_price_standard_input_per_1m: float = 0.75
    model_price_standard_output_per_1m: float = 3.75
    model_price_advanced_input_per_1m: float = 3.00
    model_price_advanced_output_per_1m: float = 15.00
    # Placeholder list prices (USD per 1M tokens) for cost estimates; set the real
    # contracted prices through the environment.
    model_price_fast_reasoning_input_per_1m: float = 0.10
    model_price_fast_reasoning_output_per_1m: float = 0.40
    model_price_standard_medical_input_per_1m: float = 0.25
    model_price_standard_medical_output_per_1m: float = 2.00
    model_price_deep_medical_input_per_1m: float = 1.25
    model_price_deep_medical_output_per_1m: float = 10.00

    # SuperShyft read-only Postgres (never used for Cura conversation tables)
    supershyft_database_url: str = ""
    supershyft_db_connect_timeout: int = 10

    log_level: str = "INFO"
    # Bearer token required on GET /metrics when set (recommended in production).
    metrics_token: str = ""
    # Chat requests one process handles at once; more get 429 with Retry-After.
    max_in_flight_chats: int = 32
    # Worker threads for sync handlers (chat waits on Jev and the model in a thread).
    worker_threads: int = 64
    dev_auth_header: bool = True
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174,"
        "http://localhost:5175,http://127.0.0.1:5175"
    )
    redis_url: str = ""
    redis_required: bool = False
    rate_limit_requests: int = 30
    # Per-endpoint and per-IP limits (plan 1.9). IP limits count every /api request.
    upload_rate_limit: int = 20
    upload_rate_window_seconds: int = 3600
    voice_rate_limit: int = 30
    voice_rate_window_seconds: int = 600
    ip_rate_limit: int = 300
    ip_rate_window_seconds: int = 60
    # Trust X-Forwarded-For only behind a known load balancer.
    trust_proxy_headers: bool = False
    # Model tokens (input + output) a member may use per UTC day. 0 disables the budget.
    member_daily_token_budget: int = 200_000
    # Above this model spend per hour, deep answers try the standard tier first (plan 6.7). 0 disables.
    spend_spike_hourly_usd: float = 5.0
    rate_limit_window_seconds: int = 60
    idempotency_ttl_seconds: int = 300

    # Voice / STT — optional. Typed chat works when this is off.
    voice_enabled: bool = False
    stt_provider: str = "none"
    stt_api_key: str = ""
    stt_base_url: str = "http://127.0.0.1:8001/v1"
    stt_model: str = "gpt-transcribe"
    stt_timeout_seconds: int = 60
    stt_max_audio_bytes: int = 10_000_000

    def resolved_stt_api_key(self) -> str:
        return (self.stt_api_key or self.openrouter_api_key or self.llm_api_key).strip()

    def resolved_stt_base_url(self) -> str:
        provider = (self.stt_provider or "").strip().lower()
        if provider in {"openrouter", "openai_compatible", "openai", "api"}:
            return (self.openrouter_base_url or self.llm_base_url or "https://openrouter.ai/api/v1").rstrip("/")
        if (self.stt_api_key or "").strip():
            return (self.stt_base_url or "http://127.0.0.1:8001/v1").rstrip("/")
        return (self.openrouter_base_url or self.llm_base_url or self.stt_base_url).rstrip("/")

    def resolved_stt_model(self) -> str:
        model = (self.stt_model or "").strip() or "gpt-transcribe"
        provider = (self.stt_provider or "").strip().lower()
        if provider == "openrouter":
            if model in {"gpt-transcribe", "whisper-1"} or "/" not in model:
                return model if "/" in model else f"openai/{model}"
            return model
        return model

    # User-uploaded medical documents (Phase 7). Files live outside SuperShyft.
    document_storage_backend: str = "local"
    document_storage_path: str = "./data/uploads"
    document_s3_bucket: str = ""
    document_s3_prefix: str = "documents"
    document_s3_region: str = "ap-south-1"
    document_s3_endpoint_url: str = ""
    document_s3_kms_key_id: str = ""
    document_max_upload_bytes: int = 20_000_000
    # Optional clamd for upload malware scanning; refuses uploads if set but unreachable.
    document_clamav_host: str = ""
    document_clamav_port: int = 3310
    # "inline": the web process extracts uploads (development). "external": the web
    # process only enqueues and scripts/document_worker.py does the work (production).
    document_worker_mode: str | None = None
    document_job_lease_seconds: int = 600
    document_job_max_attempts: int = 3
    document_ocr_provider: str = "none"
    document_min_text_chars: int = 80
    document_sparse_page_chars: int = 40
    document_max_pages: int = 50
    document_max_ocr_pages: int = 20
    document_max_extracted_chars: int = 200_000
    document_ocr_timeout_seconds: int = 60
    document_chunk_size: int = 900
    document_chunk_overlap: int = 100
    document_retrieve_limit: int = 5

    @model_validator(mode="after")
    def validate_database_separation(self) -> "Settings":
        if (
            self.supershyft_database_url
            and self.database_url.strip() == self.supershyft_database_url.strip()
        ):
            raise ValueError("DATABASE_URL must never point to the SuperShyft source database")
        if "+asyncpg" in self.database_url.lower():
            raise ValueError(
                "DATABASE_URL is Cura's conversation store and uses a sync engine. "
                "Do not use postgresql+asyncpg here. For local development use sqlite:///./cura.db. "
                "Put SuperShyft Postgres in SUPERSHYFT_DATABASE_URL."
            )
        if not self.is_development:
            if self.auth_provider == "mock":
                # Startup remains possible for health checks, but protected routes reject mock auth.
                self.dev_auth_header = False
            self.allow_mock_header_override = False
            self.allow_mock_auth_with_real_health = False
            self.mock_user_id = ""
        return self

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() in {"development", "dev", "test"}

    def resolved_llm_provider(self) -> str:
        raw = (self.llm_provider or "openrouter").strip().lower()
        if raw in {"local", "ollama", "qwen"}:
            return "openrouter"
        if raw in {"openai_compatible", "api", "huggingface", "remote", "openai"}:
            return "openrouter"
        return "openrouter"

    def active_llm_base_url(self) -> str:
        return (self.openrouter_base_url or self.llm_base_url or "https://openrouter.ai/api/v1").rstrip("/")

    def active_llm_model(self) -> str:
        return (self.medical_llm_model or self.llm_model or self.answer_model_standard_medical).strip()

    def active_llm_api_key(self) -> str:
        return (self.openrouter_api_key or self.llm_api_key).strip()

    def public_meta_enabled(self) -> bool:
        if self.public_meta_only is not None:
            return bool(self.public_meta_only)
        return not self.is_development

    def medical_require_reviewed_enabled(self) -> bool:
        if self.medical_require_reviewed is not None:
            return bool(self.medical_require_reviewed)
        return not self.is_development

    def document_workers_external(self) -> bool:
        if self.document_worker_mode:
            return self.document_worker_mode.strip().lower() == "external"
        return not self.is_development

    def consent_enforced(self) -> bool:
        if self.consent_required is not None:
            return bool(self.consent_required)
        return not self.is_development

    def cura_database_is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


settings = Settings()
