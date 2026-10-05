export interface GatewayProfile {
  id: string;
  name: string;
  base_url: string;
  api_key_masked: string;
  has_api_key: boolean;
  protocol?: "openai" | "anthropic";
}

export interface AdminConfig {
  llm: {
    base_url: string;
    api_key_masked: string;
    has_api_key: boolean;
    model: string;
    fast_model: string;
    fallback_model: string | null;
    temperature: number;
    profiles: GatewayProfile[];
    primary_profile_id: string;
    fast_profile_id: string;
    fallback_profile_id: string;
  };
  storage: {
    storage_type: "local" | "s3";
    s3_endpoint: string;
    s3_bucket: string;
    s3_region: string;
    s3_access_key_masked: string;
    has_s3_secret: boolean;
    is_configured: boolean;
  };
  secrets: {
    active_provider: "local" | "infisical" | "doppler";
    infisical_project_id: string;
    infisical_env: string;
    doppler_project: string;
    doppler_config: string;
  };
  embedding: {
    provider: "local" | "gemini" | "openai" | "custom";
    gemini_model: string;
    gemini_key_masked: string;
    has_gemini_key: boolean;
    local_model: string;
    custom_base_url?: string;
    custom_model_name?: string;
    custom_key_masked?: string;
    has_custom_key?: boolean;
    custom_local_path?: string;
    hybrid_bm25_enabled: boolean;
  };
  reranker?: {
    model: string;
    top_n: number;
  };
}

export interface AdminSystemHealth {
  status: string;
  database: {
    engine: string;
    chat_sessions: number;
    documents: number;
    messages: number;
  };
  vector_store: {
    status: string;
    collections: Array<{
      name: string;
      points_count: number;
      status: string;
    }>;
    error?: string;
  };
  disk: {
    total_gb: number;
    free_gb: number;
    used_gb: number;
  };
}

export interface TestResult {
  success: boolean;
  message: string;
  latency_ms?: number;
}
