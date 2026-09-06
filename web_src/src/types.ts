export type JsonObject = Record<string, any>;
export interface Character {name:string;identity:string;personality:string;speaking_style:string;example_dialogues:string;system_prompt:string}
export interface ContextSources {foreground_window:boolean;browser_windows:boolean;idle_time:boolean;activity_rhythm:boolean;app_category:boolean;window_switch_activity:boolean;task_pressure_signals:boolean;time_context:boolean;media_audio_state:boolean;fullscreen_focus_state:boolean;system_health:boolean;screen_ocr:boolean;screen_vision:boolean}
export interface ActivitySettings {enabled:boolean;interaction_mode:'fixed_interval'|'manager';interval_minutes:number;min_speech_interval_minutes:number;max_speech_interval_minutes:number;do_not_disturb:boolean;save_latest_screenshot:boolean;context_sources:ContextSources}
export interface PetSettings {enabled:boolean;font_size:number;position:'auto'|'left_top'|'right_top';duration_seconds:number;background:string;border:string;text_color:string}
export interface LlmField {
  key: string;
  label: string;
  type: "text" | "password" | "number" | "checkbox" | "select";
  placeholder?: string;
  step?: string;
  required?: boolean;
  options?: string[];
}

export interface LlmProvider {
  id: string;
  label: string;
  vendor_id?: string;
  billing_mode?: "payg" | "coding_plan" | "token_plan";
  credential_hint?: string;
  usage_notice?: string;
  official_base_url?: string;
  description?: string;
  model?: string;
  config?: JsonObject;
  fields?: LlmField[];
  recommended_models?: string[];
  requires_api_key?: boolean;
  has_api_key?: boolean;
  supports_vision?: boolean;
  supports_native_tools?: boolean;
  can_fetch_models?: boolean;
}

export interface LlmProfile extends LlmProvider {
  name: string;
  provider: string;
  provider_label?: string;
  active?: boolean;
  configured?: boolean;
  unavailable_reason?: string;
  vision_capability?: "supported" | "unsupported" | "unknown";
}

export interface LlmModelEntry {
  id: string;
  name?: string;
  owned_by?: string;
  source?: "recommended" | "live" | "configured";
  recommended?: boolean;
  context_length?: number;
  context_source?: "provider" | "builtin" | "detected" | "default";
  max_context_length?: number;
  context_conditional?: boolean;
}

export interface LlmCatalog {
  entries: LlmModelEntry[];
  models?: string[];
  cache_state?: "fresh" | "stale" | "recommended";
  refreshing?: boolean;
  error?: string;
  fetched_at?: number | null;
  current_model?: LlmModelEntry | null;
}
