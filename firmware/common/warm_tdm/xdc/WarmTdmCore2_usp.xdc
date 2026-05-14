## fabRefClk from ClockDist (US+: IBUFDS_GTE4 ODIV2 → BUFG_GT)
create_generated_clock -name fabRefClk0 [get_pins -hier -filter {NAME =~ */U_ClockDist_1/*IBUFDS*_0/ODIV2}]
create_generated_clock -name fabRefClk1 [get_pins -hier -filter {NAME =~ */U_ClockDist_1/*IBUFDS*_1/ODIV2}]

## UltraScale+ timing word clocks (from BUFGCE_DIV, no bit clocks needed)
create_generated_clock -name timingTxWordClk [get_pins -hier -filter {NAME =~ *U_TimingTx*BUFGCE_DIV*/O}]
create_generated_clock -name timingRxWordClk [get_pins -hier -filter {NAME =~ *U_TimingRx*BUFGCE_DIV*/O}]

set_clock_groups -asynchronous \
    -group [get_clocks axilClk] \
    -group [get_clocks timingTxWordClk] \
    -group [get_clocks timingRxWordClk]
