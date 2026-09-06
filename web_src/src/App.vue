<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, toRaw } from 'vue';
import { Bot, UserRound, Sparkles, ScanEye, MessageSquare, Save, X, Check, RefreshCw, Eye, EyeOff, PawPrint } from 'lucide-vue-next';
import LlmSettingsSection from './LlmSettingsSection.vue';
import { api, bootstrap } from './api';
import { createSaveQueue } from './saveQueue';
import type { ActivitySettings, Character, ContextSources, JsonObject, LlmCatalog, LlmProfile, LlmProvider, PetSettings } from './types';

const sections=[{id:'llm',label:'AI 模型',icon:Bot},{id:'character',label:'VN 角色',icon:UserRound},{id:'activity',label:'主动陪伴',icon:Sparkles},{id:'sources',label:'感知来源',icon:ScanEye},{id:'pet',label:'发言气泡',icon:MessageSquare}];
const page=ref(localStorage.getItem('vn.settings.page') || 'llm');
if(!sections.some(s=>s.id===page.value))page.value='llm';
const ready=ref(false),fatal=ref(''),notice=ref(''),noticeError=ref(false),busy=ref(false),saveStatus=ref('所有设置已保存');
const profiles=ref<LlmProfile[]>([]),providers=ref<LlmProvider[]>([]),selectedId=ref(''),activeId=ref('');
const config=ref<JsonObject>({}),profileName=ref(''),advanced=ref('{}'),clearKey=ref(false);
const catalog=ref<LlmCatalog>({entries:[],cache_state:'recommended'}),loadingModels=ref(false);
const connectionStates=ref<Record<string,'idle'|'testing'|'connected'|'failed'>>({});
const modelBaseline=ref('');
const character=ref<Character>({name:'VN',identity:'',personality:'',speaking_style:'',example_dialogues:'',system_prompt:''});
const characterBaseline=ref('');
const activity=ref<ActivitySettings>({enabled:false,interaction_mode:'fixed_interval',interval_minutes:5,min_speech_interval_minutes:10,max_speech_interval_minutes:45,do_not_disturb:false,save_latest_screenshot:false,context_sources:{} as ContextSources});
const pet=ref<PetSettings>({enabled:true,font_size:14,position:'auto',duration_seconds:10,background:'#fff8ed',border:'#b99666',text_color:'#40382d'});
const status=ref<JsonObject>({state:'idle',warnings:[]});
const previewText=ref('忙了一会儿，也记得让眼睛歇一歇。我在这里陪着你。');
const closing=ref(false);
const characterFields:[keyof Character,string][]=[['name','名称'],['identity','身份'],['personality','性格'],['speaking_style','说话风格'],['example_dialogues','示例对话'],['system_prompt','补充系统提示']];
const sourceOptions:[keyof ContextSources,string,string][]=[
 ['foreground_window','当前窗口','读取前台窗口标题与进程名。'],['browser_windows','浏览器标题','读取可见浏览器窗口的标题。'],['idle_time','空闲时长','判断多久没有操作电脑。'],
 ['activity_rhythm','操作节奏','判断刚停下、刚回来和连续使用时长。'],['app_category','应用类型','区分编程、文档、浏览、娱乐和通讯。'],['window_switch_activity','窗口切换','统计近期窗口切换频率。'],
 ['task_pressure_signals','任务压力信号','从窗口标题或已启用的 OCR 中识别报错。'],['time_context','时间作息','使用本地时间判断时段。'],['media_audio_state','媒体 / 音频状态','检测正在播放的音频，减少打扰。'],
 ['fullscreen_focus_state','全屏 / 专注状态','检测全屏游戏、视频与会议。'],['system_health','系统状态','读取电量、网络、CPU、内存与磁盘状态。'],['screen_ocr','屏幕文字 OCR','在本机识别截图文字；文字会提供给当前模型。'],['screen_vision','屏幕截图视觉','将当前截图发送给已配置的视觉模型。']
];
const promptPreview=computed(()=>characterFields.filter(([key])=>character.value[key].trim()).map(([key,label])=>`${label}：${character.value[key].trim()}`).join('\n\n'));
const modelDirty=computed(()=>JSON.stringify([config.value,profileName.value,advanced.value,clearKey.value])!==modelBaseline.value);
const characterDirty=computed(()=>JSON.stringify(character.value)!==characterBaseline.value);
const saveLabel=computed(()=>ready.value&&(modelDirty.value||characterDirty.value)?'有未保存修改':saveStatus.value);
const stateNames:Record<string,string>={idle:'等待下一次陪伴',collecting:'正在了解当前状态',generating:'正在组织语言',displaying:'正在显示气泡',error:'需要检查配置'};
const skipNames:Record<string,string>={silent:'这次保持安静',min_interval:'距离上次发言还很近',no_event:'当前没有适合的话题',focused:'保持专注，稍后再来',media_audio:'正在播放音频，暂不打扰',fullscreen_focus:'全屏专注中',continuous_typing:'正在连续输入',do_not_disturb:'勿扰模式已开启',cancelled:'设置已更新，等待下一次检查',bubble_disabled:'气泡已关闭，本次未显示'};
function clone<T>(v:T):T{return structuredClone(toRaw(v));}
function notify(message:string,error=false){notice.value=message;noticeError.value=error;}
async function action(work:()=>Promise<void>){if(busy.value)return;busy.value=true;try{await work();}catch(e){notify(e instanceof Error?e.message:'操作失败',true);}finally{busy.value=false;}}
let activityRevision=0,petRevision=0;
let savedActivity:ActivitySettings,savedPet:PetSettings;
const activityQueue=createSaveQueue<{value:ActivitySettings;revision:number}>(async({value,revision})=>{
 try{const r=await api('/activity/settings',value,'PUT',5000);savedActivity=r.settings;if(revision===activityRevision){activity.value=r.settings;saveStatus.value='所有设置已保存';}}
 catch(e){if(revision===activityRevision)activity.value=clone(savedActivity);throw e;}
},e=>{saveStatus.value='保存失败，已恢复上次设置';notify(String(e instanceof Error?e.message:e),true);});
const petQueue=createSaveQueue<{value:PetSettings;revision:number}>(async({value,revision})=>{
 try{const r=await api('/settings/pet',value,'PUT',5000);savedPet=r.settings;if(revision===petRevision){pet.value=r.settings;saveStatus.value='所有设置已保存';}}
 catch(e){if(revision===petRevision)pet.value=clone(savedPet);throw e;}
},e=>{saveStatus.value='保存失败，已恢复上次设置';notify(String(e instanceof Error?e.message:e),true);});
function scheduleActivity(){saveStatus.value='正在保存…';activityQueue.schedule({value:clone(activity.value),revision:++activityRevision});}
function schedulePet(){saveStatus.value='正在保存…';petQueue.schedule({value:clone(pet.value),revision:++petRevision});}
function navigate(id:string){page.value=id;localStorage.setItem('vn.settings.page',id);}
function reload(){window.location.reload();}
function applyModels(data:JsonObject,id=selectedId.value){profiles.value=data.profiles;providers.value=data.providers;activeId.value=data.active_id;openModel(profiles.value.some(p=>p.id===id)?id:activeId.value || profiles.value[0]?.id || '');}
function openModel(id:string){
 selectedId.value=id;const p=profiles.value.find(x=>x.id===id);config.value=clone(p?.config || {});config.value.api_key='';profileName.value=p?.name || '';clearKey.value=false;
 const known=new Set([...(p?.fields || []).map(f=>f.key),'api_key','provider_id','context_length']);
 advanced.value=JSON.stringify(Object.fromEntries(Object.entries(config.value).filter(([key])=>!known.has(key))),null,2);
 catalog.value={entries:(p?.recommended_models || []).map(id=>({id,source:'recommended',recommended:true})),cache_state:'recommended'};
 modelBaseline.value=JSON.stringify([config.value,profileName.value,advanced.value,clearKey.value]);
}
function modelBody(){let extras:JsonObject;try{extras=JSON.parse(advanced.value);}catch{throw new Error('高级参数必须是有效 JSON。');}if(!extras || Array.isArray(extras) || typeof extras!=='object')throw new Error('高级参数必须是 JSON 对象。');if('api_key' in extras)throw new Error('请在密钥字段中填写 API Key。');return {name:profileName.value,config:{...config.value,...extras},clear_api_key:clearKey.value};}
async function chooseModel(id:string){if(id===selectedId.value)return;if(modelDirty.value){notify('当前配置有未保存修改，请先保存或还原。',true);return;}await action(async()=>{const p=profiles.value.find(x=>x.id===id);if(p?.configured){applyModels(await api('/settings/llm',{profile_id:id},'PUT'),id);notify('当前模型已切换');}else openModel(id);});}
function createModel(provider:string){return action(async()=>{if(modelDirty.value)throw new Error('请先保存或还原当前配置。');const data=await api('/settings/llm/profiles',{provider});applyModels(data,data.selected_id);notify('配置已创建，请填写并保存。');});}
function duplicateModel(){return action(async()=>{if(modelDirty.value)throw new Error('请先保存或还原当前配置。');const p=profiles.value.find(x=>x.id===selectedId.value)!;const data=await api('/settings/llm/profiles',{provider:p.provider,duplicate:p.id});applyModels(data,data.selected_id);notify('已复制保存的配置');});}
function deleteModel(){return action(async()=>{const data=await api(`/settings/llm/profiles/${selectedId.value}`,undefined,'DELETE');applyModels(data);notify('配置已删除');});}
function saveModel(){return action(async()=>{applyModels(await api(`/settings/llm/profiles/${selectedId.value}`,modelBody(),'PUT'));notify('模型配置已保存');});}
function activateModel(){return action(async()=>{if(modelDirty.value)throw new Error('请先保存配置。');applyModels(await api('/settings/llm',{profile_id:selectedId.value},'PUT'));notify('已设为当前模型');});}
function testModel(){return action(async()=>{const id=selectedId.value;connectionStates.value[id]='testing';try{await api(`/settings/llm/profiles/${id}/test`,modelBody());connectionStates.value[id]='connected';notify('连接测试通过');}catch(e){connectionStates.value[id]='failed';throw e;}});}
function fetchModels(){return action(async()=>{loadingModels.value=true;try{catalog.value=await api(`/settings/llm/profiles/${selectedId.value}/models/refresh`,modelBody());notify('模型列表已更新');}finally{loadingModels.value=false;}});}
function saveCharacter(){return action(async()=>{const sent=JSON.stringify(character.value);const r=await api('/settings/character',character.value,'PUT');if(JSON.stringify(character.value)===sent)character.value=r.settings;characterBaseline.value=JSON.stringify(r.settings);notify('VN 角色设定已保存');});}
function trigger(){return action(async()=>{await activityQueue.flush();const r=await api('/activity/proactive',{manual:true});notify(r.accepted?'已触发，稍后会在桌宠旁显示气泡。':'已有陪伴请求正在进行，请稍候。');await refreshStatus();});}
function preview(){return action(async()=>{await api('/pet/preview',{settings:pet.value,text:previewText.value});notify('预览气泡已显示在桌宠旁');});}
async function refreshStatus(){try{status.value=await api('/activity/status');}catch(e){status.value={...status.value,error:'无法连接桌宠服务，请重新打开设置。'};}}
async function close(){
 if(closing.value)return;
 closing.value=true;
 try{
  const pending=Promise.all([activityQueue.flush(),petQueue.flush()]);
  await Promise.race([pending,new Promise((_,reject)=>setTimeout(()=>reject(new Error('保存超时，请稍后重试。')),3000))]);
  if(modelDirty.value || characterDirty.value){closing.value=false;notify('模型或角色有未保存修改，请先保存或还原。',true);return;}
  if(!window.pywebview?.api.close)throw new Error('设置窗口连接已失效，请重新打开。');
  await window.pywebview.api.close();
 }catch(e){
  closing.value=false;
  notify(e instanceof Error?e.message:'关闭前保存失败，请重试。',true);
 }
}
let poll:ReturnType<typeof setInterval>|undefined;
window.requestSettingsClose=()=>{void close();};
onMounted(async()=>{try{await bootstrap();const [m,c,a,p]=await Promise.all([api('/settings/llm'),api('/settings/character'),api('/activity/settings'),api('/settings/pet')]);applyModels(m);character.value=c.settings;characterBaseline.value=JSON.stringify(character.value);activity.value=a.settings;savedActivity=clone(activity.value);pet.value=p.settings;savedPet=clone(pet.value);ready.value=true;await refreshStatus();poll=setInterval(()=>void refreshStatus(),2500);}catch(e){fatal.value=e instanceof Error?e.message:'无法加载设置';}});
onBeforeUnmount(()=>{clearInterval(poll);activityQueue.cancel();petQueue.cancel();});
</script>

