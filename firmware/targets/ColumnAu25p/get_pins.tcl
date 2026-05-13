create_project -in_memory -part xcau25p-sfvb784-1-e
set_property design_mode PinPlanning [current_fileset]
open_io_design -name io_1

set fp [open "/tmp/au25p_pins.txt" w]
foreach pin [lsort [get_package_pins -filter {IS_GENERAL_PURPOSE}]] {
    set bank [get_property BANK $pin]
    set name [get_property NAME $pin]
    set pair [get_property DIFF_PAIR_PIN $pin]
    set master [get_property IS_MASTER $pin]
    puts $fp "$name $bank $pair $master"
}
close $fp

close_design
close_project
