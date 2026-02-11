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
    const dashboard = document.getElementById('multi-host-dashboard');
    if (!dashboard) {
        console.error('未找到 multi-host-dashboard 元素');
        return;
    }

    dashboard.innerHTML = '';

    // 添加标题行
    const headerRow = createHeaderRow();
    dashboard.appendChild(headerRow);

    // 添加主机列表容器
    const hostList = document.createElement('div');
    hostList.className = 'host-list';
    hostList.id = 'host-list';
    dashboard.appendChild(hostList);

    // 本地主机
    const localCard = createHostCard('local', '本地主机 (localhost)');
    hostList.appendChild(localCard);
    hostMonitors['local'] = {
        hostName: '本地主机',
        failures: 0,
        intervals: []
    };

    // 远程服务器
    serversList.forEach(server => {
        const card = createHostCard(String(server.id), `${server.name} (${server.host})`);
        hostList.appendChild(card);
        hostMonitors[String(server.id)] = {
            hostName: server.name,
            failures: 0,
            intervals: []
        };
    });

    console.log(`已初始化 ${Object.keys(hostMonitors).length} 个主机的监控`);

    // 开始轮询
    startAllPolling();
}

function createHeaderRow() {
    const header = document.createElement('div');
    header.className = 'monitor-header';

    header.innerHTML = `
        <div class="header-cell host-name">主机名称</div>
        <div class="header-cell cpu">CPU</div>
        <div class="header-cell memory">内存</div>
        <div class="header-cell stat">CPU 核心</div>
        <div class="header-cell stat">总内存</div>
        <div class="header-cell stat">内存使用</div>
        <div class="header-cell stat">磁盘使用</div>
        <div class="header-cell stat">状态</div>
    `;

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

function startAllPolling() {
    console.log('开始启动轮询...');
    for (const hostKey in hostMonitors) {
        const host = hostMonitors[hostKey];
        
        // 立即执行一次
        updateDashboardForHost(hostKey);
        
        // 设置定时器
        const interval = hostKey === 'local' ? 2000 : 5000; // 本地 2s，远程 5s
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
    const interval = hostKey === 'local' ? 2000 : 5000; // 本地 2s，远程 5s
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
