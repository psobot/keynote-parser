//
//  CLUArgumentParser.m
//  Command Line Utilities
//
//  Created by Sean Patrick O'Brien on 8/2/12.
//  Copyright (c) 2012 Sean Patrick O'Brien. All rights reserved.
//

#import "CLUArgumentParser.h"

#import "argtable2.h"
#import "CLUOptionDefinitionPrivate.h"


NSString * const CLUArgumentParserErrorDomain = @"CLUArgumentParserErrorDomain";

NSString * const CLUArgumentParserOptionDefinitionKey = @"CLUArgumentParserOptionDefinition";

@implementation CLUArgumentParser
{
	NSMutableArray *_definitions;
}

- (id)init
{
	self = [super init];
	if (self == nil) {
		return nil;
	}
	
	_definitions = [[NSMutableArray alloc] init];
	
	return self;
}

- (CLUOptionDefinition *)addLiteralOptionWithShortNames:(NSString *)shortNames longNames:(NSString *)longNames
{
	CLULiteralOptionDefinition *definition = [[CLULiteralOptionDefinition alloc] initWithShortNames:shortNames longNames:longNames];
	if (definition == nil) {
		return nil;
	}
	
	[_definitions addObject:definition];
	
	return definition;
}

- (CLUIntegerOptionDefinition *)addIntegerOptionWithShortNames:(NSString *)shortNames longNames:(NSString *)longNames
{
	CLUIntegerOptionDefinition *definition = [[CLUIntegerOptionDefinition alloc] initWithShortNames:shortNames longNames:longNames];
	if (definition == nil) {
		return nil;
	}
	
	[_definitions addObject:definition];
	
	return definition;
}

- (CLUStringOptionDefinition *)addStringOptionWithShortNames:(NSString *)shortNames longNames:(NSString *)longNames
{
	CLUStringOptionDefinition *definition = [[CLUStringOptionDefinition alloc] initWithShortNames:shortNames longNames:longNames];
	if (definition == nil) {
		return nil;
	}
	
	[_definitions addObject:definition];
	
	return definition;
}

