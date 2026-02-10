// 工作流编辑器 JavaScript

class WorkflowEditor {
    constructor() {
        this.nodes = [];
        this.connections = [];
        this.nextNodeId = 1;
        this.isDragging = false;
        this.draggedNode = null;
        this.dragOffset = { x: 0, y: 0 };
        this.isConnecting = false;
        this.connectionStart = null;
        this.currentCommandNode = null;
        
        this.init();
    }

    init() {
        this.canvas = document.getElementById('canvas');
        this.connectionsLayer = document.getElementById('connections');
        this.serverList = document.getElementById('server-list');
        this.consoleOutput = document.getElementById('console-output');
        
        this.loadServers();
        this.setupDragAndDrop();
        this.setupCanvasEvents();
        this.setupModal();
        this.setupButtons();
        
        this.addDropHint();
    }

    async loadServers() {
        const response = await ServerAPI.listServers();
        if (response.status === 'success' && response.data) {
            response.data.forEach(server => {
                const item = document.createElement('div');
                item.className = 'draggable-item';
                item.setAttribute('draggable', 'true');
                item.dataset.type = 'server';
                item.dataset.serverId = server.id;
                item.dataset.serverName = server.name;
                item.dataset.serverHost = server.host;
                item.innerHTML = `
                    <span class="icon">🖥️</span>
                    <span>${server.name}</span>
                    <span style="font-size: 12px; color: #999; margin-left: auto;">${server.host}</span>
                `;
                this.serverList.appendChild(item);
            });
        }
    }

    addDropHint() {
        const hint = document.createElement('div');
        hint.className = 'drop-hint';
        hint.textContent = '拖拽组件到此处';
        this.canvas.appendChild(hint);
    }

