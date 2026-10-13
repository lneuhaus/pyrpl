# Two-input arithmetic profile: no IIR or PID prefilters, derivatives enabled
# on all PIDs, and an arithmetic block in stable DSP slot 4.
set profile_id arithmetic
set rtl_overrides [dict create \
    red_pitaya_dsp.v rtl_profiles/no_iir/red_pitaya_dsp.v]
set synth_generics {PID_DERIVATIVE=1 PID_FILTERSTAGES=0 PID_DERIVATIVE_FILTER_SHIFT=4 ARITHMETIC=1}
set place_directive ExtraTimingOpt
set phys_opt_directive AggressiveExplore
set route_directive AggressiveExplore
set post_route_phys_opt_passes 2
set post_route_phys_opt_max_threads 1
