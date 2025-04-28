#!/usr/bin/env python3
"""
Main entry point for IntentLayer CLI.
"""
import sys
import typer
from typing import Optional
import importlib.metadata

from . import verify

try:
    __version__ = importlib.metadata.version("intentlayer-sdk")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0-dev"

app = typer.Typer(
    help="IntentLayer CLI - Tools for working with IntentLayer protocol",
    no_args_is_help=True,
)

# Register commands
app.add_typer(verify.app, name="verify", help="Verify an intent transaction")

@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", "-v", 
        help="Show the application version and exit",
        is_flag=True
    ),
):
    """IntentLayer CLI - Tools for working with IntentLayer protocol."""
    if version:
        typer.echo(f"IntentLayer CLI version: {__version__}")
        raise typer.Exit()

if __name__ == "__main__":
    app()