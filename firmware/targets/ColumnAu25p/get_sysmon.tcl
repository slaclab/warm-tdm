create_project -in_memory -part xcau25p-sfvb784-1-e
set_property design_mode PinPlanning [current_fileset]
open_io_design -name io_1

set fp [open "/tmp/au25p_sysmon.txt" w]
puts $fp "=== All pins with SYSMON/ADC functions ==="
foreach pin [get_package_pins] {
    set name [get_property NAME $pin]
    set func [get_property PIN_FUNC $pin]
    if {[string match "*AUX*" $func] || [string match "*SYSMON*" $func] || [string match "*AD*" $func] || [string match "*VP*" $func] || [string match "*VN*" $func]} {
        set bank [get_property BANK $pin]
        puts $fp "$name bank=$bank func=$func"
    }
}

puts $fp "\n=== Pin functions containing numbers (potential VAUX) ==="
foreach pin [get_package_pins -filter {PIN_FUNC_COUNT > 1}] {
    set name [get_property NAME $pin]
    set func [get_property PIN_FUNC $pin]
    set bank [get_property BANK $pin]
    if {[string match "*AUX*" $func] || [string match "*AD*" $func]} {
        puts $fp "$name bank=$bank func=$func"
    }
}
close $fp

close_design
close_project
