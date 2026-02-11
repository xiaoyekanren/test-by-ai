// 集成监控面板脚本 - 多主机版本

const hostMonitors = {};    // 每个主机的监控实例 {hostKey: {charts, intervals, failures, ...}}
let serversList = [];       // 服务器列表（来自 API）
let lastErrorNotification = {};  // 防止重复通知

// ==================== 错误诊断和提示 ====================

const diagnosisMessages = {
    'SSHFail': {
        title: 'SSH 连接失败',
        message: '无法通过 SSH 连接到该服务器。请检查凭证和网络连接。',
        icon: '⚠️'
    },
    'Limited': {
        title: '功能受限',
        message: '该服务器不支持完整的 psutil 查询，仅显示基本信息。',
        icon: '⚡'
    },
    'ParseError': {
        title: '数据解析错误',
        message: '无法解析从服务器收到的数据。',
        icon: '❌'
    },
    'KillFailed': {
        title: '进程终止失败',
        message: '无法终止指定的进程。',
        icon: '🔪'
    },
    'NotImplemented': {
        title: '功能未实现',
        message: '该操作暂未实现。',
        icon: '🛠️'
    }
};

function showErrorNotification(hostName, diagnosis) {
    const key = `${hostName}-${diagnosis}`;
    const now = Date.now();
    const lastTime = lastErrorNotification[key]?.timestamp || 0;
    
    if (now - lastTime < 5000) {
        return;
    }
    
    lastErrorNotification[key] = { diagnosis, timestamp: now };
    
    const config = diagnosisMessages[diagnosis] || { title: diagnosis, message: '发生错误', icon: '❌' };
    const container = document.getElementById('error-notification');
    
    if (!container) return;
    
    const notification = document.createElement('div');
    notification.className = 'error-toast';
    notification.innerHTML = `
        <span class="error-icon">${config.icon}</span>
        <div class="error-content">
            <strong>${config.title} (${hostName})</strong>
            <p>${config.message}</p>
        </div>
        <button class="error-close" onclick="this.parentElement.remove()">&times;</button>
    `;
    
    container.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

// ==================== API 请求函数 ====================

async function fetchStatusForHost(hostKey) {
    const host = hostMonitors[hostKey];
    if (!host) return null;
    
    let baseUrl;
    if (hostKey === 'local') {
        baseUrl = '/api';
    } else {
        baseUrl = `/api/servers/${hostKey}/proxy`;
    }
    
    try {
        console.log(`[${hostKey}] 正在获取状态: ${baseUrl}/server/status`);
        
        // 使用 AbortController 实现超时
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);
        
        const response = await fetch(`${baseUrl}/server/status`, {
            signal: controller.signal
        });
        clearTimeout(timeoutId);
        
        const data = await response.json();
        console.log(`[${hostKey}] 响应数据:`, data);
        return {hostKey, data};
    } catch (error) {
        console.error(`[${hostKey}] 状态获取失败:`, error);
        return {hostKey, error};
    }
}

// ==================== 初始化和渲染 ====================

async function loadServersList() {
    try {
        console.log('正在加载服务器列表...');
        const response = await ServerAPI.listServers();
        console.log('服务器列表响应:', response);
        if (response.status === 'success') {
            serversList = response.data;
            console.log(`已加载 ${serversList.length} 个远程服务器`);
        }
    } catch (error) {
        console.error('加载服务器列表失败:', error);
    }
}

function initializeMonitors() {
    renderDashboard();
    // 启动轮询
    startAllPolling();
}

let monitorSortState = { field: 'name', direction: 'asc' }; // 监控面板排序状态

