##
# $Id: Makefile 1249 2014-02-22 20:21:40Z ales.bardorfer $
#
# (c) Red Pitaya  http://www.redpitaya.com
#
# Monitor utility project file. To build executable for acquire utility run:
# 'make all'
#
# This project file is written for GNU/Make software. For more details please 
# visit: http://www.gnu.org/software/make/manual/make.html
# GNU Compiler Collection (GCC) tools are used for the compilation and linkage. 
# For the details about the usage and building please visit:
# http://gcc.gnu.org/onlinedocs/gcc/
#

###############################################################################
#    pyrplockbox - DSP servo controller for quantum optics with the RedPitaya
#    Copyright (C) 2014-2016  Leonhard Neuhaus  (neuhaus@spectro.jussieu.fr)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
############################################################################### 

# Versioning system
VERSION ?= 0.00-0000
REVISION ?= devbuild

# List of compiled object files (not yet linked to executable)
OBJS = monitor_server.o
# List of raw source files (all object files, renamed from .o to .c)
SRCS = $(subst .o,.c, $(OBJS)))

# Executable name
TARGET=monitor_server

# GCC compiling & linking flags
CFLAGS=-g -std=gnu99 -Wall -Werror
CFLAGS += -DVERSION=$(VERSION) -DREVISION=$(REVISION)

# Red Pitaya common SW directory
SHARED=../../shared/

# Additional libraries which needs to be dynamically linked to the executable
# -lm - System math library (used by cos(), sin(), sqrt(), ... functions)
LIBS=-lm -lpthread

#Cross-compile default
CROSS_COMPILE=arm-linux-gnueabi-

# Main GCC executable (used for compiling and linking)
CC=$(CROSS_COMPILE)gcc

# Main Makefile target 'all' - it iterates over all targets listed in $(TARGET)
# variable.
all: $(TARGET)

%.o: %.c version.h
	$(CC) -c $(CFLAGS) $< -o $@

$(TARGET): $(OBJS)
	$(CC) -o $@ $^ $(CFLAGS) $(LIBS)

# Clean target - when called it cleans all object files and executables.
clean:
	rm -f $(TARGET) *.o
