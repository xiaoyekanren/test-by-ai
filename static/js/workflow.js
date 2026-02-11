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
        this.uploadFileInput = null
        this.remotePathInput = null
        this.scale = 1
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
        this.consoleOutput = document.getElementById('console-output')
        this.loadServers()
        this.updatePanelLayout() // 初始化时检查静态列表
        this.setupDragAndDrop()
        this.setupCanvasEvents()
        this.setupModals()
        this.setupButtons()
        this.setupPanelDrag()
        this.setupSplitter()
        this.setupZoom()
        const hint = document.createElement('div')
        hint.className = 'drop-hint'
        hint.textContent = ''
        this.canvasContent.appendChild(hint)
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
        // 检查所有可拖拽容器（包括服务器列表和事件列表）
        const containers = document.querySelectorAll('.draggable-items')
        
        // 统计服务器数量
        const serverList = document.getElementById('server-list')
        const serverCount = serverList ? serverList.children.length : 0
        
        // 如果服务器数量超过5，则所有列表（包括事件）都启用多列布局
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
            this.serverList.innerHTML = '' // 清空列表以防重复加载
            res.data.forEach(s => {
                const item = document.createElement('div')
                item.className = 'draggable-item'
                item.setAttribute('draggable', 'true')
                item.dataset.type = 'server'
                item.dataset.serverId = s.id
                item.dataset.serverName = s.name
                item.dataset.serverHost = s.host
                const display = this.truncateToIpLength(s.name)
                item.innerHTML = `<span class="icon">🖥️</span><span class="server-name" title="${s.name}">${display}</span>`
                this.serverList.appendChild(item)
            })
            this.updatePanelLayout() // 加载完成后再次检查
        }
    }
    setupDragAndDrop() {
        document.addEventListener('dragstart', e => {
            const item = e.target.closest('.draggable-item')
            if (!item) return
            e.dataTransfer.setData('type', item.dataset.type)
            e.dataTransfer.setData('serverId', item.dataset.serverId || '')
            e.dataTransfer.setData('serverName', item.dataset.serverName || '')
            e.dataTransfer.setData('serverHost', item.dataset.serverHost || '')
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
            const serverId = e.dataTransfer.getData('serverId')
            const serverName = e.dataTransfer.getData('serverName')
            const serverHost = e.dataTransfer.getData('serverHost')
            const rect = this.canvasContent.getBoundingClientRect()
            const x = (e.clientX - rect.left - 100 * this.scale) / this.scale
            const y = (e.clientY - rect.top - 40 * this.scale) / this.scale
            this.createNode(type, x, y, { serverId, serverName, serverHost })
        })
    }
    setupCanvasEvents() {
        this.canvas.addEventListener('mousedown', e => {
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
                
                // 添加临时连线预览
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
            
            const node = e.target.closest('.canvas-node')
            if (node) {
                // 选中节点
                this.canvas.querySelectorAll('.canvas-node').forEach(n => n.classList.remove('selected'))
                node.classList.add('selected')
                
                // 启动拖拽
                if (!e.target.closest('.node-delete')) {
                    this.isDragging = true
                    this.draggedNode = node
                    const rect = node.getBoundingClientRect()
                    const canvasRect = this.canvas.getBoundingClientRect()
                    this.dragOffset = {
                        x: e.clientX - rect.left,
                        y: e.clientY - rect.top
                    }
                }
            } else {
                // 点击空白处取消选中
                this.canvas.querySelectorAll('.canvas-node').forEach(n => n.classList.remove('selected'))
            }
        })

        document.addEventListener('mousemove', e => {
            // 处理连线
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
            
            // 处理节点拖拽
            if (this.isDragging && this.draggedNode) {
                e.preventDefault()
                const canvasRect = this.canvasContent.getBoundingClientRect()
                let x = (e.clientX - canvasRect.left) / this.scale - this.dragOffset.x
                let y = (e.clientY - canvasRect.top) / this.scale - this.dragOffset.y
                
                // 简单的边界限制
                x = Math.max(0, x)
                y = Math.max(0, y)
                
                this.draggedNode.style.left = x + 'px'
                this.draggedNode.style.top = y + 'px'
                
                // 更新节点数据位置
                const id = parseInt(this.draggedNode.dataset.id, 10)
                const nodeData = this.nodes.find(n => n.id === id)
                if (nodeData) {
                    nodeData.x = x
                    nodeData.y = y
                }
                
                // 实时更新连线
                this.updateConnections()
            }
        })

        document.addEventListener('mouseup', e => {
            // 结束拖拽
            if (this.isDragging) {
                this.isDragging = false
                this.draggedNode = null
            }

            if (!this.isConnecting) return
            
            // 移除临时连线
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
        this.commandInput = document.getElementById('command-input')
        this.commandDescInput = document.getElementById('command-description')
        this.uploadFileInput = document.getElementById('upload-file')
        this.remotePathInput = document.getElementById('remote-path')
        cmdModal.querySelector('.close').addEventListener('click', () => cmdModal.style.display = 'none')
        uploadModal.querySelector('.close').addEventListener('click', () => uploadModal.style.display = 'none')
        document.getElementById('cancel-command').addEventListener('click', () => cmdModal.style.display = 'none')
        document.getElementById('cancel-upload').addEventListener('click', () => uploadModal.style.display = 'none')
        document.getElementById('save-command').addEventListener('click', () => {
            if (!this.currentCommandNode) return
            const id = parseInt(this.currentCommandNode.dataset.id)
            const node = this.nodes.find(n => n.id === id)
            node.command = this.commandInput.value || ''
            node.description = this.commandDescInput.value || ''
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
            this.currentUploadNode.querySelector('.node-content').textContent = remote || '未设置'
            uploadModal.style.display = 'none'
        })
    }
    setupButtons() {
        document.getElementById('clear-btn').addEventListener('click', () => this.clearCanvas())
        document.getElementById('run-btn').addEventListener('click', () => this.runWorkflow())
        const toggle = document.getElementById('toggle-components')
        if (toggle) {
            toggle.addEventListener('click', () => {
                const panel = document.querySelector('.component-panel')
                panel.classList.toggle('collapsed')
            })
        }
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
                node.addEventListener('dblclick', () => {
                    this.currentUploadNode = node
                    const id = parseInt(node.dataset.id)
                    const nodeData = this.nodes.find(n => n.id === id)
                    
                    this.uploadFileInput.value = ''
                    this.remotePathInput.value = nodeData.upload?.remote || ''
                    
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
                node.addEventListener('dblclick', () => {
                    this.currentCommandNode = node
                    this.commandInput.value = ''
                    this.commandDescInput.value = ''
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
    }
    createConnection(fromId, toId) {
        const exists = this.connections.some(c => c.from === parseInt(fromId) && c.to === parseInt(toId))
        if (exists) return
        this.connections.push({ from: parseInt(fromId), to: parseInt(toId) })
        this.updateConnections()
    }
    updateConnections() {
        const svg = this.connectionsLayer
        // 移除所有路径，但保留临时预览线（如果有）
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
            path.setAttribute('stroke', '#667eea')
            path.setAttribute('fill', 'transparent')
            path.setAttribute('stroke-width', '2')
            path.setAttribute('class', 'connection-path') // 添加类名方便样式控制
            
            // 双击删除连线
            path.addEventListener('dblclick', (e) => {
                e.stopPropagation() // 防止触发其他事件
                if (confirm('确定要删除这条连线吗？')) {
                    this.deleteConnection(conn.from, conn.to)
                }
            })
            
            // 插入到第一个位置
            svg.insertBefore(path, svg.firstChild)
        })
    }
    deleteConnection(fromId, toId) {
        this.connections = this.connections.filter(c => !(c.from === fromId && c.to === toId))
        this.updateConnections()
    }
    clearCanvas() {
        const nodes = this.canvasContent.querySelectorAll('.canvas-node')
        nodes.forEach(n => n.remove())
        this.nodes = []
        this.connections = []
        this.updateConnections()
        this.consoleOutput.innerHTML = '<p class="info">画布已清空</p>'
        this.nextNodeId = 1
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
        
        // 移除旧状态
        node.classList.remove('running', 'success', 'error')
        
        // 添加新状态
        if (status !== 'pending') {
            node.classList.add(status)
        }
    }

    async runWorkflow() {
        this.consoleOutput.innerHTML = ''
        const serverNodes = this.nodes.filter(n => n.type === 'server')
        if (serverNodes.length === 0) {
            this.log('错误: 没有找到服务器节点', 'error')
            return
        }
        
        // 重置所有节点状态
        this.nodes.forEach(n => this.updateNodeStatus(n.id, 'pending'))
        
        let hasExecutedAny = false
        for (const sn of serverNodes) {
            const steps = this.findConnectedSteps(sn.id)
            if (steps.length === 0) {
                this.log(`提示: 服务器 "${sn.serverName || '未命名'}" 未连接任何任务`, 'warning')
                continue
            }
            
            // 标记服务器节点为运行中
            this.updateNodeStatus(sn.id, 'running')
            
            for (const step of steps) {
                hasExecutedAny = true
                this.updateNodeStatus(step.id, 'running')
                
                let stepSuccess = false
                
                if (step.type === 'upload') {
                    if (!step.upload || !step.upload.file) {
                        this.log('警告: 上传节点未设置文件', 'warning')
                        this.updateNodeStatus(step.id, 'error')
                        continue
                    }
                    // 如果未设置远程路径，留空让后端处理默认值
                    const remotePath = step.upload.remote || ''
                    
                    try {
                        const res = await ServerAPI.uploadFile(sn.serverId, step.upload.file, remotePath)
                        if (res.status === 'success') {
                            // 显示实际上传路径
                            const finalPath = remotePath || `/tmp/${step.upload.file.name}`
                            this.log(`[${sn.serverName}] 上传成功: ${finalPath}`, 'success')
                            stepSuccess = true
                        } else {
                            this.log(`[${sn.serverName}] 上传失败: ${res.message || ''}`, 'error')
                        }
                    } catch (e) {
                        this.log(`[${sn.serverName}] 上传出错: ${e.message}`, 'error')
                    }
                } else if (step.type === 'command') {
                    if (!step.command) {
                        this.log('警告: 命令节点未设置命令', 'warning')
                        this.updateNodeStatus(step.id, 'error')
                        continue
                    }
                    try {
                        const res = await ServerAPI.executeCommand(sn.serverId, step.command)
                        if (res.status === 'success') {
                            this.log(`[${sn.serverName}] 命令成功: ${step.command}`, 'success')
                            const d = res.data || {}
                            this.addOutput(`[${sn.serverName}] 输出:\n${d.output || ''}\n错误:\n${d.error || ''}`)
                            // 更新连接的 Output 节点内容
                            const outNode = steps.find(s => s.type === 'output')
                            if (outNode) {
                                const el = this.canvasContent.querySelector(`.canvas-node[data-id="${outNode.id}"] .node-content`)
                                if (el) el.textContent = (d.output || '') + (d.error ? '\n错误:\n' + d.error : '')
                                this.updateNodeStatus(outNode.id, d.exit_status === 0 ? 'success' : 'error')
                            }
                            stepSuccess = d.exit_status === 0
                        } else {
                            this.log(`[${sn.serverName}] 命令失败: ${res.message || ''}`, 'error')
                        }
                    } catch (e) {
                        this.log(`[${sn.serverName}] 执行出错: ${e.message}`, 'error')
                    }
                }
                
                this.updateNodeStatus(step.id, stepSuccess ? 'success' : 'error')
                
                // 如果当前步骤失败，且没有配置"忽略错误"，则终止当前服务器的后续步骤（简单逻辑）
                if (!stepSuccess) break
            }
            
            // 服务器节点状态更新（目前简单处理：只要流程跑完就算成功，具体可根据步骤结果细化）
            this.updateNodeStatus(sn.id, 'success')
        }
        if (!hasExecutedAny) {
            this.log('未执行任何任务，请检查连线', 'warning')
        } else {
            this.log('工作流执行完成', 'success')
        }
    }
    addOutput(text) {
        const container = document.getElementById('output-container')
        const item = document.createElement('div')
        item.className = 'output-item'
        item.innerHTML = `<div class="output-header"><span class="output-title">输出</span></div><div class="output-content">${text}</div>`
        container.appendChild(item)
    }
    log(text, level='info') {
        const p = document.createElement('p')
        p.className = level
        p.textContent = text
        this.consoleOutput.appendChild(p)
    }
}
document.addEventListener('DOMContentLoaded', () => new WorkflowEditor())
