#!/bin/sh

###
# Set up the enviroment
###
export ROOT=$PWD
export EPD_BUILD_DIR=$ROOT/intermediate
export EPD_PRODUCT_DIR=$ROOT/prebuilt

export EPD_PROTOBUF_VERSION=2.5.0

# Exit if anything fails
set -e
