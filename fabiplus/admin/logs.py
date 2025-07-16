"""
FABI+ Framework Live Server Logs System
WebSocket-based real-time log streaming for admin interface
"""

import asyncio
import json

import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import aiofiles
from fastapi import Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.routing import APIRouter
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from ..conf.settings import settings
from ..core.auth import get_current_superuser
from ..core.models import User


class LogLevel:
    """Log level constants"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    ALL_LEVELS = [DEBUG, INFO, WARNING, ERROR, CRITICAL]


class LogEntry:
    """Represents a single log entry"""

    def __init__(
        self, timestamp: str, level: str, logger: str, message: str, raw_line: str
    ):
        self.timestamp = timestamp
        self.level = level
        self.logger = logger
        self.message = message
        self.raw_line = raw_line
        self.parsed_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "logger": self.logger,
            "message": self.message,
            "raw_line": self.raw_line,
            "parsed_at": self.parsed_at.isoformat(),
        }


class LogParser:
    """Parses log lines into structured LogEntry objects"""

    # Common log patterns
    PATTERNS = [
        # FABI+ format: 2025-06-16 20:10:34,004 - fabiplus.core.app - INFO - Message
        re.compile(
            r"(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (?P<logger>[\w\.]+) - (?P<level>\w+) - (?P<message>.*)"
        ),
        # Uvicorn format: INFO:     127.0.0.1:53730 - "POST /admin/customer/add/ HTTP/1.1" 303 See Other
        re.compile(r"(?P<level>INFO|DEBUG|WARNING|ERROR|CRITICAL):\s+(?P<message>.*)"),
        # Generic format: [LEVEL] Message
        re.compile(r"\[(?P<level>\w+)\]\s*(?P<message>.*)"),
        # Fallback: treat entire line as message
        re.compile(r"(?P<message>.*)"),
    ]

    @classmethod
    def parse_line(cls, line: str) -> LogEntry:
        """Parse a log line into a LogEntry"""
        line = line.strip()
        if not line:
            return None

        for pattern in cls.PATTERNS:
            match = pattern.match(line)
            if match:
                groups = match.groupdict()

                timestamp = groups.get(
                    "timestamp", datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                )
                level = groups.get("level", "INFO").upper()
                logger = groups.get("logger", "unknown")
                message = groups.get("message", line)

                return LogEntry(timestamp, level, logger, message, line)

        # Fallback
        return LogEntry(
            datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "INFO",
            "unknown",
            line,
            line,
        )


class LogFileWatcher(FileSystemEventHandler):
    """Watches log files for changes and notifies subscribers"""

    def __init__(self, log_manager):
        self.log_manager = log_manager
        super().__init__()

    def on_modified(self, event):
        """Handle file modification events"""
        if not event.is_directory and event.src_path in self.log_manager.watched_files:
            asyncio.create_task(self.log_manager.handle_file_change(event.src_path))


class LogManager:
    """Manages log file watching and WebSocket connections"""

    def __init__(self):
        self.connections: Set[WebSocket] = set()
        self.watched_files: Dict[str, int] = {}  # file_path -> last_position
        self.observer: Optional[Observer] = None
        self.log_directory = self._get_log_directory()
        self.max_lines_per_file = 1000  # Limit lines to prevent memory issues

    def _get_log_directory(self) -> Path:
        """Get the log directory path"""
        # Try to get from settings first
        if hasattr(settings, "LOG_DIRECTORY"):
            return Path(settings.LOG_DIRECTORY)

        # Default locations to check
        possible_dirs = [
            Path.cwd() / "logs",
            Path.cwd() / "log",
            Path("/var/log/fabiplus"),
            Path("/tmp/fabiplus_logs"),
            Path.cwd(),  # Current directory as fallback
        ]

        for log_dir in possible_dirs:
            if log_dir.exists() and log_dir.is_dir():
                return log_dir

        # Create logs directory if none exists
        logs_dir = Path.cwd() / "logs"
        logs_dir.mkdir(exist_ok=True)
        return logs_dir

    def start_watching(self):
        """Start watching log files"""
        if self.observer is None:
            self.observer = Observer()
            self.observer.schedule(
                LogFileWatcher(self), str(self.log_directory), recursive=False
            )
            self.observer.start()

        # Initialize watched files
        self._discover_log_files()

    def stop_watching(self):
        """Stop watching log files"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

    def _discover_log_files(self):
        """Discover log files in the log directory"""
        log_patterns = ["*.log", "*.txt", "fabiplus*", "uvicorn*", "gunicorn*"]

        for pattern in log_patterns:
            for log_file in self.log_directory.glob(pattern):
                if log_file.is_file():
                    self.watched_files[str(log_file)] = 0

    async def add_connection(self, websocket: WebSocket):
        """Add a WebSocket connection"""
        self.connections.add(websocket)

        # Send recent logs to new connection
        await self._send_recent_logs(websocket)

    def remove_connection(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        self.connections.discard(websocket)

    async def _send_recent_logs(self, websocket: WebSocket, lines: int = 100):
        """Send recent log lines to a WebSocket connection"""
        try:
            recent_logs = await self.get_recent_logs(lines)
            for log_entry in recent_logs:
                await websocket.send_text(
                    json.dumps({"type": "log_entry", "data": log_entry.to_dict()})
                )
        except Exception as e:
            print(f"Error sending recent logs: {e}")

    async def handle_file_change(self, file_path: str):
        """Handle changes to a watched file"""
        try:
            last_position = self.watched_files.get(file_path, 0)

            async with aiofiles.open(file_path, "r") as f:
                await f.seek(last_position)
                new_lines = await f.readlines()
                new_position = await f.tell()

            # Update position
            self.watched_files[file_path] = new_position

            # Parse and broadcast new lines
            for line in new_lines:
                log_entry = LogParser.parse_line(line)
                if log_entry:
                    await self._broadcast_log_entry(log_entry)

        except Exception as e:
            print(f"Error handling file change for {file_path}: {e}")

    async def _broadcast_log_entry(self, log_entry: LogEntry):
        """Broadcast a log entry to all connected WebSockets"""
        if not self.connections:
            return

        message = json.dumps({"type": "log_entry", "data": log_entry.to_dict()})

        # Send to all connections (remove failed ones)
        failed_connections = set()
        for websocket in self.connections:
            try:
                await websocket.send_text(message)
            except Exception:
                failed_connections.add(websocket)

        # Remove failed connections
        self.connections -= failed_connections

    async def get_recent_logs(
        self, lines: int = 100, level_filter: Optional[str] = None
    ) -> List[LogEntry]:
        """Get recent log entries from all watched files"""
        all_entries = []

        for file_path in self.watched_files:
            try:
                entries = await self._read_file_tail(file_path, lines)
                all_entries.extend(entries)
            except Exception as e:
                print(f"Error reading {file_path}: {e}")

        # Sort by timestamp and filter
        all_entries.sort(key=lambda x: x.parsed_at, reverse=True)

        if level_filter and level_filter in LogLevel.ALL_LEVELS:
            all_entries = [e for e in all_entries if e.level == level_filter]

        return all_entries[:lines]

    async def _read_file_tail(self, file_path: str, lines: int) -> List[LogEntry]:
        """Read the last N lines from a file"""
        try:
            async with aiofiles.open(file_path, "r") as f:
                content = await f.read()
                file_lines = content.strip().split("\n")

                # Get last N lines
                recent_lines = (
                    file_lines[-lines:] if len(file_lines) > lines else file_lines
                )

                # Parse lines
                entries = []
                for line in recent_lines:
                    entry = LogParser.parse_line(line)
                    if entry:
                        entries.append(entry)

                return entries

        except Exception as e:
            print(f"Error reading file tail for {file_path}: {e}")
            return []


# Global log manager instance
log_manager = LogManager()

# Router for log-related endpoints
logs_router = APIRouter(prefix="/logs", tags=["logs"])


@logs_router.websocket("/live")
async def websocket_logs(websocket: WebSocket):
    """WebSocket endpoint for live log streaming"""
    await websocket.accept()

    try:
        # Add connection to manager
        await log_manager.add_connection(websocket)

        # Start watching if not already started
        log_manager.start_watching()

        # Keep connection alive and handle client messages
        while True:
            try:
                # Wait for client messages (for filtering, etc.)
                data = await websocket.receive_text()
                message = json.loads(data)

                # Handle client commands
                if message.get("type") == "filter":
                    level_filter = message.get("level")
                    lines = message.get("lines", 100)

                    # Send filtered logs
                    recent_logs = await log_manager.get_recent_logs(lines, level_filter)
                    for log_entry in recent_logs:
                        await websocket.send_text(
                            json.dumps(
                                {"type": "log_entry", "data": log_entry.to_dict()}
                            )
                        )

            except WebSocketDisconnect:
                break
            except Exception as e:
                print(f"WebSocket error: {e}")
                break

    finally:
        log_manager.remove_connection(websocket)


@logs_router.get("/recent")
async def get_recent_logs(
    lines: int = 100,
    level: Optional[str] = None,
    current_user: User = Depends(get_current_superuser),
):
    """Get recent log entries (REST endpoint)"""

    if level and level not in LogLevel.ALL_LEVELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid log level. Must be one of: {LogLevel.ALL_LEVELS}",
        )

    recent_logs = await log_manager.get_recent_logs(lines, level)

    return {
        "logs": [log.to_dict() for log in recent_logs],
        "total": len(recent_logs),
        "level_filter": level,
        "lines_requested": lines,
    }
