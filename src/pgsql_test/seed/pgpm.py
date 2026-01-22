"""
pgpm seed adapter for pgsql-test.

Provides integration with pgpm (PostgreSQL Package Manager) for running
database migrations as part of test seeding.

Requires pgpm to be installed globally: npm install -g pgpm
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pgsql_test.types import SeedContext

logger = logging.getLogger(__name__)


class PgpmSeedAdapter:
    """
    Seed adapter that runs pgpm deploy to apply migrations.

    This adapter calls the pgpm CLI via subprocess, passing the database
    connection info via environment variables.

    Usage:
        adapter = PgpmSeedAdapter(module_path="./my-module")
        adapter.seed(ctx)
    """

    def __init__(
        self,
        module_path: str | None = None,
        package: str | None = None,
        deploy_args: list[str] | None = None,
        cache: bool = False,
    ) -> None:
        """
        Initialize the pgpm seed adapter.

        Args:
            module_path: Path to the pgpm module directory (defaults to cwd)
            package: Package name to deploy (avoids interactive prompt)
            deploy_args: Additional arguments to pass to pgpm deploy
            cache: Whether to enable caching (not yet implemented)
        """
        self._module_path = module_path
        self._package = package
        self._deploy_args = deploy_args or []
        self._cache = cache

    def seed(self, ctx: SeedContext) -> None:
        """
        Run pgpm deploy to apply migrations.

        Args:
            ctx: Seed context containing pg client and config

        Raises:
            RuntimeError: If pgpm deploy fails
        """
        config = ctx["config"]

        # Build environment with database connection info
        env = os.environ.copy()
        env["PGHOST"] = config.get("host", "localhost")
        env["PGPORT"] = str(config.get("port", 5432))
        env["PGDATABASE"] = config["database"]
        env["PGUSER"] = config.get("user", "postgres")
        if "password" in config:
            env["PGPASSWORD"] = config["password"]

        # Determine working directory
        cwd = self._module_path or os.getcwd()

        # Build pgpm deploy command
        cmd = ["pgpm", "deploy", "--yes", "--verbose"]
        if self._package:
            cmd.extend(["--package", self._package])
        cmd.extend(self._deploy_args)

        logger.info(f"Running pgpm deploy in {cwd}")
        logger.debug(f"Command: {' '.join(cmd)}")
        logger.debug(f"Database: {config['database']}")

        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                logger.error(f"pgpm deploy failed: {error_msg}")
                raise RuntimeError(f"pgpm deploy failed: {error_msg}")

            logger.info("pgpm deploy completed successfully")
            if result.stdout:
                logger.info(f"pgpm output: {result.stdout}")
            if result.stderr:
                logger.info(f"pgpm stderr: {result.stderr}")

        except FileNotFoundError as err:
            raise RuntimeError(
                "pgpm not found. Install it with: npm install -g pgpm"
            ) from err


def pgpm(
    module_path: str | None = None,
    package: str | None = None,
    deploy_args: list[str] | None = None,
    cache: bool = False,
) -> PgpmSeedAdapter:
    """
    Create a pgpm seed adapter.

    This adapter runs pgpm deploy to apply database migrations as part of
    test seeding. Requires pgpm to be installed globally.

    Args:
        module_path: Path to the pgpm module directory (defaults to cwd)
        package: Package name to deploy (avoids interactive prompt)
        deploy_args: Additional arguments to pass to pgpm deploy
        cache: Whether to enable caching

    Returns:
        A PgpmSeedAdapter instance

    Example:
        # Deploy migrations from a specific module
        seed_adapters = [
            seed.pgpm(module_path="./packages/my-module", package="my-module")
        ]

        # Deploy with additional arguments
        seed_adapters = [
            seed.pgpm(module_path="./my-module", package="my-module", deploy_args=["--verbose"])
        ]
    """
    return PgpmSeedAdapter(module_path=module_path, package=package, deploy_args=deploy_args, cache=cache)