function renderDashboard() {
    const dashboard = document.getElementById('multi-host-dashboard');
    if (!dashboard) {
        console.error('未找到 multi-host-dashboard 元素');
        return;
    }

    // 移除初始加载提示（如果存在）
    const loadingEl = dashboard.querySelector('.loading');
    if (loadingEl) {
        loadingEl.remove();
    }

    // 确保标题行存在
    let headerRow = dashboard.querySelector('.monitor-header');
    if (!headerRow) {
        headerRow = createHeaderRow();
        dashboard.insertBefore(headerRow, dashboard.firstChild);
    } else {
        // 更新标题行（排序图标可能变化）
        const newHeader = createHeaderRow();
        dashboard.replaceChild(newHeader, headerRow);
    }

    // 分组逻辑
    const groups = {
        '本地环境': []
    };
    
    // 初始化本地主机
    if (!hostMonitors['local']) {
        hostMonitors['local'] = {
            hostName: '本地主机',
            failures: 0,
            intervals: []
        };
    }
    groups['本地环境'].push({ key: 'local', name: '本地主机 (localhost)' });

    // 处理远程服务器分组
    const noTagServers = [];
    
    serversList.forEach(server => {
        // 初始化监控对象（如果不存在）
        const serverKey = String(server.id);
        if (!hostMonitors[serverKey]) {
            hostMonitors[serverKey] = {
                hostName: server.name,
                failures: 0,
                intervals: []
            };
        }
        
        const serverObj = { key: serverKey, name: `${server.name} (${server.host})` };

        if (server.tags && server.tags.trim()) {
            // 只取第一个标签作为主分组，避免重复显示
            const tags = server.tags.split(',').map(t => t.trim()).filter(t => t);
            if (tags.length > 0) {
                const primaryTag = tags[0];
                if (!groups[primaryTag]) {
                    groups[primaryTag] = [];
                }
                groups[primaryTag].push(serverObj);
            } else {
                noTagServers.push(serverObj);
            }
        } else {
            noTagServers.push(serverObj);
        }
    });

    // 收集所有需要显示的分组键，按顺序排列
    const groupKeys = [];
    if (groups['本地环境'].length > 0) groupKeys.push('本地环境');
    
    Object.keys(groups).sort().forEach(tag => {
        if (tag !== '本地环境') groupKeys.push(tag);
    });
    
    if (noTagServers.length > 0) {
        groups['未分类'] = noTagServers;
        groupKeys.push('未分类');
    }

    // 增量更新分组容器
    const existingGroups = Array.from(dashboard.querySelectorAll('.server-group'));
    const processedGroupIds = new Set();

    groupKeys.forEach(title => {
        const groupId = `group-${title}`; // 简单 ID，假设 title 不含特殊字符
        let groupContainer = document.getElementById(groupId);
        
        if (!groupContainer) {
            groupContainer = createGroupContainerElement(title, groupId);
            dashboard.appendChild(groupContainer);
        } else {
            // 确保顺序：将现有容器移动到末尾（即当前处理位置）
            dashboard.appendChild(groupContainer);
        }
        
        updateGroupContent(groupContainer, groups[title]);
        processedGroupIds.add(groupId);
    });

    // 移除不再存在的分组
    existingGroups.forEach(group => {
        if (!processedGroupIds.has(group.id)) {
            group.remove();
        }
    });

    console.log(`已更新监控面板布局`);
}

function createGroupContainerElement(title, id) {
    const container = document.createElement('div');
    container.className = 'server-group';
    container.id = id;
    container.style.marginBottom = '0';
    container.style.borderBottom = '1px solid var(--border-color)';
    container.style.borderRadius = '0';
    container.style.boxShadow = 'none';
    container.style.border = 'none';

    const header = document.createElement('div');
    header.className = 'group-header';
    header.style.padding = '8px 16px';
    header.style.background = '#f3f4f6';
    header.innerHTML = `
        <div class="group-title" style="font-size: 13px;">🏷️ ${title}</div>
        <div class="group-count">0</div>
    `;
    container.appendChild(header);

    const list = document.createElement('div');
    list.className = 'host-list';
    container.appendChild(list);

    return container;
}

function updateGroupContent(container, servers) {
    // 更新计数
    const countDiv = container.querySelector('.group-count');
    if (countDiv) countDiv.textContent = servers.length;

    const list = container.querySelector('.host-list');
    
    // 对组内服务器进行排序
    const sortedServers = [...servers].sort((a, b) => {
        const valA = getSortValue(a.key, monitorSortState.field);
        const valB = getSortValue(b.key, monitorSortState.field);
        
        if (valA < valB) return monitorSortState.direction === 'asc' ? -1 : 1;
        if (valA > valB) return monitorSortState.direction === 'asc' ? 1 : -1;
        return 0;
    });

    const processedServerKeys = new Set();

    sortedServers.forEach(server => {
        const cardId = `host-card-${server.key}`;
        let card = document.getElementById(cardId);

        if (!card) {
            // 创建新卡片
            card = createHostCard(server.key, server.name);
            list.appendChild(card);
            // 尝试填充初始数据
            const host = hostMonitors[server.key];
            if (host && host.lastData) {
                fillHostCardData(server.key, host.lastData);
            }
        } else {
            // 移动现有卡片到当前位置（自动处理排序）
            list.appendChild(card);
        }
        processedServerKeys.add(server.key);
    });

    // 移除该组中不再需要的卡片（例如服务器被移动到别的组，或被删除）
    // 注意：这里只移除当前组内的多余卡片。
    // 如果卡片被移动到了另一个组，上面的循环中它已经被 appendChild 走了，
    // 所以这里剩下的 children 都是不再属于任何组（或属于本组但应该被删除）的。
    // 但因为 getElementById 是全局的，如果卡片还在其他组，这里其实访问不到（除非它还在这个 list 的 children 里）。
    
    // 更安全的做法：遍历 list 的所有直接子元素
    Array.from(list.children).forEach(child => {
        // 从 id 提取 key: host-card-local -> local
        const key = child.id.replace('host-card-', '');
        if (!processedServerKeys.has(key)) {
            child.remove();
        }
    });
}

