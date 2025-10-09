"""
Metrics collection and monitoring
"""

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class ToolMetrics:
    tool_name: str
    execution_time: float
    success: bool
    error_type: Optional[str] = None
    tokens_used: int = 0
    timestamp: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


class MetricsCollector:
    """Collect and analyze tool execution metrics"""

    def __init__(self):
        self.metrics: List[ToolMetrics] = []
        self.max_metrics = 1000  # Keep last 1000 metrics

    def record_execution(
        self, tool_name: str, start_time: float, success: bool, **kwargs
    ):
        """Record a tool execution"""
        metric = ToolMetrics(
            tool_name=tool_name,
            execution_time=time.time() - start_time,
            success=success,
            **kwargs,
        )
        self.metrics.append(metric)

        # Keep only recent metrics
        if len(self.metrics) > self.max_metrics:
            self.metrics = self.metrics[-self.max_metrics :]

    def get_stats(self) -> Dict:
        """Get aggregated statistics"""
        if not self.metrics:
            return {"total_calls": 0}

        total_calls = len(self.metrics)
        successful_calls = sum(1 for m in self.metrics if m.success)
        avg_execution_time = sum(m.execution_time for m in self.metrics) / total_calls

        tool_stats = {}
        for metric in self.metrics:
            if metric.tool_name not in tool_stats:
                tool_stats[metric.tool_name] = {
                    "calls": 0,
                    "successes": 0,
                    "avg_time": 0,
                }
            tool_stats[metric.tool_name]["calls"] += 1
            if metric.success:
                tool_stats[metric.tool_name]["successes"] += 1

        return {
            "total_calls": total_calls,
            "success_rate": successful_calls / total_calls if total_calls > 0 else 0,
            "avg_execution_time": avg_execution_time,
            "tool_stats": tool_stats,
            "recent_errors": [
                m.error_type
                for m in self.metrics[-10:]
                if not m.success and m.error_type
            ],
        }

    def clear_metrics(self):
        """Clear all collected metrics"""
        self.metrics.clear()


# Global metrics collector
metrics_collector = MetricsCollector()
