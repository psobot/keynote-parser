//
//  PDProtoFile.mm
//  proto-dump
//
//  Copyright (c) 2013 Sean Patrick O'Brien. All rights reserved.
//

#import "PDProtoFile.h"
#import "PDProtoFile+Private.h"

#import <google/protobuf/descriptor.h>
#import <google/protobuf/descriptor.pb.h>


@implementation PDProtoFile
{
	google::protobuf::FileDescriptorProto _fileDescriptorProto;
}

- (instancetype)initWithCompiledData:(NSData *)data
{
	self = [super init];
	if (self == nil) {
		return nil;
	}
	
	if (!_fileDescriptorProto.ParseFromArray(data.bytes, (int)data.length)) {
		return nil;
	}
	
	_path = [NSString stringWithUTF8String:_fileDescriptorProto.name().c_str()];
	
	NSMutableArray *imports = [NSMutableArray array];
	for (const std::string &dependency : _fileDescriptorProto.dependency()) {
		[imports addObject:[NSString stringWithUTF8String:dependency.c_str()]];
	}
	
	_imports = imports;
	
	return self;
}

- (NSString *)description
{
	return [NSString stringWithFormat:@"<%@: %p; path = %@>", self.className, self, self.path];
}

- (BOOL)generateSource
{
	static google::protobuf::DescriptorPool pool;
	
	if (_source != nil) {
		return YES;
	}
		
	const google::protobuf::FileDescriptor *descriptor = pool.BuildFile(_fileDescriptorProto);
	if (descriptor == NULL) {
		return NO;
	}
	
	_source = [NSString stringWithUTF8String:descriptor->DebugString().c_str()];
	
	return YES;
}

@end
