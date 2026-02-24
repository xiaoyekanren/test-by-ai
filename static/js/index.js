// 首页脚本

async function updateStats() {
    try {
        // 并行获取所有数据，减少等待时间
        const [statusResponse, processResponse] = await Promise.all([
            ServerAPI.getServerStatus(),
            ServerAPI.getProcesses(100) // 只获取前 100 个进程，足够计算进程数
        ]);
        
        if (statusResponse.status === 'success') {
            const data = statusResponse.data;
            
            // 更新 CPU 统计
            const cpuStat = document.getElementById('cpu-stat');
            if (cpuStat) {
                cpuStat.querySelector('.stat-value').textContent = formatPercent(data.cpu.usage);
            }
            
            // 更新内存统计
            const memoryStat = document.getElementById('memory-stat');
            if (memoryStat) {
                memoryStat.querySelector('.stat-value').textContent = formatPercent(data.memory.percent);
            }
            
            // 更新磁盘统计
            const diskStat = document.getElementById('disk-stat');
            if (diskStat) {
                diskStat.querySelector('.stat-value').textContent = formatPercent(data.disk.percent);
            }
        }
        
        // 更新进程数
        if (processResponse.status === 'success') {
            // 由于我们只需要进程数，而不需要具体的进程信息，
            // 我们可以通过获取前 100 个进程来快速获取进程数
            // 这样可以避免获取所有进程导致的服务器响应缓慢
            const processCount = processResponse.data?.length || 0;
            const processStat = document.getElementById('process-stat');
            if (processStat) {
                processStat.querySelector('.stat-value').textContent = processCount;
            }
        }
    } catch (error) {
        console.error('Failed to update stats:', error);
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    updateStats();
    // 每 5 秒更新一次统计信息
    setInterval(updateStats, 5000);
});
