// API 调用模块

const API_BASE_URL = 'http://localhost:5001/api';

class ServerAPI {
    static async getServerStatus() {
        return this.request('/server/status');
    }

    static async getProcesses(limit = 20, sortBy = 'memory') {
        return this.request(`/server/processes?limit=${limit}&sort_by=${sortBy}`);
    }

    static async getNetworkInfo() {
        return this.request('/server/network');
    }

    static async getDiskInfo() {
        return this.request('/server/disk');
    }

    static async getProcessDetail(pid) {
        return this.request(`/process/${pid}`);
    }

    static async killProcess(pid) {
        return this.request(`/process/${pid}/kill`, {
            method: 'POST'
        });
    }

    static async getServices() {
        return this.request('/services');
    }

    static async createService(serviceData) {
        return this.request('/services', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(serviceData)
        });
    }

    // ==================== 服务器管理 API ====================

    static async listServers() {
        return this.request('/servers');
    }

    static async addServer(serverData) {
        return this.request('/servers', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(serverData)
        });
    }

    static async getServer(serverId) {
        return this.request(`/servers/${serverId}`);
    }

    static async updateServer(serverId, serverData) {
        return this.request(`/servers/${serverId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(serverData)
        });
    }

    static async deleteServer(serverId) {
        return this.request(`/servers/${serverId}`, {
            method: 'DELETE'
        });
    }

    static async testServerConnection(serverId) {
        return this.request(`/servers/${serverId}/test`, {
            method: 'POST'
        });
    }
    
    static async executeCommand(serverId, command) {
        return this.request(`/servers/${serverId}/execute`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ command })
        });
    }
    
    static async uploadFile(serverId, file, remotePath) {
        const form = new FormData()
        form.append('file', file)
        form.append('remote_path', remotePath)
        return this.request(`/servers/${serverId}/upload`, {
            method: 'POST',
            body: form,
            headers: {}
        })
    }

    static async request(endpoint, options = {}) {
        const url = API_BASE_URL + endpoint;
        const defaultOptions = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        };

        const finalOptions = { ...defaultOptions, ...options };
        if (finalOptions.body instanceof FormData) {
            delete finalOptions.headers['Content-Type'];
        }

        try {
            const response = await fetch(url, finalOptions);
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            return {
                status: 'error',
                message: error.message
            };
        }
    }
}

// 工具函数

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function formatPercent(value, decimals = 2) {
    return value.toFixed(decimals) + '%';
}

function updateCurrentTime() {
    const now = new Date();
    const timeStr = now.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    
    const elements = document.querySelectorAll('#current-time');
    elements.forEach(el => {
        el.textContent = timeStr;
    });
}

// 仅在非 integrated 页面上启用时间更新
// integrated.js 会处理自己的时间更新
if (!window.location.pathname.includes('/integrated')) {
    setInterval(updateCurrentTime, 1000);
    updateCurrentTime();
}
