################################################################################
# Vivado tcl script for building RedPitaya FPGA in non project mode
#
# Usage:
# vivado -mode batch -source red_pitaya_vivado_project.tcl
################################################################################

################################################################################
# define paths
################################################################################

set path_rtl rtl
set path_ip  ip
set path_sdc sdc

################################################################################
# setup a project on disk
################################################################################

set part xc7z010clg400-1

create_project -part $part -force pyrpl ./project

################################################################################
# create PS BD (processing system block design)
################################################################################

# create PS BD
source                            $path_ip/system_bd.tcl

# generate SDK files
generate_target all [get_files    system.bd]

################################################################################
# read files:
# 1. RTL design sources
# 2. IP database files
# 3. constraints
################################################################################

read_verilog                      ./project/pyrpl.srcs/sources_1/bd/system/hdl/system_wrapper.v

add_files                         $path_rtl/axi_master.v
add_files                         $path_rtl/axi_slave.v
add_files                         $path_rtl/axi_wr_fifo.v

add_files                      $path_rtl/red_pitaya_ams.v
add_files                      $path_rtl/red_pitaya_asg_ch.v
add_files                      $path_rtl/red_pitaya_asg.v
add_files                      $path_rtl/red_pitaya_dfilt1.v
add_files                      $path_rtl/red_pitaya_hk.v
add_files                      $path_rtl/red_pitaya_pid_block.v
add_files                      $path_rtl/red_pitaya_dsp.v
add_files                      $path_rtl/red_pitaya_pll.sv
add_files                      $path_rtl/red_pitaya_ps.v
add_files                      $path_rtl/red_pitaya_pwm.sv
add_files                      $path_rtl/red_pitaya_scope.v
add_files                      $path_rtl/red_pitaya_top.v

# Custom modules for FPGA (adapted from red_pitaya_vivado.tcl)
add_files                      $path_rtl/red_pitaya_adv_trigger.v
add_files                      $path_rtl/red_pitaya_saturate.v
add_files                      $path_rtl/red_pitaya_product_sat.v
add_files                      $path_rtl/red_pitaya_iir_block.v
add_files                      $path_rtl/red_pitaya_iq_modulator_block.v
add_files                      $path_rtl/red_pitaya_lpf_block.v
add_files                      $path_rtl/red_pitaya_filter_block.v
#add_files                     $path_rtl/red_pitaya_iq_lpf_block.v
add_files                      $path_rtl/red_pitaya_iq_demodulator_block.v
add_files                      $path_rtl/red_pitaya_pfd_block.v
#add_files                     $path_rtl/red_pitaya_iq_hpf_block.v
add_files                      $path_rtl/red_pitaya_iq_fgen_block.v
add_files                      $path_rtl/red_pitaya_iq_block.v
add_files                      $path_rtl/red_pitaya_trigger_block.v
add_files                      $path_rtl/red_pitaya_prng.v

add_files -fileset constrs_1      $path_sdc/red_pitaya.xdc

import_files -force

update_compile_order -fileset sources_1

################################################################################
# Start GUI, if necessary (disabled by default)
################################################################################

#start_gui