    setupDragAndDrop() {
        const draggableItems = document.querySelectorAll('.draggable-item');
        
        draggableItems.forEach(item => {
            item.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('type', item.dataset.type);
                e.dataTransfer.setData('serverId', item.dataset.serverId || '');
                e.dataTransfer.setData('serverName', item.dataset.serverName || '');
                e.dataTransfer.setData('serverHost', item.dataset.serverHost || '');
                item.classList.add('dragging');
            });

            item.addEventListener('dragend', (e) => {
                item.classList.remove('dragging');
            });
        });

        this.canvas.addEventListener('dragover', (e) => {
            e.preventDefault();
            this.canvas.classList.add('drag-over');
        });

        this.canvas.addEventListener('dragleave', (e) => {
            if (!this.canvas.contains(e.relatedTarget)) {
                this.canvas.classList.remove('drag-over');
            }
        });

        this.canvas.addEventListener('drop', (e) => {
            e.preventDefault();
            this.canvas.classList.remove('drag-over');
            
            const type = e.dataTransfer.getData('type');
            const serverId = e.dataTransfer.getData('serverId');
            const serverName = e.dataTransfer.getData('serverName');
            const serverHost = e.dataTransfer.getData('serverHost');
            
            const rect = this.canvas.getBoundingClientRect();
            const x = e.clientX - rect.left - 100;
            const y = e.clientY - rect.top - 40;
            
            this.createNode(type, x, y, { serverId, serverName, serverHost });
        });
    }

    setupCanvasEvents() {
        this.canvas.addEventListener('mousedown', (e) => {
            const node = e.target.closest('.canvas-node');
            const connector = e.target.closest('.connector');
            
            if (connector) {
                this.isConnecting = true;
                this.connectionStart = {
                    node: node,
                    type: connector.classList.contains('input') ? 'input' : 'output',
                    connector: connector
                };
                e.stopPropagation();
                return;
            }
            
            if (node) {
                this.isDragging = true;
                this.draggedNode = node;
                const rect = node.getBoundingClientRect();
                this.dragOffset = {
                    x: e.clientX - rect.left,
                    y: e.clientY - rect.top
                };
                this.selectNode(node);
            }
        });

        document.addEventListener('mousemove', (e) => {
            if (this.isDragging && this.draggedNode) {
                const canvasRect = this.canvas.getBoundingClientRect();
                let x = e.clientX - canvasRect.left - this.dragOffset.x;
                let y = e.clientY - canvasRect.top - this.dragOffset.y;
                
                x = Math.max(0, Math.min(x, canvasRect.width - 200));
                y = Math.max(0, Math.min(y, canvasRect.height - 80));
                
                this.draggedNode.style.left = x + 'px';
                this.draggedNode.style.top = y + 'px';
                
                const nodeId = parseInt(this.draggedNode.dataset.id);
                const nodeData = this.nodes.find(n => n.id === nodeId);
                if (nodeData) {
                    nodeData.x = x;
                    nodeData.y = y;
                }
                
                this.updateConnections();
            }
        });

        document.addEventListener('mouseup', (e) => {
            if (this.isConnecting && this.connectionStart) {
                const connector = e.target.closest('.connector');
                if (connector && connector !== this.connectionStart.connector) {
                    const endNode = connector.closest('.canvas-node');
                    if (endNode && endNode !== this.connectionStart.node) {
                        const startType = this.connectionStart.type;
                        const endType = connector.classList.contains('input') ? 'input' : 'output';
                        
                        if (startType === 'output' && endType === 'input') {
                            this.createConnection(
                                this.connectionStart.node.dataset.id,
                                endNode.dataset.id
                            );
                        }
                    }
                }
            }
            
            this.isDragging = false;
            this.draggedNode = null;
            this.isConnecting = false;
            this.connectionStart = null;
        });
    }

    setupModal() {
        this.modal = document.getElementById('command-modal');
        this.commandInput = document.getElementById('command-input');
        this.commandDescInput = document.getElementById('command-description');
        
        document.querySelector('.close').addEventListener('click', () => {
            this.modal.style.display = 'none';
        });
        
        document.getElementById('cancel-command').addEventListener('click', () => {
            this.modal.style.display = 'none';
        });
        
        document.getElementById('save-command').addEventListener('click', () => {
            const command = this.commandInput.value.trim();
            const description = this.commandDescInput.value.trim();
            
            if (command && this.currentCommandNode) {
                const nodeData = this.nodes.find(n => n.id === parseInt(this.currentCommandNode.dataset.id));
                if (nodeData) {
                    nodeData.command = command;
                    nodeData.description = description;
                    
                    this.currentCommandNode.querySelector('.node-content').textContent = command;
                    if (description) {
                        this.currentCommandNode.querySelector('.node-title').textContent = description;
                    }
                }
            }
            
            this.modal.style.display = 'none';
            this.commandInput.value = '';
            this.commandDescInput.value = '';
        });
        
        window.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.modal.style.display = 'none';
            }
        });
    }

    setupButtons() {
        document.getElementById('clear-btn').addEventListener('click', () => {
            this.clearCanvas();
        });
        
        document.getElementById('run-btn').addEventListener('click', () => {
            this.runWorkflow();
        });
    }

    createNode(type, x, y, data = {}) {
        const node = document.createElement('div');
        node.className = 'canvas-node';
        node.dataset.id = this.nextNodeId;
        node.style.left = x + 'px';
        node.style.top = y + 'px';
        
        const nodeData = {
            id: this.nextNodeId,
            type: type,
            x: x,
            y: y
        };
        
        let title = '';
        let content = '';
        let typeClass = type;
        
        switch (type) {
            case 'server':
                title = data.serverName || '服务器';
                content = data.serverHost || '未连接';
                nodeData.serverId = data.serverId;
                nodeData.serverName = data.serverName;
                nodeData.serverHost = data.serverHost;
                break;
            case 'command':
                title = '执行命令';
                content = '双击编辑命令';
                nodeData.command = '';
                nodeData.description = '';
                node.addEventListener('dblclick', () => {
                    this.currentCommandNode = node;
                    this.commandInput.value = nodeData.command || '';
                    this.commandDescInput.value = nodeData.description || '';
                    this.modal.style.display = 'block';
                });
                break;
            case 'output':
                title = '结果显示';
                content = '等待执行...';
                break;
        }
        
        node.innerHTML = `
            <span class="node-type ${typeClass}">${this.getTypeLabel(type)}</span>
            <div class="connector output"></div>
            <div class="connector input"></div>
            <div class="node-header">
                <span class="node-title">${title}</span>
                <button class="node-delete">&times;</button>
            </div>
            <div class="node-content">${content}</div>
        `;
        
        node.querySelector('.node-delete').addEventListener('click', (e) => {
            e.stopPropagation();
            this.deleteNode(parseInt(node.dataset.id));
        });
        
        this.canvas.appendChild(node);
        this.nodes.push(nodeData);
        this.nextNodeId++;
        
        this.log(`创建了节点: ${title}`, 'info');
        
        return node;
    }

    getTypeLabel(type) {
        const labels = {
            'server': '服务器',
            'command': '命令',
            'output': '输出'
        };
        return labels[type] || type;
    }

    deleteNode(nodeId) {
        const node = this.canvas.querySelector(`.canvas-node[data-id="${nodeId}"]`);
        if (node) {
            node.remove();
        }
        
        this.nodes = this.nodes.filter(n => n.id !== nodeId);
        this.connections = this.connections.filter(c => c.from !== nodeId && c.to !== nodeId);
        this.updateConnections();
        
        this.log(`删除了节点 ${nodeId}`, 'info');
    }

    createConnection(fromId, toId) {
        const exists = this.connections.some(c => c.from === fromId && c.to === toId);
        if (exists) return;
        
        this.connections.push({ from: parseInt(fromId), to: parseInt(toId) });
        this.updateConnections();
        this.log(`创建了连接: ${fromId} -> ${toId}`, 'info');
    }

    updateConnections() {
        this.connectionsLayer.innerHTML = '';
        
        const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
        defs.innerHTML = `
            <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                <polygon points="0 0, 10 3.5, 0 7" fill="#999" />
            </marker>
        `;
        this.connectionsLayer.appendChild(defs);
        
        this.connections.forEach(conn => {
            const fromNode = this.canvas.querySelector(`.canvas-node[data-id="${conn.from}"]`);
            const toNode = this.canvas.querySelector(`.canvas-node[data-id="${conn.to}"]`);
            
            if (!fromNode || !toNode) return;
            
            const fromRect = fromNode.getBoundingClientRect();
            const toRect = toNode.getBoundingClientRect();
            const canvasRect = this.canvas.getBoundingClientRect();
            
            const fromX = fromNode.offsetLeft + fromNode.offsetWidth;
            const fromY = fromNode.offsetTop + fromNode.offsetHeight / 2;
            const toX = toNode.offsetLeft;
            const toY = toNode.offsetTop + toNode.offsetHeight / 2;
            
            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            const midX = (fromX + toX) / 2;
            const d = `M ${fromX} ${fromY} C ${midX} ${fromY}, ${midX} ${toY}, ${toX} ${toY}`;
            
            path.setAttribute('d', d);
            path.setAttribute('class', 'connection-line');
            
            this.connectionsLayer.appendChild(path);
        });
    }

    selectNode(node) {
        document.querySelectorAll('.canvas-node').forEach(n => n.classList.remove('selected'));
        node.classList.add('selected');
    }

    clearCanvas() {
        const nodes = this.canvas.querySelectorAll('.canvas-node');
        nodes.forEach(node => node.remove());
        this.nodes = [];
        this.connections = [];
        this.updateConnections();
        this.consoleOutput.innerHTML = '<p class="info">画布已清空</p>';
        this.nextNodeId = 1;
    }

    log(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const p = document.createElement('p');
        p.className = type;
        p.textContent = `[${timestamp}] ${message}`;
        this.consoleOutput.appendChild(p);
        this.consoleOutput.scrollTop = this.consoleOutput.scrollHeight;
    }

    async runWorkflow() {
        this.consoleOutput.innerHTML = '';
        this.log('开始执行工作流...', 'info');
        
        const serverNodes = this.nodes.filter(n => n.type === 'server');
        
        if (serverNodes.length === 0) {
            this.log('错误: 没有找到服务器节点', 'error');
            return;
        }
        
        for (const serverNode of serverNodes) {
            const nodeEl = this.canvas.querySelector(`.canvas-node[data-id="${serverNode.id}"]`);
            nodeEl.classList.add('running');
            
            this.log(`连接服务器: ${serverNode.serverName} (${serverNode.serverHost})`, 'info');
            
            const commands = this.findConnectedCommands(serverNode.id);
            
            for (const commandNode of commands) {
                const cmdNodeEl = this.canvas.querySelector(`.canvas-node[data-id="${commandNode.id}"]`);
                cmdNodeEl.classList.add('running');
                
                if (!commandNode.command) {
                    this.log(`警告: 命令节点未设置命令`, 'warning');
                    cmdNodeEl.classList.remove('running');
                    continue;
                }
                
                this.log(`执行命令: ${commandNode.command}`, 'info');
                
                try {
                    const result = await ServerAPI.executeCommand(serverNode.serverId, commandNode.command);
                    
                    if (result.status === 'success') {
                        this.log(`命令执行成功`, 'success');
                        this.log(`输出:\n${result.data.output || '无输出'}`, 'info');
                        if (result.data.error) {
                            this.log(`错误输出:\n${result.data.error}`, 'warning');
                        }
                        cmdNodeEl.classList.remove('running');
                        cmdNodeEl.classList.add('success');
                        
                        this.updateOutputNodes(commandNode.id, result.data);
                    } else {
                        this.log(`命令执行失败: ${result.message}`, 'error');
                        cmdNodeEl.classList.remove('running');
                        cmdNodeEl.classList.add('error');
                    }
                } catch (error) {
                    this.log(`执行出错: ${error.message}`, 'error');
                    cmdNodeEl.classList.remove('running');
                    cmdNodeEl.classList.add('error');
                }
            }
            
            nodeEl.classList.remove('running');
            nodeEl.classList.add('success');
        }
        
        this.log('工作流执行完成', 'success');
    }

    findConnectedCommands(nodeId) {
        const commands = [];
        const visited = new Set();
        
        const search = (currentId) => {
            if (visited.has(currentId)) return;
            visited.add(currentId);
            
            const outgoing = this.connections.filter(c => c.from === currentId);
            for (const conn of outgoing) {
                const node = this.nodes.find(n => n.id === conn.to);
                if (node) {
                    if (node.type === 'command') {
                        commands.push(node);
                    } else if (node.type === 'output') {
                        continue;
                    }
                    search(conn.to);
                }
            }
        };
        
        search(nodeId);
        return commands;
    }

    updateOutputNodes(commandNodeId, result) {
        const outgoing = this.connections.filter(c => c.from === commandNodeId);
        for (const conn of outgoing) {
            const node = this.nodes.find(n => n.id === conn.to);
            if (node && node.type === 'output') {
                const nodeEl = this.canvas.querySelector(`.canvas-node[data-id="${node.id}"]`);
                nodeEl.classList.add('success');
                
                const content = nodeEl.querySelector('.node-content');
                const outputText = result.output || result.error || '无输出';
                content.textContent = outputText.substring(0, 50) + (outputText.length > 50 ? '...' : '');
                
                this.addOutputResult(node.id, result);
            }
        }
    }

    addOutputResult(nodeId, result) {
        const node = this.nodes.find(n => n.id === nodeId);
        const container = document.getElementById('output-container');
        
        const outputItem = document.createElement('div');
        outputItem.className = 'output-item';
        outputItem.innerHTML = `
            <div class="output-header">
                <span class="output-title">${node.description || '输出结果'}</span>
            </div>
            <div class="output-content">
${result.output || result.error || '无输出'}
${result.error ? '\n[错误]\n' + result.error : ''}
            </div>
        `;
        
        container.appendChild(outputItem);
    }
}

// 初始化工作流编辑器
document.addEventListener('DOMContentLoaded', () => {
    new WorkflowEditor();
});
