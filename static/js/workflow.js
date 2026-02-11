class WorkflowEditor {
    constructor() {
        this.nodes = []
        this.connections = []
        this.nextNodeId = 1
        this.isConnecting = false
        this.connectionStart = null
        this.currentCommandNode = null
        this.currentUploadNode = null
        this.commandInput = null
        this.commandDescInput = null
        this.commandRefInput = null
        this.uploadFileInput = null
        this.remotePathInput = null
        this.uploadRefInput = null
        this.scale = 1
        this.currentWorkflowId = null
        this.currentWorkflowName = null
        this.globalVars = {} // 本地缓存全局变量
        
        // 多选与剪贴板状态
        this.selectedNodes = new Set()
        this.isSelecting = false
        this.selectionStart = null
        this.clipboard = null
        
        this.init()
    }

    truncateToIpLength(name) {
        if (typeof name !== 'string') return ''
        const max = 15
        const arr = Array.from(name)
        if (arr.length <= max) return name
        return arr.slice(0, max - 3).join('') + '...'
    }

    init() {
        this.canvas = document.getElementById('canvas')
        this.canvasContent = document.getElementById('canvas-content')
        this.connectionsLayer = document.getElementById('connections')
        this.serverList = document.getElementById('server-list')
        this.consoleOutput = null 
        this.loadServers()
        this.loadGlobalVars() // 加载全局变量
        this.updatePanelLayout() 
        this.setupDragAndDrop()
        this.setupCanvasEvents()
        this.setupKeyboardShortcuts()
        this.setupModals()
        this.setupButtons()
        this.setupPanelDrag()
        this.setupSplitter()
        this.setupZoom()
        
        const hint = document.createElement('div')
        hint.className = 'drop-hint'
        hint.textContent = ''
        this.canvasContent.appendChild(hint)
        
        // 绑定新按钮
        document.getElementById('save-workflow-btn').addEventListener('click', () => this.handleSave())
        document.getElementById('save-as-workflow-btn').addEventListener('click', () => this.openSaveModal())
        document.getElementById('load-workflow-btn').addEventListener('click', () => this.openLoadModal())
    }

    setupZoom() {
        const zoomIn = document.getElementById('zoom-in')
        const zoomOut = document.getElementById('zoom-out')
        const zoomReset = document.getElementById('zoom-reset')
        const zoomLevel = document.getElementById('zoom-level')

        const updateZoom = () => {
            this.canvasContent.style.transform = `scale(${this.scale})`
            zoomLevel.textContent = `${Math.round(this.scale * 100)}%`
        }

        zoomIn.addEventListener('click', () => {
            if (this.scale < 3) {
                this.scale += 0.1
                updateZoom()
            }
        })

        zoomOut.addEventListener('click', () => {
            if (this.scale > 0.5) {
                this.scale -= 0.1
                updateZoom()
            }
        })

        zoomReset.addEventListener('click', () => {
            this.scale = 1
            updateZoom()
        })
        
        // 支持滚轮缩放
        this.canvas.addEventListener('wheel', e => {
            if (e.ctrlKey || e.metaKey) {
                e.preventDefault()
                const delta = e.deltaY > 0 ? -0.1 : 0.1
                const newScale = Math.max(0.5, Math.min(3, this.scale + delta))
                if (newScale !== this.scale) {
                    this.scale = newScale
                    updateZoom()
                }
            }
        })
    }

    setupSplitter() {
        const splitter = document.getElementById('workspace-splitter')
        const resultPanel = document.querySelector('.result-panel')
        const workspace = document.querySelector('.workspace')
        
        let isResizing = false
        let startY, startHeight
        
        splitter.addEventListener('mousedown', e => {
            e.preventDefault()
            isResizing = true
            startY = e.clientY
            startHeight = parseInt(getComputedStyle(resultPanel).height, 10)
            splitter.classList.add('resizing')
            document.body.style.cursor = 'row-resize'
        })
        
        document.addEventListener('mousemove', e => {
            if (!isResizing) return
            e.preventDefault()
            
            // 向上拖动增加高度，向下减少（因为面板在底部）
            const dy = startY - e.clientY
            let newHeight = startHeight + dy
            
            // 限制高度
            const maxH = workspace.clientHeight - 100 // 留给canvas至少100px
            if (newHeight < 100) newHeight = 100
            if (newHeight > maxH) newHeight = maxH
            
            resultPanel.style.height = `${newHeight}px`
        })
        
        document.addEventListener('mouseup', () => {
            if (isResizing) {
                isResizing = false
                splitter.classList.remove('resizing')
                document.body.style.cursor = ''
            }
        })
    }

    setupPanelDrag() {
        const panel = document.querySelector('.component-panel')
        const header = panel.querySelector('.panel-header')
        
        let isDragging = false
        let startX, startY, initialLeft, initialTop

        header.addEventListener('mousedown', e => {
            e.preventDefault()
            isDragging = true
            startX = e.clientX
            startY = e.clientY
            const style = window.getComputedStyle(panel)
            initialLeft = parseInt(style.left, 10)
            initialTop = parseInt(style.top, 10)
            panel.style.cursor = 'move'
        })

        document.addEventListener('mousemove', e => {
            if (!isDragging) return
            e.preventDefault()
            const dx = e.clientX - startX
            const dy = e.clientY - startY
            
            let newLeft = initialLeft + dx
            let newTop = initialTop + dy
            
            // 边界限制
            const container = document.getElementById('canvas')
            const rect = container.getBoundingClientRect()
            const panelRect = panel.getBoundingClientRect()
            
            if (newLeft < 0) newLeft = 0
            if (newLeft + panelRect.width > rect.width) newLeft = rect.width - panelRect.width
            if (newTop < 0) newTop = 0
            if (newTop + panelRect.height > rect.height) newTop = rect.height - panelRect.height
            
            panel.style.left = `${newLeft}px`
            panel.style.top = `${newTop}px`
        })

        document.addEventListener('mouseup', () => {
            isDragging = false
            panel.style.cursor = ''
        })
    }

    updatePanelLayout() {
        const containers = document.querySelectorAll('.draggable-items')
        const serverList = document.getElementById('server-list')
        const serverCount = serverList ? serverList.children.length : 0
        const shouldBeMultiColumn = serverCount > 5
        
        containers.forEach(container => {
            if (shouldBeMultiColumn) {
                container.classList.add('multi-column')
            } else {
                container.classList.remove('multi-column')
            }
        })
    }

    async loadServers() {
        const res = await ServerAPI.listServers()
        if (res.status === 'success' && Array.isArray(res.data)) {
            this.serverList.innerHTML = '' 
            this.allServers = res.data // 保存所有服务器数据供后续使用

            // 1. 按 Tag 分组
            const tagGroups = {}
            const noTagServers = []

            res.data.forEach(s => {
                if (s.tags && s.tags.trim()) {
                    // 支持多个 tag，以逗号分隔
                    const tags = s.tags.split(/[,，]/).map(t => t.trim()).filter(t => t)
                    tags.forEach(tag => {
                        if (!tagGroups[tag]) tagGroups[tag] = []
                        tagGroups[tag].push(s)
                    })
                    // 如果没有任何有效 tag，也归为无标签
                    if (tags.length === 0) noTagServers.push(s)
                } else {
                    noTagServers.push(s)
                }
            })

            // 2. 渲染服务器组 (Tag)
            Object.keys(tagGroups).sort().forEach(tag => {
                const count = tagGroups[tag].length
                const item = document.createElement('div')
                item.className = 'draggable-item group-item'
                item.setAttribute('draggable', 'true')
                item.dataset.type = 'server-group'
                item.dataset.tag = tag
                item.style.backgroundColor = '#f0f9ff'
                item.style.borderColor = '#bae6fd'
                item.innerHTML = `<span class="icon">🏷️</span><span class="server-name" title="服务器组: ${tag}">组: ${tag} (${count})</span>`
                this.serverList.appendChild(item)
            })

            // 分割线 (如果既有组又有单独服务器)
            if (Object.keys(tagGroups).length > 0 && noTagServers.length > 0) {
                const divider = document.createElement('div')
                divider.style.height = '1px'
                divider.style.backgroundColor = '#eee'
                divider.style.margin = '8px 0'
                divider.style.width = '100%'
                this.serverList.appendChild(divider)
            }

            // 3. 渲染所有服务器 (平铺列表)
            res.data.forEach(s => {
                const item = document.createElement('div')
                item.className = 'draggable-item'
                item.setAttribute('draggable', 'true')
                item.dataset.type = 'server'
                item.dataset.serverId = s.id
                item.dataset.serverName = s.name
                item.dataset.serverHost = s.host
                const display = this.truncateToIpLength(s.name)
                // 如果有 tag，显示一个小标记
                const tagBadge = s.tags ? `<span style="font-size:9px;color:#999;margin-left:auto;">${s.tags}</span>` : ''
                item.innerHTML = `<span class="icon">🖥️</span><span class="server-name" title="${s.name}">${display}</span>${tagBadge}`
                this.serverList.appendChild(item)
            })
            
            this.updatePanelLayout()
        }
    }

    setupDragAndDrop() {
        document.addEventListener('dragstart', e => {
            const item = e.target.closest('.draggable-item')
            if (!item) return
            e.dataTransfer.setData('type', item.dataset.type)
            if (item.dataset.type === 'server-group') {
                e.dataTransfer.setData('tag', item.dataset.tag)
            } else {
                e.dataTransfer.setData('serverId', item.dataset.serverId || '')
                e.dataTransfer.setData('serverName', item.dataset.serverName || '')
                e.dataTransfer.setData('serverHost', item.dataset.serverHost || '')
            }
        })
        this.canvas.addEventListener('dragover', e => {
            e.preventDefault()
            this.canvas.classList.add('drag-over')
        })
        this.canvas.addEventListener('dragleave', () => {
            this.canvas.classList.remove('drag-over')
        })
        this.canvas.addEventListener('drop', e => {
            e.preventDefault()
            this.canvas.classList.remove('drag-over')
            const type = e.dataTransfer.getData('type')
            const rect = this.canvasContent.getBoundingClientRect()
            const x = (e.clientX - rect.left - 100 * this.scale) / this.scale
            const y = (e.clientY - rect.top - 40 * this.scale) / this.scale

            if (type === 'server-group') {
                const tag = e.dataTransfer.getData('tag')
                this.createGroupNodes(tag, x, y)
            } else {
                const serverId = e.dataTransfer.getData('serverId')
                const serverName = e.dataTransfer.getData('serverName')
                const serverHost = e.dataTransfer.getData('serverHost')
                this.createNode(type, x, y, { serverId, serverName, serverHost })
            }
        })
    }

    createGroupNodes(tag, startX, startY) {
        if (!this.allServers) return
        
        // 找到该组所有服务器
        const servers = this.allServers.filter(s => {
            if (!s.tags) return false
            const tags = s.tags.split(/[,，]/).map(t => t.trim())
            return tags.includes(tag)
        })
        
        if (servers.length === 0) {
            this.addSystemMessage(`组 ${tag} 中没有服务器`, 'warning')
            return
        }
        
        // 级联创建节点（而不是创建单个组节点）
        servers.forEach((s, index) => {
            // 每个节点错开一点位置
            const x = startX + (index % 5) * 20
            const y = startY + index * 50
            this.createNode('server', x, y, {
                serverId: s.id,
                serverName: s.name,
                serverHost: s.host
            })
        })
        
        this.addSystemMessage(`已添加组 "${tag}" 中的 ${servers.length} 台服务器`, 'success')
    }
    
    // createGroupNodes 已被废弃，替换为单个节点的创建逻辑
    
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', e => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return

            if (e.key === 'Delete' || e.key === 'Backspace') {
                this.deleteSelection()
            }

            if (e.ctrlKey || e.metaKey) {
                if (e.key === 'c') {
                    this.copySelection()
                } else if (e.key === 'v') {
                    this.pasteSelection()
                } else if (e.key === 'x') {
                    this.cutSelection()
                } else if (e.key === 'a') {
                    e.preventDefault()
                    this.selectAll()
                }
            }
        })
    }

    clearSelection() {
        this.selectedNodes.forEach(id => {
            const el = this.canvasContent.querySelector(`.canvas-node[data-id="${id}"]`)
            if (el) el.classList.remove('selected')
        })
        this.selectedNodes.clear()
    }

    selectAll() {
        this.nodes.forEach(n => {
            this.selectedNodes.add(n.id)
            const el = this.canvasContent.querySelector(`.canvas-node[data-id="${n.id}"]`)
            if (el) el.classList.add('selected')
        })
    }

    copySelection() {
        if (this.selectedNodes.size === 0) return
        
        const nodesToCopy = []
        this.selectedNodes.forEach(id => {
            const node = this.nodes.find(n => n.id === id)
            if (node) nodesToCopy.push(JSON.parse(JSON.stringify(node)))
        })
        
        const connectionsToCopy = this.connections.filter(c => 
            this.selectedNodes.has(c.from) && this.selectedNodes.has(c.to)
        )
        
        this.clipboard = {
            nodes: nodesToCopy,
            connections: connectionsToCopy
        }
        
        this.addSystemMessage(`已复制 ${nodesToCopy.length} 个节点`, 'info')
    }

    cutSelection() {
        this.copySelection()
        this.deleteSelection()
    }

    deleteSelection() {
        if (this.selectedNodes.size === 0) return
        
        const count = this.selectedNodes.size
        Array.from(this.selectedNodes).forEach(id => {
            this.deleteNode(id)
        })
        this.selectedNodes.clear()
        this.addSystemMessage(`已删除 ${count} 个节点`, 'info')
    }
    
    pasteSelection() {
        if (!this.clipboard || this.clipboard.nodes.length === 0) return
        
        this.clearSelection()
        
        const offset = 30
        const idMap = new Map()
        
        this.clipboard.nodes.forEach(n => {
            const newId = this.nextNodeId
            idMap.set(n.id, newId)
            
            const newNodeData = { ...n, serverId: n.serverId, id: newId, x: n.x + offset, y: n.y + offset }
            // 清理一些不应保留的状态
            if (newNodeData.status) delete newNodeData.status
            
            this.createNode(newNodeData.type, newNodeData.x, newNodeData.y, newNodeData)
            
            this.selectedNodes.add(newId)
            const el = this.canvasContent.querySelector(`.canvas-node[data-id="${newId}"]`)
            if (el) el.classList.add('selected')
        })
        
        this.clipboard.connections.forEach(c => {
            const newFrom = idMap.get(c.from)
            const newTo = idMap.get(c.to)
            if (newFrom && newTo) {
                this.createConnection(newFrom, newTo, c.type)
            }
        })
        
        this.addSystemMessage(`已粘贴 ${this.clipboard.nodes.length} 个节点`, 'success')
    }

    setupCanvasEvents() {
        this.canvas.addEventListener('mousedown', e => {
            // 1. 连线逻辑 (优先)
            const out = e.target.closest('.connector.output')
            const inConn = e.target.closest('.connector.input')
            
            if (out || inConn) {
                e.preventDefault()
                e.stopPropagation()
                this.isConnecting = true
                if (out) {
                    this.connectionSource = { node: out.parentElement, type: 'output' }
                } else {
                    this.connectionSource = { node: inConn.parentElement, type: 'input' }
                }
                
                const tempLine = document.createElementNS('http://www.w3.org/2000/svg', 'path')
                tempLine.id = 'temp-connection'
                tempLine.setAttribute('stroke', '#667eea')
                tempLine.setAttribute('stroke-dasharray', '5,5')
                tempLine.setAttribute('fill', 'transparent')
                tempLine.setAttribute('stroke-width', '2')
                tempLine.setAttribute('style', 'pointer-events: none;')
                this.connectionsLayer.appendChild(tempLine)
                return
            }
            
            // 2. 节点选择逻辑
            const node = e.target.closest('.canvas-node')
            if (node) {
                const nodeId = parseInt(node.dataset.id)
                
                if (e.target.closest('.node-delete')) return 

                // 多选逻辑
                if (e.ctrlKey || e.metaKey || e.shiftKey) {
                    if (this.selectedNodes.has(nodeId)) {
                        this.selectedNodes.delete(nodeId)
                        node.classList.remove('selected')
                    } else {
                        this.selectedNodes.add(nodeId)
                        node.classList.add('selected')
                    }
                } else {
                    if (!this.selectedNodes.has(nodeId)) {
                        this.clearSelection()
                        this.selectedNodes.add(nodeId)
                        node.classList.add('selected')
                    }
                }

                this.isDragging = true
                this.draggedNode = node 
                
                this.initialNodePositions = new Map()
                this.selectedNodes.forEach(id => {
                    const n = this.nodes.find(x => x.id === id)
                    if (n) {
                        this.initialNodePositions.set(id, { x: n.x, y: n.y })
                    }
                })
                
                const rect = node.getBoundingClientRect()
                this.dragOffset = {
                    x: e.clientX - rect.left,
                    y: e.clientY - rect.top
                }
            } else {
                // 3. 空白处点击 -> 开始框选
                if (e.target === this.canvas || e.target === this.canvasContent || e.target === this.connectionsLayer) {
                     if (!e.ctrlKey && !e.metaKey && !e.shiftKey) {
                        this.clearSelection()
                    }
                    
                    this.isSelecting = true
                    const rect = this.canvasContent.getBoundingClientRect()
                    this.selectionStart = {
                        x: (e.clientX - rect.left) / this.scale,
                        y: (e.clientY - rect.top) / this.scale
                    }
                    
                    this.selectionBox = document.createElement('div')
                    this.selectionBox.className = 'selection-box'
                    this.selectionBox.style.left = this.selectionStart.x + 'px'
                    this.selectionBox.style.top = this.selectionStart.y + 'px'
                    this.selectionBox.style.width = '0px'
                    this.selectionBox.style.height = '0px'
                    this.canvasContent.appendChild(this.selectionBox)
                }
            }
        })

        document.addEventListener('mousemove', e => {
            if (this.isConnecting) {
                e.preventDefault()
                const svg = this.connectionsLayer
                const tempLine = svg.querySelector('#temp-connection')
                if (!tempLine) return

                const cr = this.canvasContent.getBoundingClientRect()
                let x1, y1, x2, y2

                if (this.connectionSource.type === 'output') {
                    const fr = this.connectionSource.node.getBoundingClientRect()
                    x1 = (fr.right - cr.left) / this.scale
                    y1 = (fr.top + fr.height / 2 - cr.top) / this.scale
                    x2 = (e.clientX - cr.left) / this.scale
                    y2 = (e.clientY - cr.top) / this.scale
                } else {
                    const fr = this.connectionSource.node.getBoundingClientRect()
                    x1 = (e.clientX - cr.left) / this.scale
                    y1 = (e.clientY - cr.top) / this.scale
                    x2 = (fr.left - cr.left) / this.scale
                    y2 = (fr.top + fr.height / 2 - cr.top) / this.scale
                }
                
                tempLine.setAttribute('d', `M ${x1} ${y1} C ${(x1+x2)/2} ${y1}, ${(x1+x2)/2} ${y2}, ${x2} ${y2}`)
                return
            }
            
            if (this.isDragging && this.initialNodePositions) {
                e.preventDefault()
                
                const canvasRect = this.canvasContent.getBoundingClientRect()
                const currentX = (e.clientX - canvasRect.left) / this.scale - this.dragOffset.x
                const currentY = (e.clientY - canvasRect.top) / this.scale - this.dragOffset.y
                
                const mainNodeId = parseInt(this.draggedNode.dataset.id)
                const mainInitial = this.initialNodePositions.get(mainNodeId)
                
                if (mainInitial) {
                    const deltaX = currentX - mainInitial.x
                    const deltaY = currentY - mainInitial.y
                    
                    this.selectedNodes.forEach(id => {
                        const initialPos = this.initialNodePositions.get(id)
                        if (!initialPos) return
                        
                        const nodeData = this.nodes.find(n => n.id === id)
                        if (nodeData) {
                            let newX = initialPos.x + deltaX
                            let newY = initialPos.y + deltaY
                            
                            newX = Math.max(0, newX)
                            newY = Math.max(0, newY)
                            
                            nodeData.x = newX
                            nodeData.y = newY
                            
                            const el = this.canvasContent.querySelector(`.canvas-node[data-id="${id}"]`)
                            if (el) {
                                el.style.left = newX + 'px'
                                el.style.top = newY + 'px'
                            }
                        }
                    })
                    this.updateConnections()
                }
            }

            if (this.isSelecting) {
                e.preventDefault()
                const rect = this.canvasContent.getBoundingClientRect()
                const currentX = (e.clientX - rect.left) / this.scale
                const currentY = (e.clientY - rect.top) / this.scale
                
                const x = Math.min(this.selectionStart.x, currentX)
                const y = Math.min(this.selectionStart.y, currentY)
                const width = Math.abs(currentX - this.selectionStart.x)
                const height = Math.abs(currentY - this.selectionStart.y)
                
                this.selectionBox.style.left = x + 'px'
                this.selectionBox.style.top = y + 'px'
                this.selectionBox.style.width = width + 'px'
                this.selectionBox.style.height = height + 'px'
                
                this.nodes.forEach(n => {
                    const nodeEl = this.canvasContent.querySelector(`.canvas-node[data-id="${n.id}"]`)
                    if (!nodeEl) return
                    
                    const nodeW = nodeEl.offsetWidth
                    const nodeH = nodeEl.offsetHeight
                    
                    const intersect = (x < n.x + nodeW && x + width > n.x &&
                                     y < n.y + nodeH && y + height > n.y)
                    
                    if (intersect) {
                        if (!this.selectedNodes.has(n.id)) {
                            this.selectedNodes.add(n.id)
                            nodeEl.classList.add('selected')
                        }
                    } else if (!e.shiftKey && !e.ctrlKey) {
                        if (this.selectedNodes.has(n.id)) {
                             this.selectedNodes.delete(n.id)
                             nodeEl.classList.remove('selected')
                        }
                    }
                })
            }
        })

        document.addEventListener('mouseup', e => {
            if (this.isDragging) {
                this.isDragging = false
                this.draggedNode = null
                this.initialNodePositions = null
            }

            if (this.isSelecting) {
                this.isSelecting = false
                if (this.selectionBox) {
                    this.selectionBox.remove()
                    this.selectionBox = null
                }
            }

            if (!this.isConnecting) return
            
            const tempLine = this.connectionsLayer.querySelector('#temp-connection')
            if (tempLine) tempLine.remove()

            const out = e.target.closest('.connector.output')
            const inConn = e.target.closest('.connector.input')

            let fromId, toId

            if (this.connectionSource.type === 'output' && inConn) {
                fromId = this.connectionSource.node.dataset.id
                toId = inConn.parentElement.dataset.id
            } else if (this.connectionSource.type === 'input' && out) {
                fromId = out.parentElement.dataset.id
                toId = this.connectionSource.node.dataset.id
            }

            if (fromId && toId && fromId !== toId) {
                this.createConnection(fromId, toId)
            }
            
            this.isConnecting = false
            this.connectionSource = null
        })
    }

    setupModals() {
        const cmdModal = document.getElementById('command-modal')
        const uploadModal = document.getElementById('upload-modal')
        const saveModal = document.getElementById('save-workflow-modal')
        const loadModal = document.getElementById('load-workflow-modal')
        
        this.commandInput = document.getElementById('command-input')
        this.commandDescInput = document.getElementById('command-description')
        this.commandRefInput = document.getElementById('command-ref-name')
        this.uploadFileInput = document.getElementById('upload-file')
        this.remotePathInput = document.getElementById('remote-path')
        this.uploadRefInput = document.getElementById('upload-ref-name')
        
        // 连线弹窗
        this.connPopover = document.getElementById('connection-popover')
        this.connTypeSelect = document.getElementById('conn-type-select')
        
        this.setupGlobalVars() // 初始化全局变量弹窗事件

        document.querySelectorAll('.modal .close').forEach(el => {
            el.addEventListener('click', e => e.target.closest('.modal').style.display = 'none')
        })
        
        document.getElementById('cancel-command').addEventListener('click', () => cmdModal.style.display = 'none')
        document.getElementById('cancel-upload').addEventListener('click', () => uploadModal.style.display = 'none')
        document.getElementById('cancel-save-wf').addEventListener('click', () => saveModal.style.display = 'none')
        document.getElementById('cancel-load-wf').addEventListener('click', () => loadModal.style.display = 'none')
        
        // 连线弹窗事件
        this.connTypeSelect.addEventListener('change', () => {
            if (this.selectedConnection) {
                this.selectedConnection.type = this.connTypeSelect.value
                this.updateConnections()
                this.selectConnection(this.selectedConnection)
            }
        })
        
        document.getElementById('delete-conn-btn').addEventListener('click', () => {
            if (this.selectedConnection) {
                if (confirm('确定要删除这条连线吗？')) {
                    this.deleteConnection(this.selectedConnection.from, this.selectedConnection.to)
                    this.hidePopover()
                }
            }
        })
        
        // 点击空白处关闭弹窗
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.connection-path') && !e.target.closest('.connection-popover')) {
                this.hidePopover()
            }
        })
        
        document.getElementById('save-command').addEventListener('click', () => {
            if (!this.currentCommandNode) return
            const id = parseInt(this.currentCommandNode.dataset.id)
            const node = this.nodes.find(n => n.id === id)
            node.command = this.commandInput.value || ''
            node.description = this.commandDescInput.value || ''
            node.refName = this.commandRefInput.value || ''
            this.currentCommandNode.querySelector('.node-content').textContent = node.command || '未设置'
            cmdModal.style.display = 'none'
        })
        
        document.getElementById('save-upload').addEventListener('click', () => {
            if (!this.currentUploadNode) return
            const id = parseInt(this.currentUploadNode.dataset.id)
            const node = this.nodes.find(n => n.id === id)
            const newFile = this.uploadFileInput.files[0]
            const file = newFile || node.upload?.file || null
            const remote = this.remotePathInput.value || ''
            node.upload = { file, remote }
            node.refName = this.uploadRefInput.value || ''
            this.currentUploadNode.querySelector('.node-content').textContent = remote || '未设置'
            uploadModal.style.display = 'none'
        })
        
        document.getElementById('confirm-save-wf').addEventListener('click', () => this.saveWorkflow())
    }

    setupGlobalVars() {
        const modal = document.getElementById('global-vars-modal')
        const btn = document.getElementById('global-vars-btn')
        const closeBtn = document.getElementById('close-global-vars')
        
        btn.addEventListener('click', () => {
            modal.style.display = 'block'
            this.loadGlobalVars(true) // 重新加载并渲染列表
        })
        
        closeBtn.addEventListener('click', () => modal.style.display = 'none')
        
        // 添加变量
        document.getElementById('add-global-var-btn').addEventListener('click', () => this.saveGlobalVar())
    }

    async loadGlobalVars(render = false) {
        try {
            const res = await ServerAPI.request('/globals')
            if (res.status === 'success') {
                this.globalVars = {}
                res.data.forEach(v => {
                    this.globalVars[v.key] = v.value
                })
                
                if (render) {
                    this.renderGlobalVars(res.data)
                }
            }
        } catch (e) {
            console.error('Failed to load global vars:', e)
        }
    }

    renderGlobalVars(vars) {
        const container = document.getElementById('global-vars-list')
        container.innerHTML = ''
        
        if (vars.length === 0) {
            container.innerHTML = '<div style="padding:10px;color:#999;text-align:center;">暂无全局变量</div>'
            return
        }
        
        vars.forEach(v => {
            const item = document.createElement('div')
            item.className = 'var-item'
            item.innerHTML = `
                <span class="var-key" style="width: 30%;" title="${this.escapeHtml(v.key)}">${this.escapeHtml(v.key)}</span>
                <span class="var-value" style="width: 40%;" title="${this.escapeHtml(v.value)}">${this.escapeHtml(v.value)}</span>
                <span class="var-desc" style="width: 20%;" title="${this.escapeHtml(v.description || '')}">${this.escapeHtml(v.description || '-')}</span>
                <div style="width: 10%; display: flex; justify-content: flex-end;">
                    <button class="node-delete" title="删除">&times;</button>
                </div>
            `
            item.querySelector('.node-delete').addEventListener('click', () => {
                if (confirm(`确定要删除变量 "${v.key}" 吗？`)) {
                    this.deleteGlobalVar(v.key)
                }
            })
            container.appendChild(item)
        })
    }

    async saveGlobalVar() {
        const keyInput = document.getElementById('new-var-key')
        const valueInput = document.getElementById('new-var-value')
        const descInput = document.getElementById('new-var-desc')
        
        const key = keyInput.value.trim()
        const value = valueInput.value.trim()
        const desc = descInput.value.trim()
        
        if (!key) {
            alert('变量名不能为空')
            return
        }
        
        try {
            const res = await ServerAPI.request('/globals', {
                method: 'POST',
                body: JSON.stringify({ key, value, description: desc })
            })
            
            if (res.status === 'success') {
                keyInput.value = ''
                valueInput.value = ''
                descInput.value = ''
                this.loadGlobalVars(true)
                this.addSystemMessage(`全局变量 ${key} 已保存`, 'success')
            } else {
                alert('保存失败: ' + res.message)
            }
        } catch (e) {
            alert('保存出错: ' + e.message)
        }
    }

    async deleteGlobalVar(key) {
        try {
            const res = await ServerAPI.request(`/globals/${key}`, { method: 'DELETE' })
            if (res.status === 'success') {
                this.loadGlobalVars(true)
                this.addSystemMessage(`全局变量 ${key} 已删除`, 'success')
            } else {
                alert('删除失败: ' + res.message)
            }
        } catch (e) {
            alert('删除出错: ' + e.message)
        }
    }

    setupButtons() {
        document.getElementById('clear-btn').addEventListener('click', () => this.clearCanvas())
        document.getElementById('run-btn').addEventListener('click', () => this.runWorkflow())
    }

    createNode(type, x, y, data = {}) {
        const node = document.createElement('div')
        node.className = 'canvas-node'
        node.dataset.id = this.nextNodeId
        node.style.left = x + 'px'
        node.style.top = y + 'px'
        const nodeData = { id: this.nextNodeId, type, x, y }
        let title = ''
        let content = ''
        let typeLabel = ''
        switch (type) {
            case 'server':
                typeLabel = '服务器'
                title = data.serverName || '服务器'
                content = ''
                nodeData.serverId = parseInt(data.serverId || '0')
                nodeData.serverName = data.serverName
                nodeData.serverHost = data.serverHost
                break
            case 'upload':
                typeLabel = '上传文件'
                title = '上传文件'
                content = '双击设置文件与路径'
                
                // 恢复数据
                if (data.upload) nodeData.upload = data.upload
                if (data.refName) nodeData.refName = data.refName
                if (nodeData.upload && nodeData.upload.remote) content = nodeData.upload.remote
                
                node.addEventListener('dblclick', () => {
                    this.currentUploadNode = node
                    const id = parseInt(node.dataset.id)
                    const nodeData = this.nodes.find(n => n.id === id)
                    
                    this.uploadFileInput.value = ''
                    this.remotePathInput.value = nodeData.upload?.remote || ''
                    this.uploadRefInput.value = nodeData.refName || ''
                    
                    const fileInfo = document.getElementById('current-file-info')
                    if (nodeData.upload?.file) {
                        fileInfo.textContent = `当前已选文件: ${nodeData.upload.file.name}`
                    } else {
                        fileInfo.textContent = '当前未选择文件'
                    }
                    
                    document.getElementById('upload-modal').style.display = 'block'
                })
                break
            case 'command':
                typeLabel = '执行命令'
                title = '执行命令'
                content = '双击编辑命令'
                
                // 恢复数据
                if (data.command) nodeData.command = data.command
                if (data.description) nodeData.description = data.description
                if (data.refName) nodeData.refName = data.refName
                if (nodeData.command) content = nodeData.command
                
                node.addEventListener('dblclick', () => {
                    this.currentCommandNode = node
                    this.commandInput.value = ''
                    this.commandDescInput.value = ''
                    this.commandRefInput.value = ''
                    document.getElementById('command-modal').style.display = 'block'
                })
                break
            case 'output':
                typeLabel = '结果显示'
                title = '结果显示'
                content = '等待执行'
                break
        }
        node.innerHTML = `
            <span class="node-type">${typeLabel}</span>
            <div class="connector output"></div>
            <div class="connector input"></div>
            <div class="node-header">
                <span class="node-title" title="${title}">${title}</span>
                <button class="node-delete">&times;</button>
            </div>
            ${content ? `<div class="node-content" title="${content}">${content}</div>` : ''}
            <div class="node-status-badge"></div>
        `
        node.querySelector('.node-delete').addEventListener('click', e => {
            e.stopPropagation()
            this.deleteNode(parseInt(node.dataset.id))
        })
        this.canvasContent.appendChild(node)
        this.nodes.push(nodeData)
        this.nextNodeId++
        return node
    }

    deleteNode(nodeId) {
        const node = this.canvasContent.querySelector(`.canvas-node[data-id="${nodeId}"]`)
        if (node) node.remove()
        this.nodes = this.nodes.filter(n => n.id !== nodeId)
        this.connections = this.connections.filter(c => c.from !== nodeId && c.to !== nodeId)
        this.updateConnections()
        
        if (this.selectedNodes.has(nodeId)) {
            this.selectedNodes.delete(nodeId)
        }
    }

    createConnection(fromId, toId, type = 'default') {
        const exists = this.connections.some(c => c.from === parseInt(fromId) && c.to === parseInt(toId))
        if (exists) return
        this.connections.push({ from: parseInt(fromId), to: parseInt(toId), type: type })
        this.updateConnections()
    }

    updateConnections() {
        const svg = this.connectionsLayer
        const paths = svg.querySelectorAll('path:not(#temp-connection)')
        paths.forEach(p => p.remove())

        this.connections.forEach(conn => {
            const fromEl = this.canvas.querySelector(`.canvas-node[data-id="${conn.from}"]`)
            const toEl = this.canvas.querySelector(`.canvas-node[data-id="${conn.to}"]`)
            if (!fromEl || !toEl) return
            
            const fromOut = fromEl.querySelector('.connector.output')
            const toIn = toEl.querySelector('.connector.input')
            if (!fromOut || !toIn) return

            const cr = this.canvasContent.getBoundingClientRect()
            const fr = fromOut.getBoundingClientRect()
            const tr = toIn.getBoundingClientRect()

            const x1 = (fr.left + fr.width / 2 - cr.left) / this.scale
            const y1 = (fr.top + fr.height / 2 - cr.top) / this.scale
            const x2 = (tr.left + tr.width / 2 - cr.left) / this.scale
            const y2 = (tr.top + tr.height / 2 - cr.top) / this.scale

            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path')
            path.setAttribute('d', `M ${x1} ${y1} C ${(x1+x2)/2} ${y1}, ${(x1+x2)/2} ${y2}, ${x2} ${y2}`)
            
            // 根据类型设置颜色
            let strokeColor = '#667eea' // default
            if (conn.type === 'success') strokeColor = '#10b981' // green
            if (conn.type === 'failure') strokeColor = '#ef4444' // red
            
            path.setAttribute('stroke', strokeColor)
            path.setAttribute('fill', 'transparent')
            path.setAttribute('stroke-width', '2')
            path.setAttribute('class', 'connection-path')
            path.dataset.from = conn.from
            path.dataset.to = conn.to
            
            path.addEventListener('click', (e) => {
                e.stopPropagation()
                this.selectConnection(conn)
                // this.toggleConnectionType() // 移除自动切换，改为显示弹窗
                this.showPopover(e, conn)
            })
            
            path.addEventListener('dblclick', (e) => {
                e.stopPropagation() 
                // 双击删除逻辑保留作为快捷方式，或者也可以移除
                if (confirm('确定要删除这条连线吗？')) {
                    this.deleteConnection(conn.from, conn.to)
                    this.hidePopover()
                }
            })
            
            svg.insertBefore(path, svg.firstChild)
        })
    }
    
    showPopover(e, conn) {
        this.connPopover.style.display = 'block'
        
        // 设置位置
        const x = e.clientX + 10
        const y = e.clientY + 10
        this.connPopover.style.left = x + 'px'
        this.connPopover.style.top = y + 'px'
        
        // 设置当前值
        this.connTypeSelect.value = conn.type || 'default'
    }

    hidePopover() {
        if (this.connPopover) {
            this.connPopover.style.display = 'none'
        }
    }

    selectConnection(conn) {
        this.selectedConnection = conn
        // 高亮显示（通过重新渲染或直接操作DOM）
        const paths = this.connectionsLayer.querySelectorAll('.connection-path')
        paths.forEach(p => {
            if (parseInt(p.dataset.from) === conn.from && parseInt(p.dataset.to) === conn.to) {
                p.setAttribute('stroke-width', '4')
                p.style.filter = 'drop-shadow(0 0 3px rgba(0,0,0,0.3))'
            } else {
                p.setAttribute('stroke-width', '2')
                p.style.filter = 'none'
            }
        })
    }
    
    toggleConnectionType() {
        if (!this.selectedConnection) return
        
        const types = ['default', 'success', 'failure']
        const currentIdx = types.indexOf(this.selectedConnection.type || 'default')
        const nextType = types[(currentIdx + 1) % types.length]
        
        this.selectedConnection.type = nextType
        this.updateConnections()
        this.selectConnection(this.selectedConnection) // 保持选中状态
    }

    deleteConnection(fromId, toId) {
        this.connections = this.connections.filter(c => !(c.from === fromId && c.to === toId))
        if (this.selectedConnection && this.selectedConnection.from === fromId && this.selectedConnection.to === toId) {
            this.selectedConnection = null
        }
        this.updateConnections()
    }

    clearCanvas() {
        const nodes = this.canvasContent.querySelectorAll('.canvas-node')
        nodes.forEach(n => n.remove())
        this.nodes = []
        this.connections = []
        this.selectedConnection = null
        
        this.updateConnections()
        this.addSystemMessage('画布已清空', 'info')
        this.nextNodeId = 1
        this.currentWorkflowId = null
        this.currentWorkflowName = null
        this.updateWorkflowDisplay()
    }

    findConnectedSteps(serverId) {
        const steps = []
        const visited = new Set()
        const dfs = id => {
            if (visited.has(id)) return
            visited.add(id)
            const outs = this.connections.filter(c => c.from === id)
            for (const c of outs) {
                const node = this.nodes.find(n => n.id === c.to)
                if (!node) continue
                if (node.type === 'upload' || node.type === 'command' || node.type === 'output') {
                    steps.push(node)
                }
                dfs(c.to)
            }
        }
        dfs(serverId)
        return steps
    }

    updateNodeStatus(nodeId, status) {
        const node = this.canvasContent.querySelector(`.canvas-node[data-id="${nodeId}"]`)
        if (!node) return
        
        node.classList.remove('running', 'success', 'error')
        
        if (status !== 'pending') {
            node.classList.add(status)
        }
    }

    // 序列化
    serialize() {
        const nodesData = this.nodes.map(n => {
            const node = { ...n }
            if (node.type === 'upload' && node.upload && node.upload.file) {
                node.upload = { 
                    ...node.upload, 
                    fileName: node.upload.file.name,
                    file: null
                }
            }
            return node
        })
        
        return {
            nodes: nodesData,
            connections: this.connections,
            nextNodeId: this.nextNodeId
        }
    }

    // 反序列化
    deserializeCorrect(data) {
        this.clearCanvas()
        
        if (!data || !data.nodes) return
        
        data.nodes.forEach(n => {
            const node = document.createElement('div')
            node.className = 'canvas-node'
            node.dataset.id = n.id
            node.style.left = n.x + 'px'
            node.style.top = n.y + 'px'
            
            let title = '', content = '', typeLabel = ''
            
            switch (n.type) {
                case 'server':
                    typeLabel = '服务器'
                    title = n.serverName || '服务器'
                    break
                case 'upload':
                    typeLabel = '上传文件'
                    title = '上传文件'
                    content = n.upload?.remote || '未设置'
                    if (n.upload?.fileName) {
                         n.upload.file = { name: n.upload.fileName + ' (需重新上传)' }
                    }
                    node.addEventListener('dblclick', () => {
                        this.currentUploadNode = node
                        this.uploadFileInput.value = ''
                        this.remotePathInput.value = n.upload?.remote || ''
                        this.uploadRefInput.value = n.refName || ''
                        const fileInfo = document.getElementById('current-file-info')
                        fileInfo.textContent = n.upload?.file ? `当前文件: ${n.upload.file.name}` : '当前未选择文件'
                        document.getElementById('upload-modal').style.display = 'block'
                    })
                    break
                case 'command':
                    typeLabel = '执行命令'
                    title = '执行命令'
                    content = n.command || '未设置'
                    node.addEventListener('dblclick', () => {
                        this.currentCommandNode = node
                        this.commandInput.value = n.command || ''
                        this.commandDescInput.value = n.description || ''
                        this.commandRefInput.value = n.refName || ''
                        document.getElementById('command-modal').style.display = 'block'
                    })
                    break
                case 'output':
                    typeLabel = '结果显示'
                    title = '结果显示'
                    content = '等待执行'
                    break
            }
            
            node.innerHTML = `
                <span class="node-type">${typeLabel}</span>
                <div class="connector output"></div>
                <div class="connector input"></div>
                <div class="node-header">
                    <span class="node-title" title="${title}">${title}</span>
                    <button class="node-delete">&times;</button>
                </div>
                ${content ? `<div class="node-content" title="${content}">${content}</div>` : ''}
                <div class="node-status-badge"></div>
            `
            node.querySelector('.node-delete').addEventListener('click', e => {
                e.stopPropagation()
                this.deleteNode(parseInt(node.dataset.id))
            })
            
            this.canvasContent.appendChild(node)
        })
        
        this.nodes = data.nodes
        this.connections = data.connections
        this.nextNodeId = data.nextNodeId
        
        this.updateConnections()
        
        this.addSystemMessage('工作流加载成功', 'success')
    }

    updateWorkflowDisplay() {
        const el = document.getElementById('current-workflow-name')
        if (!el) return
        if (this.currentWorkflowName) {
            el.textContent = `(当前: ${this.currentWorkflowName})`
            el.style.display = 'inline'
        } else {
            el.style.display = 'none'
        }
    }

    handleSave() {
        if (this.currentWorkflowId) {
            // 已有ID，直接更新
            this.updateWorkflow()
        } else {
            // 无ID，打开保存弹窗
            this.openSaveModal()
        }
    }

    async updateWorkflow() {
        if (this.nodes.length === 0) {
            alert('画布为空，无法保存')
            return
        }

        const data = this.serialize()
        
        try {
            const res = await ServerAPI.request(`/workflows/${this.currentWorkflowId}`, {
                method: 'PUT',
                body: JSON.stringify({
                    data: data
                })
            })
            
            if (res.status === 'success') {
                this.addSystemMessage(`工作流 "${this.currentWorkflowName}" 更新成功`, 'success')
            } else {
                alert('更新失败: ' + res.message)
            }
        } catch (e) {
            alert('更新出错: ' + e.message)
        }
    }

    openSaveModal() {
        if (this.nodes.length === 0) {
            alert('画布为空，无法保存')
            return
        }
        document.getElementById('workflow-name').value = ''
        document.getElementById('workflow-desc').value = ''
        document.getElementById('save-workflow-modal').style.display = 'block'
    }

    async saveWorkflow() {
        const name = document.getElementById('workflow-name').value.trim()
        const desc = document.getElementById('workflow-desc').value.trim()
        
        if (!name) {
            alert('请输入工作流名称')
            return
        }
        
        const data = this.serialize()
        
        try {
            const res = await ServerAPI.request('/workflows', {
                method: 'POST',
                body: JSON.stringify({
                    name: name,
                    description: desc,
                    data: data
                })
            })
            
            if (res.status === 'success') {
                this.addSystemMessage(`工作流 "${name}" 保存成功`, 'success')
                this.currentWorkflowId = res.data.id
                this.currentWorkflowName = name
                this.updateWorkflowDisplay()
                document.getElementById('save-workflow-modal').style.display = 'none'
            } else {
                alert('保存失败: ' + res.message)
            }
        } catch (e) {
            alert('保存出错: ' + e.message)
        }
    }

    async openLoadModal() {
        const modal = document.getElementById('load-workflow-modal')
        const list = document.getElementById('workflow-list')
        list.innerHTML = '<div class="loading-spinner"></div>'
        modal.style.display = 'block'
        
        try {
            const res = await ServerAPI.request('/workflows')
            list.innerHTML = ''
            if (res.status === 'success' && res.data.length > 0) {
                res.data.forEach(wf => {
                    const div = document.createElement('div')
                    div.className = 'workflow-item'
                    div.innerHTML = `
                        <div class="wf-info">
                            <h4>${this.escapeHtml(wf.name)}</h4>
                            <p>${this.escapeHtml(wf.description || '无描述')}</p>
                            <div class="wf-meta">更新于: ${wf.updated_at}</div>
                        </div>
                        <div class="wf-actions">
                            <button class="btn btn-sm btn-primary load-btn" data-id="${wf.id}">加载</button>
                            <button class="btn btn-sm btn-danger delete-btn" data-id="${wf.id}">删除</button>
                        </div>
                    `
                    list.appendChild(div)
                    
                    div.querySelector('.load-btn').addEventListener('click', () => {
                        this.loadWorkflow(wf.id)
                        modal.style.display = 'none'
                    })
                    
                    div.querySelector('.delete-btn').addEventListener('click', async (e) => {
                        if (confirm('确定要删除该工作流吗？')) {
                            await ServerAPI.request(`/workflows/${wf.id}`, { method: 'DELETE' })
                            div.remove()
                        }
                    })
                })
            } else {
                list.innerHTML = '<div style="padding:20px;text-align:center;color:#666">暂无保存的工作流</div>'
            }
        } catch (e) {
            list.innerHTML = `<div style="color:red">加载失败: ${e.message}</div>`
        }
    }

    async loadWorkflow(id) {
        try {
            const res = await ServerAPI.request(`/workflows/${id}`)
            if (res.status === 'success') {
                const data = typeof res.data.data === 'string' ? JSON.parse(res.data.data) : res.data.data
                this.deserializeCorrect(data)
                this.currentWorkflowId = id
                this.currentWorkflowName = res.data.name
                this.updateWorkflowDisplay()
            }
        } catch (e) {
            this.addSystemMessage('加载工作流失败: ' + e.message, 'error')
        }
    }

    async runWorkflow() {
        const container = document.getElementById('output-container')
        container.innerHTML = ''
        
        const serverNodes = this.nodes.filter(n => n.type === 'server')
        
        if (serverNodes.length === 0) {
            this.addSystemMessage('错误: 没有找到服务器节点', 'error')
            return
        }
        
        this.addSystemMessage('🚀 开始并发执行工作流...', 'info')
        
        this.nodes.forEach(n => this.updateNodeStatus(n.id, 'pending'))
        
        const promises = []
        
        // 执行单个服务器节点
        serverNodes.forEach(sn => {
            promises.push(this.runServerWorkflow(sn))
        })
        
        await Promise.all(promises)
        
        this.addSystemMessage('✅ 所有任务执行完成', 'success')
    }

    async runServerWorkflow(startNode, serverContext = null) {
        // startNode: 画布上的起始节点 (server)
        // serverContext: 实际执行的服务器信息 {id, name, host...}
        // 如果 startNode 是 server 类型，serverContext 默认为 null，我们会从 startNode 提取
        
        let sn = startNode
        let realServer = null
        
        if (startNode.type === 'server') {
            realServer = {
                serverId: startNode.serverId,
                serverName: startNode.serverName,
                serverHost: startNode.serverHost
            }
        }
        
        if (!realServer) {
            console.error('Missing server context')
            return
        }

        // 1. 找到所有直接连接到服务器的起始节点
        // 注意：连接是基于 startNode.id 的
        const initialConnections = this.connections.filter(c => c.from === sn.id)
        if (initialConnections.length === 0) {
            if (startNode.type === 'server') {
                 this.addSystemMessage(`提示: 服务器 "${realServer.serverName}" 未连接任何任务`, 'warning')
            }
            return
        }
        
        const initialNodes = initialConnections.map(c => this.nodes.find(n => n.id === c.to)).filter(n => n)
        
        // 如果是单个服务器节点，更新其状态
        if (startNode.type === 'server') {
            this.updateNodeStatus(sn.id, 'running')
        }
        
        const context = {} // 存储变量上下文
        
        try {
            // 并发执行所有起始分支
            await Promise.all(initialNodes.map(node => this.executeNode(node, context, realServer)))
            
            if (startNode.type === 'server') {
                this.updateNodeStatus(sn.id, 'success')
            }
        } catch (e) {
            this.addSystemMessage(`[${realServer.serverName}] 流程异常终止: ${e.message}`, 'error')
            if (startNode.type === 'server') {
                this.updateNodeStatus(sn.id, 'error')
            }
            throw e 
        }
    }

    async executeNode(node, context, sn) {
        this.updateNodeStatus(node.id, 'running')
        
        let success = false
        let outputData = null
        
        try {
            // 变量替换
            const replaceVars = (str) => {
                if (!str) return str
                return str.replace(/\{\{\s*([\w\.]+)\s*\}\}/g, (match, varPath) => {
                    // 1. 全局变量 (global.key)
                    if (varPath.startsWith('global.')) {
                        const key = varPath.substring(7) // remove 'global.'
                        if (this.globalVars && this.globalVars[key] !== undefined) {
                            return this.globalVars[key]
                        }
                        return match
                    }
                    
                    // 2. 上下文变量 (refName.field)
                    const parts = varPath.split('.')
                    if (parts.length === 2) {
                        const [refName, field] = parts
                        if (context[refName] && context[refName][field] !== undefined) {
                            return context[refName][field]
                        }
                    }
                    
                    return match // 未找到变量，保持原样
                })
            }
            
            if (node.type === 'upload') {
                if (!node.upload || !node.upload.file) throw new Error('未设置文件')
                
                let remotePath = replaceVars(node.upload.remote || '')
                // 如果路径是空的，使用默认逻辑（后端处理）
                
                const res = await ServerAPI.uploadFile(sn.serverId, node.upload.file, remotePath)
                if (res.status === 'success') {
                    const finalPath = remotePath || `/tmp/${node.upload.file.name}`
                    this.addSystemMessage(`[${sn.serverName}] 上传成功: ${finalPath}`, 'success')
                    success = true
                    outputData = { path: finalPath, status: 'success' }
                } else {
                    throw new Error(res.message || '上传失败')
                }
                
            } else if (node.type === 'command') {
                if (!node.command) throw new Error('未设置命令')
                
                const cmd = replaceVars(node.command)
                const res = await ServerAPI.executeCommand(sn.serverId, cmd)
                
                if (res.status === 'success') {
                    const d = res.data || {}
                    success = d.exit_status === 0
                    outputData = { 
                        stdout: d.output || '', 
                        stderr: d.error || '', 
                        exit_code: d.exit_status,
                        status: success ? 'success' : 'failure'
                    }
                    
                    // 显示结果...
                    const hasOutput = d.output && d.output.trim().length > 0
                    const hasError = d.error && d.error.trim().length > 0
                    let outputHtml = ''
                    if (hasOutput) outputHtml += `<div class="cmd-output-section"><div class="section-title success-text">STDOUT</div><pre>${this.escapeHtml(d.output)}</pre></div>`
                    if (hasError) outputHtml += `<div class="cmd-output-section"><div class="section-title error-text">STDERR</div><pre>${this.escapeHtml(d.error)}</pre></div>`
                    if (!hasOutput && !hasError) outputHtml = '<div class="cmd-output-empty">（无输出）</div>'
                    
                    this.addOutput(`
                        <div class="cmd-result-header ${success ? 'success' : 'error'}">
                            <span class="toggle-icon">▶</span>
                            <span class="server-badge">[${this.escapeHtml(sn.serverName)}]</span>
                            <span class="cmd-text">${this.escapeHtml(cmd)}</span>
                            <span class="status-tag">${success ? 'SUCCESS' : 'FAILED'}</span>
                        </div>
                        <div class="cmd-result-body">${outputHtml}</div>
                    `)
                    
                    // 如果有输出节点连接到此节点，更新它
                    // 注意：这里的逻辑稍微复杂，因为输出节点可能不是直接连接的下一级
                    // 简化处理：查找当前节点直接连接的 output 类型节点
                    const outConns = this.connections.filter(c => c.from === node.id)
                    outConns.forEach(c => {
                        const nextNode = this.nodes.find(n => n.id === c.to)
                        if (nextNode && nextNode.type === 'output') {
                            const el = this.canvasContent.querySelector(`.canvas-node[data-id="${nextNode.id}"] .node-content`)
                            if (el) el.textContent = (d.output || '') + (d.error ? '\n错误:\n' + d.error : '')
                            this.updateNodeStatus(nextNode.id, success ? 'success' : 'error')
                        }
                    })
                } else {
                    throw new Error(res.message || '请求失败')
                }
            }
        } catch (e) {
            success = false
            outputData = { error: e.message, status: 'failure' }
            this.addSystemMessage(`[${sn.serverName}] 节点执行错误: ${e.message}`, 'error')
        }
        
        // 保存上下文
        if (node.refName) {
            context[node.refName] = outputData
        }
        
        this.updateNodeStatus(node.id, success ? 'success' : 'error')
        
        // 决定下一步
        // 查找所有从当前节点出发的连接
        const nextConns = this.connections.filter(c => c.from === node.id)
        const nextNodesToRun = []
        
        for (const conn of nextConns) {
            const nextNode = this.nodes.find(n => n.id === conn.to)
            if (!nextNode || nextNode.type === 'output') continue // 输出节点已处理，不作为执行节点
            
            const type = conn.type || 'default'
            if (type === 'default') {
                nextNodesToRun.push(nextNode)
            } else if (type === 'success' && success) {
                nextNodesToRun.push(nextNode)
            } else if (type === 'failure' && !success) {
                nextNodesToRun.push(nextNode)
            }
        }
        
        if (nextNodesToRun.length > 0) {
            await Promise.all(nextNodesToRun.map(n => this.executeNode(n, context, sn)))
        }
    }

    addSystemMessage(text, type = 'info') {
        const container = document.getElementById('output-container')
        const item = document.createElement('div')
        item.className = `output-item system-message ${type}`
        item.textContent = text
        container.appendChild(item)
        container.scrollTop = container.scrollHeight
    }

    log(text, level='info') {
        this.addSystemMessage(text, level)
    }

    addOutput(htmlContent) {
        const container = document.getElementById('output-container')
        const item = document.createElement('div')
        item.className = 'output-item'
        item.innerHTML = htmlContent
        container.appendChild(item)
        
        const header = item.querySelector('.cmd-result-header')
        if (header) {
            header.addEventListener('click', () => {
                item.classList.toggle('expanded')
            })
        }
        
        container.scrollTop = container.scrollHeight
    }

    escapeHtml(text) {
        if (!text) return ''
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;")
    }
}

document.addEventListener('DOMContentLoaded', () => new WorkflowEditor())
