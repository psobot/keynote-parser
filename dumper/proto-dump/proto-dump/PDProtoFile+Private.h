//
//  PDProtoFile+Private.h
//  proto-dump
//
//  Copyright (c) 2013 Sean Patrick O'Brien. All rights reserved.
//

#import "PDProtoFile.h"

@interface PDProtoFile ()

- (instancetype)initWithCompiledData:(NSData *)data;

// The paths to proto files on which this file depends.
@property(readonly) NSArray *imports;

// Will fail if any of the file's imports have not had their sources generated.
- (BOOL)generateSource;

@end
