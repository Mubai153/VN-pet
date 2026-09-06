<script setup lang="ts">
import { Copy, Gauge, LoaderCircle, Plus, RefreshCw, RotateCcw, Save, Search, Trash2 } from "lucide-vue-next";
import { computed, ref, watch } from "vue";
import type { JsonObject, LlmCatalog, LlmModelEntry, LlmProfile, LlmProvider } from "./types";
import SettingHelp from "./SettingHelp.vue";

const props = defineProps<{
  profiles: LlmProfile[];
  providers: LlmProvider[];
  selectedId: string;
  catalog: LlmCatalog;
  advancedJson: string;
  clearApiKey: boolean;
  dirty: boolean;
  loadingModels?: boolean;
  connectionStates?: Record<string, "idle" | "testing" | "connected" | "failed">;
}>();
const config = defineModel<JsonObject>("config", { required: true });
const profileName = defineModel<string>("profileName", { required: true });
const emit = defineEmits<{
  select: [id: string]; create: [provider: string]; duplicate: []; remove: [];
  fetchModels: []; test: []; save: []; revert: [];
  "update:advancedJson": [value: string]; "update:clearApiKey": [value: boolean];
}>();

const profileQuery = ref("");
const newProvider = ref("deepseek");
const modelOpen = ref(false);
const activeModelIndex = ref(0);
const modelFilter = ref("");
type ContextMode = "auto" | "131072" | "262144" | "1048576" | "custom";
const CONTEXT_PRESETS = new Set([131072, 262144, 1048576]);
const customContextMode = ref(false);
const selected = computed(() => props.profiles.find((item) => item.id === props.selectedId));
const providerOrder = computed(() => new Map(props.providers.map((item, index) => [item.id, index])));
const orderedProfiles = computed(() => props.profiles
  .map((profile, index) => ({ profile, index }))
  .sort((left, right) => {
    const leftOrder = providerOrder.value.get(left.profile.provider) ?? Number.MAX_SAFE_INTEGER;
    const rightOrder = providerOrder.value.get(right.profile.provider) ?? Number.MAX_SAFE_INTEGER;
    return leftOrder - rightOrder || left.index - right.index;
  })
  .map(({ profile }) => profile));
