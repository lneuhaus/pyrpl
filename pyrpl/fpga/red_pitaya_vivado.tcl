################################################################################
# Vivado tcl script for building RedPitaya FPGA in non project mode
#
# Usage:
# vivado -mode batch -source red_pitaya_vivado.tcl -tclargs default build/default
################################################################################

################################################################################
# define paths
################################################################################

# Resolve every source relative to this script, not Vivado's launch directory.
# Avoid `file normalize` here: some sandboxed Windows launchers canonicalize a
# mapped workspace incorrectly. Tcl and Vivado accept forward-slash paths.
set script_dir [string map {\\ /} [file dirname [info script]]]
cd $script_dir

set profile [lindex $argv 0]
if {$profile eq ""} {
    set profile default
}
set profile_script [file join profiles $profile profile.tcl]
if {![file exists $profile_script]} {
    error "Unknown FPGA profile '$profile': missing $profile_script"
}
source $profile_script
if {$profile_id ne $profile} {
    error "Profile file $profile_script declares '$profile_id', expected '$profile'"
}

set path_rtl rtl
set path_ip  ip
set path_sdc sdc

set path_out [lindex $argv 1]
if {$path_out eq ""} {
    # Preserve the historical direct-script/Makefile output locations. The
    # profile-aware wrappers always pass an isolated path explicitly.
    set path_out out
    set path_sdk sdk
} else {
    set path_sdk [file join $path_out sdk]
}
# Windows batch files naturally pass backslashes. Convert them without asking
# Tcl to canonicalize the workspace path, then make relative paths script-local.
set path_out [string map {\\ /} $path_out]
set path_sdk [string map {\\ /} $path_sdk]
if {[file pathtype $path_out] eq "relative"} {
    set path_out [file join $script_dir $path_out]
}
if {[file pathtype $path_sdk] eq "relative"} {
    set path_sdk [file join $script_dir $path_sdk]
}

file mkdir $path_out
file mkdir $path_sdk

################################################################################
# setup an in memory project
################################################################################

set part xc7z010clg400-1

# Some non-interactive Windows launchers cannot create Vivado's per-user Tcl
# store. Ensure the bundled simulator app needed by project initialization is
# discoverable directly from the installation in that case.
set bundled_tcl_store [file join $::env(XILINX_VIVADO) data XilinxTclStore]
set bundled_xsim [file join $bundled_tcl_store tclapp xilinx xsim]
if {[file isdirectory $bundled_xsim]} {
    source [file join $bundled_tcl_store support appinit appinit.tcl]
    lappend auto_path $bundled_xsim
    # Vivado's package resolver still consults the unwritable per-user app
    # store before auto_path. Source and register the bundled app directly.
    source [file join $bundled_xsim xsim.tcl]
    ::tclapp::support::appinit::load_app \
        $bundled_tcl_store ::tclapp::xilinx::xsim
}

create_project -in_memory -part $part

# Return a profile-specific implementation when one exists, otherwise use the
# shared timing-optimized RTL. Module names and addresses remain unchanged.
proc rtl_source {path_rtl overrides filename} {
    if {[dict exists $overrides $filename]} {
        set source [dict get $overrides $filename]
    } else {
        set source [file join $path_rtl $filename]
    }
    if {![file exists $source]} {
        error "RTL source does not exist: $source"
    }
    return $source
}

# experimental attempts to avoid a warning
#get_projects
#get_designs
#list_property  [current_project]
#set_property FAMILY 7SERIES [current_project]
#set_property SIM_DEVICE 7SERIES [current_project]

################################################################################
# create PS BD (processing system block design)
################################################################################

# file was created from GUI using "write_bd_tcl -force ip/system_bd.tcl"
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

# template
#read_verilog                      $path_rtl/...

read_verilog                      .gen/sources_1/bd/system/hdl/system_wrapper.v

read_verilog                      $path_rtl/axi_master.v
read_verilog                      $path_rtl/axi_slave.v
read_verilog                      $path_rtl/axi_wr_fifo.v

read_verilog                      $path_rtl/red_pitaya_ams.v
read_verilog                      $path_rtl/red_pitaya_asg_ch.v
read_verilog                      $path_rtl/red_pitaya_asg.v
read_verilog                      $path_rtl/red_pitaya_dfilt1.v
read_verilog                      $path_rtl/red_pitaya_hk.v
read_verilog                      [rtl_source $path_rtl $rtl_overrides red_pitaya_pid_block.v]
set dsp_rtl_source [rtl_source $path_rtl $rtl_overrides red_pitaya_dsp.v]
read_verilog $dsp_rtl_source
read_verilog                      $path_rtl/red_pitaya_pll.sv
read_verilog                      $path_rtl/red_pitaya_ps.v
read_verilog                      [rtl_source $path_rtl $rtl_overrides red_pitaya_pwm.sv]
read_verilog                      $path_rtl/red_pitaya_scope.v
read_verilog                      $path_rtl/red_pitaya_top.v

