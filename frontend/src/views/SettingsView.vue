<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  ElButton,
  ElCard,
  ElDescriptions,
  ElDescriptionsItem,
  ElDivider,
  ElDialog,
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElMessage,
  ElOption,
  ElPopconfirm,
  ElSelect,
  ElSwitch,
  ElTable,
  ElTableColumn,
  ElTag,
  ElCollapse,
  ElCollapseItem
} from 'element-plus'
import { Delete, DocumentCopy, Edit, Plus, Refresh } from '@element-plus/icons-vue'

import { webhooksApi, workflowsApi } from '@/api'
import { useSettingsStore } from '@/stores/settings'
import type { GitLabWebhookEvent, GitLabWebhookRule, Workflow } from '@/types'

const settingsStore = useSettingsStore()
const saving = ref(false)
const webhookLoading = ref(false)
const webhookDialogVisible = ref(false)
const editingWebhookRuleId = ref<number | null>(null)
const workflows = ref<Workflow[]>([])
const webhookRules = ref<GitLabWebhookRule[]>([])
const webhookEvents = ref<GitLabWebhookEvent[]>([])

const monitorForm = ref({
  refreshInterval: 10
})

const observabilityForm = ref({
  prometheusUrl: '',
  grafanaUrl: '',
  grafanaDashboardUid: '',
  grafanaDatasource: '',
  grafanaOrgId: '',
  grafanaTimeRange: 'now-6h',
  grafanaEmbedEnabled: false
})

const webhookForm = ref({
  name: '',
  enabled: true,
  workflow_ids: [] as number[],
  project_id: '',
  project_path: '',
  ref_patterns_text: '',
  secret_token: ''
})

function syncFormsFromStore() {
  monitorForm.value.refreshInterval = settingsStore.settings.monitor.refreshInterval
  observabilityForm.value = {
    prometheusUrl: settingsStore.settings.observability.prometheusUrl ?? '',
    grafanaUrl: settingsStore.settings.observability.grafanaUrl ?? '',
    grafanaDashboardUid: settingsStore.settings.observability.grafanaDashboardUid ?? '',
    grafanaDatasource: settingsStore.settings.observability.grafanaDatasource ?? '',
    grafanaOrgId: settingsStore.settings.observability.grafanaOrgId ?? '',
    grafanaTimeRange: settingsStore.settings.observability.grafanaTimeRange,
    grafanaEmbedEnabled: settingsStore.settings.observability.grafanaEmbedEnabled
  }
}

watch(() => settingsStore.settings, syncFormsFromStore, { deep: true })

const hasChanges = computed(() => {
  const { monitor, observability } = settingsStore.settings
  return (
    monitorForm.value.refreshInterval !== monitor.refreshInterval ||
    observabilityForm.value.prometheusUrl !== (observability.prometheusUrl ?? '') ||
    observabilityForm.value.grafanaUrl !== (observability.grafanaUrl ?? '') ||
    observabilityForm.value.grafanaDashboardUid !== (observability.grafanaDashboardUid ?? '') ||
    observabilityForm.value.grafanaDatasource !== (observability.grafanaDatasource ?? '') ||
    observabilityForm.value.grafanaOrgId !== (observability.grafanaOrgId ?? '') ||
    observabilityForm.value.grafanaTimeRange !== observability.grafanaTimeRange ||
    observabilityForm.value.grafanaEmbedEnabled !== observability.grafanaEmbedEnabled
  )
})

async function handleSave() {
  saving.value = true
  try {
    await settingsStore.updateMonitorSettings({
      refreshInterval: monitorForm.value.refreshInterval
    })

    await settingsStore.updateObservabilitySettings({
      prometheusUrl: observabilityForm.value.prometheusUrl || null,
      grafanaUrl: observabilityForm.value.grafanaUrl || null,
      grafanaDashboardUid: observabilityForm.value.grafanaDashboardUid || null,
      grafanaDatasource: observabilityForm.value.grafanaDatasource || null,
      grafanaOrgId: observabilityForm.value.grafanaOrgId || null,
      grafanaTimeRange: observabilityForm.value.grafanaTimeRange || 'now-6h',
      grafanaEmbedEnabled: observabilityForm.value.grafanaEmbedEnabled
    })

    ElMessage.success('设置已保存')
  } catch (error) {
    console.error(error)
    ElMessage.error('保存设置失败')
  } finally {
    saving.value = false
  }
}

