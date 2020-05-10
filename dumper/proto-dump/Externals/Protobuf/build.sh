#!/bin/sh

###
# Set up the enviroment
###
source common.sh

###
# Prepare build directories
###
rm -rf "$EPD_BUILD_DIR"
rm -rf "$EPD_PRODUCT_DIR"
mkdir "$EPD_BUILD_DIR"
mkdir "$EPD_PRODUCT_DIR"

###
# Clean up any existing sources and extract new ones
###
rm -rf protobuf_$EPD_PROTOBUF_VERSION
tar -xzf packages/protobuf-$EPD_PROTOBUF_VERSION.tar.gz

###
# Build Protobuf
###
cd "$ROOT/protobuf-$EPD_PROTOBUF_VERSION"
./configure --prefix="$EPD_BUILD_DIR"
make install

###
# Copy build products
###
mkdir $EPD_PRODUCT_DIR/include $EPD_PRODUCT_DIR/lib
cp -r $EPD_BUILD_DIR/include/* $EPD_PRODUCT_DIR/include/
for libname in libprotobuf.a; do
	cp $EPD_BUILD_DIR/lib/$libname $EPD_PRODUCT_DIR/lib/$libname
done