#custom modules
read_verilog                      $path_rtl/red_pitaya_adv_trigger.v
read_verilog                      $path_rtl/red_pitaya_saturate.v
read_verilog                      $path_rtl/red_pitaya_product_sat.v
read_verilog                      $path_rtl/red_pitaya_arithmetic_block.v
read_verilog                      $path_rtl/red_pitaya_cordic_block.v
read_verilog                      [rtl_source $path_rtl $rtl_overrides red_pitaya_iir_block.v]
read_verilog                      [rtl_source $path_rtl $rtl_overrides red_pitaya_iq_modulator_block.v]
read_verilog                      $path_rtl/red_pitaya_lpf_block.v
read_verilog                      $path_rtl/red_pitaya_filter_block.v
#read_verilog                     $path_rtl/red_pitaya_iq_lpf_block.v
read_verilog                      $path_rtl/red_pitaya_iq_demodulator_block.v
read_verilog                      $path_rtl/red_pitaya_pfd_block.v
#read_verilog                     $path_rtl/red_pitaya_iq_hpf_block.v
read_verilog                      $path_rtl/red_pitaya_iq_fgen_block.v
read_verilog                      $path_rtl/red_pitaya_iq_trigger.v
read_verilog                      $path_rtl/red_pitaya_iq_block.v
read_verilog                      $path_rtl/red_pitaya_trigger_block.v
read_verilog                      $path_rtl/red_pitaya_prng.v

#constraints
read_xdc                          $path_sdc/red_pitaya.xdc

################################################################################
# run synthesis
# report utilization and timing estimates
# write checkpoint design
################################################################################

#synth_design -top red_pitaya_top
set synth_args [list -top red_pitaya_top -flatten_hierarchy none -bufg 16 -keep_equivalent_registers]
if {[info exists synth_generics] && [llength $synth_generics] > 0} {
    lappend synth_args -generic $synth_generics
}
# Vivado 2024.2 on Windows occasionally starts synthesis in a helper process
# that cannot read files from its own installation (most visibly
# scripts/rt/data/common.tcl). Keep synthesis in the parent process, then
# restore the configured thread count before the longer implementation stages.
# Linux builds retain Vivado's normal parallel synthesis.
set synthesis_thread_count ""
if {$tcl_platform(platform) eq "windows"} {
    set synthesis_thread_count [get_param general.maxThreads]
    puts "Using single-threaded Windows synthesis to avoid the Vivado helper-process file-access bug."
    set_param general.maxThreads 1
}
synth_design {*}$synth_args
if {$synthesis_thread_count ne ""} {
    set_param general.maxThreads $synthesis_thread_count
    puts "Restored Vivado thread count to $synthesis_thread_count for implementation."
}

write_checkpoint         -force   $path_out/post_synth
report_timing_summary    -file    $path_out/post_synth_timing_summary.rpt
report_power             -file    $path_out/post_synth_power.rpt

################################################################################
# run placement and logic optimization
# report utilization and timing estimates
# write checkpoint design
################################################################################

opt_design
power_opt_design
# The design is routing-limited at high slice utilization. Give placement more
# weight to estimated net delay, then use the most timing-focused physical
# optimization pass before routing.
place_design            -directive $place_directive
phys_opt_design         -directive $phys_opt_directive
write_checkpoint         -force   $path_out/post_place
report_timing_summary    -file    $path_out/post_place_timing_summary.rpt
#write_hwdef              -file    $path_sdk/red_pitaya.hwdef

################################################################################
# run router
# report actual utilization and timing,
# write checkpoint design
# run drc, write verilog and xdc out
################################################################################

# Explore additional timing-driven routes, then optimize the real routed
# critical paths. The post-route pass does not alter RTL pipeline latency.
route_design             -directive $route_directive
# Preserve the expensive routed result before post-route optimization.  This
# also makes an abrupt Vivado termination diagnosable and recoverable.
write_checkpoint         -force   $path_out/post_route_unoptimized
report_timing_summary    -file    $path_out/post_route_unoptimized_timing_summary.rpt
# On Vivado 2024.2, phys_opt_design detects that the design is routed; there is
# no separate -post_route command-line option. The pass count is profile-specific
# because dense profiles may need another iteration to close the routed design.
if {[info exists post_route_phys_opt_max_threads]} {
    set_param general.maxThreads $post_route_phys_opt_max_threads
}
for {set pass 0} {$pass < $post_route_phys_opt_passes} {incr pass} {
    puts "Running post-route physical optimization pass [expr {$pass + 1}] of $post_route_phys_opt_passes"
    phys_opt_design      -directive $phys_opt_directive
    set completed_pass [expr {$pass + 1}]
    write_checkpoint -force $path_out/post_route_phys_opt_${completed_pass}
    report_timing_summary -file $path_out/post_route_phys_opt_${completed_pass}_timing_summary.rpt
}
write_checkpoint         -force   $path_out/post_route
report_timing_summary    -file    $path_out/post_route_timing_summary.rpt
report_timing            -file    $path_out/post_route_timing.rpt -sort_by group -max_paths 100 -path_type summary
report_clock_utilization -file    $path_out/clock_util.rpt
report_utilization       -file    $path_out/post_route_util.rpt
report_power             -file    $path_out/post_route_power.rpt
report_drc               -file    $path_out/post_imp_drc.rpt
#write_verilog            -force   $path_out/bft_impl_netlist.v
#write_xdc -no_fixed_only -force   $path_out/bft_impl.xdc

################################################################################
# generate a bitstream
################################################################################

set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]
write_bitstream -force $path_out/red_pitaya.bit

################################################################################
# generate the .bin file for flashing
################################################################################

set_property BITSTREAM.GENERAL.COMPRESS FALSE [current_design]
write_bitstream -force $path_out/red_pitaya_uncompressed.bit
write_cfgmem -force -format BIN -size 2 -interface SMAPx32 -disablebitswap -loadbit "up 0x0 $path_out/red_pitaya_uncompressed.bit" $path_out/red_pitaya.bin

################################################################################
# generate system definition
################################################################################

write_hw_platform -include_bit -fixed -force $path_sdk/red_pitaya.xsa
validate_hw_platform $path_sdk/red_pitaya.xsa

file copy -force .gen/sources_1/bd/system/hw_handoff/system.hwh $path_sdk/red_pitaya.hwh

exit
