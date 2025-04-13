
.PHONY=clean all

# Find whichever version of Python is installed in the LLVM directory:
LLVM_DIR := /opt/homebrew/opt/llvm/
# Error if LLVM_DIR is not set:
ifeq ($(LLVM_DIR),)
$(error LLVM_DIR is not set)
endif
LLVM_PYTHON_PATH := $(shell find $(LLVM_DIR) -name "python3.*" | head -n 1)
ifeq ($(LLVM_PYTHON_PATH),)
$(error LLVM_PYTHON_PATH is not set)
endif
LLVM_PYTHON := $(shell basename $(LLVM_PYTHON_PATH))
ifeq ($(LLVM_PYTHON),)
$(error LLVM_PYTHON is not set)
endif

# TODO: Verify that this identity is valid and not expired; this causes silent failures.
IDENTITY := $(shell security find-identity -v -p codesigning | head -n 1 | uv run python -c 'import sys; print(sys.stdin.read().split("\"")[1])')

all: mapping.py proto

mapping.json: Keynote.unsigned.app/Contents/MacOS/Keynote ./extract_mapping.py
	PYTHONPATH=${LLVM_PYTHON_PATH}/site-packages xcrun $(LLVM_PYTHON) ./extract_mapping.py Keynote.unsigned.app/Contents/MacOS/Keynote --output $@
	rm -rf Keynote.unsigned.app

proto: /Applications/Keynote.app
	uv run protodump.py /Applications/Keynote.app ./proto/
	# Note that if any of the incoming Protobuf definitions contain periods,
	# protoc will put them into their own Python packages. This is not desirable
	# for import rules in Python, so we replace non-final period characters with
	# underscores.
	uv run ./rename_proto_files.py proto
	cp ./proto/*.proto ../protos/
	rm -rfv proto

Keynote.unsigned.app/Contents/MacOS/Keynote: /Applications/Keynote.app
	cp -r /Applications/Keynote.app ./Keynote.unsigned.app
	codesign --remove-signature --verbose ./Keynote.unsigned.app/Contents/MacOS/Keynote
	codesign --sign "${IDENTITY}" --verbose ./Keynote.unsigned.app/Contents/MacOS/Keynote

mapping.py: mapping.json
	uv run generate_mapping.py
	mv mapping.py ../keynote_parser/mapping.py
	echo "mapping.py generated (size: $(shell wc -c < mapping.py) bytes); the dumper worked!"
	rm -rf mapping.json

clean:
	rm -rf Keynote.unsigned.app
	rm -rf mapping.json
	rm -rf mapping.py
	rm -rf proto