// 移除不再使用的函数
// function createGroupContainer(...) {} 已经被拆分和重构

function getSortValue(hostKey, field) {
    const host = hostMonitors[hostKey];
    if (!host) return 0;

    // 静态字段
    if (field === 'name') return host.hostName || '';
    if (field === 'status') {
        // 简单的状态排序：在线 > 离线 > 未知
        // 我们没有直接存储 status 字符串，但有 failures 计数
        // failures > 3 为离线
        return host.failures > 3 ? 0 : 1; 
    }

    // 动态字段，从 lastData 中获取
    const data = host.lastData;
    if (!data) return -1; // 无数据排在最后（或最前，取决于需求）

    switch (field) {
        case 'cpu': return data.cpu?.usage || 0;
        case 'memory': return data.memory?.percent || 0;
        case 'cores': return data.cpu?.count || 0;
        case 'mem_total': return data.memory?.total || 0;
        case 'mem_used': return data.memory?.used || 0;
        case 'disk': return data.disk?.percent || 0;
        default: return 0;
    }
}

function sortMonitor(field) {
    if (monitorSortState.field === field) {
        monitorSortState.direction = monitorSortState.direction === 'asc' ? 'desc' : 'asc';
    } else {
        monitorSortState.field = field;
        monitorSortState.direction = 'desc'; // 数值型默认降序更符合直觉
        if (field === 'name') monitorSortState.direction = 'asc'; // 名称默认升序
    }
    renderDashboard();
}

function createHeaderRow() {
    const header = document.createElement('div');
    header.className = 'monitor-header';
    
    const fields = [
        { key: 'name', label: '主机名称', class: 'host-name' },
        { key: 'cpu', label: 'CPU', class: 'cpu' },
        { key: 'memory', label: '内存', class: 'memory' },
        { key: 'cores', label: 'CPU 核心', class: 'stat' },
        { key: 'mem_total', label: '总内存', class: 'stat' },
        { key: 'mem_used', label: '内存使用', class: 'stat' },
        { key: 'disk', label: '磁盘使用', class: 'stat' },
        { key: 'status', label: '状态', class: 'stat' }
    ];

    const headerCells = fields.map(field => {
        const isSorted = monitorSortState.field === field.key;
        const sortClass = isSorted ? (monitorSortState.direction === 'asc' ? 'sort-asc' : 'sort-desc') : '';
        return `
            <div class="header-cell ${field.class} ${sortClass}" onclick="sortMonitor('${field.key}')" style="cursor: pointer; user-select: none;">
                ${field.label}<span class="sort-icon"></span>
            </div>
        `;
    }).join('');

    header.innerHTML = headerCells;
    return header;
}

function createHostCard(hostKey, hostName) {
    const card = document.createElement('div');
    card.className = 'host-row';
    card.id = `host-card-${hostKey}`;

    // 提取主机名（去除IP地址部分）
    let displayName = hostName.split(' (')[0];
    
    // 截断逻辑：最大15个字符，保留12个 + "..."
    const MAX_LENGTH = 15;
    if (displayName.length > MAX_LENGTH) {
        displayName = displayName.substring(0, MAX_LENGTH - 3) + '...';
    }

    card.innerHTML = `
        <div class="host-name" title="${hostName}">${displayName}</div>
        <div class="host-item">
            <div class="progress-bar">
                <div class="progress-fill cpu" id="cpu-progress-${hostKey}" style="width: 0%"></div>
            </div>
            <span class="progress-value" id="cpu-value-${hostKey}">0%</span>
        </div>
        <div class="host-item">
            <div class="progress-bar">
                <div class="progress-fill memory" id="mem-progress-${hostKey}" style="width: 0%"></div>
            </div>
            <span class="progress-value" id="mem-value-${hostKey}">0%</span>
        </div>
        <div class="host-stat-value" id="cores-${hostKey}">--</div>
        <div class="host-stat-value" id="mem-total-${hostKey}">--</div>
        <div class="host-stat-value" id="mem-used-${hostKey}">--</div>
        <div class="host-stat-value" id="disk-percent-${hostKey}">--</div>
        <div class="host-card-status" id="status-${hostKey}">检查中...</div>
    `;

    return card;
}

