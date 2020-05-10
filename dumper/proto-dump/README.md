proto-dump
==========================

proto-dump is a tool for recovering [Protobuf](https://code.google.com/p/protobuf/) descriptors (.proto files) from compiled programs. It can be thought of as [class-dump](http://stevenygard.com/projects/class-dump) for Protobuf.

Usage
-----
	proto-dump 0.1
	Usage: proto-dump [-hv] [-o <output>] <input>
	  -h, --help                Show usage information and exit
	  -v, --version             Show version information
	  -o, --output=<output>     Write the .proto files to <output>
	  <input>                   Extract Protobuf descriptors from <input>
