#!/bin/sh

# To remove intermediates, run:
#   ./clean.sh 
# To remove all build products, run:
#   ./clean.sh --all

###
# Set up the enviroment
###
source common.sh

###
# Remove build directories
###
rm -rf "$EPD_BUILD_DIR"

if [[ $* == *--all* ]]
	then
		rm -rf "$EPD_PRODUCT_DIR"
fi

rm -rf protobuf-$EPD_PROTOBUF_VERSION
