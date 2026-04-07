# backend/app/services/monitoring_service.py
"""
Monitoring service for system status and process management.
Provides both local and remote monitoring capabilities.
"""
import psutil
import logging
from typing import List, Dict, Any, Optional
from ..services.ssh_service import SSHService

logger = logging.getLogger(__name__)


class MonitoringService:
    """Service for monitoring system status and managing processes."""

    def __init__(self):
        self.ssh_service = SSHService()
        logger.info("MonitoringService initialized")

    def get_status(self) -> Dict[str, Any]:
        """Get local system status including CPU, memory, and disk usage.

        Returns:
            Dict containing cpu_percent, memory info, and disk info.
        """
        logger.info("Getting local system status")

        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            logger.debug(f"CPU percent: {cpu_percent}")
        except Exception as e:
            logger.error(f"Failed to get CPU percent: {e}")
            cpu_percent = 0.0

        try:
            memory = psutil.virtual_memory()
            memory_info = {
                "total": memory.total,
                "available": memory.available,
                "percent": memory.percent,
                "used": memory.used,
                "free": memory.free
            }
            logger.debug(f"Memory info: {memory_info}")
        except Exception as e:
            logger.error(f"Failed to get memory info: {e}")
            memory_info = {
                "total": 0,
                "available": 0,
                "percent": 0.0,
                "used": 0,
                "free": 0
            }

        try:
            disk = psutil.disk_usage('/')
            disk_info = {
                "total": disk.total,
                "used": disk.used,
                "free": disk.free,
                "percent": disk.percent
            }
            logger.debug(f"Disk info: {disk_info}")
        except Exception as e:
            logger.error(f"Failed to get disk info: {e}")
            disk_info = {
                "total": 0,
                "used": 0,
                "free": 0,
                "percent": 0.0
            }

        result = {
            "cpu_percent": cpu_percent,
            "memory": memory_info,
            "disk": disk_info
        }

        logger.info(f"Local system status retrieved: CPU={cpu_percent}%, Memory={memory_info['percent']}%, Disk={disk_info['percent']}%")
        return result

    def get_processes(self, limit: int = 50, sort_by: str = "cpu") -> List[Dict[str, Any]]:
        """Get list of local processes sorted by CPU or memory usage.

        Args:
            limit: Maximum number of processes to return (default 50).
            sort_by: Sort field - 'cpu' or 'memory' (default 'cpu').

        Returns:
            List of process dictionaries with pid, name, cpu_percent, memory_percent.
        """
        logger.info(f"Getting local processes with limit={limit}, sort_by={sort_by}")

        processes = []

        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    pinfo = proc.info
                    processes.append({
                        "pid": pinfo['pid'],
                        "name": pinfo['name'] or "",
                        "cpu_percent": pinfo['cpu_percent'] or 0.0,
                        "memory_percent": pinfo['memory_percent'] or 0.0
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                    logger.debug(f"Skipping process due to error: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error iterating processes: {e}")

        # Sort by cpu_percent or memory_percent (descending)
        sort_key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
        logger.debug(f"Sorting processes by {sort_key}")
        processes.sort(key=lambda x: x[sort_key], reverse=True)

        # Limit results
        result = processes[:limit]
        logger.info(f"Retrieved {len(result)} processes (total found: {len(processes)})")
        return result

    def kill_process(self, pid: int) -> Dict[str, Any]:
        """Kill a local process by PID.

        Args:
            pid: Process ID to kill.

        Returns:
            Dict with success status and pid or error message.
        """
        logger.info(f"Attempting to kill process with PID: {pid}")

        try:
            process = psutil.Process(pid)
            process_name = process.name()
            logger.debug(f"Found process: {process_name} (PID: {pid})")

            process.terminate()
            logger.info(f"Successfully sent terminate signal to process {process_name} (PID: {pid})")

            return {
                "success": True,
                "pid": pid,
                "name": process_name
            }
        except psutil.NoSuchProcess:
            logger.warning(f"Process with PID {pid} not found")
            return {
                "success": False,
                "pid": pid,
                "error": f"Process with PID {pid} not found"
            }
        except psutil.AccessDenied as e:
            logger.error(f"Access denied when trying to kill process {pid}: {e}")
            return {
                "success": False,
                "pid": pid,
                "error": f"Access denied: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Failed to kill process {pid}: {e}")
            return {
                "success": False,
                "pid": pid,
                "error": str(e)
            }

    def get_remote_status(self, host: str, username: Optional[str], password: Optional[str],
                          port: int = 22, server_id: Optional[int] = None,
                          server_name: Optional[str] = None) -> Dict[str, Any]:
        """Get remote server status via SSH.

        Uses a single combined shell command to gather CPU, memory, and disk info.

        Args:
            host: Remote server hostname or IP.
            username: SSH username.
            password: SSH password.
            port: SSH port (default 22).
            server_id: Optional server ID for response.
            server_name: Optional server name for response.

        Returns:
            Dict containing server info and system status.
        """
        logger.info(f"Getting remote status for server {server_name} (ID: {server_id}) at {host}")

        result = {
            "server_id": server_id,
            "server_name": server_name,
            "host": host,
            "cpu_percent": 0.0,
            "memory": {"total": 0, "available": 0, "percent": 0.0, "used": 0, "free": 0},
            "disk": {"total": 0, "used": 0, "free": 0, "percent": 0.0}
        }

        # Combined command to get all info in one SSH call
        # Output format: CPU|MEM_TOTAL MEM_USED MEM_FREE MEM_AVAIL|DISK_TOTAL DISK_USED DISK_FREE DISK_PERCENT
        combined_cmd = """
echo "===CPU==="
top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1 || echo "0"
echo "===MEM==="
free -b | grep Mem | awk '{print $2,$3,$4,$7}'
echo "===DISK==="
df -B1 / | tail -1 | awk '{print $2,$3,$4,$5}'
"""

        try:
            cmd_result = self.ssh_service.run_command(host, username, password, combined_cmd, port)
            if cmd_result.exit_status == 0 and cmd_result.stdout.strip():
                output = cmd_result.stdout.strip()

                # Parse CPU
                try:
                    cpu_section = output.split("===CPU===")[1].split("===MEM===")[0].strip()
                    result["cpu_percent"] = float(cpu_section.split()[0])
                except (ValueError, IndexError, KeyError):
                    result["cpu_percent"] = 0.0

                # Parse Memory
                try:
                    mem_section = output.split("===MEM===")[1].split("===DISK===")[0].strip()
                    parts = mem_section.split()
                    if len(parts) >= 4:
                        total = int(parts[0])
                        used = int(parts[1])
                        free = int(parts[2])
                        available = int(parts[3])
                        percent = (used / total * 100) if total > 0 else 0
                        result["memory"] = {
                            "total": total,
                            "available": available,
                            "percent": round(percent, 1),
                            "used": used,
                            "free": free
                        }
                except (ValueError, IndexError, KeyError):
                    pass

                # Parse Disk
                try:
                    disk_section = output.split("===DISK===")[1].strip()
                    parts = disk_section.split()
                    if len(parts) >= 4:
                        total = int(parts[0])
                        used = int(parts[1])
                        free = int(parts[2])
                        percent = float(parts[3].rstrip('%'))
                        result["disk"] = {
                            "total": total,
                            "used": used,
                            "free": free,
                            "percent": percent
                        }
                except (ValueError, IndexError, KeyError):
                    pass

                logger.info(f"Retrieved remote status for {server_name}: CPU={result['cpu_percent']}%, "
                           f"Memory={result['memory']['percent']}%, Disk={result['disk']['percent']}%")
        except Exception as e:
            logger.warning(f"Failed to get remote status for {server_name}: {e}")

        return result

    def get_remote_processes(self, host: str, username: Optional[str], password: Optional[str],
                             port: int = 22, limit: int = 50, sort_by: str = "cpu",
                             server_id: Optional[int] = None,
                             server_name: Optional[str] = None) -> Dict[str, Any]:
        """Get list of processes from remote server via SSH.

        Args:
            host: Remote server hostname or IP.
            username: SSH username.
            password: SSH password.
            port: SSH port (default 22).
            limit: Maximum number of processes to return.
            sort_by: Sort field - 'cpu' or 'memory'.
            server_id: Optional server ID for response.
            server_name: Optional server name for response.

        Returns:
            Dict containing server info and list of processes.
        """
        logger.info(f"Getting remote processes for server {server_name} (ID: {server_id}) at {host}")

        result = {
            "server_id": server_id,
            "server_name": server_name,
            "host": host,
            "processes": []
        }

        # Use ps command to get process list
        # Format: PID, %CPU, %MEM, COMM
        sort_flag = "-pcpu" if sort_by == "cpu" else "-pmem"
        ps_cmd = f"ps aux --sort={sort_flag} | head -n {limit + 1} | tail -n {limit}"

        try:
            proc_result = self.ssh_service.run_command(host, username, password, ps_cmd, port)
            if proc_result.exit_status == 0 and proc_result.stdout.strip():
                processes = []
                for line in proc_result.stdout.strip().split('\n'):
                    parts = line.split(None, 10)  # Split into max 11 parts
                    if len(parts) >= 11:
                        try:
                            processes.append({
                                "pid": int(parts[1]),
                                "name": parts[10][:50] if len(parts[10]) > 50 else parts[10],  # Limit name length
                                "cpu_percent": float(parts[2]),
                                "memory_percent": float(parts[3])
                            })
                        except (ValueError, IndexError) as e:
                            logger.debug(f"Skipping malformed process line: {line} - {e}")
                            continue

                result["processes"] = processes
                logger.info(f"Retrieved {len(processes)} processes from remote server {server_name}")
        except Exception as e:
            logger.error(f"Failed to get remote processes: {e}")

        return result