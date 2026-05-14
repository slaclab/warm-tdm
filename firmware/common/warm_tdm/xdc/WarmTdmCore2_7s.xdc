## fabRefClk from ClockDist (7-series: IBUFDS_GTE2 ODIV2 → BUFG)
create_generated_clock -name fabRefClk0 [get_pins -hier -filter {NAME =~ */U_ClockDist_1/*/ODIV2}]

## 7-Series specific clock constraints (DNA, ICAP)
create_generated_clock -name dnaDivClk [get_pins -hier -filter {NAME =~ */DeviceDna*/*BUFR*/O}]
create_generated_clock -name icapClk   [get_pins -hier -filter {NAME =~ */Iprog*/*BUFR*/O}]

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks dnaDivClk] \
    -group [get_clocks icapClk]

## Timing clocks (from PLL on 7-series)
create_generated_clock -name timingTxBitClk  [get_pins -hier -filter {NAME =~ *U_TimingTx*/CLKOUT0}]
create_generated_clock -name timingTxWordClk [get_pins -hier -filter {NAME =~ *U_TimingTx*/CLKOUT1}]
create_generated_clock -name timingRxBitClk  [get_pins -hier -filter {NAME =~ *U_TimingRx*/CLKOUT0}]
create_generated_clock -name timingRxWordClk [get_pins -hier -filter {NAME =~ *U_TimingRx*/CLKOUT1}]

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks timingTxWordClk] \
    -group [get_clocks timingRxWordClk]

## PGP GT recovered clocks (GTX on 7-series)
create_clock -name pgpTxRecClk -period 16.000 [get_pins -hier -filter {NAME =~ *U_PgpCore_1/*/TXOUTCLK}]

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks pgpClk] \
    -group [get_clocks pgpTxRecClk]