const filteredProfiles = computed(() => {
  const query = profileQuery.value.trim().toLowerCase();
  if (!query) return orderedProfiles.value;
  return orderedProfiles.value.filter((item) => `${item.name} ${item.provider_label || item.provider} ${item.model || ""}`.toLowerCase().includes(query));
});
const filteredModels = computed(() => {
  const query = modelFilter.value.trim().toLowerCase();
  const entries = props.catalog.entries || [];
  return (query ? entries.filter((item) => `${item.id} ${item.owned_by || ""}`.toLowerCase().includes(query)) : entries).slice(0, 120);
});
const selectedModelEntry = computed(() => {
  const model = String(config.value.model || "").trim().toLowerCase();
  const listed = (props.catalog.entries || []).find((entry) => entry.id.toLowerCase() === model);
  const current = props.catalog.current_model;
  return listed || (current?.id.toLowerCase() === model ? current : undefined);
});
const contextMode = computed<ContextMode>(() => {
  if (customContextMode.value) return "custom";
  const value = Number(config.value.context_length);
  if (!Number.isFinite(value) || value <= 0) return "auto";
  return CONTEXT_PRESETS.has(value) ? String(value) as ContextMode : "custom";
});
const contextWarning = computed(() => {
  const selectedValue = Number(config.value.context_length || 0);
  const entry = selectedModelEntry.value;
  if (!selectedValue || !entry) return "";
  if (entry.max_context_length && selectedValue > entry.max_context_length) {
    return `所选窗口超过已知最高值 ${formatContext(entry.max_context_length)}，供应商可能拒绝请求。`;
  }
  if (entry.context_conditional && entry.context_length && selectedValue > entry.context_length) {
    return `${formatContext(selectedValue)} 能力取决于账号套餐或部署配置，请确认当前密钥已开通。`;
  }
  if (entry.context_source === "provider" && entry.context_length && selectedValue > entry.context_length) {
    return `所选窗口超过目录标称的 ${formatContext(entry.context_length)}，供应商可能拒绝请求。`;
  }
  return "";
});
const automaticContextText = computed(() => {
  const entry = selectedModelEntry.value;
  if (!entry?.context_length || !entry.context_source || entry.context_source === "default") {
    return "未识别，运行时使用保守默认值";
  }
  const source = {
    provider: "厂商目录",
    builtin: "内置规则",
    detected: "运行探测",
    default: "保守默认值",
  }[entry.context_source];
  const conditional = entry.context_conditional ? "（保守值，最高能力取决于套餐）" : "";
  return `${source}：${formatContext(entry.context_length)}${conditional}`;
});
function inputType(kind: string) { return kind === "password" ? "password" : kind === "number" ? "number" : "text"; }
function formatContext(value: number) {
  if (value === 1048576 || value === 1000000) return "1M";
  if (value >= 1024 && value % 1024 === 0) return `${value / 1024}K`;
  if (value >= 1000 && value % 1000 === 0) return `${value / 1000}K`;
  return value.toLocaleString("zh-CN");
}
function modelContextLabel(entry: LlmModelEntry) {
  if (!entry.context_length) return "";
  if (entry.context_source === "default") return `默认 ${formatContext(entry.context_length)}`;
  if (entry.max_context_length && entry.max_context_length > entry.context_length) {
    return `默认 ${formatContext(entry.context_length)} · 最高 ${formatContext(entry.max_context_length)}${entry.context_conditional ? "（套餐相关）" : ""}`;
  }
  return `上下文 ${formatContext(entry.context_length)}`;
}
function setContextMode(event: Event) {
  const mode = (event.target as HTMLSelectElement).value as ContextMode;
  customContextMode.value = mode === "custom";
  if (mode === "auto") {
    delete config.value.context_length;
    return;
  }
  if (mode === "custom") {
    const current = Number(config.value.context_length);
    if (!Number.isFinite(current) || current < 1000 || CONTEXT_PRESETS.has(current)) {
      config.value.context_length = selectedModelEntry.value?.context_length || 131072;
    }
    return;
  }
  config.value.context_length = Number(mode);
}
watch(() => config.value, () => { customContextMode.value = false; });
watch(() => props.selectedId, () => { customContextMode.value = false; });
function chooseModel(entry: LlmModelEntry) { config.value.model = entry.id; modelFilter.value = ""; modelOpen.value = false; }
function modelKeydown(event: KeyboardEvent) {
  if (event.key === "ArrowDown") { event.preventDefault(); modelOpen.value = true; activeModelIndex.value = Math.min(activeModelIndex.value + 1, Math.max(0, filteredModels.value.length - 1)); }
  else if (event.key === "ArrowUp") { event.preventDefault(); activeModelIndex.value = Math.max(0, activeModelIndex.value - 1); }
  else if (event.key === "Enter" && modelOpen.value && filteredModels.value[activeModelIndex.value]) { event.preventDefault(); chooseModel(filteredModels.value[activeModelIndex.value]); }
  else if (event.key === "Escape") modelOpen.value = false;
}
function openModels() { modelFilter.value = ""; modelOpen.value = true; activeModelIndex.value = 0; }
function requestModels() { openModels(); emit("fetchModels"); }
function filterModels() { modelFilter.value = String(config.value.model || ""); modelOpen.value = true; activeModelIndex.value = 0; }
function closeModelsOnBlur(event: FocusEvent) {
  const next = event.relatedTarget as Node | null;
  if (!next || !(event.currentTarget as HTMLElement).contains(next)) modelOpen.value = false;
}
function connectionLabel(profile: LlmProfile) {
  const state = props.connectionStates?.[profile.id] || "idle";
  if (state === "testing") return "正在测试连接";
  if (state === "connected") return "连接测试通过";
  if (state === "failed") return "连接测试失败";
  return profile.configured ? "配置可用" : profile.unavailable_reason || "配置不完整";
}
function billingModeLabel(mode?: LlmProvider["billing_mode"]) {
  if (mode === "coding_plan") return "Coding Plan";
  if (mode === "token_plan") return "Token Plan";
  return "按量";
}
</script>