async function handleReset() {
  saving.value = true
  try {
    await settingsStore.resetSettings()
    ElMessage.success('设置已恢复默认值')
  } catch (error) {
    console.error(error)
    ElMessage.error('重置设置失败')
  } finally {
    saving.value = false
  }
}

function resetWebhookForm() {
  webhookForm.value = {
    name: '',
    enabled: true,
    workflow_ids: [],
    project_id: '',
    project_path: '',
    ref_patterns_text: '',
    secret_token: ''
  }
  editingWebhookRuleId.value = null
}

async function fetchWebhookData() {
  webhookLoading.value = true
  try {
    const [nextWorkflows, nextRules, nextEvents] = await Promise.all([
      workflowsApi.list(),
      webhooksApi.listGitLabRules(),
      webhooksApi.listGitLabEvents({ limit: 50 })
    ])
    workflows.value = nextWorkflows
    webhookRules.value = nextRules
    webhookEvents.value = nextEvents
  } catch (error) {
    console.error(error)
    ElMessage.error('加载 GitLab Webhook 配置失败')
  } finally {
    webhookLoading.value = false
  }
}

function openCreateWebhookDialog() {
  resetWebhookForm()
  webhookDialogVisible.value = true
}

function openEditWebhookDialog(rule: GitLabWebhookRule) {
  editingWebhookRuleId.value = rule.id
  webhookForm.value = {
    name: rule.name,
    enabled: rule.enabled,
    workflow_ids: [...rule.workflow_ids],
    project_id: rule.project_id || '',
    project_path: rule.project_path || '',
    ref_patterns_text: rule.ref_patterns.join('\n'),
    secret_token: ''
  }
  webhookDialogVisible.value = true
}

function webhookRefPatterns() {
  return webhookForm.value.ref_patterns_text
    .split(/[\n,]/)
    .map(item => item.trim())
    .filter(Boolean)
}

function webhookUrl(rule: GitLabWebhookRule) {
  return `${window.location.origin}/api/webhooks/gitlab/${rule.id}`
}

async function copyWebhookUrl(rule: GitLabWebhookRule) {
  try {
    await navigator.clipboard.writeText(webhookUrl(rule))
    ElMessage.success('Webhook URL 已复制')
  } catch (error) {
    console.error(error)
    ElMessage.error('复制失败，请手动复制 URL')
  }
}

function workflowNames(rule: GitLabWebhookRule) {
  return rule.workflow_ids
    .map(id => workflows.value.find(workflow => workflow.id === id)?.name || `#${id}`)
    .join('、')
}

async function saveWebhookRule() {
  if (!webhookForm.value.name.trim()) {
    ElMessage.warning('请输入规则名称')
    return
  }
  if (webhookForm.value.workflow_ids.length === 0) {
    ElMessage.warning('请选择至少一个工作流')
    return
  }
  if (!editingWebhookRuleId.value && !webhookForm.value.secret_token.trim()) {
    ElMessage.warning('新建规则需要填写 Secret Token')
    return
  }

  webhookLoading.value = true
  try {
    const payload = {
      name: webhookForm.value.name.trim(),
      enabled: webhookForm.value.enabled,
      workflow_ids: webhookForm.value.workflow_ids,
      project_id: webhookForm.value.project_id.trim() || null,
      project_path: webhookForm.value.project_path.trim() || null,
      ref_patterns: webhookRefPatterns()
    }

    if (editingWebhookRuleId.value) {
      await webhooksApi.updateGitLabRule(editingWebhookRuleId.value, {
        ...payload,
        ...(webhookForm.value.secret_token.trim() ? { secret_token: webhookForm.value.secret_token.trim() } : {})
      })
      ElMessage.success('Webhook 规则已更新')
    } else {
      await webhooksApi.createGitLabRule({
        ...payload,
        secret_token: webhookForm.value.secret_token.trim()
      })
      ElMessage.success('Webhook 规则已创建')
    }

    webhookDialogVisible.value = false
    resetWebhookForm()
    await fetchWebhookData()
  } catch (error) {
    console.error(error)
    ElMessage.error('保存 GitLab Webhook 规则失败')
  } finally {
    webhookLoading.value = false
  }
}

