.PHONY: all
SHELL:=/bin/bash
VIVADO_PATH:=/opt/Xilinx/Vivado/2015.4/settings64.sh
SOURCE_FILE=monitor_server.c
	
all: clean monitor_server monitor_server_0.95

monitor_server:  # for version 0.92
	source $(VIVADO_PATH) && arm-xilinx-linux-gnueabi-gcc -o monitor_server $(SOURCE_FILE)

monitor_server_0.95:
	source $(VIVADO_PATH) && arm-linux-gnueabihf-gcc -o monitor_server_0.95 $(SOURCE_FILE)

clean: 
	rm -f monitor_server_*
