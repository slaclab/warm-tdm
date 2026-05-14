-------------------------------------------------------------------------------
-- Title      : Timing Tx PHY for 7-Series
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Standard   : VHDL'93/02
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

library surf;
use surf.StdRtlPkg.all;

library warm_tdm;

entity TimingTxPhy7s is
   generic (
      TPD_G : time := 1 ns);
   port (
      timingRefClk  : in  sl;
      timingRefRst  : in  sl;
      bitClk        : out sl;
      bitRst        : out sl;
      wordClk       : out sl;
      wordRst       : out sl;
      dataIn        : in  slv(9 downto 0);
      enable        : in  sl;
      timingTxDataP : out sl;
      timingTxDataN : out sl);
end entity TimingTxPhy7s;

architecture rtl of TimingTxPhy7s is

   signal bitClkInt  : sl;
   signal bitRstInt  : sl;
   signal wordClkInt : sl;
   signal wordRstInt : sl;

begin

   -------------------------------------------------------------------------------------------------
   -- PLL: 125 MHz -> 625 MHz bitClk + 125 MHz wordClk
   -------------------------------------------------------------------------------------------------
   U_ClockManager7_1 : entity surf.ClockManager7
      generic map (
         TPD_G            => TPD_G,
         SIMULATION_G     => false,
         TYPE_G           => "PLL",
         INPUT_BUFG_G     => false,
         FB_BUFG_G        => true,
         OUTPUT_BUFG_G    => true,
         NUM_CLOCKS_G     => 2,
         BANDWIDTH_G      => "HIGH",
         CLKIN_PERIOD_G   => 8.0,
         DIVCLK_DIVIDE_G  => 1,
         CLKFBOUT_MULT_G  => 10,
         CLKOUT0_DIVIDE_G => 2,
         CLKOUT1_DIVIDE_G => 10)
      port map (
         clkIn     => timingRefClk,      -- [in]
         rstIn     => timingRefRst,      -- [in]
         clkOut(0) => bitClkInt,         -- [out]
         clkOut(1) => wordClkInt,        -- [out]
         rstOut(0) => bitRstInt,         -- [out]
         rstOut(1) => wordRstInt);       -- [out]

   bitClk  <= bitClkInt;
   bitRst  <= bitRstInt;
   wordClk <= wordClkInt;
   wordRst <= wordRstInt;

   -------------------------------------------------------------------------------------------------
   -- Serializer
   -------------------------------------------------------------------------------------------------
   U_TimingSerializer7s_1 : entity warm_tdm.TimingSerializer7s
      generic map (
         TPD_G => TPD_G)
      port map (
         rst           => wordRstInt,       -- [in]
         enable        => enable,           -- [in]
         bitClk        => bitClkInt,        -- [in]
         timingTxDataP => timingTxDataP,    -- [out]
         timingTxDataN => timingTxDataN,    -- [out]
         wordClk       => wordClkInt,       -- [in]
         wordRst       => wordRstInt,       -- [in]
         dataIn        => dataIn);          -- [in]

end architecture rtl;
