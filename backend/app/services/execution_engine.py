# backend/app/services/execution_engine.py
import logging
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import Execution, NodeExecution, Workflow, Server
from app.services.ssh_service import SSHService

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Service for managing workflow executions"""

    def __init__(self, db: Session):
        self.db = db
        self.ssh_service = SSHService()

    def create_execution(
        self,
        workflow_id: int,
        trigger_type: str = "manual",
        triggered_by: Optional[str] = None
    ) -> Execution:
        """Create a new execution record"""
        execution = Execution(
            workflow_id=workflow_id,
            status="pending",
            trigger_type=trigger_type,
            triggered_by=triggered_by
        )
        self.db.add(execution)
        self.db.commit()
        self.db.refresh(execution)
        logger.info(f"Created execution {execution.id} for workflow {workflow_id}")
        return execution

    def get_execution(self, execution_id: int) -> Optional[Execution]:
        """Get execution by ID"""
        return self.db.query(Execution).filter(Execution.id == execution_id).first()

    def list_executions(
        self,
        workflow_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100
    ) -> List[Execution]:
        """List all executions with optional filters"""
        query = self.db.query(Execution)
        if workflow_id:
            query = query.filter(Execution.workflow_id == workflow_id)
        if status:
            query = query.filter(Execution.status == status)
        return query.order_by(Execution.created_at.desc()).limit(limit).all()

    def stop_execution(self, execution_id: int) -> Optional[Execution]:
        """Stop a running execution"""
        execution = self.get_execution(execution_id)
        if not execution:
            return None

        if execution.status in ["pending", "running"]:
            execution.status = "failed"
            execution.finished_at = datetime.utcnow()
            if execution.started_at:
                execution.duration = int((execution.finished_at - execution.started_at).total_seconds())
            self.db.commit()
            self.db.refresh(execution)
            logger.info(f"Stopped execution {execution_id}")

        return execution

    def execute_workflow(self, execution_id: int) -> None:
        """Execute a workflow asynchronously (basic sequential execution)"""
        execution = self.get_execution(execution_id)
        if not execution:
            logger.error(f"Execution {execution_id} not found")
            return

        workflow = self.db.query(Workflow).filter(Workflow.id == execution.workflow_id).first()
        if not workflow:
            logger.error(f"Workflow {execution.workflow_id} not found")
            execution.status = "failed"
            execution.finished_at = datetime.utcnow()
            self.db.commit()
            return

        # Update execution status
        execution.status = "running"
        execution.started_at = datetime.utcnow()
        self.db.commit()

        nodes = workflow.nodes or []
        edges = workflow.edges or []
        passed_count = 0
        failed_count = 0

        try:
            # Basic sequential execution
            for node in nodes:
                node_id = node.get("id")
                node_type = node.get("type", "shell")
                config = node.get("config", {})

                # Create node execution record
                node_execution = NodeExecution(
                    execution_id=execution_id,
                    node_id=node_id,
                    node_type=node_type,
                    status="running",
                    started_at=datetime.utcnow(),
                    input_data=config
                )
                self.db.add(node_execution)
                self.db.commit()
                self.db.refresh(node_execution)

                try:
                    # Execute based on node type
                    if node_type == "shell":
                        result = self._execute_shell_node(config)
                        node_execution.status = "success" if result.get("exit_status", -1) == 0 else "failed"
                        node_execution.output_data = result
                        if result.get("exit_status", -1) != 0:
                            node_execution.error_message = result.get("stderr", "Unknown error")
                    else:
                        # For other node types, just mark as success for now
                        node_execution.status = "success"
                        node_execution.output_data = {"message": f"Node type {node_type} executed (basic implementation)"}

                    if node_execution.status == "success":
                        passed_count += 1
                    else:
                        failed_count += 1

                except Exception as e:
                    logger.error(f"Error executing node {node_id}: {e}")
                    node_execution.status = "failed"
                    node_execution.error_message = str(e)
                    failed_count += 1

                node_execution.finished_at = datetime.utcnow()
                node_execution.duration = int((node_execution.finished_at - node_execution.started_at).total_seconds())
                self.db.commit()

            # Update execution final status
            execution.finished_at = datetime.utcnow()
            execution.duration = int((execution.finished_at - execution.started_at).total_seconds())
            execution.summary = {"total": len(nodes), "passed": passed_count, "failed": failed_count}

            if failed_count == 0:
                execution.status = "completed"
                execution.result = "passed"
            elif passed_count == 0:
                execution.status = "failed"
                execution.result = "failed"
            else:
                execution.status = "completed"
                execution.result = "partial"

            self.db.commit()
            logger.info(f"Execution {execution_id} completed with status {execution.status}")

        except Exception as e:
            logger.error(f"Error in execution {execution_id}: {e}")
            execution.status = "failed"
            execution.finished_at = datetime.utcnow()
            if execution.started_at:
                execution.duration = int((execution.finished_at - execution.started_at).total_seconds())
            execution.result = "failed"
            self.db.commit()

    def _execute_shell_node(self, config: dict) -> dict:
        """Execute a shell node"""
        command = config.get("command", "")
        server_id = config.get("server_id")

        if server_id:
            # Execute on remote server
            server = self.db.query(Server).filter(Server.id == server_id).first()
            if server:
                result = self.ssh_service.run_command(
                    host=server.host,
                    username=server.username,
                    password=server.password,
                    command=command,
                    port=server.port
                )
                return {
                    "exit_status": result.exit_status,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "error": result.error
                }
            else:
                return {"exit_status": -1, "error": f"Server {server_id} not found"}
        else:
            # Execute locally
            import subprocess
            try:
                proc = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                return {
                    "exit_status": proc.returncode,
                    "stdout": proc.stdout,
                    "stderr": proc.stderr
                }
            except subprocess.TimeoutExpired:
                return {"exit_status": -1, "error": "Command timed out"}
            except Exception as e:
                return {"exit_status": -1, "error": str(e)}