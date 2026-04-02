<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import {
  ElForm,
  ElFormItem,
  ElInput,
  ElInputNumber,
  ElSelect,
  ElOption,
  ElCheckbox,
  ElButton,
  ElIcon,
  ElEmpty
} from 'element-plus'
import { ArrowRight, ArrowLeft, Edit } from '@element-plus/icons-vue'
import { useWorkflowsStore } from '@/stores/workflows'
import { useServersStore } from '@/stores/servers'
import { NODE_CONFIGS } from '@/types'
import type { NodeType } from '@/types'

const workflowsStore = useWorkflowsStore()
const serversStore = useServersStore()

// Panel state
const isCollapsed = ref(false)

// Local edit state for node label
const editingLabel = ref('')
const isEditingLabel = ref(false)

// Get selected node
const selectedNode = computed(() => workflowsStore.selectedNode)

// Get node config
const nodeConfig = computed(() => {
  if (!selectedNode.value) return null
  return NODE_CONFIGS[selectedNode.value.data.nodeType as NodeType] || null
})

// Get node type label and color
const nodeTypeLabel = computed(() => nodeConfig.value?.label || '')
const nodeTypeColor = computed(() => nodeConfig.value?.color || '#909399')
const nodeCategory = computed(() => nodeConfig.value?.category || '')

// Category labels
const categoryLabels: Record<string, string> = {
  basic: 'Basic Node',
  iotdb: 'IoTDB Node',
  control: 'Control Node',
  result: 'Result Node'
}

// Server options for dropdown
const serverOptions = computed(() => {
  return serversStore.servers.map(server => ({
    value: server.id,
    label: `${server.name} (${server.host})`
  }))
})

// Fetch servers on mount
onMounted(async () => {
  if (serversStore.servers.length === 0) {
    try {
      await serversStore.fetchServers()
    } catch {
      // Silently fail - servers may not be configured
    }
  }
})

// Watch selected node to update local state
watch(selectedNode, (node) => {
  if (node) {
    editingLabel.value = node.data.label
  }
}, { immediate: true })

// Toggle panel
const togglePanel = () => {
  isCollapsed.value = !isCollapsed.value
}

// Start editing label
const startEditLabel = () => {
  if (selectedNode.value) {
    editingLabel.value = selectedNode.value.data.label
    isEditingLabel.value = true
  }
}

// Save label
const saveLabel = () => {
  if (selectedNode.value && editingLabel.value.trim()) {
    workflowsStore.updateNodeLabel(selectedNode.value.id, editingLabel.value.trim())
  }
  isEditingLabel.value = false
}

// Cancel label edit
const cancelEditLabel = () => {
  if (selectedNode.value) {
    editingLabel.value = selectedNode.value.data.label
  }
  isEditingLabel.value = false
}

// Update config field
const updateConfig = (field: string, value: unknown) => {
  if (!selectedNode.value) return
  workflowsStore.updateNodeConfig(selectedNode.value.id, { [field]: value })
}

// Get config value
const getConfigValue = (field: string): unknown => {
  if (!selectedNode.value) return null
  return selectedNode.value.data.config[field]
}