// ==================== 轮询和更新 ====================

// ==================== 辅助函数 ====================

function fillHostCardData(hostKey, sysData) {
    if (!sysData) return;

    // 更新 CPU 信息
    if (sysData.cpu) {
        const cpuUsage = sysData.cpu.usage || 0;
        const cpuCount = sysData.cpu.count || 1;

        const cpuProgress = document.getElementById(`cpu-progress-${hostKey}`);
        const cpuValue = document.getElementById(`cpu-value-${hostKey}`);
        if (cpuProgress) cpuProgress.style.width = `${Math.min(cpuUsage, 100)}%`;
        if (cpuValue) cpuValue.textContent = `${cpuUsage.toFixed(0)}%`;

        const coresDiv = document.getElementById(`cores-${hostKey}`);
        if (coresDiv) coresDiv.textContent = cpuCount;
    }

    // 更新内存信息
    if (sysData.memory) {
        const memTotal = sysData.memory.total || 0;
        const memUsed = sysData.memory.used || 0;
        const memPercent = sysData.memory.percent || 0;

        const memProgress = document.getElementById(`mem-progress-${hostKey}`);
        const memValue = document.getElementById(`mem-value-${hostKey}`);
        if (memProgress) memProgress.style.width = `${Math.min(memPercent, 100)}%`;
        if (memValue) memValue.textContent = `${memPercent.toFixed(0)}%`;

        const memTotalDiv = document.getElementById(`mem-total-${hostKey}`);
        if (memTotalDiv) memTotalDiv.textContent = formatBytes(memTotal);

        const memUsedDiv = document.getElementById(`mem-used-${hostKey}`);
        if (memUsedDiv) memUsedDiv.textContent = formatBytes(memUsed);
    }

    // 更新磁盘信息
    if (sysData.disk) {
        const diskPercent = sysData.disk.percent || 0;
        const diskPercentDiv = document.getElementById(`disk-percent-${hostKey}`);
        if (diskPercentDiv) diskPercentDiv.textContent = `${diskPercent.toFixed(1)}%`;
    }
}

function startAllPolling() {
    console.log('开始启动轮询...');
    for (const hostKey in hostMonitors) {
        const host = hostMonitors[hostKey];
        
        // 立即执行一次
        updateDashboardForHost(hostKey);
        
        // 设置定时器
        const interval = hostKey === 'local' ? 5000 : 5000; // 本地 5s，远程 5s
        console.log(`[${hostKey}] 设置轮询间隔: ${interval}ms`);
        
        const intervalId = setInterval(() => {
            updateDashboardForHost(hostKey);
        }, interval);
        
        host.intervals.push(intervalId);
    }
}

