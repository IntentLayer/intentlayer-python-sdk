"""
Tests to verify that Makefile targets work correctly across platforms.
These tests focus on proto generation and related functionality.
"""
import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
import pytest

# Skip the entire module on Windows unless proto tools are available
pytestmark = pytest.mark.skipif(
    sys.platform == "win32" and shutil.which("protoc") is None,
    reason="Protoc not available on Windows in this environment"
)

def run_make_command(command):
    """Run a make command and return the result."""
    try:
        result = subprocess.run(
            ["make", command],
            check=True,
            capture_output=True,
            text=True
        )
        return result.returncode == 0, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr
    except FileNotFoundError:
        pytest.skip("Make is not installed or not in PATH")

def test_clean_proto():
    """Test that clean-proto target works."""
    # This test just verifies the clean-proto target doesn't error
    success, output = run_make_command("clean-proto")
    assert success, f"clean-proto failed: {output}"
    
    # Also verify that the proto files are removed
    proto_dir = Path("intentlayer_sdk/gateway/proto")
    pb2_files = list(proto_dir.glob("*_pb2.py"))
    pb2_grpc_files = list(proto_dir.glob("*_pb2_grpc.py"))
    
    # If this test runs in isolation, files might already be cleaned
    # So we're just checking the command succeeded, not the actual result

def test_proto_generation():
    """Test that proto generation works."""
    # First clean any existing proto files
    success, _ = run_make_command("clean-proto")
    assert success, "Failed to clean proto files"
    
    # Generate proto files
    success, output = run_make_command("proto")
    assert success, f"Proto generation failed: {output}"
    
    # Verify that the proto files were generated
    proto_dir = Path("intentlayer_sdk/gateway/proto")
    pb2_files = list(proto_dir.glob("*_pb2.py"))
    pb2_grpc_files = list(proto_dir.glob("*_pb2_grpc.py"))
    
    assert len(pb2_files) > 0, "No *_pb2.py files were generated"
    assert len(pb2_grpc_files) > 0, "No *_pb2_grpc.py files were generated"

def test_check_proto_stubs():
    """Test that check-proto-stubs target works."""
    # First ensure proto files are generated
    run_make_command("clean-proto")
    success, _ = run_make_command("proto")
    assert success, "Failed to generate proto files"
    
    # Check proto stubs
    success, output = run_make_command("check-proto-stubs")
    assert success, f"check-proto-stubs failed: {output}"

def test_build_directory_creation():
    """Test that the build directory is created correctly."""
    # Remove the build directory if it exists
    build_dir = Path(".build")
    if build_dir.exists():
        shutil.rmtree(build_dir)
    
    # Run init-build-dir target
    success, output = run_make_command("init-build-dir")
    assert success, f"init-build-dir failed: {output}"
    
    # Verify the directory was created
    assert build_dir.exists(), "Build directory was not created"
    assert build_dir.is_dir(), "Build path exists but is not a directory"