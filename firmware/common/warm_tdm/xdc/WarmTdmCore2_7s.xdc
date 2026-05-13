## 7-Series specific clock constraints (DNA, ICAP)
create_generated_clock -name dnaDivClk [get_pins -hier -filter {NAME =~ */DeviceDna*/*BUFR*/O}]
create_generated_clock -name icapClk   [get_pins -hier -filter {NAME =~ */Iprog*/*BUFR*/O}]

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks dnaDivClk] \
    -group [get_clocks icapClk]
