//
//  PDProtoFile.h
//  proto-dump
//
//  Copyright (c) 2013 Sean Patrick O'Brien. All rights reserved.
//

#import <Foundation/Foundation.h>


@interface PDProtoFile : NSObject

// The file's path.
@property(readonly) NSString *path;

// The file's source code.
@property(readonly) NSString *source;

@end
