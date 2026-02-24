// 首页脚本

async function updateStats() {
    try {
        const response = await ServerAPI.getServerStatus();
        
        if (response.status === 'success') {
            const data = response.data;
            
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
            
            // 获取进程数
            const processResponse = await ServerAPI.getProcesses(1);
            if (processResponse.status === 'success') {
                // 获取真实进程数
                const allProcesses = await fetch('http://localhost:5001/api/server/processes?limit=10000')
                    .then(r => r.json())
                    .catch(() => ({ data: [] }));
                
                const processStat = document.getElementById('process-stat');
                if (processStat) {
                    processStat.querySelector('.stat-value').textContent = allProcesses.data?.length || '--';
                }
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
