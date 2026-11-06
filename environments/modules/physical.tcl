# Run from the pinned OpenROAD/test directory. The upstream sample owns its
# implementation flow; this wrapper only adds acceptance measurements.
source gcd_nangate45.tcl
puts "MODULE_ROUTED [design_is_routed]"
puts "MODULE_DRC [detailed_route_num_drvs]"
puts "MODULE_ANTENNA [ant::antenna_violation_count]"
check_setup -verbose
# Independently exercise the timing checker on the same routed design.
create_clock [get_ports clk] -name core_clock -period 2.0
set_propagated_clock [all_clocks]
puts "MODULE_RELAXED_SETUP [sta::worst_slack -max]"
report_worst_slack -max
create_clock [get_ports clk] -name core_clock -period 0.01
set_propagated_clock [all_clocks]
puts "MODULE_TIGHT_SETUP [sta::worst_slack -max]"
report_worst_slack -max
