import paramiko


def ssh_run_command(server, command, timeout=5, logger=None):
    """通过 SSH 在远程主机上运行命令，返回字典包含 stdout/stderr/exit_status 或 error."""
    host = server.get('host')
    username = server.get('username') or None
    password = server.get('password') or None
    
    ports_to_try = [22]
    # 如果数据库里保存了端口，尝试备用端口（兼容旧字段）
    try:
        if server.get('port'):
            ports_to_try.append(int(server.get('port')))
    except Exception:
        pass

    if logger:
        logger.info(f"🔐 Attempting SSH to {host} with username={username}, ports={ports_to_try}")
    last_exc = None
    for ssh_port in ports_to_try:
        try:
            if logger:
                logger.debug(f"  Trying SSH port {ssh_port}...")
            client = paramiko.SSHClient()
            client.load_system_host_keys()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            client.connect(hostname=host, port=ssh_port, username=username, password=password, timeout=timeout)
            if logger:
                logger.info(f"  ✓ SSH connected on port {ssh_port}. Executing: {command[:80]}...")
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            out = stdout.read().decode('utf-8', errors='ignore')
            err = stderr.read().decode('utf-8', errors='ignore')
            exit_status = stdout.channel.recv_exit_status()
            client.close()
            if logger:
                logger.info(f"  ✓ SSH command succeeded with exit_status={exit_status}")
            return {'exit_status': exit_status, 'stdout': out, 'stderr': err, 'ssh_port': ssh_port}
        except paramiko.AuthenticationException as e:
            last_exc = e
            if logger:
                logger.warning(f"❌ SSH auth failed to {host}:{ssh_port}: {str(e)[:100]}")
            continue
        except paramiko.SSHException as e:
            last_exc = e
            if logger:
                logger.warning(f"❌ SSH protocol error to {host}:{ssh_port}: {str(e)[:100]}")
            continue
        except Exception as e:
            last_exc = e
            if logger:
                logger.warning(f"❌ SSH error to {host}:{ssh_port}: {type(e).__name__}: {str(e)[:100]}")
            continue

    error_msg = str(last_exc) if last_exc else 'SSH connection failed'
    if logger:
        logger.error(f"❌ SSH all ports failed for {host}: {error_msg}")
    return {'error': error_msg}


