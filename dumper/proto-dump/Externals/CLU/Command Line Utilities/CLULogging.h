//
//  CLULogging.h
//  Command Line Utilities
//
//  Created by Sean Patrick O'Brien on 8/2/12.
//  Copyright (c) 2012 Sean Patrick O'Brien. All rights reserved.
//

#import <Foundation/Foundation.h>

extern void CLULog(NSString *format, ...) NS_FORMAT_FUNCTION(1, 2);
extern void CLULogv(NSString *format, va_list args) NS_FORMAT_FUNCTION(1,0);

extern void CLULogf(FILE *file, NSString *format, ...)  NS_FORMAT_FUNCTION(2, 3);
extern void CLULogfv(FILE *file, NSString *format, va_list args) NS_FORMAT_FUNCTION(2,0);