<template>
  <div class="page-heading"><div><h1>AI 模型（LLM）</h1><p>主动陪伴和截图视觉使用当前启用的模型。<SettingHelp help-key="llm.profile" /></p></div></div>
  <section class="llm-manager settings-section">
    <aside class="llm-profile-list">
      <label class="search-box"><Search /><input v-model="profileQuery" aria-label="搜索配置实例" placeholder="搜索配置" /></label>
      <div class="profile-create-row">
        <select v-model="newProvider" aria-label="新增配置模板"><option v-for="provider in providers" :key="provider.id" :value="provider.id">{{ provider.label }}</option></select>
        <button class="icon-button" type="button" title="新增配置实例" aria-label="新增配置实例" @click="emit('create', newProvider)"><Plus /></button>
      </div>
      <div class="profile-scroll">
        <button v-for="profile in filteredProfiles" :key="profile.id" type="button" :class="{ active: profile.id === selectedId, global: profile.active }" @click="emit('select', profile.id)">
          <span><strong>{{ profile.name }}</strong><small>{{ profile.provider_label || profile.provider }} · {{ billingModeLabel(profile.billing_mode) }} · {{ profile.model || '未设置模型' }}</small></span>
          <i :class="[props.connectionStates?.[profile.id] || 'idle', { ready: profile.configured }]" :title="connectionLabel(profile)" />
          <em v-if="profile.active">当前全局</em>
          <em v-else-if="!profile.configured">待配置</em>
        </button>
        <p v-if="!filteredProfiles.length" class="empty-state">没有匹配的配置</p>
      </div>
    </aside>

    <div v-if="selected" class="llm-editor">
      <div class="section-heading">
        <div><h2>{{ selected.name }}</h2><p><span class="billing-badge">{{ billingModeLabel(selected.billing_mode) }}</span>{{ selected.provider_label }} · {{ selected.description }}</p></div>
        <div class="button-row">
          <span class="status-tag" :class="{ error: props.connectionStates?.[selected.id] === 'failed' || !selected.configured, running: props.connectionStates?.[selected.id] === 'connected' || selected.active }">{{ selected.active ? '当前全局模型' : connectionLabel(selected) }}</span>
          <button class="icon-button" type="button" title="复制配置" aria-label="复制配置" @click="emit('duplicate')"><Copy /></button>
          <button class="icon-button danger" type="button" title="删除配置" aria-label="删除配置" :disabled="selected.active" @click="emit('remove')"><Trash2 /></button>
        </div>
      </div>
      <p v-if="selected.usage_notice" class="inline-warning provider-usage-notice">{{ selected.usage_notice }}</p>
      <label>配置名称<input v-model="profileName" maxlength="80" /></label>
      <div class="form-grid two">
        <template v-for="field in selected.fields || []" :key="field.key">
          <label v-if="field.type !== 'checkbox' && field.type !== 'select' && field.key !== 'model' && field.key !== 'context_length'">
            {{ field.label }}
            <small v-if="field.key === 'base_url' && selected.official_base_url" class="field-hint">官方默认：{{ selected.official_base_url }}</small>
            <small v-else-if="field.key === 'api_key' && selected.credential_hint" class="field-hint">{{ selected.credential_hint }}</small>
            <input v-model="config[field.key]" :type="inputType(field.type)" :step="field.step || undefined" :placeholder="field.type === 'password' && selected.has_api_key ? '留空保留已保存密钥' : field.key === 'api_key' && selected.credential_hint ? selected.credential_hint : field.placeholder" />
          </label>
          <label v-else-if="field.type === 'select'">
            {{ field.label }}
            <select v-model="config[field.key]"><option v-for="option in field.options || []" :key="option" :value="option">{{ option }}</option></select>
          </label>
          <label v-else-if="field.type === 'checkbox' && field.key !== 'context_length'" class="switch-row compact"><span><strong>{{ field.label }}</strong></span><input v-model="config[field.key]" type="checkbox" /></label>
        </template>
      </div>

      <label class="model-picker" @focusout="closeModelsOnBlur">模型
        <input v-model="config.model" role="combobox" aria-autocomplete="list" :aria-expanded="modelOpen" aria-controls="llm-model-options" :aria-activedescendant="modelOpen && filteredModels[activeModelIndex] ? `llm-model-option-${activeModelIndex}` : undefined" placeholder="输入或选择模型" @focus="openModels" @input="filterModels" @keydown="modelKeydown" />
        <Transition name="fade"><div v-if="modelOpen" id="llm-model-options" class="model-options" role="listbox">
          <div class="catalog-state">
            <span v-if="loadingModels"><LoaderCircle class="spin" />正在拉取模型</span>
            <span v-else>{{ catalog.cache_state === 'fresh' ? '现场目录' : catalog.cache_state === 'stale' ? '缓存目录' : '推荐模型' }}</span>
            <small v-if="catalog.error">拉取失败：{{ catalog.error }}</small>
          </div>
          <button v-for="(entry, index) in filteredModels" :id="`llm-model-option-${index}`" :key="entry.id" type="button" role="option" :aria-selected="String(config.model || '') === entry.id" :class="{ active: index === activeModelIndex }" @mousedown.prevent="chooseModel(entry)">
            <span><strong>{{ entry.id }}</strong><small>{{ entry.owned_by || selected.provider_label }}<template v-if="modelContextLabel(entry)"> · {{ modelContextLabel(entry) }}</template></small></span>
            <em>{{ entry.recommended ? '推荐' : entry.source === 'live' ? '现场' : '缓存' }}</em>
          </button>
          <p v-if="!filteredModels.length" class="empty-state">没有匹配模型，可保留手工输入</p>
        </div></Transition>
      </label>
      <p v-if="catalog.cache_state === 'stale'" class="inline-warning">当前显示过期缓存，后台拉取不会修改草稿。</p>
      <p v-if="catalog.error" class="inline-warning">{{ catalog.error }}</p>

      <div class="context-window-control">
        <div class="form-grid two">
          <label><span>上下文窗口<SettingHelp help-key="llm.context-window" /></span>
            <select :value="contextMode" aria-label="上下文窗口" @change="setContextMode">
              <option value="auto">自动识别</option>
              <option value="131072">128K（131072）</option>
              <option value="262144">256K（262144）</option>
              <option value="1048576">1M（1048576）</option>
              <option value="custom">自定义</option>
            </select>
          </label>
          <label v-if="contextMode === 'custom'">自定义窗口（Token）<input v-model.number="config.context_length" aria-label="自定义上下文窗口" type="number" min="1000" step="1" /></label>
        </div>
        <p v-if="contextMode === 'auto'" class="context-detection">自动识别结果：{{ automaticContextText }}</p>
        <p v-if="contextWarning" class="inline-warning">{{ contextWarning }}</p>
      </div>

      <details class="advanced-editor"><summary>高级模型参数（JSON）<SettingHelp help-key="llm.advanced-json" /></summary><label>未在表单中展示的模型参数<textarea class="code-textarea" :value="advancedJson" @input="emit('update:advancedJson', ($event.target as HTMLTextAreaElement).value)" /></label></details>
      <label class="switch-row"><span><strong>清空此配置的 API 密钥（API Key）</strong><small>空值或掩码保留密钥，只有此开关会删除。</small></span><input type="checkbox" :checked="clearApiKey" @change="emit('update:clearApiKey', ($event.target as HTMLInputElement).checked)" /></label>
      <div class="button-row end">
        <button class="pp-button" :disabled="selected.can_fetch_models === false || loadingModels" @click="requestModels"><RefreshCw :class="{ spin: loadingModels }" />拉取可用模型</button>
        <button class="pp-button" @click="emit('test')"><Gauge />测试连接</button>
        <button class="pp-button" :disabled="!dirty" @click="emit('revert')"><RotateCcw />还原修改</button>
        <button class="pp-button primary" @click="emit('save')"><Save />保存配置</button>
      </div>
      <p v-if="dirty" class="inline-warning">当前配置有未保存修改，保存或还原后才能切换其他配置。</p>
      <p v-else-if="!selected.configured" class="inline-warning">{{ selected.unavailable_reason || '配置不完整' }}。保存完整后，再次点击左侧配置即可启用。</p>
    </div>
    <div v-else class="llm-empty">
      <Plus />
      <h2>为 VN 添加第一个模型</h2>
      <p>在左侧选择服务商，点击「＋」创建配置。<br>填写连接信息并保存后，将它设为当前模型。</p>
      <small>VN 的模型配置独立保存，由你决定使用哪项服务。</small>
    </div>
  </section>

