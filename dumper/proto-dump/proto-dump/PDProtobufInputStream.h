//
//  PDProtobufInputStream.h
//  Exproto-dumptractProtobufDescriptors
//
//  Copyright (c) 2013 Sean Patrick O'Brien. All rights reserved.
//

#import <Foundation/Foundation.h>


@interface PDProtobufInputStream : NSObject

- (instancetype)initWithData:(NSData *)data;

- (BOOL)readVarint:(uint64_t *)valuePtr;

- (BOOL)readUInt32:(uint32_t *)valuePtr;
- (BOOL)readUInt64:(uint64_t *)valuePtr;

- (NSData *)readDataWithLength:(NSUInteger)length;
- (NSData *)readLengthDelimitedData;

- (BOOL)isAtEnd;
- (NSUInteger)lengthRemaining;
- (NSUInteger)currentPosition;

// Reads until it encounters a null tag. Returns the number of bytes consumed, including the final null tag.
- (NSUInteger)readUntilNullTag;

+ (BOOL)readVarint:(uint64_t *)valuePtr fromData:(NSData *)data offset:(NSUInteger)offset bytesConsumed:(NSUInteger *)bytesConsumerPtr;

@end
