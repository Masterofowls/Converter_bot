"""
Queue Manager - handles parallel processing with fair user scheduling
"""

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task status enumeration"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ConversionTask:
    """Represents a queued conversion task"""

    task_id: str
    user_id: int
    file_info: Dict[str, Any]
    target_format: str
    created_at: float = field(default_factory=time.time)
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 0  # Lower = higher priority
    result: Any = None
    error: Optional[str] = None


class QueueManager:
    """
    Manages conversion queue with fair scheduling.

    Features:
    - Fair round-robin scheduling between users
    - Configurable concurrent workers
    - Per-user queue limits
    - Priority support
    """

    def __init__(
        self,
        max_workers: int = 3,
        max_queue_per_user: int = 10,
        max_total_queue: int = 100,
    ):
        self.max_workers = max_workers
        self.max_queue_per_user = max_queue_per_user
        self.max_total_queue = max_total_queue

        # User queues: {user_id: [task, ...]}
        self._user_queues: Dict[int, List[ConversionTask]] = defaultdict(list)

        # Active tasks: {task_id: task}
        self._active_tasks: Dict[str, ConversionTask] = {}

        # Processing semaphore
        self._semaphore = asyncio.Semaphore(max_workers)

        # Lock for queue operations
        self._lock = asyncio.Lock()

        # Round-robin index
        self._user_index: Dict[int, int] = defaultdict(int)
        self._users_order: List[int] = []

        # Stats
        self._stats = {
            "total_processed": 0,
            "total_failed": 0,
            "current_active": 0,
        }

    async def add_task(
        self,
        task_id: str,
        user_id: int,
        file_info: Dict[str, Any],
        target_format: str,
        priority: int = 0,
    ) -> Optional[ConversionTask]:
        """
        Add a conversion task to the queue.

        Returns:
            ConversionTask if added, None if queue is full
        """
        async with self._lock:
            # Check per-user limit
            user_queue = self._user_queues[user_id]
            if len(user_queue) >= self.max_queue_per_user:
                logger.warning(f"User {user_id} queue full ({len(user_queue)} tasks)")
                return None

            # Check total limit
            total_pending = sum(len(q) for q in self._user_queues.values())
            if total_pending >= self.max_total_queue:
                logger.warning(f"Global queue full ({total_pending} tasks)")
                return None

            # Create task
            task = ConversionTask(
                task_id=task_id,
                user_id=user_id,
                file_info=file_info,
                target_format=target_format,
                priority=priority,
            )

            # Add to user queue (sorted by priority)
            user_queue.append(task)
            user_queue.sort(key=lambda t: (t.priority, t.created_at))

            # Track user order for round-robin
            if user_id not in self._users_order:
                self._users_order.append(user_id)

            logger.debug(
                f"Task {task_id} added for user {user_id}, "
                f"queue size: {len(user_queue)}"
            )
            return task

    async def get_next_task(self) -> Optional[ConversionTask]:
        """
        Get next task using fair round-robin scheduling.
        Cycles through users fairly.
        """
        async with self._lock:
            if not self._users_order:
                return None

            # Try each user in round-robin order
            tried_users = set()
            start_idx = getattr(self, "_rr_index", 0)

            for _ in range(len(self._users_order)):
                idx = start_idx % len(self._users_order)
                user_id = self._users_order[idx]
                start_idx += 1

                if user_id in tried_users:
                    continue
                tried_users.add(user_id)

                user_queue = self._user_queues.get(user_id, [])
                if user_queue:
                    task = user_queue.pop(0)
                    task.status = TaskStatus.PROCESSING
                    self._active_tasks[task.task_id] = task
                    self._rr_index = start_idx

                    # Remove user from order if queue empty
                    if not user_queue:
                        self._users_order.remove(user_id)

                    self._stats["current_active"] += 1
                    return task

            return None

    async def complete_task(
        self,
        task_id: str,
        success: bool = True,
        result: Any = None,
        error: Optional[str] = None,
    ):
        """Mark a task as completed"""
        async with self._lock:
            task = self._active_tasks.pop(task_id, None)
            if task:
                task.status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
                task.result = result
                task.error = error

                self._stats["current_active"] -= 1
                if success:
                    self._stats["total_processed"] += 1
                else:
                    self._stats["total_failed"] += 1

    async def cancel_task(self, task_id: str, user_id: int) -> bool:
        """Cancel a pending task"""
        async with self._lock:
            # Check active tasks
            if task_id in self._active_tasks:
                # Can't cancel active task easily
                return False

            # Check user queue
            user_queue = self._user_queues.get(user_id, [])
            for i, task in enumerate(user_queue):
                if task.task_id == task_id:
                    user_queue.pop(i)
                    task.status = TaskStatus.CANCELLED
                    logger.info(f"Task {task_id} cancelled")
                    return True

            return False

    async def cancel_user_tasks(self, user_id: int) -> int:
        """Cancel all pending tasks for a user"""
        async with self._lock:
            user_queue = self._user_queues.get(user_id, [])
            count = len(user_queue)

            for task in user_queue:
                task.status = TaskStatus.CANCELLED

            self._user_queues[user_id] = []

            if user_id in self._users_order:
                self._users_order.remove(user_id)

            return count

    def get_user_queue_position(self, user_id: int) -> Dict[str, int]:
        """Get queue info for a user"""
        user_queue = self._user_queues.get(user_id, [])
        total_pending = sum(len(q) for q in self._user_queues.values())

        return {
            "user_pending": len(user_queue),
            "total_pending": total_pending,
            "active_workers": self._stats["current_active"],
            "max_workers": self.max_workers,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        total_pending = sum(len(q) for q in self._user_queues.values())
        return {
            **self._stats,
            "total_pending": total_pending,
            "users_in_queue": len(self._users_order),
            "max_workers": self.max_workers,
        }

    async def process_with_queue(
        self,
        processor: Callable,
        task_id: str,
        user_id: int,
        file_info: Dict[str, Any],
        target_format: str,
        **kwargs,
    ) -> Any:
        """
        Process a conversion with queue management.

        Args:
            processor: Async function to call for conversion
            task_id: Unique task identifier
            user_id: User ID
            file_info: File information dict
            target_format: Target format
            **kwargs: Additional args passed to processor

        Returns:
            Result from processor
        """
        # Add to queue
        task = await self.add_task(task_id, user_id, file_info, target_format)

        if not task:
            raise QueueFullError(
                f"Queue full. Max {self.max_queue_per_user} files per user."
            )

        try:
            # Wait for semaphore (fair access)
            async with self._semaphore:
                # Process
                result = await processor(
                    file_info=file_info,
                    target_format=target_format,
                    **kwargs,
                )
                await self.complete_task(task_id, success=True, result=result)
                return result

        except Exception as e:
            await self.complete_task(task_id, success=False, error=str(e))
            raise


class QueueFullError(Exception):
    """Raised when queue is full"""

    pass


# Global queue manager instance
queue_manager = QueueManager(
    max_workers=3,
    max_queue_per_user=10,
    max_total_queue=100,
)
