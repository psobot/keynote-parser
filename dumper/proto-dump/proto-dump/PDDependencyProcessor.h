//
//  PDDependencyProcessor.h
//  proto-dump
//
//  Copyright (c) 2013 Sean Patrick O'Brien. All rights reserved.
//

#import <Foundation/Foundation.h>


@interface PDDependencyProcessor : NSObject

// Given an array of PDProtoFile objects, attempt to sort them such that a file's imports will always precede it in the array.
// Returns nil if there are missing or circular dependencies.
+ (NSArray *)sortProtoFilesAccordingToDependencies:(NSArray *)protoFiles;

@end
