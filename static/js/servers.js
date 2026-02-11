// 服务器管理脚本

async function loadServers() {
    try {
        const response = await ServerAPI.listServers();

        if (response.status === 'success') {
            displayServers(response.data);
        }
    } catch (error) {
        console.error('Failed to load servers:', error);
    }
}

let currentSort = {
    field: 'created_at',
    direction: 'desc'
};

let groupByTag = true; // 是否按标签分组

function createServerHeaderRow() {
    const fields = [
        { key: 'name', label: '服务器名称', class: 'server-name' },
        { key: 'host', label: '主机地址', class: 'server-host' },
        { key: 'port', label: '端口', class: 'server-port' },
        { key: 'username', label: '用户名', class: 'server-username' },
        { key: 'status', label: '状态', class: 'server-status' }
    ];

    const headerCells = fields.map(field => {
        const isSorted = currentSort.field === field.key;
        const sortClass = isSorted ? (currentSort.direction === 'asc' ? 'sort-asc' : 'sort-desc') : '';
        return `
            <div class="header-cell ${field.class} ${sortClass}" onclick="sortServers('${field.key}')">
                ${field.label}<span class="sort-icon"></span>
            </div>
        `;
    }).join('');

    return `
        <div class="server-header">
            ${headerCells}
            <div class="header-cell server-actions">操作</div>
            <div class="header-cell server-tags" onclick="toggleGrouping()">
                标签 <span class="sort-icon" style="opacity: ${groupByTag ? 1 : 0.3}">🏷️</span>
            </div>
            <div class="header-cell server-created" onclick="sortServers('created_at')">
                创建时间<span class="sort-icon ${currentSort.field === 'created_at' ? (currentSort.direction === 'asc' ? 'sort-asc' : 'sort-desc') : ''}"></span>
            </div>
            <div class="header-cell server-description">描述</div>
        </div>
    `;
}

function toggleGrouping() {
    groupByTag = !groupByTag;
    loadServers();
}

function sortServers(field) {
    if (currentSort.field === field) {
        currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
    } else {
        currentSort.field = field;
        currentSort.direction = 'asc';
    }
    loadServers();
}

