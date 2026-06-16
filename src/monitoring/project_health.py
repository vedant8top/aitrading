"""Project health monitoring utility for TradingAI platform."""

from __future__ import annotations

import argparse
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_PATH = PROJECT_ROOT / "logs" / "project_health.log"


class ProjectHealthError(RuntimeError):
    """Base exception for project health monitoring failures."""


@dataclass(frozen=True)
class HealthMetrics:
    """Container for project health statistics."""

    scan_time: str
    project_root: str
    python_files: int
    csv_files: int
    markdown_files: int
    log_files: int
    total_files: int


def configure_logging(log_path: Path) -> logging.Logger:
    """Configure console and rotating-file logging for health monitoring."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("project_health")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    file_handler = RotatingFileHandler(
        log_path, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger


class ProjectHealthMonitor:
    """Monitors and reports on project file structure and health."""

    def __init__(self, project_root: Path, logger: logging.Logger) -> None:
        """Initialize the health monitor.

        Args:
            project_root: Root directory of the project to monitor
            logger: Configured logger instance
        """
        self.project_root = project_root
        self.logger = logger

    def _count_files_by_extension(self, extension: str) -> int:
        """Count files with a specific extension in the project.

        Args:
            extension: File extension to search for (e.g., '.py', '.csv')

        Returns:
            Number of files found with the given extension
        """
        try:
            pattern = f"*{extension}"
            files = list(self.project_root.rglob(pattern))
            count = len(files)
            self.logger.debug(f"Found {count} {extension} files")
            return count
        except Exception as e:
            self.logger.warning(f"Error counting {extension} files: {e}")
            return 0

    def scan_project(self) -> HealthMetrics:
        """Scan the project and collect health metrics.

        Returns:
            HealthMetrics object containing file counts and statistics

        Raises:
            ProjectHealthError: If project root is invalid or inaccessible
        """
        if not self.project_root.exists():
            raise ProjectHealthError(
                f"Project root does not exist: {self.project_root}"
            )

        if not self.project_root.is_dir():
            raise ProjectHealthError(
                f"Project root is not a directory: {self.project_root}"
            )

        self.logger.info(f"Scanning project at: {self.project_root}")

        # Count files by extension
        python_files = self._count_files_by_extension(".py")
        csv_files = self._count_files_by_extension(".csv")
        markdown_files = self._count_files_by_extension(".md")
        log_files = self._count_files_by_extension(".log")

        total_files = python_files + csv_files + markdown_files + log_files

        metrics = HealthMetrics(
            scan_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            project_root=str(self.project_root),
            python_files=python_files,
            csv_files=csv_files,
            markdown_files=markdown_files,
            log_files=log_files,
            total_files=total_files,
        )

        self.logger.info(f"Scan complete. Total tracked files: {total_files}")
        return metrics

    def print_summary(self, metrics: HealthMetrics) -> None:
        """Print a formatted health summary to console.

        Args:
            metrics: HealthMetrics object to display
        """
        print("\n" + "=" * 50)
        print("TradingAI Project Health Summary")
        print("=" * 50)
        print(f"Scan Time:     {metrics.scan_time}")
        print(f"Project Root:  {metrics.project_root}")
        print()
        print("File Counts:")
        print(f"  Python files (.py):      {metrics.python_files:>5}")
        print(f"  CSV files (.csv):        {metrics.csv_files:>5}")
        print(f"  Markdown reports (.md):  {metrics.markdown_files:>5}")
        print(f"  Log files (.log):        {metrics.log_files:>5}")
        print(f"  {'─' * 30}")
        print(f"  Total tracked files:     {metrics.total_files:>5}")
        print()

        # Simple health status
        if metrics.python_files > 0:
            status = "✓ Project structure intact"
        else:
            status = "⚠ Warning: No Python files found"

        print(f"Health Status: {status}")
        print("=" * 50)
        print()


def _display_path(path: Path) -> str:
    """Format a path for display, showing relative path when possible.

    Args:
        path: Path object to format

    Returns:
        Formatted path string
    """
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the health monitor.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Monitor and report TradingAI project health",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help=f"Project root directory (default: {_display_path(PROJECT_ROOT)})",
    )
    parser.add_argument(
        "--log-path",
        type=Path,
        default=DEFAULT_LOG_PATH,
        help=f"Log file path (default: {_display_path(DEFAULT_LOG_PATH)})",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging",
    )
    return parser.parse_args()


def main() -> int:
    """Main entry point for project health monitoring.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    args = parse_args()

    # Configure logging
    logger = configure_logging(args.log_path)
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    logger.info("=" * 60)
    logger.info("Project Health Monitor Started")
    logger.info("=" * 60)

    try:
        # Initialize monitor and scan project
        monitor = ProjectHealthMonitor(args.project_root, logger)
        metrics = monitor.scan_project()

        # Display results
        monitor.print_summary(metrics)

        # Log metrics as structured data
        logger.info("Health metrics collected:")
        for key, value in asdict(metrics).items():
            logger.info(f"  {key}: {value}")

        logger.info("Project health check completed successfully")
        return 0

    except ProjectHealthError as e:
        logger.error(f"Health check failed: {e}")
        return 1
    except Exception as e:
        logger.exception(f"Unexpected error during health check: {e}")
        return 1
    finally:
        logger.info("=" * 60)


if __name__ == "__main__":
    raise SystemExit(main())