async function updateDashboardForHost(hostKey) {
    const host = hostMonitors[hostKey];
    if (!host) return;
    
    const result = await fetchStatusForHost(hostKey);
    
    if (result.error) {
        console.error(`[${hostKey}] 获取数据失败:`, result.error);
        host.failures++;
        
        if (host.failures > 3) {
            const statusDiv = document.getElementById(`status-${hostKey}`);
            if (statusDiv) {
                statusDiv.textContent = '离线';
                statusDiv.className = 'host-card-status offline';
            }
        }
        return;
    }
    
    const data = result.data;
    
    // 缓存最新数据，用于排序
    host.lastData = data.data;

    // 检查诊断信息
    if (data.diagnosis && data.diagnosis !== 'success') {
        console.warn(`[${hostKey}] 诊断信息: ${data.diagnosis}`);
        // showErrorNotification(host.hostName, data.diagnosis);
    }

    // 重置失败计数
    host.failures = 0;

    // 更新状态
    const statusDiv = document.getElementById(`status-${hostKey}`);
    if (statusDiv) {
        statusDiv.textContent = '在线';
        statusDiv.className = 'host-card-status online';
    }

    // 提取数据
    if (!data.data) {
        console.warn(`[${hostKey}] 没有数据字段`, data);
        return;
    }

    const sysData = data.data;

    // 更新 CPU 信息
    if (sysData.cpu) {
        const cpuUsage = sysData.cpu.usage || 0;
        const cpuCount = sysData.cpu.count || 1;

        // 更新进度条
        const cpuProgress = document.getElementById(`cpu-progress-${hostKey}`);
        const cpuValue = document.getElementById(`cpu-value-${hostKey}`);
        if (cpuProgress) cpuProgress.style.width = `${Math.min(cpuUsage, 100)}%`;
        if (cpuValue) cpuValue.textContent = `${cpuUsage.toFixed(0)}%`;

        const coresDiv = document.getElementById(`cores-${hostKey}`);
        if (coresDiv) coresDiv.textContent = cpuCount;
    }

    // 更新内存信息
    if (sysData.memory) {
        const memTotal = sysData.memory.total || 0;
        const memUsed = sysData.memory.used || 0;
        const memPercent = sysData.memory.percent || 0;

        // 更新进度条
        const memProgress = document.getElementById(`mem-progress-${hostKey}`);
        const memValue = document.getElementById(`mem-value-${hostKey}`);
        if (memProgress) memProgress.style.width = `${Math.min(memPercent, 100)}%`;
        if (memValue) memValue.textContent = `${memPercent.toFixed(0)}%`;

        const memTotalDiv = document.getElementById(`mem-total-${hostKey}`);
        if (memTotalDiv) {
            memTotalDiv.textContent = formatBytes(memTotal);
        }

        const memUsedDiv = document.getElementById(`mem-used-${hostKey}`);
        if (memUsedDiv) {
            memUsedDiv.textContent = formatBytes(memUsed);
        }
    }

    // 更新磁盘信息
    if (sysData.disk) {
        const diskPercent = sysData.disk.percent || 0;
        const diskPercentDiv = document.getElementById(`disk-percent-${hostKey}`);
        if (diskPercentDiv) {
            diskPercentDiv.textContent = `${diskPercent.toFixed(1)}%`;
        }
    }
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i];
}

// ==================== 页面初始化 ====================

document.addEventListener('DOMContentLoaded', async () => {
    console.log('页面已加载，开始初始化集成监控面板...');
    await loadServersList();
    initializeMonitors();
    updateCurrentTime();
    setInterval(updateCurrentTime, 1000);

    // 定期刷新服务器列表（每30秒），以支持动态添加新服务器
    setInterval(async () => {
        console.log('定时刷新服务器列表...');
        await loadServersList();
        refreshMonitors();
    }, 30000);
});

// ==================== 动态刷新监控器 ====================

function refreshMonitors() {
    const dashboard = document.getElementById('multi-host-dashboard');
    if (!dashboard) {
        console.error('未找到 multi-host-dashboard 元素');
        return;
    }

    const hostList = document.getElementById('host-list');
    if (!hostList) {
        console.error('未找到 host-list 元素');
        return;
    }

    // 检查是否有新的服务器需要添加
    const currentHostKeys = Object.keys(hostMonitors);

    // 检查本地主机
    if (!currentHostKeys.includes('local')) {
        console.log('添加本地主机监控...');
        const localCard = createHostCard('local', '本地主机 (localhost)');
        hostList.appendChild(localCard);
        hostMonitors['local'] = {
            hostName: '本地主机',
            failures: 0,
            intervals: []
        };
        startPollingForHost('local');
    }

    // 检查远程服务器
    serversList.forEach(server => {
        const serverKey = String(server.id);
        if (!currentHostKeys.includes(serverKey)) {
            console.log(`添加新服务器监控: ${server.name} (${server.host})`);
            const card = createHostCard(serverKey, `${server.name} (${server.host})`);
            hostList.appendChild(card);
            hostMonitors[serverKey] = {
                hostName: server.name,
                failures: 0,
                intervals: []
            };
            startPollingForHost(serverKey);
        }
    });

    console.log(`监控器刷新完成，当前共有 ${Object.keys(hostMonitors).length} 个主机在监控中`);
}

function startPollingForHost(hostKey) {
    // 立即执行一次
    updateDashboardForHost(hostKey);

    // 设置定时器
    const interval = hostKey === 'local' ? 5000 : 5000; // 本地 5s，远程 5s
    console.log(`[${hostKey}] 设置轮询间隔: ${interval}ms`);

    const intervalId = setInterval(() => {
        updateDashboardForHost(hostKey);
    }, interval);

    hostMonitors[hostKey].intervals.push(intervalId);
}

function updateCurrentTime() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('zh-CN');
    const timeDiv = document.getElementById('current-time');
    if (timeDiv) {
        timeDiv.textContent = '当前时间: ' + timeStr;
    }
}
