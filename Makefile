.PHONY: proto clean-proto check-proto-stubs init-build-dir

# Base directory for proto files
PROTO_DIR = intentlayer_sdk/gateway/proto
# Output directory for generated Python files
PROTO_OUT = intentlayer_sdk/gateway/proto
# Build directory for temporary files
BUILD_DIR = .build

# Initialize build directory
init-build-dir:
	@mkdir -p $(BUILD_DIR)

# Generate python files from proto definitions
# Note: This assumes grpcio-tools and protobuf are already installed
# via poetry/pip using the [grpc] extra dependency
proto: init-build-dir
	@echo "Generating proto files..."
	python -m grpc_tools.protoc \
		--proto_path=$(PROTO_DIR) \
		--python_out=$(PROTO_OUT) \
		--grpc_python_out=$(PROTO_OUT) \
		$(PROTO_DIR)/gateway.proto
	@echo "Fixing imports in generated files..."
	@if [ -f $(PROTO_OUT)/gateway_pb2_grpc.py ]; then \
		python -c "import re; \
			content = open('$(PROTO_OUT)/gateway_pb2_grpc.py', 'r').read(); \
			content = re.sub(r'import gateway_pb2 as gateway__pb2', 'from intentlayer_sdk.gateway.proto import gateway_pb2 as gateway__pb2', content); \
			open('$(PROTO_OUT)/gateway_pb2_grpc.py', 'w').write(content)"; \
	fi
	@echo "Proto generation complete"

# Clean generated proto files
clean-proto:
	@echo "Cleaning generated proto files..."
	rm -f $(PROTO_OUT)/gateway_pb2*.py
	@echo "Proto files cleaned"

# Target to check for stale proto stubs (cross-platform compatible)
check-proto-stubs: init-build-dir
	@echo "Checking for stale proto stubs..."
	@# Save timestamp of latest proto file modification
	@# Use stat with different syntax depending on OS
	@if [ "$(shell uname -s)" = "Darwin" ]; then \
		find $(PROTO_DIR) -name "*.proto" -type f -exec stat -f "%m" {} \; | sort -nr | head -n 1 > $(BUILD_DIR)/proto_time.txt; \
	else \
		find $(PROTO_DIR) -name "*.proto" -type f -exec stat -c "%Y" {} \; | sort -nr | head -n 1 > $(BUILD_DIR)/proto_time.txt; \
	fi
	@# Save timestamp of oldest generated stub
	@if [ "$(shell uname -s)" = "Darwin" ]; then \
		find $(PROTO_OUT) -name "*_pb2*.py" -type f -exec stat -f "%m" {} \; | sort -n | head -n 1 > $(BUILD_DIR)/stub_time.txt; \
	else \
		find $(PROTO_OUT) -name "*_pb2*.py" -type f -exec stat -c "%Y" {} \; | sort -n | head -n 1 > $(BUILD_DIR)/stub_time.txt; \
	fi
	@# Compare timestamps
	@if [ ! -s $(BUILD_DIR)/stub_time.txt ] || [ $$(cat $(BUILD_DIR)/proto_time.txt) -gt $$(cat $(BUILD_DIR)/stub_time.txt) ]; then \
		echo "Proto stubs are outdated or missing. Run 'make proto' to update."; \
		exit 1; \
	else \
		echo "Proto stubs are up to date."; \
	fi
	@rm -f $(BUILD_DIR)/proto_time.txt $(BUILD_DIR)/stub_time.txt