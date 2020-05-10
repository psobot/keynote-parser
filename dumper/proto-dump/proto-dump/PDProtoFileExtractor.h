//
//  PDProtoFileExtractor.h
//  proto-dump
//
//  Copyright (c) 2013 Sean Patrick O'Brien. All rights reserved.
//

#import <Foundation/Foundation.h>


extern NSString * const PDProtoFileExtractorErrorDomain;


enum {
	// The data doesn't contain any .proto descriptors.
	PDProtoFileExtractorErrorDataContainsNoProtobufDescriptors	= 1,
	
	// There was a missing dependency or a dependency loop in the descriptors.
	PDProtoFileExtractorErrorDependencySortingFailed			= 2,
	
	// A problem occured while generating source code for the descriptors.
	PDProtoFileExtractorErrorSourceGenerationFailed				= 3,
};


@interface PDProtoFileExtractor : NSObject

// Finds Protobuf descriptors in the data and returns them as instances of PDProtoFile.
+ (NSArray *)extractProtoFilesFromData:(NSData *)data error:(NSError **)errorPtr;
+ (NSArray *)extractProtoFilesFromDatas:(NSArray *)datas error:(NSError **)errorPtr;

@end