async function toggleWebhookRule(rule: GitLabWebhookRule, enabled: boolean) {
  webhookLoading.value = true
  try {
    await webhooksApi.updateGitLabRule(rule.id, { enabled })
    await fetchWebhookData()
  } catch (error) {
    console.error(error)
    ElMessage.error('更新规则状态失败')
  } finally {
    webhookLoading.value = false
  }
}

async function deleteWebhookRule(rule: GitLabWebhookRule) {
  webhookLoading.value = true
  try {
    await webhooksApi.deleteGitLabRule(rule.id)
    ElMessage.success('Webhook 规则已删除')
    await fetchWebhookData()
  } catch (error) {
    console.error(error)
    ElMessage.error('删除 GitLab Webhook 规则失败')
  } finally {
    webhookLoading.value = false
  }
}

function eventRuleName(event: GitLabWebhookEvent) {
  return webhookRules.value.find(r => r.id === event.rule_id)?.name || `规则 #${event.rule_id}`
}

function shortRef(ref: string | null) {
  if (!ref) return '-'
  return ref.replace(/^refs\/heads\//, '')
}

function eventStatusType(status: string) {
  if (status === 'accepted') return 'success'
  if (status === 'error') return 'danger'
  return 'info'
}

function formatTime(iso: string) {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

onMounted(async () => {
  await settingsStore.fetchSettings()
  await fetchWebhookData()
  syncFormsFromStore()
})
</script>

<template>
  <div class="settings-view">
    <div class="toolbar">
      <div class="toolbar-title">
        <h2>系统设置</h2>
      </div>
      <div class="toolbar-actions">
        <ElButton @click="handleReset" :icon="Refresh" :loading="saving">
          重置
        </ElButton>
        <ElButton type="primary" @click="handleSave" :disabled="!hasChanges" :loading="saving">
          保存
        </ElButton>
      </div>
    </div>

    <ElCard shadow="hover" class="settings-card">
      <template #header>
        <div class="card-header">
          <ElTag type="info" size="small">监控</ElTag>
          <span>系统监控刷新设置</span>
        </div>
      </template>

      <ElForm label-width="180px" label-position="left">
        <ElFormItem label="刷新间隔">
          <ElInputNumber
            v-model="monitorForm.refreshInterval"
            :min="5"
            :max="300"
            :step="5"
            style="width: 180px"
          />
          <span class="unit">秒</span>
        </ElFormItem>
      </ElForm>

      <ElDivider />

      <ElDescriptions :column="1" border size="small">
        <ElDescriptionsItem label="当前刷新间隔">
          {{ settingsStore.settings.monitor.refreshInterval }} 秒
        </ElDescriptionsItem>
        <ElDescriptionsItem label="说明">
          控制监控面板刷新本地和远程服务器指标的频率。
        </ElDescriptionsItem>
      </ElDescriptions>
    </ElCard>

    <ElCard shadow="hover" class="settings-card">
      <template #header>
        <div class="card-header">
          <ElTag type="success" size="small">可观测性</ElTag>
          <span>外部 Prometheus 和 Grafana 入口配置</span>
        </div>
      </template>

      <ElForm label-width="180px" label-position="left">
        <ElFormItem label="Prometheus 地址">
          <ElInput
            v-model="observabilityForm.prometheusUrl"
            placeholder="http://prometheus.example.com:9090"
            clearable
          />
        </ElFormItem>

        <ElFormItem label="Grafana 地址">
          <ElInput
            v-model="observabilityForm.grafanaUrl"
            placeholder="http://grafana.example.com:3000"
            clearable
          />
        </ElFormItem>

        <ElFormItem label="Grafana 仪表盘 UID">
          <ElInput
            v-model="observabilityForm.grafanaDashboardUid"
            placeholder="iotdb-overview"
            clearable
          />
        </ElFormItem>

        <ElFormItem label="Grafana 数据源">
          <ElInput
            v-model="observabilityForm.grafanaDatasource"
            placeholder="Prometheus"
            clearable
          />
        </ElFormItem>

        <ElFormItem label="Grafana 组织 ID">
          <ElInput
            v-model="observabilityForm.grafanaOrgId"
            placeholder="1"
            clearable
          />
        </ElFormItem>

        <ElFormItem label="默认时间范围">
          <ElInput
            v-model="observabilityForm.grafanaTimeRange"
            placeholder="now-6h"
          />
        </ElFormItem>

        <ElFormItem label="Grafana 嵌入模式">
          <ElSwitch v-model="observabilityForm.grafanaEmbedEnabled" />
          <span class="hint">为仪表盘链接添加 Kiosk 模式，获得更简洁的展示视图。</span>
        </ElFormItem>
      </ElForm>

      <ElDivider />

      <ElDescriptions :column="1" border size="small">
        <ElDescriptionsItem label="推荐配置">
          建议将 Prometheus 和 Grafana 独立部署，通过此处配置的地址作为统一入口。
        </ElDescriptionsItem>
        <ElDescriptionsItem label="生效位置">
          监控页面将显示已配置的 Prometheus 和 Grafana 快捷链接。
        </ElDescriptionsItem>
      </ElDescriptions>
    </ElCard>

    <ElCard shadow="hover" class="settings-card">
      <template #header>
        <div class="card-header split">
          <div>
            <ElTag type="warning" size="small">GitLab</ElTag>
            <span>Push Webhook 触发工作流</span>
          </div>
          <div class="card-actions">
            <ElButton size="small" :icon="Refresh" :loading="webhookLoading" @click="fetchWebhookData">
              刷新
            </ElButton>
            <ElButton size="small" type="primary" :icon="Plus" @click="openCreateWebhookDialog">
              新建规则
            </ElButton>
          </div>
        </div>
      </template>

      <ElTable :data="webhookRules" size="small" border v-loading="webhookLoading">
        <ElTableColumn prop="name" label="规则" min-width="140" />
        <ElTableColumn label="启用" width="90">
          <template #default="{ row }">
            <ElSwitch
              :model-value="row.enabled"
              size="small"
              @update:model-value="toggleWebhookRule(row, Boolean($event))"
            />
          </template>
        </ElTableColumn>
        <ElTableColumn label="工作流" min-width="220">
          <template #default="{ row }">
            {{ workflowNames(row) || '-' }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="分支 Pattern" min-width="160">
          <template #default="{ row }">
            {{ row.ref_patterns.length ? row.ref_patterns.join(', ') : '全部分支' }}
          </template>
        </ElTableColumn>
        <ElTableColumn label="Secret" width="100">
          <template #default="{ row }">
            <ElTag :type="row.secret_configured ? 'success' : 'danger'" size="small">
              {{ row.secret_configured ? '已配置' : '未配置' }}
            </ElTag>
          </template>
        </ElTableColumn>
        <ElTableColumn label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <ElButton text size="small" :icon="DocumentCopy" @click="copyWebhookUrl(row)">
              复制 URL
            </ElButton>
            <ElButton text size="small" :icon="Edit" @click="openEditWebhookDialog(row)">
              编辑
            </ElButton>
            <ElPopconfirm title="确定删除该 webhook 规则？" @confirm="deleteWebhookRule(row)">
              <template #reference>
                <ElButton text size="small" type="danger" :icon="Delete">
                  删除
                </ElButton>
              </template>
            </ElPopconfirm>
          </template>
        </ElTableColumn>
      </ElTable>

      <ElCollapse class="webhook-events-collapse">
        <ElCollapseItem title="触发事件记录" name="events">
          <ElTable :data="webhookEvents" size="small" border empty-text="暂无触发记录">
            <ElTableColumn label="时间" width="170">
              <template #default="{ row }">
                {{ formatTime(row.received_at) }}
              </template>
            </ElTableColumn>
            <ElTableColumn label="规则" min-width="120">
              <template #default="{ row }">
                {{ eventRuleName(row) }}
              </template>
            </ElTableColumn>
            <ElTableColumn label="分支" min-width="130">
              <template #default="{ row }">
                {{ shortRef(row.ref) }}
              </template>
            </ElTableColumn>
            <ElTableColumn label="推送人" width="120">
              <template #default="{ row }">
                {{ row.user_name || '-' }}
              </template>
            </ElTableColumn>
            <ElTableColumn label="状态" width="100">
              <template #default="{ row }">
                <ElTag :type="eventStatusType(row.status)" size="small">
                  {{ row.status }}
                </ElTag>
              </template>
            </ElTableColumn>
            <ElTableColumn label="执行 ID" min-width="100">
              <template #default="{ row }">
                {{ row.execution_ids.length ? row.execution_ids.join(', ') : '-' }}
              </template>
            </ElTableColumn>
          </ElTable>
        </ElCollapseItem>
      </ElCollapse>

      <ElDivider />

      <ElDescriptions :column="1" border size="small">
        <ElDescriptionsItem label="GitLab 配置">
          在 GitLab 项目 Webhooks 中选择 Push events，URL 使用复制的地址，Secret token 填写本规则的 Secret Token。
        </ElDescriptionsItem>
        <ElDescriptionsItem label="访问说明">
          如果 GitLab 不能访问当前页面的 localhost 地址，请将复制出来的 URL 主机名替换为可访问的代理地址。
        </ElDescriptionsItem>
      </ElDescriptions>
    </ElCard>

    <ElDialog
      v-model="webhookDialogVisible"
      :title="editingWebhookRuleId ? '编辑 GitLab Webhook 规则' : '新建 GitLab Webhook 规则'"
      width="720px"
      @closed="resetWebhookForm"
    >
      <ElForm label-width="150px" label-position="left">
        <ElFormItem label="规则名称">
          <ElInput v-model="webhookForm.name" placeholder="例如 main 分支回归测试" />
        </ElFormItem>
        <ElFormItem label="启用规则">
          <ElSwitch v-model="webhookForm.enabled" />
        </ElFormItem>
        <ElFormItem label="触发工作流">
          <ElSelect
            v-model="webhookForm.workflow_ids"
            multiple
            filterable
            placeholder="选择一个或多个工作流"
            style="width: 100%"
          >
            <ElOption
              v-for="workflow in workflows"
              :key="workflow.id"
              :label="workflow.name"
              :value="workflow.id"
            />
          </ElSelect>
        </ElFormItem>
        <ElFormItem label="Project ID">
          <ElInput v-model="webhookForm.project_id" placeholder="可选，留空则不限制项目 ID" />
        </ElFormItem>
        <ElFormItem label="Project Path">
          <ElInput v-model="webhookForm.project_path" placeholder="可选，例如 group/project" />
        </ElFormItem>
        <ElFormItem label="分支 Pattern">
          <ElInput
            v-model="webhookForm.ref_patterns_text"
            type="textarea"
            :rows="3"
            placeholder="每行一个，例如 main、release/*、refs/heads/main；留空表示全部分支"
          />
        </ElFormItem>
        <ElFormItem label="Secret Token">
          <ElInput
            v-model="webhookForm.secret_token"
            show-password
            :placeholder="editingWebhookRuleId ? '留空表示不修改 Secret Token' : '填写 GitLab Webhook Secret Token'"
          />
        </ElFormItem>
      </ElForm>
      <template #footer>
        <ElButton @click="webhookDialogVisible = false">取消</ElButton>
        <ElButton type="primary" :loading="webhookLoading" @click="saveWebhookRule">
          保存
        </ElButton>
      </template>
    </ElDialog>
  </div>
</template>

<style scoped>
.settings-view {
  padding: 0;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding: 8px 10px;
  background: #fff;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
}

.toolbar-title h2 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.toolbar-actions {
  display: flex;
  gap: 6px;
}

.settings-card {
  margin-bottom: 10px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.card-header.split {
  justify-content: space-between;
}

.card-header.split > div {
  display: flex;
  align-items: center;
  gap: 6px;
}

.card-actions {
  display: flex;
  gap: 6px;
}

.webhook-events-collapse {
  margin-top: 10px;
}

.unit {
  margin-left: 6px;
  color: #94a3b8;
  font-size: 10px;
}

.hint {
  margin-left: 10px;
  color: #94a3b8;
  font-size: 10px;
}
</style>
