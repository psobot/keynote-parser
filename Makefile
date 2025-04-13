PROTO_SOURCES = $(wildcard protos/*.proto)
PROTO_CLASSES = $(patsubst protos/%.proto,keynote_parser/generated/%_pb2.py,$(PROTO_SOURCES))

.PHONY: all clean install test

all: $(PROTO_CLASSES) keynote_parser/generated/__init__.py

install: $(PROTO_CLASSES) keynote_parser/generated/__init__.py keynote_parser/*
	python3 setup.py install

upload: $(PROTO_CLASSES) keynote_parser/generated/__init__.py keynote_parser/*
	python3 setup.py upload

keynote_parser/generated:
	mkdir -p keynote_parser/generated

keynote_parser/generated/%_pb2.py: protos/%.proto keynote_parser/generated
	protoc -I=protos --proto_path protos --python_out=keynote_parser/generated $<

keynote_parser/generated/__init__.py: keynote_parser/generated $(PROTO_CLASSES)
	touch $@
	python3 dumper/rewrite_imports.py keynote_parser/generated/*.py

clean:
	rm -rf keynote_parser/generated
	rm -rf keynote_parser.egg_info
	rm -rf dist

test: all
	python3 -m pytest . --cov=keynote_parser -W ignore::DeprecationWarning