// Field definitions by node type
const getFieldDefinitions = (nodeType: NodeType): Array<{
  field: string
  label: string
  type: 'text' | 'textarea' | 'number' | 'select' | 'checkbox' | 'json' | 'server'
  options?: Array<{ value: string | number | boolean; label: string }>
  placeholder?: string
  min?: number
  max?: number
}> => {
  const definitions: Record<NodeType, Array<{
    field: string
    label: string
    type: 'text' | 'textarea' | 'number' | 'select' | 'checkbox' | 'json' | 'server'
    options?: Array<{ value: string | number | boolean; label: string }>
    placeholder?: string
    min?: number
    max?: number
  }>> = {
    // Basic nodes
    shell: [
      { field: 'command', label: 'Command', type: 'textarea', placeholder: 'Enter shell command...' },
      { field: 'server_id', label: 'Server', type: 'server' },
      { field: 'timeout', label: 'Timeout (seconds)', type: 'number', min: 1, max: 3600 },
      { field: 'retry', label: 'Retry Count', type: 'number', min: 0, max: 10 }
    ],
    upload: [
      { field: 'local_path', label: 'Local Path', type: 'text', placeholder: '/path/to/local/file' },
      { field: 'remote_path', label: 'Remote Path', type: 'text', placeholder: '/path/to/remote/file' },
      { field: 'server_id', label: 'Server', type: 'server' }
    ],
    download: [
      { field: 'remote_path', label: 'Remote Path', type: 'text', placeholder: '/path/to/remote/file' },
      { field: 'local_path', label: 'Local Path', type: 'text', placeholder: '/path/to/local/file' },
      { field: 'server_id', label: 'Server', type: 'server' }
    ],
    config: [
      { field: 'file_path', label: 'File Path', type: 'text', placeholder: '/path/to/config/file' },
      { field: 'replacements', label: 'Replacements', type: 'json', placeholder: '{"key": "value"}' },
      { field: 'server_id', label: 'Server', type: 'server' }
    ],
    log_view: [
      { field: 'file_path', label: 'File Path', type: 'text', placeholder: '/path/to/log/file' },
      { field: 'lines', label: 'Lines', type: 'number', min: 1, max: 10000 },
      { field: 'server_id', label: 'Server', type: 'server' }
    ],

    // IoTDB nodes
    iotdb_deploy: [
      { field: 'version', label: 'Version', type: 'text', placeholder: '0.13.0' },
      { field: 'install_path', label: 'Install Path', type: 'text', placeholder: '/opt/iotdb' },
      { field: 'server_id', label: 'Server', type: 'server' },
      { field: 'config_template', label: 'Config Template', type: 'text', placeholder: 'Template name (optional)' }
    ],
    iotdb_start: [
      { field: 'server_id', label: 'Server', type: 'server' },
      { field: 'wait_port', label: 'Wait Port', type: 'number', min: 1, max: 65535 },
      { field: 'timeout', label: 'Timeout (seconds)', type: 'number', min: 1, max: 600 }
    ],
    iotdb_stop: [
      { field: 'server_id', label: 'Server', type: 'server' },
      { field: 'graceful', label: 'Graceful Shutdown', type: 'checkbox' }
    ],
    iotdb_cli: [
      { field: 'commands', label: 'Commands', type: 'textarea', placeholder: 'Enter IoTDB CLI commands (one per line)...' },
      { field: 'server_id', label: 'Server', type: 'server' },
      { field: 'timeout', label: 'Timeout (seconds)', type: 'number', min: 1, max: 3600 }
    ],
    iotdb_config: [
      { field: 'template_name', label: 'Template Name', type: 'text', placeholder: 'Configuration template name' },
      { field: 'server_id', label: 'Server', type: 'server' }
    ],

    // Control nodes
    condition: [
      { field: 'expression', label: 'Expression', type: 'textarea', placeholder: 'Enter condition expression...' }
    ],
    loop: [
      { field: 'loop_type', label: 'Loop Type', type: 'select', options: [
        { value: 'for', label: 'For Loop' },
        { value: 'while', label: 'While Loop' }
      ]},
      { field: 'iterations', label: 'Iterations', type: 'number', min: 1, max: 10000 },
      { field: 'condition', label: 'Condition', type: 'text', placeholder: 'Loop condition (for while)' }
    ],
    wait: [
      { field: 'condition', label: 'Wait Condition', type: 'textarea', placeholder: 'Condition to wait for...' },
      { field: 'timeout', label: 'Timeout (seconds)', type: 'number', min: 1, max: 3600 },
      { field: 'interval', label: 'Check Interval (seconds)', type: 'number', min: 1, max: 300 }
    ],
    parallel: [
      { field: 'max_concurrent', label: 'Max Concurrent', type: 'number', min: 1, max: 100 }
    ],
    assert: [
      { field: 'assert_type', label: 'Assert Type', type: 'select', options: [
        { value: 'log_contains', label: 'Log Contains' },
        { value: 'file_exists', label: 'File Exists' },
        { value: 'process_running', label: 'Process Running' },
        { value: 'port_open', label: 'Port Open' },
        { value: 'custom', label: 'Custom' }
      ]},
      { field: 'params', label: 'Parameters', type: 'json', placeholder: '{"param": "value"}' },
      { field: 'expected', label: 'Expected Value', type: 'text', placeholder: 'Expected result' }
    ],

    // Result nodes
    report: [
      { field: 'format', label: 'Format', type: 'select', options: [
        { value: 'html', label: 'HTML' },
        { value: 'json', label: 'JSON' },
        { value: 'markdown', label: 'Markdown' }
      ]},
      { field: 'include_logs', label: 'Include Logs', type: 'checkbox' }
    ],
    summary: [],
    notify: [
      { field: 'type', label: 'Notification Type', type: 'select', options: [
        { value: 'email', label: 'Email' },
        { value: 'slack', label: 'Slack' },
        { value: 'webhook', label: 'Webhook' }
      ]},
      { field: 'recipient', label: 'Recipient', type: 'text', placeholder: 'Email address or channel' },
      { field: 'template', label: 'Template', type: 'text', placeholder: 'Message template name' }
    ]
  }

  return definitions[nodeType] || []
}