- (BOOL)parseArguments:(const char **)args count:(NSUInteger)count errors:(NSArray **)errorsPtr
{
	NSUInteger definitionCount = _definitions.count;
	void **argtable = malloc((definitionCount + 1) * sizeof(void *));
	
	for (NSUInteger i = 0; i < definitionCount; i++) {
		argtable[i] = [[_definitions objectAtIndex:i] argtableRepresentation];
	}
	
	argtable[definitionCount] = arg_end((int)count + 2);
	
	NSUInteger numberOfErrors = arg_parse((int)count, (char **)args, argtable);
	if (numberOfErrors > 0 && errorsPtr != NULL) {
		NSString *effectiveProgramName = self.programName;
		if (effectiveProgramName == nil) {
			effectiveProgramName = [[NSString stringWithUTF8String:args[0]] lastPathComponent];
		}
		
		struct arg_end *end = (struct arg_end *)argtable[definitionCount];
		
		// Construct a pipe for getting the error strings from argtable
		NSPipe *pipe = [NSPipe pipe];
		NSFileHandle *readingFileHandle = [pipe fileHandleForReading];
		NSFileHandle *writingFileHandle = [pipe fileHandleForWriting];
		int fileDescriptor = writingFileHandle.fileDescriptor;
		FILE *fileStream = fdopen(fileDescriptor, "w");
		
		// Create the error objects
		NSCharacterSet *trimmingCharacterSet = [NSCharacterSet whitespaceAndNewlineCharacterSet];
		NSMutableArray *errors = [NSMutableArray arrayWithCapacity:numberOfErrors];
		
		for (NSUInteger i = 0; i < numberOfErrors; i++) {
			
			struct arg_hdr *errorParent = (struct arg_hdr *)(end->parent[i]);
			if (errorParent->errorfn == NULL) {
				continue;
			}
			
			NSInteger errorCode = 0;
			
			// Skip internal regex errors
			if ((end->error[i] & ARG_EREGEX_FLAG) != 0) {
				continue;
			}
			
			// Convert the error code to the CLUArgumentParserErrorDomain
			switch (end->error[i]) {
				case ARG_ELIMIT:
				case ARG_EMALLOC:
					continue;
					
				case ARG_ENOMATCH:
					errorCode = CLUArgumentParserUnexpectedOptionError;
					break;
					
				case ARG_ELONGOPT:
					errorCode = CLUArgumentParserInvalidLongOptionError;
					break;
					
				case ARG_EMISSARG:
					errorCode = CLUArgumentParserMissingArgumentError;
					break;
					
				case ARG_EMINCOUNT:
					errorCode = CLUArgumentParserMinCountError;
					break;
					
				case ARG_EMAXCOUNT:
					errorCode = CLUArgumentParserMaxCountError;
					break;
					
				case ARG_EBADDATE:
					break;
					
				case ARG_EBADDOUBLE:
					break;
					
				case ARG_EBADINT:
					errorCode = CLUArgumentParserBadInteger;
					break;
					
				case ARG_EINTOVERFLOW:
					errorCode = CLUArgumentParserIntegerOverflow;
					break;
					
				default:
					errorCode = CLUArgumentParserInvalidShortOptionError;
					break;
					
			}
			
			// Print the error string to the pipe
			errorParent->errorfn(end->parent[i], fileStream, end->error[i], end->argval[i], effectiveProgramName.UTF8String);
			
			// Flush the pipe and get the available data from the other end
			fflush(fileStream);
			NSData *stringData = readingFileHandle.availableData;
			
			// Construct the error string and trim it
			NSString *errorString = [[NSString alloc] initWithData:stringData encoding:NSUTF8StringEncoding];
			errorString = [errorString stringByTrimmingCharactersInSet:trimmingCharacterSet];
			
			CLUOptionDefinition *relatedDefinition = nil;
			for (NSUInteger j = 0; j < definitionCount; j++) {
				if (errorParent == argtable[j]) {
					relatedDefinition = _definitions[j];
					break;
				}
			}
			
			NSMutableDictionary *userInfo = [NSMutableDictionary dictionary];
			userInfo[NSLocalizedFailureReasonErrorKey] = errorString;
			
			if (relatedDefinition != nil) {
				userInfo[CLUArgumentParserOptionDefinitionKey] = relatedDefinition;
			}
			
			NSError *error = [NSError errorWithDomain:CLUArgumentParserErrorDomain code:errorCode userInfo:userInfo];
			[errors addObject:error];
		}
		
		fclose(fileStream);
		
		(*errorsPtr) = errors;
	}
	
	for (CLUOptionDefinition *definition in _definitions) {
		[definition finishParsing];
	}
	
	free(argtable[definitionCount]);
	free(argtable);
	
	return numberOfErrors == 0;
}

- (NSString *)usageString
{
	NSUInteger definitionCount = _definitions.count;
	void **argtable = malloc((definitionCount + 1) * sizeof(void *));
	
	for (NSUInteger i = 0; i < definitionCount; i++) {
		argtable[i] = [[_definitions objectAtIndex:i] argtableRepresentation];
	}
	
	argtable[definitionCount] = arg_end(0);

	// Construct a pipe for getting the string from argtable
	NSPipe *pipe = [NSPipe pipe];
	NSFileHandle *readingFileHandle = [pipe fileHandleForReading];
	NSFileHandle *writingFileHandle = [pipe fileHandleForWriting];
	int fileDescriptor = writingFileHandle.fileDescriptor;
	FILE *fileStream = fdopen(fileDescriptor, "w");
	
	fprintf(fileStream, "%s", self.programName.UTF8String);
	arg_print_syntax(fileStream, argtable, "\n");
	arg_print_glossary_gnu(fileStream, argtable);
	
	free(argtable[definitionCount]);
	free(argtable);
	
	// Flush the pipe and get the available data from the other end
	fflush(fileStream);
	fclose(fileStream);
	NSData *stringData = readingFileHandle.availableData;
	
	return [[[NSString alloc] initWithData:stringData encoding:NSUTF8StringEncoding] stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
}

@end
