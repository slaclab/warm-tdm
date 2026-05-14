-------------------------------------------------------------------------------
-- Title      : Timing Rx PHY for 7-Series
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : Xilinx 7-Series
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Extracts the 7-series-specific clock and deserializer logic
-- from TimingRx. Contains IBUFGDS, ClockManager7 PLL (125 MHz -> 625 MHz
-- bitClk + 125 MHz wordClk), and TimingDeserializer7s.
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

entity TimingRxPhy7s is
   generic (
      TPD_G             : time    := 1 ns;
      IODELAY_GROUP_G   : string  := "DEFAULT_GROUP";
      DEFAULT_DELAY_G   : integer := 0;
      IDELAYCTRL_FREQ_G : real    := 200.0);
   port (
      timingRxClkP  : in  sl;
      timingRxClkN  : in  sl;
      timingRxDataP : in  sl;
      timingRxDataN : in  sl;
      wordClk       : out sl;
      wordRst       : out sl;
      dataOut       : out slv(9 downto 0);
      slip          : in  sl;
      setDelay      : in  slv(4 downto 0);
      setValid      : in  sl;
      curDelay      : out slv(4 downto 0);
      locked        : out sl);  -- PLL locked
end entity TimingRxPhy7s;

architecture rtl of TimingRxPhy7s is

   signal timingRxClk : sl;
   signal timingRxRst : sl;
   signal bitClk      : sl;
   signal bitClkInv   : sl;
   signal bitRst      : sl;
   signal wordClkLoc  : sl;
   signal wordRstLoc  : sl;

begin

   -------------------------
   -- 125 MHz Timing RX clock input buffer
   -------------------------
   TIMING_RX_CLK_BUFF : IBUFGDS
      port map (
         i  => timingRxClkP,
         ib => timingRxClkN,
         o  => timingRxClk);

   -- Hold PLL in reset until clock is stable
   timingRxRst <= '0';

   -------------------------
   -- PLL: 125 MHz -> 625 MHz (bitClk) + 125 MHz (wordClk)
   -------------------------
   U_ClockManager7_1 : entity surf.ClockManager7
      generic map (
         TPD_G            => TPD_G,
         SIMULATION_G     => false,
         TYPE_G           => "PLL",
         INPUT_BUFG_G     => false,
         FB_BUFG_G        => true,
         OUTPUT_BUFG_G    => true,
         NUM_CLOCKS_G     => 2,
         BANDWIDTH_G      => "OPTIMIZED",
         CLKIN_PERIOD_G   => 8.0,
         DIVCLK_DIVIDE_G  => 1,
         CLKFBOUT_MULT_G  => 10,
         CLKOUT0_DIVIDE_G => 2,
         CLKOUT1_DIVIDE_G => 10)
      port map (
         clkIn     => timingRxClk,
         rstIn     => timingRxRst,
         clkOut(0) => bitClk,
         clkOut(1) => wordClkLoc,
         rstOut(0) => bitRst,
         rstOut(1) => wordRstLoc,
         locked    => locked);

   bitClkInv <= not bitClk;

   wordClk <= wordClkLoc;
   wordRst <= wordRstLoc;

   -------------------------
   -- Deserializer
   -------------------------
   U_TimingDeserializer7s_1 : entity warm_tdm.TimingDeserializer7s
      generic map (
         TPD_G             => TPD_G,
         IODELAY_GROUP_G   => IODELAY_GROUP_G,
         DEFAULT_DELAY_G   => DEFAULT_DELAY_G,
         IDELAYCTRL_FREQ_G => IDELAYCTRL_FREQ_G)
      port map (
         rst           => wordRstLoc,
         bitClk        => bitClk,
         bitClkInv     => bitClkInv,
         timingRxDataP => timingRxDataP,
         timingRxDataN => timingRxDataN,
         wordClk       => wordClkLoc,
         wordRst       => wordRstLoc,
         dataOut       => dataOut,
         slip          => slip,
         sysClk        => wordClkLoc,
         curDelay      => curDelay,
         setDelay      => setDelay,
         setValid      => setValid);

end architecture rtl;
