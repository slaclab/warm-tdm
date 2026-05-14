-------------------------------------------------------------------------------
-- Title      : Timing Deserializer for UltraScale+
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : Xilinx UltraScale+
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: UltraScale+ ISERDESE3 deserializer (8-bit DDR).
-- Outputs raw 8-bit parallel data on clkx1 (156.25 MHz) domain.
-- The gearbox and CDC are handled externally by AsyncGearbox.
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

entity TimingDeserializerUsp is
   generic (
      TPD_G : time := 1 ns);
   port (
      clkx4         : in  sl;
      clkx1         : in  sl;
      rstx1         : in  sl;
      timingRxDataP : in  sl;
      timingRxDataN : in  sl;
      dataOut       : out slv(7 downto 0);
      dlyLoad       : in  sl;
      dlyCfg        : in  slv(8 downto 0));
end entity TimingDeserializerUsp;

architecture rtl of TimingDeserializerUsp is

   signal timingRxData    : sl;
   signal timingRxDataDly : sl;
   signal clkx4L          : sl;

begin

   ---------------------------------------------------------------------------
   -- Differential Input Buffer
   ---------------------------------------------------------------------------
   U_IBUFDS : IBUFDS
      port map (
         I  => timingRxDataP,
         IB => timingRxDataN,
         O  => timingRxData);

   ---------------------------------------------------------------------------
   -- Programmable Input Delay
   ---------------------------------------------------------------------------
   U_DELAY : entity surf.Idelaye3Wrapper
      generic map (
         DELAY_FORMAT     => "COUNT",
         SIM_DEVICE       => "ULTRASCALE_PLUS",
         DELAY_VALUE      => 0,
         REFCLK_FREQUENCY => 300.0,
         UPDATE_MODE      => "ASYNC",
         CASCADE          => "NONE",
         DELAY_SRC        => "IDATAIN",
         DELAY_TYPE       => "VAR_LOAD")
      port map (
         DATAIN      => '0',
         IDATAIN     => timingRxData,
         DATAOUT     => timingRxDataDly,
         CLK         => clkx1,
         RST         => rstx1,
         CE          => '0',
         INC         => '0',
         LOAD        => dlyLoad,
         EN_VTC      => '0',
         CASC_IN     => '0',
         CASC_RETURN => '0',
         CNTVALUEIN  => dlyCfg);

   ---------------------------------------------------------------------------
   -- ISERDESE3: 8-bit DDR deserializer
   ---------------------------------------------------------------------------
   clkx4L <= not(clkx4);

   U_ISERDES : ISERDESE3
      generic map (
         DATA_WIDTH     => 8,
         FIFO_ENABLE    => "FALSE",
         FIFO_SYNC_MODE => "FALSE",
         SIM_DEVICE     => "ULTRASCALE_PLUS")
      port map (
         D           => timingRxDataDly,
         Q           => dataOut,
         CLK         => clkx4,
         CLK_B       => clkx4L,
         CLKDIV      => clkx1,
         RST         => rstx1,
         FIFO_RD_CLK => '0',
         FIFO_RD_EN  => '0',
         FIFO_EMPTY  => open);

end architecture rtl;