</template>

<style scoped>
.llm-empty{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:320px;text-align:center;color:var(--pp-muted)}.llm-empty>svg{width:32px;height:32px;margin-bottom:24px;color:#91a488}.llm-empty h2{font-weight:500;color:#607658;font-size:18px;margin-bottom:10px}.llm-empty p{font-size:12px;line-height:2}.llm-empty small{font-size:10px;color:#a0ab98}
.llm-manager{display:grid;grid-template-columns:240px minmax(0,1fr);gap:16px;min-height:520px}.llm-profile-list{display:flex;flex-direction:column;min-width:0;border-right:1px solid var(--pp-line);padding-right:12px}.search-box{position:relative;margin:0 0 8px}.search-box svg{position:absolute;left:9px;top:9px;width:15px;color:var(--pp-muted)}.search-box input{padding-left:31px}.profile-create-row{display:grid;grid-template-columns:minmax(0,1fr) 36px;gap:6px;margin-bottom:8px}.profile-scroll{display:grid;align-content:start;gap:4px;max-height:500px;overflow:auto}.profile-scroll>button{display:grid;grid-template-columns:minmax(0,1fr) 10px;gap:3px 7px;border:1px solid transparent;border-radius:7px;padding:8px;background:transparent;color:var(--pp-text);text-align:left}.profile-scroll>button.active{border-color:var(--pp-line);background:var(--pp-selected-bg,rgba(90,130,110,.12))}.profile-scroll>button.global{border-left:3px solid var(--pp-accent)}.profile-scroll span{display:grid;min-width:0}.profile-scroll small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--pp-muted)}.profile-scroll i{width:8px;height:8px;margin-top:5px;border-radius:50%;background:var(--pp-danger)}.profile-scroll i.ready{background:var(--pp-accent)}.profile-scroll i.testing{background:var(--pp-warning,var(--pp-accent))}.profile-scroll i.connected{background:var(--pp-success,var(--pp-accent))}.profile-scroll i.failed{background:var(--pp-danger)}.profile-scroll em{grid-column:auto;justify-self:start;border:1px solid var(--pp-line);border-radius:4px;padding:1px 4px;color:var(--pp-muted);font-size:9px;font-style:normal}.llm-editor{min-width:0}.model-picker{position:relative}.model-options{position:absolute;z-index:20;top:100%;left:0;right:0;max-height:310px;overflow:auto;border:1px solid var(--pp-line);border-radius:7px;background:var(--pp-panel);box-shadow:0 12px 30px rgba(24,19,42,.18)}.model-options>button{width:100%;display:flex;justify-content:space-between;gap:10px;border:0;border-top:1px solid var(--pp-line);padding:8px 10px;background:transparent;color:var(--pp-text);text-align:left}.model-options>button.active,.model-options>button:hover{background:var(--pp-selected-bg,rgba(90,130,110,.12))}.model-options span{display:grid}.model-options small,.catalog-state small{color:var(--pp-muted)}.model-options em{color:var(--pp-accent);font-size:10px;font-style:normal}.catalog-state{display:flex;justify-content:space-between;gap:10px;padding:7px 10px}.catalog-state span{display:flex;align-items:center;gap:5px}.catalog-state svg{width:14px}.empty-state{padding:12px;color:var(--pp-muted);text-align:center}.icon-button.danger{color:var(--pp-danger)}
.context-window-control{margin-top:14px;padding-top:12px;border-top:1px solid var(--pp-line)}.context-window-control .form-grid{margin-bottom:6px}.context-detection{margin:0;color:var(--pp-muted);font-size:12px}
.billing-badge{display:inline-block;margin-right:6px;border:1px solid var(--pp-line);border-radius:4px;padding:1px 5px;color:var(--pp-accent);font-size:10px;font-weight:700;vertical-align:1px}.field-hint{display:block;min-width:0;overflow-wrap:anywhere;color:var(--pp-muted);font-size:11px;font-weight:400}.provider-usage-notice{margin:0 0 12px}
@media(max-width:860px){.llm-manager{grid-template-columns:1fr}.llm-profile-list{border-right:0;border-bottom:1px solid var(--pp-line);padding:0 0 10px}.profile-scroll{max-height:210px}}
</style>
