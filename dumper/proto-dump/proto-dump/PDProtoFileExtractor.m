//
//  PDProtoFileExtractor.m
//  proto-dump
//
//  Copyright (c) 2013 Sean Patrick O'Brien. All rights reserved.
//

#import "PDProtoFileExtractor.h"

#import "PDDependencyProcessor.h"
#import "PDProtobufInputStream.h"
#import "PDProtoFile+Private.h"


NSString * const PDProtoFileExtractorErrorDomain = @"PDProtoFileExtractorErrorDomain";


@implementation PDProtoFileExtractor

+ (NSArray *)extractUnsortedProtoFilesFromData:(NSData *)data
{
	if (data == nil) {
		return nil;
	}
	
	NSMutableArray *protos = [NSMutableArray array];
	
	NSUInteger length = data.length;
	NSUInteger offset = 0;
	
	// Descriptors start with a string containing the filename. Search for the ".proto" file extension
	NSData *protoSuffixData = [@".proto" dataUsingEncoding:NSUTF8StringEncoding];
	
	// Protobuf tag indicating length-delimited data for identifier 1 (name)
	uint8_t protoStartMarker = 0x0A;
	NSData *protoStartMarkerData = [NSData dataWithBytes:&protoStartMarker length:1];
	
	while (YES) {
		// Look for the ".proto" string
		NSRange suffixRange = [data rangeOfData:protoSuffixData options:0 range:NSMakeRange(offset, length - offset)];
		if (suffixRange.location == NSNotFound) {
			// No more ".proto" strings
			break;
		}
		
		// Search backwards from the ".proto" until we find a 0x0A byte.
		NSRange markerRange = [data rangeOfData:protoStartMarkerData options:NSDataSearchBackwards range:NSMakeRange(offset, suffixRange.location - offset)];
		if (markerRange.location == NSNotFound) {
			// This ".proto" string isn't part of a protobuf descriptor
			offset = NSMaxRange(suffixRange);
			continue;
		}
		
		// Read the name length as a varint.
		uint64_t nameLength = 0;
		NSUInteger nameLengthBytesConsumed = 0;
		if (![PDProtobufInputStream readVarint:&nameLength fromData:data offset:NSMaxRange(markerRange) bytesConsumed:&nameLengthBytesConsumed]) {
			offset = NSMaxRange(suffixRange);
			continue;
		}
		
		// Length = 1 byte for the marker (0x0A) + length of the varint + length of the descriptor name
		NSUInteger expectedLength = 1 + nameLengthBytesConsumed + nameLength;
		NSUInteger currentLength = NSMaxRange(suffixRange) - markerRange.location;
		
		if (currentLength != expectedLength) {
			// Lengths don't match up.
			offset = NSMaxRange(suffixRange);
			continue;
		}
		
		// Split the data starting at the marker byte and try to read it as a protobuf stream.
		// Descriptors are stored as c strings in the .pb.cc files. They're null-terminated, but can also contain embedded null bytes.
		// Since we can't search for the null-terminator explicitly, we parse the string manually until we reach a protobuf
		// tag which equals 0 (identifier = 0, wiretype = varint), signalling the final null byte of the string.
		// This works because there are no 0 tags in a real FileDescriptorProto stream.
		NSData *potentialDescriptorData = [data subdataWithRange:NSMakeRange(markerRange.location, length - markerRange.location)];
		PDProtobufInputStream *stream = [[PDProtobufInputStream alloc] initWithData:potentialDescriptorData];
		NSUInteger descriptorLength = [stream readUntilNullTag] - 1;
		
		// Construct the proto file and make sure it's not the embedded descriptor.proto file.
		NSData *descriptorData = [potentialDescriptorData subdataWithRange:NSMakeRange(0, descriptorLength)];
		PDProtoFile *protoFile = [[PDProtoFile alloc] initWithCompiledData:descriptorData];
		if (protoFile != nil && ![protoFile.path isEqualToString:@"google/protobuf/descriptor.proto"]) {
			[protos addObject:protoFile];
		}
		
		offset = markerRange.location + descriptorLength;
	}
	
	return protos;
}

