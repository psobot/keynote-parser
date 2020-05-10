//
//  CLUOptionDefinition.m
//  Command Line Utilities
//
//  Created by Sean Patrick O'Brien on 8/2/12.
//  Copyright (c) 2012 Sean Patrick O'Brien. All rights reserved.
//

#import "CLUOptionDefinition.h"
#import "CLUOptionDefinitionPrivate.h"

#import "argtable2.h"


@implementation CLUOptionDefinition
{
	NSString *_shortNames;
	NSString *_longNames;
	NSArray *_values;
	NSMutableDictionary *_defaultValues;
}

- (id)initWithShortNames:(NSString *)shortNames longNames:(NSString *)longNames
{
	self = [self init];
	if (self == nil) {
		return nil;
	}
	
	_shortNames = shortNames;
	_longNames = longNames;
	
	_minCount = 0;
	_maxCount = 1;
	
	return self;
}

- (NSString *)description
{
	return [NSString stringWithFormat:@"<%@: %p, %@, %@>", NSStringFromClass(self.class), self, _shortNames, _longNames];
}

- (void *)argtableRepresentation
{
	return NULL;
}

- (NSArray *)copyValuesFromArgtable
{
	return nil;
}

- (void)finishParsing
{
	NSArray *values = [self copyValuesFromArgtable];
	_values = values;
	_count = values.count;
}

- (NSArray *)values
{
	return _values;
}

- (NSString *)shortNames
{
	return _shortNames;
}

- (NSString *)longNames
{
	return _longNames;
}

- (id)objectValueAtIndex:(NSUInteger)anIndex
{
	if (anIndex >= _values.count) {
		return [self defaultObjectValueAtIndex:anIndex];
	}
	
	return _values[anIndex];
}

- (void)setDefaultObjectValue:(id)value atIndex:(NSUInteger)anIndex
{
	if (_defaultValues == nil) {
		_defaultValues = [[NSMutableDictionary alloc] init];
	}
	
	_defaultValues[@(anIndex)] = value;
}

- (id)defaultObjectValueAtIndex:(NSUInteger)anIndex
{
	return _defaultValues[@(anIndex)];
}

@end



@implementation CLUIntegerOptionDefinition
{
	struct arg_int *_argtableRepresentation;
}

- (void)dealloc
{
	if (_argtableRepresentation != NULL) {
		free(_argtableRepresentation);
	}
}

- (void *)argtableRepresentation
{
	if (_argtableRepresentation == NULL) {
		_argtableRepresentation = arg_intn(self.shortNames.UTF8String, self.longNames.UTF8String, self.dataTypeDescription.UTF8String,
										   (int)self.minCount, (int)self.maxCount, self.optionDescription.UTF8String);
		
		if (self.hasOptionalArgument) {
			_argtableRepresentation->hdr.flag |= ARG_HASOPTVALUE;
		}
		
		NSUInteger maxCount = self.maxCount;
		for (NSUInteger i = 0; i < maxCount; i++) {
			_argtableRepresentation->ival[i] = (int)[self defaultValueAtIndex:i];
		}
	}
	
	return _argtableRepresentation;
}

- (NSArray *)copyValuesFromArgtable
{
	NSMutableArray *values = [NSMutableArray arrayWithCapacity:_argtableRepresentation->count];
	for (int i = 0; i < _argtableRepresentation->count; i++) {
		[values addObject:@(_argtableRepresentation->ival[i])];
	}
	
	return values;
}

- (NSInteger)valueAtIndex:(NSUInteger)anIndex
{
	return [[self objectValueAtIndex:anIndex] integerValue];
}

- (void)setDefaultValue:(NSInteger)value atIndex:(NSUInteger)anIndex
{
	[self setDefaultObjectValue:@(value) atIndex:anIndex];
}

- (NSInteger)defaultValueAtIndex:(NSUInteger)anIndex
{
	return [[self defaultObjectValueAtIndex:anIndex] integerValue];
}

@end



@implementation CLUStringOptionDefinition
{
	struct arg_str *_argtableRepresentation;
}

- (void)dealloc
{
	if (_argtableRepresentation != NULL) {
		free(_argtableRepresentation);
	}
}

- (void *)argtableRepresentation
{
	if (_argtableRepresentation == NULL) {
		_argtableRepresentation = arg_strn(self.shortNames.UTF8String, self.longNames.UTF8String, self.dataTypeDescription.UTF8String,
										   (int)self.minCount, (int)self.maxCount, self.optionDescription.UTF8String);
		
		if (self.hasOptionalArgument) {
			_argtableRepresentation->hdr.flag |= ARG_HASOPTVALUE;
		}
		
		NSUInteger maxCount = self.maxCount;
		for (NSUInteger i = 0; i < maxCount; i++) {
			_argtableRepresentation->sval[i] = [[self defaultValueAtIndex:i] UTF8String];
		}
	}
	
	return _argtableRepresentation;
}

- (NSArray *)copyValuesFromArgtable
{
	NSMutableArray *values = [NSMutableArray arrayWithCapacity:_argtableRepresentation->count];
	for (int i = 0; i < _argtableRepresentation->count; i++) {
		[values addObject:[NSString stringWithUTF8String:_argtableRepresentation->sval[i]]];
	}
	
	return values;
}

- (NSString *)valueAtIndex:(NSUInteger)anIndex
{
	return [self objectValueAtIndex:anIndex];
}

- (void)setDefaultValue:(NSString *)value atIndex:(NSUInteger)anIndex
{
	[self setDefaultObjectValue:value atIndex:anIndex];
}

- (NSString *)defaultValueAtIndex:(NSUInteger)anIndex
{
	return [self defaultObjectValueAtIndex:anIndex];
}

@end



@implementation CLULiteralOptionDefinition
{
	struct arg_lit *_argtableRepresentation;
}

- (void)dealloc
{
	if (_argtableRepresentation != NULL) {
		free(_argtableRepresentation);
	}
}

- (void *)argtableRepresentation
{
	if (_argtableRepresentation == NULL) {
		_argtableRepresentation = arg_litn(self.shortNames.UTF8String, self.longNames.UTF8String,
										   (int)self.minCount, (int)self.maxCount, self.optionDescription.UTF8String);
	}
	
	return _argtableRepresentation;
}

- (NSArray *)copyValuesFromArgtable
{
	NSMutableArray *values = [NSMutableArray arrayWithCapacity:_argtableRepresentation->count];
	for (int i = 0; i < _argtableRepresentation->count; i++) {
		[values addObject:[NSNull null]];
	}
	
	return values;
}

@end