def fetch_remote_api(server, path, params=None, method='GET', json_data=None, timeout=5, logger=None):
    """使用 SSH 从远程主机收集监控数据或执行操作；直接使用 shell 命令收集，不尝试远程 psutil。
    返回与原先 API 兼容的 JSON-like dict。"""
    if logger:
        logger.info(f"🔌 SSH proxy request to {server.get('host')} path={path} method={method}")
        logger.debug(f"   Server details: host={server.get('host')}, port={server.get('port')}, user={server.get('username')}")

    # 获取系统状态
    if path == '/api/server/status':
        # 使用一组 shell 命令来获取CPU、内存、磁盘信息
        fallback_cmd = (
            "(nproc || echo '1') && "
            "(average=$(uptime | grep -oP 'average: \\K[0-9.]+' || echo '0'); echo $average) && "
            "(free -b | awk '/^Mem:/ {print $2, $3}' || echo '0 0') && "
            "(df -B1 / | tail -1 | awk '{print $2, $3, $(NF-1)}' || echo '0 0 0')"
        )
        res2 = ssh_run_command(server, fallback_cmd, timeout=timeout, logger=logger)
        if res2.get('error') or res2.get('exit_status', 1) != 0:
            if logger:
                logger.error(f"  ❌ Fallback failed: {res2.get('error')}")
            return {'status': 'error', 'message': res2.get('error'), 'diagnosis': 'SSHFail'}
        
        # 解析 shell 输出
        try:
            lines = res2.get('stdout', '').strip().split('\n')
            cpu_count = int(lines[0].strip()) if len(lines) > 0 else 1
            cpu_usage = float(lines[1].strip()) if len(lines) > 1 else 0
            
            mem_data = lines[2].strip().split() if len(lines) > 2 else ['0', '0']
            mem_total = int(mem_data[0]) if len(mem_data) > 0 else 0
            mem_used = int(mem_data[1]) if len(mem_data) > 1 else 0
            mem_percent = (mem_used / mem_total * 100) if mem_total > 0 else 0
            
            disk_data = lines[3].strip().split() if len(lines) > 3 else ['0', '0', '0']
            disk_total = int(disk_data[0]) if len(disk_data) > 0 else 0
            disk_used = int(disk_data[1]) if len(disk_data) > 1 else 0
            disk_percent_str = disk_data[2] if len(disk_data) > 2 else '0%'
            disk_percent = float(disk_percent_str.rstrip('%')) if disk_percent_str.endswith('%') else 0
            
            if logger:
                logger.info(f"  ✓ Parsed shell fallback: cpu_count={cpu_count}, mem={mem_percent:.1f}%, disk={disk_percent:.1f}%")
            
            return {
                'status': 'success',
                'data': {
                    'cpu': {'count': cpu_count, 'usage': cpu_usage},
                    'memory': {'total': mem_total, 'used': mem_used, 'available': mem_total - mem_used, 'percent': mem_percent},
                    'disk': {'total': disk_total, 'used': disk_used, 'free': disk_total - disk_used, 'percent': disk_percent}
                },
                'diagnosis': 'Limited'
            }
        except Exception as e:
            if logger:
                logger.warning(f"  ⚠️  Failed to parse shell fallback: {str(e)[:80]}, returning raw output")
            return {'status': 'success', 'data': {'raw': res2.get('stdout', '')}, 'diagnosis': 'Limited'}

    # 列表进程
    if path.startswith('/api/server/processes'):
        limit = int(params.get('limit', 20)) if params else 20
        # 直接使用 ps 命令
        cmd2 = f"ps -eo pid,comm,%cpu,%mem --sort=-%mem | head -n {limit+1}"
        res2 = ssh_run_command(server, cmd2, timeout=timeout, logger=logger)
        if res2.get('error') or res2.get('exit_status', 1) != 0:
            if logger:
                logger.error(f"  ❌ ps command failed: {res2.get('error')}")
            return {'status': 'error', 'message': res2.get('error'), 'diagnosis': 'SSHFail'}
        lines = res2.get('stdout','').strip().splitlines()
        procs = []
        for line in lines[1:]:
            parts = line.split()
            if len(parts) >= 4:
                pid = parts[0]
                name = parts[1]
                cpu = parts[2]
                mem = parts[3]
                try:
                    procs.append({'pid': int(pid), 'name': name, 'cpu': float(cpu), 'memory': float(mem)})
                except Exception:
                    continue
        if logger:
            logger.info(f"  ✓ Parsed {len(procs)} processes from ps output")
        return {'status':'success','data':procs}

    # 强制 kill
    if path.startswith('/api/process/') and path.endswith('/kill'):

        # path format: /api/process/{pid}/kill
        try:
            pid = int(path.split('/')[3])
        except Exception:
            if logger:
                logger.warning(f"  Invalid pid in path: {path}")
            return {'status':'error','message':'Invalid pid', 'diagnosis':'BadRequest'}
        if logger:
            logger.debug(f"  Executing kill command for pid {pid}")
        cmd = f"kill -TERM {pid} && echo OK || echo FAIL"
        res = ssh_run_command(server, cmd, timeout=timeout, logger=logger)
        if res.get('error') or res.get('exit_status', 1) != 0:
            if logger:
                logger.error(f"  Kill command failed: {res.get('error')}")
            return {'status':'error','message':res.get('error'),'diagnosis':'SSHFail'}
        out = res.get('stdout','')
        if 'OK' in out:
            if logger:
                logger.info(f"  Successfully killed process {pid}")
            return {'status':'success','message':f'Process {pid} terminated'}
        else:
            if logger:
                logger.warning(f"  Kill process returned: {out}")
            return {'status':'error','message':out or res.get('stderr',''), 'diagnosis':'KillFailed'}

    # 网络信息 / 磁盘等：尝试简单命令并返回原始输出，前端可根据诊断简化显示
    if path == '/api/server/network':
        if logger:
            logger.debug(f"  Fetching network info using ip/ifconfig")
        cmd = "ip -j addr || ifconfig"
        res = ssh_run_command(server, cmd, timeout=timeout, logger=logger)
        if res.get('error') or res.get('exit_status', 1) != 0:
            if logger:
                logger.warning(f"  Network fetch failed: {res.get('error')}")
            return {'status':'error','message':res.get('error'),'diagnosis':'SSHFail'}
        if logger:
            logger.info(f"  Successfully fetched network info")
        return {'status':'success','data':{'raw': res.get('stdout','')}, 'diagnosis':'Limited'}

    if path == '/api/server/disk':
        if logger:
            logger.debug(f"  Fetching disk info using df")
        cmd = "df -B1 -h || df -h"
        res = ssh_run_command(server, cmd, timeout=timeout, logger=logger)
        if res.get('error') or res.get('exit_status', 1) != 0:
            if logger:
                logger.warning(f"  Disk fetch failed: {res.get('error')}")
            return {'status':'error','message':res.get('error'),'diagnosis':'SSHFail'}
        if logger:
            logger.info(f"  Successfully fetched disk info")
        return {'status':'success','data':{'raw': res.get('stdout','')}, 'diagnosis':'Limited'}

    return {'status':'error','message':'Unsupported path for SSH proxy', 'diagnosis':'NotImplemented'}


def sftp_upload(server, local_path, remote_path, timeout=10, logger=None):
    host = server.get('host')
    username = server.get('username') or None
    password = server.get('password') or None
    ports = [22]
    try:
        if server.get('port'):
            ports.append(int(server.get('port')))
    except Exception:
        pass
    last_exc = None
    for p in ports:
        try:
            transport = paramiko.Transport((host, p))
            transport.connect(username=username, password=password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            sftp.put(local_path, remote_path)
            sftp.close()
            transport.close()
            return {'status': 'success'}
        except Exception as e:
            last_exc = e
            try:
                transport.close()
            except Exception:
                pass
            continue
    return {'status': 'error', 'message': str(last_exc) if last_exc else 'SFTP failed'}
