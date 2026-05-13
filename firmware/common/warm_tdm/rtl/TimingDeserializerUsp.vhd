-------------------------------------------------------------------------------
-- Title      : Timing Deserializer for UltraScale+
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : Xilinx UltraScale+
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: UltraScale+ version of TimingDeserializer using ISERDESE3
-- (8-bit DDR) + IDELAYE3 + Gearbox for 8-to-10 bit conversion.
-- Replaces the Kintex-7 version which used cascaded ISERDESE2 + IDELAYE2.
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
      -- SERDES clocks
      clkx4         : in  sl;                -- 625 MHz serial clock
      clkx1         : in  sl;                -- 156.25 MHz (clkx4/4)
      rstx1         : in  sl;
      -- Differential LVDS input
      timingRxDataP : in  sl;
      timingRxDataN : in  sl;
      -- 10-bit parallel output (clkx1 domain)
      wordClk       : out sl;                -- output: this IS clkx1 for downstream
      wordRst       : out sl;                -- output: this IS rstx1
      dataOut       : out slv(9 downto 0);
      dataValid     : out sl;
      -- Gearbox slip control (from SelectIoRxGearboxAligner)
      slip          : in  sl;
      -- Delay control
      dlyLoad       : in  sl;
      dlyCfg        : in  slv(8 downto 0);   -- IDELAYE3 uses 9-bit delay
      -- Status
      locked        : out sl);
end entity TimingDeserializerUsp;

architecture rtl of TimingDeserializerUsp is

   signal timingRxData    : sl;
   signal timingRxDataDly : sl;
   signal clkx4L          : sl;
   signal iserdesData     : slv(7 downto 0);
   signal gearboxData     : slv(9 downto 0);
   signal gearboxValid    : sl;

begin

   -- Pass through clock/reset for downstream use
   wordClk <= clkx1;
   wordRst <= rstx1;

   -- Locked status: asserted when gearbox is producing valid output
   locked <= gearboxValid;

   ---------------------------------------------------------------------------
   -- Differential Input Buffer
   ---------------------------------------------------------------------------
   U_IBUFDS : IBUFDS
      port map (
         I  => timingRxDataP,
         IB => timingRxDataN,
         O  => timingRxData);

   ---------------------------------------------------------------------------
   -- Programmable Input Delay (IDELAYE3 via surf wrapper)
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
         Q           => iserdesData,
         CLK         => clkx4,
         CLK_B       => clkx4L,
         CLKDIV      => clkx1,
         RST         => rstx1,
         FIFO_RD_CLK => '0',
         FIFO_RD_EN  => '0',
         FIFO_EMPTY  => open);

   ---------------------------------------------------------------------------
   -- Gearbox: 8-bit to 10-bit width conversion
   -- Alignment is achieved by the upstream aligner driving the slip port
   -- to adjust the 8-to-10 framing boundary.
   ---------------------------------------------------------------------------
   U_GEARBOX : entity surf.Gearbox
      generic map (
         TPD_G          => TPD_G,
         SLAVE_WIDTH_G  => 8,
         MASTER_WIDTH_G => 10)
      port map (
         clk         => clkx1,
         rst         => rstx1,
         -- Input from ISERDESE3
         slaveData   => iserdesData,
         slaveValid  => '1',
         slaveReady  => open,
         -- Slip for alignment
         slip        => slip,
         startOfSeq  => '0',
         -- 10-bit output
         masterData  => gearboxData,
         masterValid => gearboxValid,
         masterReady => '1');

   -- Output assignments
   dataOut   <= gearboxData;
   dataValid <= gearboxValid;

end architecture rtl;
