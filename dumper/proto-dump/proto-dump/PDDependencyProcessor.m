//
//  PDDependencyProcessor.m
//  proto-dump
//
//  Copyright (c) 2013 Sean Patrick O'Brien. All rights reserved.
//

#import "PDDependencyProcessor.h"

#import "PDProtoFile+Private.h"


@implementation PDDependencyProcessor

+ (NSArray *)sortProtoFilesAccordingToDependencies:(NSArray *)protoFiles
{
	NSMutableArray *sortedFiles = [NSMutableArray array];
	
	// Gather dependency information.
	NSMutableDictionary *protoFilesByPath = [NSMutableDictionary dictionary];
	NSMutableDictionary *dependenciesByPath = [NSMutableDictionary dictionary];
	NSMutableSet *remainingPaths = [NSMutableSet set];
	
	for (PDProtoFile *protoFile in protoFiles) {
		NSString *path = protoFile.path;
		
		protoFilesByPath[path] = protoFile;
		dependenciesByPath[path] = [NSMutableSet setWithArray:protoFile.imports];
		[remainingPaths addObject:path];
	}
	
	NSLog(@"Looking at remaining paths: %@", remainingPaths);

	// Loop until we've processed all files.
	while (remainingPaths.count != 0) {
		NSMutableSet *processedPaths = [NSMutableSet set];
		
		// Process paths with completed dependencies.
		for (NSString *path in remainingPaths) {
			NSMutableSet *dependencies = dependenciesByPath[path];
			if (dependencies.count != 0) {
				// Can't process this file yet
				continue;
			}
			
			PDProtoFile *protoFile = protoFilesByPath[path];
			if (protoFile == nil) {
				NSLog(@"Referenced proto file %@ not found in data.", path);
				continue;
			}
			
			[sortedFiles addObject:protoFile];
			[processedPaths addObject:path];
		}
		
		if (processedPaths.count == 0) {
			// We weren't able to process any paths this round, so there must be a missing dependency, or a dependency loop.
			NSLog(@"Missing dependencies not present in the provided files:");
			NSMutableSet *printed = [NSMutableSet set];
			for (NSString *path in remainingPaths) {
				for (NSString *dependency in dependenciesByPath[path]) {
					if (![printed containsObject:dependency] && protoFilesByPath[dependency] == nil) {
						NSLog(@"\t%@ (required by %@)", dependency, path);
						[printed addObject:dependency];
					}
				}
			}
			return nil;
		}
		
		[remainingPaths minusSet:processedPaths];
		
		[dependenciesByPath enumerateKeysAndObjectsUsingBlock:^(NSString *path, NSMutableSet *dependencies, BOOL *stop) {
			[dependencies minusSet:processedPaths];
		}];
	}
	
	return sortedFiles;
}

@end
