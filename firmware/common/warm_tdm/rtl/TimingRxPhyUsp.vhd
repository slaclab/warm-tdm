-------------------------------------------------------------------------------
-- Title      : Timing Rx PHY for UltraScale+
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : Xilinx UltraScale+
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: UltraScale+ timing RX clock recovery and deserialization.
-- IBUFDS -> MMCM (625 MHz + 156.25 MHz + 125 MHz) -> ISERDESE3 + Gearbox
-- -> CDC FIFO -> 125 MHz output domain.
--
-- The 156.25 MHz clock is internal only (ISERDES CLKDIV + gearbox).
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

   signal desData      : slv(9 downto 0);
   signal desDataValid : sl;

begin

   -------------------------
   -- 125 MHz Timing RX clock input buffer
   -------------------------
   TIMING_RX_CLK_BUFF : IBUFDS
      port map (
         i  => timingRxClkP,   -- [in]
         ib => timingRxClkN,   -- [in]
         o  => timingRxClk);   -- [out]

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
         clkIn     => timingRxClk,   -- [in]
         rstIn     => '0',           -- [in]
         clkOut(0) => clkx4,         -- [out]
         clkOut(1) => clkx1,         -- [out]
         clkOut(2) => wordClkLoc,    -- [out]
         rstOut(0) => open,          -- [out]
         rstOut(1) => open,          -- [out]
         rstOut(2) => open,          -- [out]
         locked    => mmcmLocked);   -- [out]

   locked <= mmcmLocked;

   -------------------------
   -- Reset synchronizers
   -------------------------
   mmcmRst <= not mmcmLocked;

   U_RstSync_clkx1 : entity surf.RstSync
      generic map (
         TPD_G => TPD_G)
      port map (
         clk      => clkx1,     -- [in]
         asyncRst => mmcmRst,   -- [in]
         syncRst  => rstx1);    -- [out]

   U_RstSync_wordClk : entity surf.RstSync
      generic map (
         TPD_G => TPD_G)
      port map (
         clk      => wordClkLoc,   -- [in]
         asyncRst => mmcmRst,      -- [in]
         syncRst  => wordRstLoc);  -- [out]

   wordClk <= wordClkLoc;
   wordRst <= wordRstLoc;

   -------------------------
   -- Deserializer (outputs on clkx1 = 156.25 MHz domain)
   -------------------------
   U_TimingDeserializerUsp_1 : entity warm_tdm.TimingDeserializerUsp
      port map (
         clkx4         => clkx4,          -- [in]
         clkx1         => clkx1,          -- [in]
         rstx1         => rstx1,          -- [in]
         timingRxDataP => timingRxDataP,   -- [in]
         timingRxDataN => timingRxDataN,   -- [in]
         wordClk       => open,           -- [out]
         wordRst       => open,           -- [out]
         dataOut       => desData,        -- [out]
         dataValid     => desDataValid,   -- [out]
         slip          => slip,           -- [in]
         dlyLoad       => dlyLoad,        -- [in]
         dlyCfg        => dlyCfg,         -- [in]
         locked        => open);          -- [out]

   -------------------------
   -- CDC FIFO: clkx1 (156.25 MHz) -> wordClkLoc (125 MHz)
   -- Write: gearbox output at 156.25 MHz, valid 4/5 cycles = 125 Mword/s
   -- Read: 125 MHz, drains at exactly the fill rate
   -------------------------
   U_CdcFifo : entity surf.FifoAsync
      generic map (
         TPD_G         => TPD_G,
         MEMORY_TYPE_G => "distributed",
         FWFT_EN_G     => true,
         DATA_WIDTH_G  => 10,
         ADDR_WIDTH_G  => 4)
      port map (
         rst    => rstx1,         -- [in]
         wr_clk => clkx1,         -- [in]
         wr_en  => desDataValid,   -- [in]
         din    => desData,        -- [in]
         full   => open,           -- [out]
         rd_clk => wordClkLoc,     -- [in]
         rd_en  => '1',            -- [in]
         dout   => dataOut,        -- [out]
         valid  => dataValid,      -- [out]
         empty  => open);          -- [out]

end architecture rtl;
