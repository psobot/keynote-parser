//
//  CLUOptionDefinition.h
//  Command Line Utilities
//
//  Created by Sean Patrick O'Brien on 8/2/12.
//  Copyright (c) 2012 Sean Patrick O'Brien. All rights reserved.
//

#import <Foundation/Foundation.h>


@interface CLUOptionDefinition : NSObject

@property NSUInteger minCount;
@property NSUInteger maxCount;
@property(readonly) NSUInteger count;

@property(readonly) NSArray *values;

@property BOOL hasOptionalArgument;

@property(copy) NSString *optionDescription;
@property(copy) NSString *dataTypeDescription;

@end



@interface CLUIntegerOptionDefinition : CLUOptionDefinition

- (NSInteger)valueAtIndex:(NSUInteger)anIndex;

- (void)setDefaultValue:(NSInteger)value atIndex:(NSUInteger)anIndex;
- (NSInteger)defaultValueAtIndex:(NSUInteger)anIndex;

@end



@interface CLUStringOptionDefinition : CLUOptionDefinition

- (NSString *)valueAtIndex:(NSUInteger)anIndex;

- (void)setDefaultValue:(NSString *)value atIndex:(NSUInteger)anIndex;
- (NSString *)defaultValueAtIndex:(NSUInteger)anIndex;

@end