<template>
 <div class="settings-workspace">
  <aside class="sidebar">
   <div class="brand"><div class="brand-mark">VN</div><div><strong>VN 桌宠</strong><small>陪伴，恰到好处</small></div></div>
   <div class="nav-caption">偏好设置</div>
   <nav aria-label="设置分类"><button v-for="s in sections" :key="s.id" :class="{active:page===s.id}" @click="navigate(s.id)"><component :is="s.icon"/><span>{{ s.label }}</span><i v-if="page===s.id"></i></button></nav>
   <div class="sidebar-foot"><PawPrint/><p>一点小小的陪伴<br><span>从属于你的设置开始。</span></p></div>
  </aside>
  <div class="workspace-body">
   <header class="workspace-top"><span>桌面伙伴 <span class="breadcrumb">/</span> {{ sections.find(s=>s.id===page)?.label }}</span><div><small :class="{'save-error':saveStatus.includes('失败')}"><Check/>{{ saveLabel }}</small><button class="icon-button" aria-label="关闭设置" :disabled="closing" @click="close"><X/></button></div></header>
   <main>
    <div v-if="fatal" class="fatal" role="alert"><h2>暂时无法打开设置</h2><p>{{ fatal }}</p><button class="pp-button" @click="reload">重新加载</button></div>
    <div v-else-if="!ready" class="loading"><RefreshCw class="spin"/>正在连接桌宠…</div>
    <template v-else>
     <div v-if="status.storage_warning" class="inline-warning">{{ status.storage_warning }}</div>
     <fieldset v-if="page==='llm'" class="reset-fieldset" :disabled="busy">
      <LlmSettingsSection :profiles="profiles" :providers="providers" :selected-id="selectedId" :catalog="catalog" :advanced-json="advanced" :clear-api-key="clearKey" :dirty="modelDirty" :loading-models="loadingModels" :connection-states="connectionStates" v-model:config="config" v-model:profile-name="profileName" @select="chooseModel" @create="createModel" @duplicate="duplicateModel" @remove="deleteModel" @fetch-models="fetchModels" @test="testModel" @save="saveModel" @revert="openModel(selectedId)" @update:advanced-json="advanced=$event" @update:clear-api-key="clearKey=$event"/>
      <div v-if="selectedId" class="button-row end"><span class="muted">{{ selectedId===activeId?'此配置正在用于 VN 主动陪伴':'保存后可将此配置设为当前模型' }}</span><button class="pp-button primary" :disabled="selectedId===activeId || modelDirty" @click="activateModel">设为当前模型</button></div>
     </fieldset>
     <template v-if="page==='character'">
      <div class="page-heading"><div><div class="eyebrow">CHARACTER</div><h1>VN 角色</h1><p>让每一次发言，都有熟悉的语气。</p></div><div class="button-row"><button class="pp-button" :disabled="!characterDirty" @click="character=JSON.parse(characterBaseline)">还原修改</button><button class="pp-button primary" :disabled="busy || !characterDirty" @click="saveCharacter"><Save/>保存设定</button></div></div>
      <section class="settings-section"><div class="section-title"><UserRound/><h2>认识 VN</h2></div><div class="form-grid two"><label v-for="[key,label] in characterFields" :key="key" :class="{'full-width':key==='system_prompt' || key==='example_dialogues'}">{{ label }}<input v-if="key==='name'" v-model="character[key]" maxlength="80"><textarea v-else v-model="character[key]" :rows="key==='system_prompt'?5:3" :maxlength="key==='system_prompt'?16000:key==='example_dialogues'?8000:4000"></textarea></label></div></section>
      <section class="settings-section"><h2>最终角色提示词预览</h2><p class="muted">保存后，主动陪伴会使用以下人设，再结合已启用的感知信息。</p><pre class="prompt-preview">{{ promptPreview }}</pre></section>
     </template>
     <template v-if="page==='activity'">
      <div class="page-heading"><div><div class="eyebrow">COMPANIONSHIP</div><h1>主动陪伴</h1><p>在合适的时候，说一句刚刚好的话。</p></div><button class="pp-button primary" :disabled="busy" @click="trigger"><Sparkles/>立即触发一次</button></div>
      <section class="settings-section"><label class="switch-row"><span><strong>启用主动陪伴</strong><small>开启后按所选节奏感知状态并尝试发言。</small></span><input type="checkbox" v-model="activity.enabled" @change="scheduleActivity"></label><label class="switch-row"><span><strong>勿扰模式</strong><small>暂停自动发言；仍可手动触发一次。</small></span><input type="checkbox" v-model="activity.do_not_disturb" @change="scheduleActivity"></label></section>
      <section class="settings-section"><h2>陪伴节奏</h2><div class="form-grid two"><label>触发方式<select v-model="activity.interaction_mode" @change="scheduleActivity"><option value="fixed_interval">固定间隔</option><option value="manager">智能判断合适时机</option></select></label><label>检查间隔（分钟）<input type="number" min="1" max="180" v-model.number="activity.interval_minutes" @change="scheduleActivity"></label><label>最短发言间隔（分钟）<input type="number" min="1" max="180" v-model.number="activity.min_speech_interval_minutes" @change="scheduleActivity"></label><label>最长发言间隔（分钟）<input type="number" min="1" max="240" v-model.number="activity.max_speech_interval_minutes" @change="scheduleActivity"></label></div><p class="muted">最长间隔用于智能判断模式；专注、勿扰与模型静默仍会优先。</p></section>
      <section class="settings-section"><div class="section-title"><span class="status-dot" :class="{running:activity.enabled&&!activity.do_not_disturb}"></span><h2>{{ stateNames[status.state] || status.state }}</h2></div><p v-if="status.skip_reason" class="muted">{{ skipNames[status.skip_reason] || status.skip_reason }}</p><p v-if="status.error" class="inline-warning">{{ status.error }}</p><p v-for="warning in status.warnings" class="inline-warning">{{ warning }}</p><div class="status-times"><span>上次检查 <b>{{ status.last_checked?new Date(status.last_checked*1000).toLocaleTimeString():'尚未检查' }}</b></span><span>上次发言 <b>{{ status.last_spoken?new Date(status.last_spoken*1000).toLocaleTimeString():'尚未发言' }}</b></span></div><blockquote v-if="status.last_text">{{ status.last_text }}</blockquote></section>
     </template>
     <template v-if="page==='sources'">
      <div class="page-heading"><div><div class="eyebrow">AWARENESS</div><h1>感知来源</h1><p>选择 VN 可以参考哪些信息，每项都可以单独关闭。</p></div></div>
      <section class="settings-section"><div class="source-grid"><label v-for="[key,label,help] in sourceOptions" :key="key" class="source-option"><input type="checkbox" v-model="activity.context_sources[key]" :disabled="key==='screen_vision' && !status.vision_available && !activity.context_sources.screen_vision || key==='screen_ocr' && !status.ocr_available && !activity.context_sources.screen_ocr" @change="scheduleActivity"><span><strong>{{ label }}</strong><small>{{ help }}</small><small v-if="key==='screen_vision'&&!status.vision_available" class="unavailable">需要先启用支持视觉的模型</small><small v-if="key==='screen_ocr'&&!status.ocr_available" class="unavailable">需安装可选 OCR 依赖，安装后自动可用</small></span></label></div></section>
      <section class="settings-section"><label class="switch-row"><span><strong>保存最近截图</strong><small>仅在 OCR 或视觉开启时生效，只保留最近一次截图用于排查。</small></span><input type="checkbox" v-model="activity.save_latest_screenshot" @change="scheduleActivity"></label></section>
     </template>
     <template v-if="page==='pet'">
      <div class="page-heading"><div><div class="eyebrow">SPEECH BUBBLE</div><h1>发言气泡</h1><p>调整文字的样子，找到舒适的阅读节奏。</p></div><button class="pp-button" @click="action(async()=>{await api('/pet/clear',{});notify('当前气泡已隐藏');})"><EyeOff/>隐藏当前气泡</button></div>
      <section class="settings-section"><label class="switch-row"><span><strong>显示发言气泡</strong><small>关闭后不展示或记录新的陪伴发言。</small></span><input type="checkbox" v-model="pet.enabled" @change="schedulePet"></label><div class="form-grid two"><label>文字大小（像素）<input type="number" min="12" max="32" v-model.number="pet.font_size" @change="schedulePet"></label><label>每页显示时长（秒）<input type="number" min="4" max="120" v-model.number="pet.duration_seconds" @change="schedulePet"></label><label>气泡位置<select v-model="pet.position" @change="schedulePet"><option value="auto">自动选择</option><option value="left_top">优先左上方</option><option value="right_top">优先右上方</option></select></label><div></div><label>气泡背景<input type="color" v-model="pet.background" @change="schedulePet"></label><label>边框颜色<input type="color" v-model="pet.border" @change="schedulePet"></label><label>文字颜色<input type="color" v-model="pet.text_color" @change="schedulePet"></label></div></section>
      <section class="settings-section"><h2>看看效果</h2><label>预览文字<textarea v-model="previewText" maxlength="12000" rows="3"></textarea></label><div class="bubble-preview-area"><div class="bubble-preview" :style="{background:pet.background,borderColor:pet.border,color:pet.text_color,fontSize:pet.font_size+'px'}">{{ previewText }}</div><span class="preview-avatar">VN</span></div><div class="button-row end"><button class="pp-button primary" :disabled="busy" @click="preview"><Eye/>在桌宠旁预览</button></div></section>
     </template>
    </template>
   </main>
  </div>
  <div v-if="notice" class="notice" :class="{error:noticeError}" :role="noticeError?'alert':'status'"><span>{{ notice }}</span><button class="icon-button" aria-label="关闭提示" @click="notice=''">×</button></div>
 </div>
</template>