function displayServers(servers) {
    const container = document.getElementById('server-list-container');

    if (!container) return;

    if (servers.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🖥️</div>
                <h3>暂无服务器</h3>
                <p>还没有添加任何服务器，点击"添加服务器"按钮开始</p>
            </div>
        `;
        return;
    }

    // 排序逻辑
    const sortedServers = [...servers].sort((a, b) => {
        let valA = a[currentSort.field];
        let valB = b[currentSort.field];

        // 处理空值
        if (valA === undefined || valA === null) valA = '';
        if (valB === undefined || valB === null) valB = '';

        // 端口转数字比较
        if (currentSort.field === 'port') {
            valA = parseInt(valA) || 0;
            valB = parseInt(valB) || 0;
        } else {
            // 字符串转小写比较
            valA = String(valA).toLowerCase();
            valB = String(valB).toLowerCase();
        }

        if (valA < valB) return currentSort.direction === 'asc' ? -1 : 1;
        if (valA > valB) return currentSort.direction === 'asc' ? 1 : -1;
        return 0;
    });

    if (groupByTag) {
        // 分组逻辑
        const groups = {};
        const noTagServers = [];

        sortedServers.forEach(server => {
            if (server.tags && server.tags.trim()) {
                const tags = server.tags.split(',').map(t => t.trim()).filter(t => t);
                if (tags.length > 0) {
                    tags.forEach(tag => {
                        if (!groups[tag]) groups[tag] = [];
                        // 避免同一个服务器在同一个标签组重复（虽然理论上不会，但以防万一）
                        if (!groups[tag].find(s => s.id === server.id)) {
                            groups[tag].push(server);
                        }
                    });
                } else {
                    noTagServers.push(server);
                }
            } else {
                noTagServers.push(server);
            }
        });

        // 如果一个服务器有多个标签，它会出现在多个组中。
        // 如果完全没有标签的服务器，单独放一组。
        
        let html = '';
        
        // 按标签名排序
        Object.keys(groups).sort().forEach(tag => {
            html += createServerGroup(tag, groups[tag]);
        });
        
        if (noTagServers.length > 0) {
            html += createServerGroup('未分类', noTagServers);
        }
        
        // 如果没有任何分组（所有服务器都没标签），直接显示列表
        if (Object.keys(groups).length === 0) {
             html = `
                <div class="server-group">
                    <div class="server-list">
                        ${createServerHeaderRow()}
                        ${sortedServers.map(server => createServerRow(server)).join('')}
                    </div>
                </div>
            `;
        }

        container.innerHTML = html;

    } else {
        // 不分组显示
        container.innerHTML = `
            <div class="server-group">
                <div class="server-list">
                    ${createServerHeaderRow()}
                    ${sortedServers.map(server => createServerRow(server)).join('')}
                </div>
            </div>
        `;
    }
}

function createServerGroup(title, servers) {
    return `
        <div class="server-group">
            <div class="group-header">
                <div class="group-title">🏷️ ${title}</div>
                <div class="group-count">${servers.length}</div>
            </div>
            <div class="server-list">
                ${createServerHeaderRow()}
                ${servers.map(server => createServerRow(server)).join('')}
            </div>
        </div>
    `;
}

function createServerRow(server) {
    // 处理标签显示
    let tagsHtml = '';
    if (server.tags) {
        tagsHtml = server.tags.split(',')
            .map(t => t.trim())
            .filter(t => t)
            .map(t => `<span class="tag-badge">${t}</span>`)
            .join('');
    }

    return `
        <div class="server-row">
            <div class="server-name">${server.name}</div>
            <div class="server-host">${server.host}</div>
            <div class="server-port">${server.port}</div>
            <div class="server-username">${server.username || '--'}</div>
            <div class="server-status">
                <span class="status-badge status-${server.status}">${getStatusText(server.status)}</span>
            </div>
            <div class="server-actions">
                <button class="btn btn-small btn-primary" onclick="testServerConnection(${server.id})">
                    测试连接
                </button>
                <button class="btn btn-small btn-primary" onclick="openEditServerModal(${server.id})">
                    编辑
                </button>
                <button class="btn btn-small btn-danger" onclick="deleteServer(${server.id}, '${server.name}')">
                    删除
                </button>
            </div>
            <div class="server-tags">${tagsHtml}</div>
            <div class="server-created">${formatDateTime(server.created_at)}</div>
            <div class="server-description" title="${server.description || ''}">${server.description || '--'}</div>
        </div>
    `;
}

function getStatusText(status) {
    const statusMap = {
        'online': '在线',
        'offline': '离线',
        'error': '错误'
    };
    return statusMap[status] || status;
}

function formatDateTime(dateStr) {
    if (!dateStr) return '--';
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function openAddServerModal() {
    const modal = document.getElementById('add-server-modal');
    if (modal) {
        modal.style.display = 'block';
        document.getElementById('add-server-form').reset();
    }
}

function closeAddServerModal() {
    const modal = document.getElementById('add-server-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

async function openEditServerModal(serverId) {
    const modal = document.getElementById('edit-server-modal');
    if (!modal) return;

    try {
        // 从 API 获取服务器详情
        const response = await ServerAPI.getServer(serverId);

        if (response.status === 'success' && response.data) {
            const server = response.data;

            // 填充表单数据
            document.getElementById('edit-server-id').value = server.id;
            document.getElementById('edit-server-name').value = server.name || '';
            document.getElementById('edit-server-host').value = server.host || '';
            document.getElementById('edit-server-port').value = server.port || '';
            document.getElementById('edit-server-username').value = server.username || '';
            document.getElementById('edit-server-password').value = ''; // 密码不回显
            document.getElementById('edit-server-description').value = server.description || '';
            document.getElementById('edit-server-tags').value = server.tags || '';

            modal.style.display = 'block';
        } else {
            alert('获取服务器信息失败: ' + (response.message || '未知错误'));
        }
    } catch (error) {
        console.error('Failed to load server details:', error);
        alert('获取服务器信息出错: ' + error.message);
    }
}

function closeEditServerModal() {
    const modal = document.getElementById('edit-server-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

async function addServer(event) {
    event.preventDefault();

    const form = document.getElementById('add-server-form');
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);

    try {
        const response = await ServerAPI.addServer(data);

        if (response.status === 'success') {
            alert('服务器添加成功');
            closeAddServerModal();
            loadServers();

            // 自动测试连接,使用 showNotification 避免弹窗
            if (response.data && response.data.id) {
                await testServerConnection(response.data.id, true);
            }
        } else {
            alert('添加失败: ' + response.message);
        }
    } catch (error) {
        alert('添加出错: ' + error.message);
    }
}

async function updateServer(event) {
    event.preventDefault();
    
    const form = document.getElementById('edit-server-form');
    const serverId = document.getElementById('edit-server-id').value;
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);
    delete data.id; // 移除 ID 字段
    
    try {
        const response = await ServerAPI.updateServer(serverId, data);
        
        if (response.status === 'success') {
            alert('服务器更新成功');
            closeEditServerModal();
            loadServers();
        } else {
            alert('更新失败: ' + response.message);
        }
    } catch (error) {
        alert('更新出错: ' + error.message);
    }
}

async function deleteServer(serverId, serverName) {
    if (!confirm(`确定要删除服务器 "${serverName}" 吗？`)) {
        return;
    }
    
    try {
        const response = await ServerAPI.deleteServer(serverId);
        
        if (response.status === 'success') {
            alert('服务器删除成功');
            loadServers();
        } else {
            alert('删除失败: ' + response.message);
        }
    } catch (error) {
        alert('删除出错: ' + error.message);
    }
}

async function testServerConnection(serverId, showNotification = false) {
    try {
        // 如果是通过按钮点击触发的,更新按钮状态
        let btn = null;
        let originalText = '';
        if (event && event.target) {
            btn = event.target;
            originalText = btn.textContent;
            btn.textContent = '测试中...';
            btn.disabled = true;
        }

        // 如果是自动调用且需要显示通知
        if (showNotification) {
            showRefreshNotification('测试连接中...');
        }

        const response = await ServerAPI.testServerConnection(serverId);

        if (response.status === 'success') {
            if (!showNotification) {
                alert('连接成功！服务器已上线');
            } else {
                setTimeout(() => {
                    showRefreshNotification('连接成功');
                }, 500);
            }
            loadServers();
        } else {
            if (!showNotification) {
                alert('连接失败: ' + response.message);
            } else {
                setTimeout(() => {
                    showRefreshNotification('连接失败');
                }, 500);
            }
        }

        if (btn) {
            btn.textContent = originalText;
            btn.disabled = false;
        }
    } catch (error) {
        alert('测试出错: ' + error.message);
        if (event && event.target) {
            event.target.disabled = false;
        }
    }
}

// 事件监听
document.addEventListener('DOMContentLoaded', () => {
    loadServers();

    // 添加服务器按钮
    const addServerBtn = document.getElementById('add-server-btn');
    if (addServerBtn) {
        addServerBtn.addEventListener('click', openAddServerModal);
    }

    // 添加服务器表单提交
    const addServerForm = document.getElementById('add-server-form');
    if (addServerForm) {
        addServerForm.addEventListener('submit', addServer);
    }

    // 编辑服务器表单提交
    const editServerForm = document.getElementById('edit-server-form');
    if (editServerForm) {
        editServerForm.addEventListener('submit', updateServer);
    }

    // 每 10 秒刷新一次服务器列表
    setInterval(loadServers, 10000);
});

// 点击模态框外部关闭
window.addEventListener('click', (event) => {
    const addModal = document.getElementById('add-server-modal');
    const editModal = document.getElementById('edit-server-modal');
    
    if (event.target === addModal) {
        closeAddServerModal();
    }
    if (event.target === editModal) {
        closeEditServerModal();
    }
});