// Handle JSON input
const handleJsonInput = (field: string, value: string) => {
  try {
    const parsed = JSON.parse(value)
    updateConfig(field, parsed)
  } catch {
    // Invalid JSON - keep the current value
  }
}

// Handle commands array (for iotdb_cli)
const handleCommandsInput = (value: string) => {
  const commands = value.split('\n').filter(cmd => cmd.trim())
  updateConfig('commands', commands)
}

// Get commands as string for display
const getCommandsString = (): string => {
  const commands = getConfigValue('commands')
  if (Array.isArray(commands)) {
    return commands.join('\n')
  }
  return ''
}

// Handle textarea with commands
const isCommandsField = (field: string): boolean => {
  return field === 'commands' && selectedNode.value?.data.nodeType === 'iotdb_cli'
}
</script>

<template>
  <div class="node-config-panel" :class="{ collapsed: isCollapsed }">
    <!-- Toggle Button -->
    <div class="panel-toggle" @click="togglePanel">
      <ElIcon :size="16">
        <ArrowRight v-if="isCollapsed" />
        <ArrowLeft v-else />
      </ElIcon>
    </div>

    <!-- Panel Content -->
    <div v-if="!isCollapsed" class="panel-content">
      <!-- No Selection State -->
      <div v-if="!selectedNode" class="no-selection">
        <ElEmpty description="Select a node to configure" :image-size="80" />
      </div>

      <!-- Node Configuration -->
      <div v-else class="config-container">
        <!-- Node Header -->
        <div class="node-header" :style="{ backgroundColor: nodeTypeColor }">
          <div class="node-type-info">
            <span class="node-type-label">{{ nodeTypeLabel }}</span>
            <span class="node-category">{{ categoryLabels[nodeCategory] }}</span>
          </div>
        </div>

        <!-- Node Name (Editable) -->
        <div class="node-name-section">
          <div class="node-name-label">Node Name</div>
          <div v-if="!isEditingLabel" class="node-name-display">
            <span class="node-name">{{ selectedNode.data.label }}</span>
            <ElButton
              text
              size="small"
              @click="startEditLabel"
            >
              <ElIcon><Edit /></ElIcon>
            </ElButton>
          </div>
          <div v-else class="node-name-edit">
            <ElInput
              v-model="editingLabel"
              size="small"
              placeholder="Enter node name"
              @keyup.enter="saveLabel"
              @keyup.escape="cancelEditLabel"
            />
            <ElButton size="small" type="primary" @click="saveLabel">Save</ElButton>
            <ElButton size="small" @click="cancelEditLabel">Cancel</ElButton>
          </div>
        </div>

        <!-- Configuration Form -->
        <ElForm
          label-position="top"
          class="config-form"
        >
          <ElFormItem
            v-for="field in getFieldDefinitions(selectedNode.data.nodeType as NodeType)"
            :key="field.field"
            :label="field.label"
            class="config-item"
          >
            <!-- Server Dropdown -->
            <template v-if="field.type === 'server'">
              <ElSelect
                :model-value="(getConfigValue(field.field) as number | null | undefined)"
                placeholder="Select server"
                clearable
                style="width: 100%"
                @update:model-value="updateConfig(field.field, $event)"
              >
                <ElOption
                  v-for="option in serverOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </ElSelect>
            </template>

            <!-- Select -->
            <template v-else-if="field.type === 'select'">
              <ElSelect
                :model-value="(getConfigValue(field.field) as string | number | null | undefined)"
                placeholder="Select option"
                style="width: 100%"
                @update:model-value="updateConfig(field.field, $event)"
              >
                <ElOption
                  v-for="option in field.options"
                  :key="String(option.value)"
                  :label="option.label"
                  :value="option.value"
                />
              </ElSelect>
            </template>

            <!-- Checkbox -->
            <template v-else-if="field.type === 'checkbox'">
              <ElCheckbox
                :model-value="Boolean(getConfigValue(field.field))"
                @update:model-value="updateConfig(field.field, $event)"
              >
                {{ field.placeholder || 'Enabled' }}
              </ElCheckbox>
            </template>

            <!-- Number -->
            <template v-else-if="field.type === 'number'">
              <ElInputNumber
                :model-value="(getConfigValue(field.field) as number) || field.min || 0"
                :min="field.min"
                :max="field.max"
                controls-position="right"
                style="width: 100%"
                @update:model-value="updateConfig(field.field, $event)"
              />
            </template>

            <!-- Textarea (Command/Commands) -->
            <template v-else-if="field.type === 'textarea'">
              <ElInput
                v-if="isCommandsField(field.field)"
                :model-value="getCommandsString()"
                type="textarea"
                :rows="4"
                :placeholder="field.placeholder"
                @update:model-value="handleCommandsInput($event)"
              />
              <ElInput
                v-else
                :model-value="(getConfigValue(field.field) as string) || ''"
                type="textarea"
                :rows="4"
                :placeholder="field.placeholder"
                @update:model-value="updateConfig(field.field, $event)"
              />
            </template>

            <!-- JSON Editor -->
            <template v-else-if="field.type === 'json'">
              <ElInput
                :model-value="JSON.stringify(getConfigValue(field.field) || {}, null, 2)"
                type="textarea"
                :rows="4"
                :placeholder="field.placeholder"
                @update:model-value="handleJsonInput(field.field, $event)"
              />
            </template>

            <!-- Text Input -->
            <template v-else>
              <ElInput
                :model-value="(getConfigValue(field.field) as string) || ''"
                :placeholder="field.placeholder"
                @update:model-value="updateConfig(field.field, $event)"
              />
            </template>
          </ElFormItem>
        </ElForm>

        <!-- Node ID Display -->
        <div class="node-id-section">
          <span class="node-id-label">Node ID:</span>
          <span class="node-id-value">{{ selectedNode.id }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.node-config-panel {
  width: 320px;
  height: 100%;
  background: #fff;
  border-left: 1px solid #dcdfe6;
  display: flex;
  flex-direction: column;
  position: relative;
  transition: width 0.3s ease;
}

.node-config-panel.collapsed {
  width: 32px;
}

.panel-toggle {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 32px;
  height: 48px;
  background: #f5f7fa;
  border: 1px solid #dcdfe6;
  border-left: none;
  border-radius: 0 8px 8px 0;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 10;
  transition: background 0.2s;
}

.panel-toggle:hover {
  background: #e6e8eb;
}

.collapsed .panel-toggle {
  left: 0;
}

.panel-content {
  flex: 1;
  overflow: hidden;
  margin-left: 32px;
  display: flex;
  flex-direction: column;
}

.no-selection {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.config-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.node-header {
  padding: 16px;
  color: #fff;
}

.node-type-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.node-type-label {
  font-size: 16px;
  font-weight: 600;
}

.node-category {
  font-size: 12px;
  opacity: 0.8;
}

.node-name-section {
  padding: 12px 16px;
  border-bottom: 1px solid #ebeef5;
}

.node-name-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
}

.node-name-display {
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-name {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  flex: 1;
}

.node-name-edit {
  display: flex;
  gap: 8px;
  align-items: center;
}

.config-form {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.config-item {
  margin-bottom: 16px;
}

.config-item :deep(.el-form-item__label) {
  font-size: 12px;
  color: #606266;
  font-weight: 500;
  padding-bottom: 4px;
}

.node-id-section {
  padding: 12px 16px;
  border-top: 1px solid #ebeef5;
  background: #f5f7fa;
  font-size: 12px;
}

.node-id-label {
  color: #909399;
  margin-right: 8px;
}

.node-id-value {
  color: #606266;
  font-family: monospace;
}
</style>