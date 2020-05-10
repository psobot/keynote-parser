//
//  CLUOptionDefinitionPrivate.h
//  Command Line Utilities
//
//  Created by Sean Patrick O'Brien on 8/2/12.
//  Copyright (c) 2012 Sean Patrick O'Brien. All rights reserved.
//

#import "CLUOptionDefinition.h"


@interface CLUOptionDefinition ()

- (id)initWithShortNames:(NSString *)shortNames longNames:(NSString *)longNames;

- (void *)argtableRepresentation;
- (NSArray *)copyValuesFromArgtable;
- (void)finishParsing;

@end


@interface CLULiteralOptionDefinition : CLUOptionDefinition
@end
