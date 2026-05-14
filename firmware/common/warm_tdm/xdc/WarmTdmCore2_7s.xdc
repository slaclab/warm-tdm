## 7-Series specific clock constraints (DNA, ICAP)
create_generated_clock -name dnaDivClk [get_pins -hier -filter {NAME =~ */DeviceDna*/*BUFR*/O}]
create_generated_clock -name icapClk   [get_pins -hier -filter {NAME =~ */Iprog*/*BUFR*/O}]

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks dnaDivClk] \
    -group [get_clocks icapClk]

## PGP GT recovered clocks (GTX on 7-series)
create_clock -name pgpTxRecClk -period 16.000 [get_pins -hier -filter {NAME =~ *U_PgpCore_1/*/TXOUTCLK}]

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks pgpClk] \
    -group [get_clocks pgpTxRecClk]
