import { NODE_CONFIGS } from '@/types'
import type { NodeType } from '@/types'

export const TOP_LEVEL_SERVER_NODE_TYPES = new Set<NodeType>(
  Object.entries(NODE_CONFIGS)
    .filter(([, config]) => Object.prototype.hasOwnProperty.call(config.defaultConfig, 'server_id'))
    .map(([nodeType]) => nodeType as NodeType)
)

export const nodeUsesTopLevelServer = (nodeType: NodeType) => TOP_LEVEL_SERVER_NODE_TYPES.has(nodeType)
