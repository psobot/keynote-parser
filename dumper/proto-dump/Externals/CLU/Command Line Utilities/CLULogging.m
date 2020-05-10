//
//  CLULogging.m
//  Command Line Utilities
//
//  Created by Sean Patrick O'Brien on 8/2/12.
//  Copyright (c) 2012 Sean Patrick O'Brien. All rights reserved.
//

#import "CLULogging.h"

void CLULog(NSString *format, ...)
{
	va_list args;
	va_start(args, format);
	
	CLULogv(format, args);
	
	va_end(args);
}

void CLULogv(NSString *format, va_list args)
{
	NSString *string = [[NSString alloc] initWithFormat:format arguments:args];
	printf("%s\n", string.UTF8String);
}

void CLULogf(FILE *file, NSString *format, ...)
{
	va_list args;
	va_start(args, format);
	
	CLULogfv(file, format, args);
	
	va_end(args);
}

void CLULogfv(FILE *file, NSString *format, va_list args)
{
	NSString *string = [[NSString alloc] initWithFormat:format arguments:args];
	fprintf(file, "%s\n", string.UTF8String);
}
