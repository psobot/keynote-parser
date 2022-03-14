
.PHONY=clean all

LLDB_PYTHON_PATH := ${shell lldb --python-path}
LLDB_PYTHON := ${shell lldb --python-path | cut -f 8 -d /}
IDENTITY := $(shell security find-identity -v -p codesigning | head -n 1 | python -c 'import sys; print(sys.stdin.read().split("\"")[1])')

all: mapping.json proto

mapping.json: Keynote.unsigned.app/Contents/MacOS/Keynote ./extract_mapping.py
	PYTHONPATH=${LLDB_PYTHON_PATH} xcrun $(LLDB_PYTHON) ./extract_mapping.py Keynote.unsigned.app/Contents/MacOS/Keynote > $@
	rm -rf Keynote.unsigned.app

proto: /Applications/Keynote.app
	python3 protodump.py /Applications/Keynote.app ./proto/
	# Note that if any of the incoming Protobuf definitions contain periods,
	# protoc will put them into their own Python packages. This is not desirable
	# for import rules in Python, so we replace non-final period characters with
	# underscores.
	python3 ./rename_proto_files.py proto
	cp ./proto/*.proto ../protos/

Keynote.unsigned.app/Contents/MacOS/Keynote: /Applications/Keynote.app
	cp -r /Applications/Keynote.app ./Keynote.unsigned.app
	codesign --remove-signature --verbose ./Keynote.unsigned.app/Contents/MacOS/Keynote
	codesign --sign "${IDENTITY}" --verbose ./Keynote.unsigned.app/Contents/MacOS/Keynote

clean:
	rm -rf Keynote.unsigned.app
	rm -rf mapping.json
	rm -rf proto
