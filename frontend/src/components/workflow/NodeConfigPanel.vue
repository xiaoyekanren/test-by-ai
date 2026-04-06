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
const nodeDescription = computed(() => nodeConfig.value?.description || '')

const nodeHelpText = computed(() => {
  if (!selectedNode.value) return ''

  if (selectedNode.value.data.nodeType === 'iotdb_config') {
    return 'Use this node to declare the config items that should be written during workflow execution. It does not read the remote file while you are editing the workflow.'
  }

  if (selectedNode.value.data.nodeType === 'iotdb_cluster_deploy') {
    return 'Describe the cluster topology here. During execution, the workflow will upload the package, unpack it on each host, and write role-specific ConfigNode/DataNode settings.'
  }

  if (selectedNode.value.data.nodeType === 'iotdb_cluster_start') {
    return 'This node starts the first ConfigNode, then the remaining ConfigNodes, and finally all DataNodes.'
  }

  if (selectedNode.value.data.nodeType === 'iotdb_cluster_check') {
    return 'This node runs show cluster against the first DataNode and can execute extra validation SQL statements afterward.'
  }

  return ''
})

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
      { field: 'server_id', label: 'Server', type: 'server' },
      { field: 'timeout', label: 'Timeout (seconds)', type: 'number', min: 1, max: 3600 }
    ],
    download: [
      { field: 'remote_path', label: 'Remote Path', type: 'text', placeholder: '/path/to/remote/file' },
      { field: 'local_path', label: 'Local Path', type: 'text', placeholder: '/path/to/local/file' },
      { field: 'server_id', label: 'Server', type: 'server' }
    ],
    config: [
      { field: 'file_path', label: 'File Path', type: 'text', placeholder: '/path/to/config/file' },
      { field: 'config_items', label: 'Config Items', type: 'json', placeholder: '{"key": "value"}' },
      { field: 'backup_before_write', label: 'Backup Before Write', type: 'checkbox', placeholder: 'Create a .bak file before writing' },
      { field: 'server_id', label: 'Server', type: 'server' },
      { field: 'timeout', label: 'Timeout (seconds)', type: 'number', min: 1, max: 600 }
    ],
    log_view: [
      { field: 'file_path', label: 'File Path', type: 'text', placeholder: '/path/to/log/file' },
      { field: 'lines', label: 'Lines', type: 'number', min: 1, max: 10000 },
      { field: 'server_id', label: 'Server', type: 'server' }
    ],

    // IoTDB nodes
    iotdb_deploy: [
      { field: 'server_id', label: 'Server', type: 'server' },
      { field: 'artifact_local_path', label: 'Artifact Local Path', type: 'text', placeholder: '/path/to/apache-iotdb-bin.zip' },
      { field: 'remote_package_path', label: 'Remote Package Path', type: 'text', placeholder: '/tmp/apache-iotdb-bin.zip' },
      { field: 'install_dir', label: 'Install Directory', type: 'text', placeholder: '/opt/iotdb' },
      { field: 'package_type', label: 'Package Type', type: 'select', options: [
        { value: 'auto', label: 'Auto Detect' },
        { value: 'zip', label: 'ZIP' },
        { value: 'tar.gz', label: 'tar.gz' }
      ]},
      { field: 'extract_subdir', label: 'Extract Subdirectory', type: 'text', placeholder: 'Optional inner directory name' },
      { field: 'overwrite', label: 'Overwrite Install Dir', type: 'checkbox', placeholder: 'Delete existing install directory first' },
      { field: 'rpc_port', label: 'RPC Port', type: 'number', min: 1, max: 65535 },
      { field: 'timeout', label: 'Timeout (seconds)', type: 'number', min: 1, max: 3600 }
    ],
    iotdb_start: [
      { field: 'server_id', label: 'Server', type: 'server' },
      { field: 'node_role', label: 'Node Role', type: 'select', options: [
        { value: 'standalone', label: 'Standalone' },
        { value: 'confignode', label: 'ConfigNode' },
        { value: 'datanode', label: 'DataNode' }
      ]},
      { field: 'iotdb_home', label: 'IoTDB Home', type: 'text', placeholder: '/opt/iotdb' },
      { field: 'host', label: 'Host', type: 'text', placeholder: 'Optional, defaults to server host' },
      { field: 'rpc_port', label: 'RPC Port', type: 'number', min: 1, max: 65535 },
      { field: 'wait_port', label: 'Wait Port', type: 'number', min: 1, max: 65535 },
      { field: 'wait_strategy', label: 'Wait Strategy', type: 'select', options: [
        { value: 'port', label: 'Port Check' },
        { value: 'cli', label: 'CLI Check' }
      ]},
      { field: 'timeout_seconds', label: 'Timeout (seconds)', type: 'number', min: 1, max: 600 }
    ],
    iotdb_stop: [
      { field: 'server_id', label: 'Server', type: 'server' },
      { field: 'node_role', label: 'Node Role', type: 'select', options: [
        { value: 'standalone', label: 'Standalone' },
        { value: 'confignode', label: 'ConfigNode' },
        { value: 'datanode', label: 'DataNode' }
      ]},
      { field: 'iotdb_home', label: 'IoTDB Home', type: 'text', placeholder: '/opt/iotdb' },
      { field: 'graceful', label: 'Graceful Shutdown', type: 'checkbox', placeholder: 'Use graceful shutdown script' },
      { field: 'timeout_seconds', label: 'Timeout (seconds)', type: 'number', min: 1, max: 600 }
    ],
    iotdb_cli: [
      { field: 'server_id', label: 'Server', type: 'server' },
      { field: 'iotdb_home', label: 'IoTDB Home', type: 'text', placeholder: '/opt/iotdb' },
      { field: 'host', label: 'Host', type: 'text', placeholder: 'Optional, defaults to server host' },
      { field: 'rpc_port', label: 'RPC Port', type: 'number', min: 1, max: 65535 },
      { field: 'username', label: 'Username', type: 'text', placeholder: 'root' },
      { field: 'password', label: 'Password', type: 'text', placeholder: 'root' },
      { field: 'sql_dialect', label: 'SQL Dialect', type: 'select', options: [
        { value: 'tree', label: 'Tree' },
        { value: 'table', label: 'Table' }
      ]},
      { field: 'sqls', label: 'SQL Statements', type: 'textarea', placeholder: 'Enter one SQL statement per line...' },
      { field: 'timeout_seconds', label: 'Timeout (seconds)', type: 'number', min: 1, max: 3600 }
    ],
    iotdb_config: [
      { field: 'server_id', label: 'Server', type: 'server' },
      { field: 'node_role', label: 'Node Role', type: 'select', options: [
        { value: 'standalone', label: 'Standalone' },
        { value: 'confignode', label: 'ConfigNode' },
        { value: 'datanode', label: 'DataNode' }
      ]},
      { field: 'iotdb_home', label: 'IoTDB Home', type: 'text', placeholder: '/opt/iotdb' },
      { field: 'file_path', label: 'Target Config File', type: 'text', placeholder: 'Optional, defaults to {iotdb_home}/conf/iotdb-system.properties' },
      { field: 'config_items', label: 'Override Items', type: 'json', placeholder: '{"dn_rpc_port": "6667", "dn_rpc_address": "10.0.0.10"}' },
      { field: 'backup_before_write', label: 'Backup Before Write', type: 'checkbox', placeholder: 'Create a backup before applying overrides' },
      { field: 'timeout', label: 'Timeout (seconds)', type: 'number', min: 1, max: 600 }
    ],
    iotdb_cluster_deploy: [
      { field: 'artifact_local_path', label: 'Artifact Local Path', type: 'text', placeholder: '/path/to/apache-iotdb-bin.zip' },
      { field: 'remote_package_path', label: 'Remote Package Path', type: 'text', placeholder: '/tmp/apache-iotdb-cluster-bin.zip' },
      { field: 'install_dir', label: 'Base Install Directory', type: 'text', placeholder: '/opt/iotdb-cluster' },
      { field: 'package_type', label: 'Package Type', type: 'select', options: [
        { value: 'auto', label: 'Auto Detect' },
        { value: 'zip', label: 'ZIP' },
        { value: 'tar.gz', label: 'tar.gz' }
      ]},
      { field: 'extract_subdir', label: 'Extract Subdirectory', type: 'text', placeholder: 'Optional inner directory name' },
      { field: 'overwrite', label: 'Overwrite Install Dir', type: 'checkbox', placeholder: 'Delete existing install directory first' },
      { field: 'cluster_name', label: 'Cluster Name', type: 'text', placeholder: 'defaultCluster' },
      { field: 'config_nodes', label: 'Config Nodes', type: 'json', placeholder: '[{"server_id":1,"host":"10.0.0.1","install_dir":"/opt/iotdb-cn-1","cn_internal_port":10710,"cn_consensus_port":10720}]' },
      { field: 'data_nodes', label: 'Data Nodes', type: 'json', placeholder: '[{"server_id":2,"host":"10.0.0.2","install_dir":"/opt/iotdb-dn-1","dn_rpc_port":6667,"dn_internal_port":10730}]' },
      { field: 'common_config', label: 'Common Config', type: 'json', placeholder: '{"schema_replication_factor":"1","data_replication_factor":"1"}' },
      { field: 'timeout', label: 'Timeout (seconds)', type: 'number', min: 1, max: 3600 }
    ],
    iotdb_cluster_start: [
      { field: 'cluster_name', label: 'Cluster Name', type: 'text', placeholder: 'Inherited from deploy node' },
      { field: 'config_nodes', label: 'Config Nodes', type: 'json', placeholder: 'Inherited from deploy node' },
      { field: 'data_nodes', label: 'Data Nodes', type: 'json', placeholder: 'Inherited from deploy node' },
      { field: 'wait_strategy', label: 'Wait Strategy', type: 'select', options: [
        { value: 'port', label: 'Port Check' },
        { value: 'cli', label: 'CLI Check (DataNode only)' }
      ]},
      { field: 'timeout_seconds', label: 'Timeout (seconds)', type: 'number', min: 1, max: 1800 }
    ],
    iotdb_cluster_check: [
      { field: 'cluster_name', label: 'Cluster Name', type: 'text', placeholder: 'Inherited from deploy/start node' },
      { field: 'config_nodes', label: 'Config Nodes', type: 'json', placeholder: 'Inherited from deploy/start node' },
      { field: 'data_nodes', label: 'Data Nodes', type: 'json', placeholder: 'Inherited from deploy/start node' },
      { field: 'username', label: 'Username', type: 'text', placeholder: 'root' },
      { field: 'password', label: 'Password', type: 'text', placeholder: 'root' },
      { field: 'sql_dialect', label: 'SQL Dialect', type: 'select', options: [
        { value: 'tree', label: 'Tree' },
        { value: 'table', label: 'Table' }
      ]},
      { field: 'validation_sqls', label: 'Validation SQLs', type: 'textarea', placeholder: 'Optional extra SQL statements, one per line...' },
      { field: 'timeout_seconds', label: 'Timeout (seconds)', type: 'number', min: 1, max: 1800 }
    ],
    iotdb_cluster_stop: [
      { field: 'cluster_name', label: 'Cluster Name', type: 'text', placeholder: 'Inherited from deploy/start node' },
      { field: 'config_nodes', label: 'Config Nodes', type: 'json', placeholder: 'Inherited from deploy/start node' },
      { field: 'data_nodes', label: 'Data Nodes', type: 'json', placeholder: 'Inherited from deploy/start node' },
      { field: 'graceful', label: 'Graceful Shutdown', type: 'checkbox', placeholder: 'Stop nodes gracefully before forcing' },
      { field: 'timeout_seconds', label: 'Timeout (seconds)', type: 'number', min: 1, max: 1800 }
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
const handleListInput = (field: string, value: string) => {
  const items = value.split('\n').filter(item => item.trim())
  updateConfig(field, items)
}

// Get list field as string for display
const getListFieldString = (field: string): string => {
  const value = getConfigValue(field)
  if (Array.isArray(value)) {
    return value.join('\n')
  }
  return ''
}

// Handle textarea with line-based array fields
const isListField = (field: string): boolean => {
  return ['commands', 'sqls', 'validation_sqls'].includes(field)
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
            <span v-if="nodeDescription" class="node-description">{{ nodeDescription }}</span>
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
          <div v-if="nodeHelpText" class="node-help">
            {{ nodeHelpText }}
          </div>
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
                v-if="isListField(field.field)"
                :model-value="getListFieldString(field.field)"
                type="textarea"
                :rows="4"
                :placeholder="field.placeholder"
                @update:model-value="handleListInput(field.field, $event)"
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

.node-description {
  font-size: 12px;
  line-height: 1.4;
  opacity: 0.92;
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

.node-help {
  margin-bottom: 16px;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.5;
  color: #606266;
  background: #f5f7fa;
  border: 1px solid #ebeef5;
  border-radius: 6px;
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
