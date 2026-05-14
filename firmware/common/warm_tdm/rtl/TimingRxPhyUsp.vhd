-------------------------------------------------------------------------------
-- Title      : Timing Rx PHY for UltraScale+
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : Xilinx UltraScale+
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: UltraScale+ timing RX clock recovery and deserialization.
-- IBUFDS -> MMCM (625 MHz + 156.25 MHz + 125 MHz) -> ISERDESE3 -> AsyncGearbox
-- (8->10 with CDC from 156.25 to 125 MHz) -> 125 MHz output domain.
--
-- The 156.25 MHz clock is internal only (ISERDES CLKDIV + gearbox fast side).
-- The 125 MHz wordClk output matches the transmitted clock rate.
-------------------------------------------------------------------------------
-- This file is part of Warm TDM. It is subject to
-- the license terms in the LICENSE.txt file found in the top-level directory
-- of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of Warm TDM, including this file, may be
-- copied, modified, propagated, or distributed except according to the terms
-- contained in the LICENSE.txt file.
-------------------------------------------------------------------------------

library ieee;
use ieee.std_logic_1164.all;

library unisim;
use unisim.vcomponents.all;

library surf;
use surf.StdRtlPkg.all;

library warm_tdm;

entity TimingRxPhyUsp is
   generic (
      TPD_G : time := 1 ns);
   port (
      timingRxClkP  : in  sl;
      timingRxClkN  : in  sl;
      timingRxDataP : in  sl;
      timingRxDataN : in  sl;
      wordClk       : out sl;
      wordRst       : out sl;
      dataOut       : out slv(9 downto 0);
      dataValid     : out sl;
      slip          : in  sl;
      dlyLoad       : in  sl;
      dlyCfg        : in  slv(8 downto 0);
      locked        : out sl);
end entity TimingRxPhyUsp;

architecture rtl of TimingRxPhyUsp is

   signal timingRxClk  : sl;
   signal clkx4        : sl;
   signal clkx1        : sl;
   signal wordClkLoc   : sl;
   signal rstx1        : sl;
   signal wordRstLoc   : sl;
   signal mmcmLocked   : sl;
   signal mmcmRst      : sl;

   signal iserdesData  : slv(7 downto 0);

begin

   -------------------------
   -- 125 MHz Timing RX clock input buffer
   -------------------------
   TIMING_RX_CLK_BUFF : IBUFDS
      port map (
         i  => timingRxClkP,
         ib => timingRxClkN,
         o  => timingRxClk);

   -------------------------
   -- MMCM: 125 MHz -> 625 MHz + 156.25 MHz + 125 MHz
   -- VCO = 125 x 10 = 1250 MHz
   -------------------------
   U_ClockManagerUsp_1 : entity surf.ClockManagerUltraScale
      generic map (
         TPD_G              => TPD_G,
         TYPE_G             => "MMCM",
         INPUT_BUFG_G       => true,
         FB_BUFG_G          => true,
         NUM_CLOCKS_G       => 3,
         BANDWIDTH_G        => "OPTIMIZED",
         CLKIN_PERIOD_G     => 8.0,
         DIVCLK_DIVIDE_G    => 1,
         CLKFBOUT_MULT_F_G  => 10.0,
         CLKOUT0_DIVIDE_F_G => 2.0,
         CLKOUT1_DIVIDE_G   => 8,
         CLKOUT2_DIVIDE_G   => 10)
      port map (
         clkIn     => timingRxClk,
         rstIn     => '0',
         clkOut(0) => clkx4,
         clkOut(1) => clkx1,
         clkOut(2) => wordClkLoc,
         rstOut(0) => open,
         rstOut(1) => open,
         rstOut(2) => open,
         locked    => mmcmLocked);

   locked <= mmcmLocked;

   -------------------------
   -- Reset synchronizers
   -------------------------
   mmcmRst <= not mmcmLocked;

   U_RstSync_clkx1 : entity surf.RstSync
      generic map (
         TPD_G => TPD_G)
      port map (
         clk      => clkx1,
         asyncRst => mmcmRst,
         syncRst  => rstx1);

   U_RstSync_wordClk : entity surf.RstSync
      generic map (
         TPD_G => TPD_G)
      port map (
         clk      => wordClkLoc,
         asyncRst => mmcmRst,
         syncRst  => wordRstLoc);

   wordClk <= wordClkLoc;
   wordRst <= wordRstLoc;

   -------------------------
   -- Deserializer: ISERDESE3 only (8-bit DDR output on clkx1)
   -------------------------
   U_TimingDeserializerUsp_1 : entity warm_tdm.TimingDeserializerUsp
      generic map (
         TPD_G => TPD_G)
      port map (
         clkx4         => clkx4,
         clkx1         => clkx1,
         rstx1         => rstx1,
         timingRxDataP => timingRxDataP,
         timingRxDataN => timingRxDataN,
         dataOut       => iserdesData,
         dlyLoad       => dlyLoad,
         dlyCfg        => dlyCfg);

   -------------------------
   -- AsyncGearbox: 8-bit @ 156.25 MHz -> 10-bit @ 125 MHz
   -- Gearbox runs on fast clock (156.25 MHz slave side).
   -- FIFO on master (output) side crosses to 125 MHz.
   -- Slip input synchronized internally.
   -------------------------
   U_AsyncGearbox : entity surf.AsyncGearbox
      generic map (
         TPD_G              => TPD_G,
         SLAVE_WIDTH_G      => 8,
         MASTER_WIDTH_G     => 10,
         EN_EXT_CTRL_G      => true,
         FIFO_MEMORY_TYPE_G => "distributed",
         FIFO_ADDR_WIDTH_G  => 4)
      port map (
         slaveClk    => clkx1,
         slaveRst    => rstx1,
         slaveData   => iserdesData,
         slaveValid  => '1',
         slaveReady  => open,
         slip        => slip,
         masterClk   => wordClkLoc,
         masterRst   => wordRstLoc,
         masterData  => dataOut,
         masterValid => dataValid,
         masterReady => '1');

end architecture rtl;
