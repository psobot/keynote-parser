
.PHONY=clean all

all: mapping.json proto

mapping.json: Keynote.unsigned.app/Contents/MacOS/Keynote.unsigned ./extract_mapping.py
	PYTHONPATH=`lldb -P` xcrun python3 ./extract_mapping.py Keynote.unsigned.app/Contents/MacOS/Keynote.unsigned > $@
	rm -rf Keynote.unsigned.app

proto: proto-dump/build/Release/proto-dump /Applications/Keynote.app
	proto-dump/build/Release/proto-dump -o ./proto /Applications/Keynote.app
	mv proto/CodeResources/* proto/
	rmdir proto/CodeResources
	# Note that if any of the incoming Protobuf definitions contain periods,
	# protoc will put them into their own Python packages. This is not desirable
	# for import rules in Python, so we replace non-final period characters with
	# underscores.
	python ./rename_proto_files.py proto
	cp ./proto/*.proto ../protos/

Keynote.unsigned.app/Contents/MacOS/Keynote: /Applications/Keynote.app
	cp -r /Applications/Keynote.app ./Keynote.unsigned.app

Keynote.unsigned.app/Contents/MacOS/Keynote.unsigned: Keynote.unsigned.app/Contents/MacOS/Keynote unsign/unsign
	unsign/unsign ./Keynote.unsigned.app/Contents/MacOS/Keynote

unsign/unsign: unsign/unsign.c unsign/Makefile unsign/endian.c unsign/endian.h
	cd unsign && make

proto-dump/build/Release/proto-dump: proto-dump/proto-dump/*
	cd proto-dump && make

clean:
	cd unsign && make clean
	cd proto-dump && make clean
	find . -name "*xcuserdata*" -depth -exec rm -rf {} \;
	rm -rf Keynote.unsigned.app
	rm -rf mapping.json
	rm -rf proto