//
//  PDProtobufInputStream.mm
//  proto-dump
//
//  Copyright (c) 2013 Sean Patrick O'Brien. All rights reserved.
//

#import "PDProtobufInputStream.h"

#import <google/protobuf/io/coded_stream.h>
#import <google/protobuf/wire_format.h>

using namespace google::protobuf::internal;


@implementation PDProtobufInputStream
{
	NSData *_data;
	google::protobuf::io::CodedInputStream *_stream;
}

- (instancetype)initWithData:(NSData *)data
{
	self = [super init];
	if (self == nil) {
		return nil;
	}
	
	_data = data;
	_stream = new google::protobuf::io::CodedInputStream((const uint8_t *)_data.bytes, (int)_data.length);
	
	return self;
}

- (void)dealloc
{
    delete _stream;
}

- (BOOL)readVarint:(uint64_t *)valuePtr
{
	return _stream->ReadVarint64(valuePtr);
}

- (BOOL)readUInt8:(uint8_t *)valuePtr
{
	return _stream->ReadRaw(valuePtr, 1);
}

- (BOOL)readUInt32:(uint32_t *)valuePtr
{
	return _stream->ReadLittleEndian32(valuePtr);
}

- (BOOL)readUInt64:(uint64_t *)valuePtr
{
	return _stream->ReadLittleEndian64(valuePtr);
}

- (NSData *)readDataWithLength:(NSUInteger)length
{
	NSMutableData *data = [NSMutableData dataWithLength:length];
	if (!_stream->ReadRaw(data.mutableBytes, (int)length)) {
		return nil;
	}
	
	return data;
}

- (NSData *)readLengthDelimitedData
{
	uint64_t length = 0;
	if (![self readVarint:&length]) {
		return nil;
	}

	return [self readDataWithLength:length];
}

- (BOOL)isAtEnd
{
	return _stream->BytesUntilLimit() == 0;
}

- (NSUInteger)lengthRemaining
{
	return _stream->BytesUntilLimit();
}

- (NSUInteger)currentPosition
{
	return _stream->CurrentPosition();
}

#pragma mark -

- (void)_readUntilNullTag
{
	while (!self.isAtEnd) {
		uint64_t tag = 0;
		if (![self readVarint:&tag]) {
			return;
		}
		
		if (tag == 0) {
			// Found a null tag, so we're done
			return;
		}
		
		WireFormatLite::WireType type = (WireFormatLite::WireType)(tag & 0x7);
		uint64_t uint64Value;
		uint32_t uint32Value;
		
		switch (type) {
			case WireFormatLite::WIRETYPE_VARINT:
				if (![self readVarint:&uint64Value]) {
					return;
				}
				break;
			
			case WireFormatLite::WIRETYPE_FIXED64:
				if (![self readUInt64:&uint64Value]) {
					return;
				}
				break;
				
			case WireFormatLite::WIRETYPE_LENGTH_DELIMITED:
				if ([self readLengthDelimitedData] == nil) {
					return;
				}
				break;
				
			case WireFormatLite::WIRETYPE_START_GROUP:
				break;
				
			case WireFormatLite::WIRETYPE_END_GROUP:
				break;
				
			case WireFormatLite::WIRETYPE_FIXED32:
				if (![self readUInt32:&uint32Value]) {
					return;
				}
				break;
				
			default:
				// Unrecognized wire type
				return;
		}
	}
}

- (NSUInteger)readUntilNullTag
{
	NSUInteger initialPosition = self.currentPosition;
	[self _readUntilNullTag];
	return self.currentPosition - initialPosition;
}

+ (BOOL)readVarint:(uint64_t *)valuePtr fromData:(NSData *)data offset:(NSUInteger)offset bytesConsumed:(NSUInteger *)bytesConsumerPtr
{
	data = [data subdataWithRange:NSMakeRange(offset, data.length - offset)];
	
	PDProtobufInputStream *stream = [[self alloc] initWithData:data];
	if (![stream readVarint:valuePtr]) {
		return NO;
	}
	
	if (bytesConsumerPtr != NULL) {
		(*bytesConsumerPtr) = stream.currentPosition;
	}
	
	return YES;
}

@end