+ (NSArray *)extractProtoFilesFromData:(NSData *)data error:(NSError **)errorPtr
{
	// Extract Protobuf descriptors.
	NSArray *unsortedProtoFiles = [PDProtoFileExtractor extractUnsortedProtoFilesFromData:data];
	if (unsortedProtoFiles.count == 0) {
		if (errorPtr != NULL) {
			NSDictionary *userInfo = @{ NSLocalizedDescriptionKey: @"The data does not contain any Protobuf descriptors." };
			(*errorPtr) = [NSError errorWithDomain:PDProtoFileExtractorErrorDomain code:PDProtoFileExtractorErrorDataContainsNoProtobufDescriptors userInfo:userInfo];
		}

		return nil;
	}

	NSLog(@"Found unsorted proto files: %@", unsortedProtoFiles);
	
	// Sort the files according to their dependencies.
	NSArray *sortedProtoFiles = [PDDependencyProcessor sortProtoFilesAccordingToDependencies:unsortedProtoFiles];
	if (sortedProtoFiles == nil) {
		if (errorPtr != NULL) {
			NSDictionary *userInfo = @{ NSLocalizedDescriptionKey: @"Unable to process dependencies." };
			(*errorPtr) = [NSError errorWithDomain:PDProtoFileExtractorErrorDomain code:PDProtoFileExtractorErrorDependencySortingFailed userInfo:userInfo];
		}

		return nil;
	}

	NSLog(@"Using sorted proto files: %@", sortedProtoFiles);
	
	// Generate sources.
	for (PDProtoFile *protoFile in sortedProtoFiles) {
		if (![protoFile generateSource]) {
			if (errorPtr != NULL) {
				NSDictionary *userInfo = @{ NSLocalizedDescriptionKey: [NSString stringWithFormat:@"Failed to generate source for \u201C%@\u201D.", protoFile.path] };
				(*errorPtr) = [NSError errorWithDomain:PDProtoFileExtractorErrorDomain code:PDProtoFileExtractorErrorSourceGenerationFailed userInfo:userInfo];
			}
			return nil;
		}
	}
	
	return sortedProtoFiles;
}

+ (NSArray *)extractProtoFilesFromDatas:(NSArray *)datas error:(NSError **)errorPtr
{
	NSMutableArray *unsortedProtoFiles = [NSMutableArray array];

	for (NSData *data in datas) {
		// Extract Protobuf descriptors.
		[unsortedProtoFiles addObjectsFromArray:[PDProtoFileExtractor extractUnsortedProtoFilesFromData:data]];
	}

	if (unsortedProtoFiles.count == 0) {
		if (errorPtr != NULL) {
			NSDictionary *userInfo = @{ NSLocalizedDescriptionKey: @"The data does not contain any Protobuf descriptors." };
			(*errorPtr) = [NSError errorWithDomain:PDProtoFileExtractorErrorDomain code:PDProtoFileExtractorErrorDataContainsNoProtobufDescriptors userInfo:userInfo];
		}

		return nil;
	}

	NSLog(@"Found unsorted proto files: %@", unsortedProtoFiles);
	
	// Sort the files according to their dependencies.
	NSArray *sortedProtoFiles = [PDDependencyProcessor sortProtoFilesAccordingToDependencies:unsortedProtoFiles];
	if (sortedProtoFiles == nil) {
		if (errorPtr != NULL) {
			NSDictionary *userInfo = @{ NSLocalizedDescriptionKey: @"Unable to process dependencies." };
			(*errorPtr) = [NSError errorWithDomain:PDProtoFileExtractorErrorDomain code:PDProtoFileExtractorErrorDependencySortingFailed userInfo:userInfo];
		}

		return nil;
	}

	NSLog(@"Using sorted proto files: %@", sortedProtoFiles);
	
	// Generate sources.
	for (PDProtoFile *protoFile in sortedProtoFiles) {
		if (![protoFile generateSource]) {
			if (errorPtr != NULL) {
				NSDictionary *userInfo = @{ NSLocalizedDescriptionKey: [NSString stringWithFormat:@"Failed to generate source for \u201C%@\u201D.", protoFile.path] };
				(*errorPtr) = [NSError errorWithDomain:PDProtoFileExtractorErrorDomain code:PDProtoFileExtractorErrorSourceGenerationFailed userInfo:userInfo];
			}
			return nil;
		}
	}
	
	return sortedProtoFiles;
}

@end
