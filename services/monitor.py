import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from core.database import DatabaseService
from services.ingestion import IngestionService
from services.sync_manager_service import SyncManagerService

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class HealthIssue:
    """Represents a health issue"""
    type: str
    severity: HealthStatus
    namespace: Optional[str]
    message: str
    details: Dict[str, Any]
    first_seen: datetime
    last_seen: datetime
    count: int = 1


class HealthMonitor:
    """Monitors system health and tracks issues"""

    def __init__(self,
                 sync_manager: SyncManagerService,
                 ingestion_service: IngestionService,
                 database: DatabaseService):
        self.sync_manager = sync_manager
        self.ingestion_service = ingestion_service
        self.database = database
        self.active_issues: Dict[str, HealthIssue] = {}
        self.resolved_issues: List[HealthIssue] = []

        # Health check thresholds
        self.thresholds = {
            "max_consecutive_failures": 3,
            "staleness_multiplier": 2.0,  # 2x the expected interval
            "critical_staleness_multiplier": 4.0,  # 4x the expected interval
            "max_error_rate_percentage": 20.0,
            "min_success_rate_percentage": 80.0,
            "max_pending_embeddings": 1000,
        }

    async def perform_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        health_report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_status": HealthStatus.HEALTHY.value,
            "services": {},
            "sources": {},
            "issues": [],
            "metrics": {},
            "recommendations": [],
        }

        try:
            # Check core services
            await self._check_core_services(health_report)

            # Check sync health
            await self._check_sync_health(health_report)

            # Check source-specific health
            await self._check_source_health(health_report)

            # Check system metrics
            await self._check_system_metrics(health_report)

            # Update overall status based on issues
            self._update_overall_status(health_report)

            # Generate recommendations
            self._generate_recommendations(health_report)

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health_report["overall_status"] = HealthStatus.CRITICAL.value
            health_report["issues"].append({
                "type": "health_check_failure",
                "severity": HealthStatus.CRITICAL.value,
                "message": f"Health check system failure: {e!s}",
            })

        return health_report

    async def _check_core_services(self, health_report: Dict[str, Any]):
        """Check core service health"""
        services = health_report["services"]

        # Check network binding health
        await self._check_network_health(health_report)

        # Database health
        try:
            db_stats = self.database.get_database_stats()
            services["database"] = {
                "status": HealthStatus.HEALTHY.value,
                "stats": db_stats,
            }
        except Exception as e:
            services["database"] = {
                "status": HealthStatus.CRITICAL.value,
                "error": str(e),
            }
            self._add_issue(health_report, "database_failure", HealthStatus.CRITICAL,
                          None, f"Database service failure: {e!s}")

        # Ingestion service health
        try:
            ingestion_status = self.ingestion_service.get_ingestion_status()
            services["ingestion"] = {
                "status": HealthStatus.HEALTHY.value,
                "stats": ingestion_status,
            }

            # Check pending embeddings
            pending_embeddings = ingestion_status.get("pending_embeddings", 0)
            if pending_embeddings > self.thresholds["max_pending_embeddings"]:
                self._add_issue(health_report, "high_pending_embeddings", HealthStatus.WARNING,
                              None, f"High number of pending embeddings: {pending_embeddings}")

        except Exception as e:
            services["ingestion"] = {
                "status": HealthStatus.CRITICAL.value,
                "error": str(e),
            }
            self._add_issue(health_report, "ingestion_failure", HealthStatus.CRITICAL,
                          None, f"Ingestion service failure: {e!s}")

        # Scheduler health
        try:
            if self.sync_manager.scheduler:
                scheduler_status = self.sync_manager.scheduler.is_running
                services["scheduler"] = {
                    "status": HealthStatus.HEALTHY.value if scheduler_status else HealthStatus.CRITICAL.value,
                    "running": scheduler_status,
                    "stats": self.sync_manager.scheduler.stats,
                }

                if not scheduler_status:
                    self._add_issue(health_report, "scheduler_not_running", HealthStatus.CRITICAL,
                                  None, "Scheduler is not running")
            else:
                services["scheduler"] = {
                    "status": HealthStatus.UNKNOWN.value,
                    "message": "Scheduler not initialized",
                }

        except Exception as e:
            services["scheduler"] = {
                "status": HealthStatus.CRITICAL.value,
                "error": str(e),
            }

    async def _check_network_health(self, health_report: Dict[str, Any]):
        """Check network binding and connectivity health"""
        try:
            import os

            from services.port_state_service import PortStateService

            # Get the port the server should be running on
            server_port = int(os.getenv("SERVER_PORT", "8000"))
            server_host = os.getenv("SERVER_HOST", "127.0.0.1")

            port_service = PortStateService()

            # Validate server binding
            network_validation = await port_service.validate_server_binding(server_host, server_port)

            services = health_report["services"]

            if network_validation["is_healthy"]:
                services["network"] = {
                    "status": HealthStatus.HEALTHY.value,
                    "port": server_port,
                    "host": server_host,
                    "state": network_validation.get("state"),
                    "response_time_ms": network_validation.get("response_time_ms"),
                }
            else:
                # Network issues detected
                services["network"] = {
                    "status": HealthStatus.CRITICAL.value,
                    "port": server_port,
                    "host": server_host,
                    "state": network_validation.get("state"),
                    "issues": network_validation.get("issues", []),
                }

                # Add network issues to main health report
                for issue in network_validation.get("issues", []):
                    self._add_issue(health_report, f"network_{issue['type']}",
                                  HealthStatus.CRITICAL if issue["severity"] == "critical" else HealthStatus.WARNING,
                                  None, f"Network issue: {issue['message']}", issue.get("details"))

        except Exception as e:
            logger.error(f"Network health check failed: {e}")
            services = health_report["services"]
            services["network"] = {
                "status": HealthStatus.UNKNOWN.value,
                "error": f"Network health check failed: {e!s}",
            }

    async def _check_sync_health(self, health_report: Dict[str, Any]):
        """Check overall sync system health"""
        try:
            sync_status = self.sync_manager.get_all_sources_sync_status()

            total_sources = len(sync_status.get("sources", {}))
            failed_sources = 0
            warning_sources = 0

            for namespace, status in sync_status.get("sources", {}).items():
                job_status = status.get("scheduler_status", {})
                error_count = job_status.get("error_count", 0)

                if error_count >= self.thresholds["max_consecutive_failures"]:
                    failed_sources += 1
                elif error_count > 0:
                    warning_sources += 1

            health_report["metrics"]["sync_summary"] = {
                "total_sources": total_sources,
                "healthy_sources": total_sources - failed_sources - warning_sources,
                "warning_sources": warning_sources,
                "failed_sources": failed_sources,
                "success_rate": ((total_sources - failed_sources) / total_sources * 100) if total_sources > 0 else 100,
            }

            # Check overall success rate
            success_rate = health_report["metrics"]["sync_summary"]["success_rate"]
            if success_rate < self.thresholds["min_success_rate_percentage"]:
                severity = HealthStatus.CRITICAL if success_rate < 50 else HealthStatus.WARNING
                self._add_issue(health_report, "low_sync_success_rate", severity, None,
                              f"Low sync success rate: {success_rate:.1f}%")

        except Exception as e:
            logger.error(f"Failed to check sync health: {e}")

    async def _check_source_health(self, health_report: Dict[str, Any]):
        """Check health of individual sources"""
        try:
            sync_status = self.sync_manager.get_all_sources_sync_status()

            for namespace, status in sync_status.get("sources", {}).items():
                source_health = await self._analyze_source_health(namespace, status)
                health_report["sources"][namespace] = source_health

                # Add issues to overall report
                for issue in source_health.get("issues", []):
                    health_report["issues"].append(issue)

        except Exception as e:
            logger.error(f"Failed to check source health: {e}")

    async def _analyze_source_health(self, namespace: str, status: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze health of a specific source"""
        source_health = {
            "status": HealthStatus.HEALTHY.value,
            "issues": [],
            "metrics": {},
            "last_check": datetime.now(timezone.utc).isoformat(),
        }

        job_status = status.get("scheduler_status", {})

        # Check for consecutive failures
        error_count = job_status.get("error_count", 0)
        if error_count >= self.thresholds["max_consecutive_failures"]:
            source_health["status"] = HealthStatus.CRITICAL.value
            issue = {
                "type": "consecutive_failures",
                "severity": HealthStatus.CRITICAL.value,
                "namespace": namespace,
                "message": f"Source has {error_count} consecutive failures",
                "details": {"error_count": error_count, "last_error": job_status.get("last_error")},
            }
            source_health["issues"].append(issue)
        elif error_count > 0:
            source_health["status"] = HealthStatus.WARNING.value

        # Check for staleness
        last_run = job_status.get("last_run")
        interval_seconds = job_status.get("interval_seconds", 3600)

        if last_run:
            try:
                last_run_dt = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
                time_since_last_run = datetime.now(timezone.utc) - last_run_dt
                expected_interval = timedelta(seconds=interval_seconds)

                staleness_ratio = time_since_last_run / expected_interval

                if staleness_ratio > self.thresholds["critical_staleness_multiplier"]:
                    source_health["status"] = HealthStatus.CRITICAL.value
                    issue = {
                        "type": "critical_staleness",
                        "severity": HealthStatus.CRITICAL.value,
                        "namespace": namespace,
                        "message": f"Source has not run for {staleness_ratio:.1f}x expected interval",
                        "details": {
                            "last_run": last_run,
                            "expected_interval_hours": interval_seconds / 3600,
                            "hours_since_last_run": time_since_last_run.total_seconds() / 3600,
                        },
                    }
                    source_health["issues"].append(issue)

                elif staleness_ratio > self.thresholds["staleness_multiplier"]:
                    if source_health["status"] == HealthStatus.HEALTHY.value:
                        source_health["status"] = HealthStatus.WARNING.value

                    issue = {
                        "type": "staleness_warning",
                        "severity": HealthStatus.WARNING.value,
                        "namespace": namespace,
                        "message": f"Source is overdue for sync by {staleness_ratio:.1f}x expected interval",
                        "details": {
                            "last_run": last_run,
                            "expected_interval_hours": interval_seconds / 3600,
                            "hours_since_last_run": time_since_last_run.total_seconds() / 3600,
                        },
                    }
                    source_health["issues"].append(issue)

                source_health["metrics"]["staleness_ratio"] = staleness_ratio
                source_health["metrics"]["hours_since_last_run"] = time_since_last_run.total_seconds() / 3600

            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse last_run time for {namespace}: {e}")

        # Check job status
        if job_status.get("status") == "paused":
            if source_health["status"] == HealthStatus.HEALTHY.value:
                source_health["status"] = HealthStatus.WARNING.value

            issue = {
                "type": "source_paused",
                "severity": HealthStatus.WARNING.value,
                "namespace": namespace,
                "message": "Source sync is paused",
                "details": {"paused_at": job_status.get("last_run")},
            }
            source_health["issues"].append(issue)

        return source_health

    async def _check_system_metrics(self, health_report: Dict[str, Any]):
        """Check system-wide metrics"""
        try:
            # Get database metrics
            db_stats = self.database.get_database_stats()

            # Get ingestion metrics
            ingestion_status = self.ingestion_service.get_ingestion_status()

            health_report["metrics"]["system"] = {
                "total_data_items": db_stats.get("data_items_count", 0),
                "total_sources": len(ingestion_status.get("registered_sources", [])),
                "pending_embeddings": ingestion_status.get("pending_embeddings", 0),
                "database_size_mb": db_stats.get("database_size_bytes", 0) / 1024 / 1024,
                "vector_store_size": ingestion_status.get("vector_store_stats", {}).get("total_vectors", 0),
            }

        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")

    def _add_issue(self, health_report: Dict[str, Any], issue_type: str, severity: HealthStatus,
                   namespace: Optional[str], message: str, details: Optional[Dict[str, Any]] = None):
        """Add an issue to the health report"""
        issue = {
            "type": issue_type,
            "severity": severity.value,
            "namespace": namespace,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        health_report["issues"].append(issue)

    def _update_overall_status(self, health_report: Dict[str, Any]):
        """Update overall health status based on issues"""
        issues = health_report.get("issues", [])

        if not issues:
            health_report["overall_status"] = HealthStatus.HEALTHY.value
            return

        # Check for critical issues
        critical_issues = [i for i in issues if i["severity"] == HealthStatus.CRITICAL.value]
        if critical_issues:
            health_report["overall_status"] = HealthStatus.CRITICAL.value
            return

        # Check for warning issues
        warning_issues = [i for i in issues if i["severity"] == HealthStatus.WARNING.value]
        if warning_issues:
            health_report["overall_status"] = HealthStatus.WARNING.value
            return

        health_report["overall_status"] = HealthStatus.HEALTHY.value

    def _generate_recommendations(self, health_report: Dict[str, Any]):
        """Generate recommendations based on health issues"""
        recommendations = []

        for issue in health_report.get("issues", []):
            issue_type = issue["type"]
            namespace = issue.get("namespace")

            if issue_type == "consecutive_failures":
                recommendations.append({
                    "priority": "high",
                    "action": f"Check API connectivity and credentials for {namespace}",
                    "description": "Multiple consecutive sync failures may indicate authentication or network issues",
                })

            elif issue_type == "critical_staleness":
                recommendations.append({
                    "priority": "high",
                    "action": f"Investigate why {namespace} sync has not run recently",
                    "description": "Source is significantly overdue for sync",
                })

            elif issue_type == "high_pending_embeddings":
                recommendations.append({
                    "priority": "medium",
                    "action": "Process pending embeddings or increase embedding batch size",
                    "description": "Large backlog of items waiting for embedding generation",
                })

            elif issue_type == "low_sync_success_rate":
                recommendations.append({
                    "priority": "high",
                    "action": "Review failed sources and fix underlying issues",
                    "description": "Overall sync success rate is below acceptable threshold",
                })

            elif issue_type == "scheduler_not_running":
                recommendations.append({
                    "priority": "critical",
                    "action": "Restart the scheduler service",
                    "description": "Automatic syncing is disabled",
                })

        health_report["recommendations"] = recommendations

    def get_health_trends(self, hours: int = 24) -> Dict[str, Any]:
        """Get health trends over time"""
        # This would typically query a time-series database
        # For now, return current snapshot
        return {
            "period_hours": hours,
            "trend_data": "Not implemented - would require time-series storage",
            "note": "Health trends require historical data storage",
        }

    def get_active_issues(self) -> List[Dict[str, Any]]:
        """Get currently active issues"""
        return [
            {
                "id": issue_id,
                "type": issue.type,
                "severity": issue.severity.value,
                "namespace": issue.namespace,
                "message": issue.message,
                "first_seen": issue.first_seen.isoformat(),
                "last_seen": issue.last_seen.isoformat(),
                "count": issue.count,
            }
            for issue_id, issue in self.active_issues.items()
        ]
