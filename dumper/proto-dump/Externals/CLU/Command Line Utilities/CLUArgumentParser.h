//
//  CLUArgumentParser.h
//  Command Line Utilities
//
//  Created by Sean Patrick O'Brien on 8/2/12.
//  Copyright (c) 2012 Sean Patrick O'Brien. All rights reserved.
//

#import <Foundation/Foundation.h>

#import "CLUOptionDefinition.h"


@interface CLUArgumentParser : NSObject

@property(copy) NSString *programName;

- (CLUOptionDefinition *)addLiteralOptionWithShortNames:(NSString *)shortNames longNames:(NSString *)longNames;
- (CLUIntegerOptionDefinition *)addIntegerOptionWithShortNames:(NSString *)shortNames longNames:(NSString *)longNames;
- (CLUStringOptionDefinition *)addStringOptionWithShortNames:(NSString *)shortNames longNames:(NSString *)longNames;

- (BOOL)parseArguments:(const char **)args count:(NSUInteger)count errors:(NSArray **)errorsPtr;

- (NSString *)usageString;

@end

extern NSString * const CLUArgumentParserErrorDomain;

// The instance of CLUOptionDefinition associated with the error
extern NSString * const CLUArgumentParserOptionDefinitionKey;

enum {
	// An extra argument was passed in
	CLUArgumentParserUnexpectedOptionError		= 1,
	
	// Unrecognized long option
	CLUArgumentParserInvalidLongOptionError		= 2,
	
	// Unrecognized short option
	CLUArgumentParserInvalidShortOptionError	= 3,
	
	// An option was expecting an argument but didn't find one
	CLUArgumentParserMissingArgumentError		= 4,
	
	// Too few instances of an expected option
	CLUArgumentParserMinCountError				= 5,
	
	// Too many instances of an option
	CLUArgumentParserMaxCountError				= 6,
	
	CLUArgumentParserBadInteger					= 7,
	
	CLUArgumentParserIntegerOverflow			= 8
};
