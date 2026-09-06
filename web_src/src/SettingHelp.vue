<script setup lang="ts">
import { CircleHelp } from 'lucide-vue-next';
defineProps<{helpKey:string}>();
const help:Record<string,string>={
 'llm.profile':'新增配置、填写连接信息并保存。选择已配置的实例可将它设为当前模型。',
 'llm.context-window':'模型上下文窗口。以实际服务支持的长度为准。',
 'llm.advanced-json':'用于保存模板之外的模型参数，不应在这里填写密钥。'
};
</script>
<template><span class="setting-help" tabindex="0" :title="help[helpKey] || '修改后保存配置即可生效。'" :aria-label="help[helpKey] || '设置说明'"><CircleHelp /></span></template>
