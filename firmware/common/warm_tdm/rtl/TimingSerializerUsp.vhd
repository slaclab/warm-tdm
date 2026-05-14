-------------------------------------------------------------------------------
-- Title      : Timing Serializer for UltraScale+
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : UltraScale+
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Serializes 10-bit parallel data (125 MHz) to 1.25 Gbps serial
-- using OSERDESE3 (8-bit DDR). An AsyncGearbox handles the clock domain
-- crossing (125 -> 156.25 MHz) and width conversion (10 -> 8) in one step.
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

entity TimingSerializerUsp is
   generic (
      TPD_G : time := 1 ns);
   port (
      wordClk       : in  sl;
      wordRst       : in  sl;
      dataIn        : in  slv(9 downto 0);
      clkx4         : in  sl;
      clkx1         : in  sl;
      rstx1         : in  sl;
      timingTxDataP : out sl;
      timingTxDataN : out sl);
end entity TimingSerializerUsp;

architecture rtl of TimingSerializerUsp is

   signal oserdData : slv(7 downto 0) := (others => '0');
   signal oserdValid : sl;
   signal txData    : sl;

begin

   ---------------------------------------------------------------------------
   -- AsyncGearbox: 10-bit @ 125 MHz -> 8-bit @ 156.25 MHz
   -- Handles CDC (125 -> 156.25) and width conversion in one entity.
   -- SLAVE_WIDTH=10 > MASTER_WIDTH=8, so FIFO is on slave (input) side.
   ---------------------------------------------------------------------------
   U_AsyncGearbox : entity surf.AsyncGearbox
      generic map (
         TPD_G              => TPD_G,
         SLAVE_WIDTH_G      => 10,
         MASTER_WIDTH_G     => 8,
         EN_EXT_CTRL_G      => false,
         FIFO_MEMORY_TYPE_G => "distributed",
         FIFO_ADDR_WIDTH_G  => 4)
      port map (
         slaveClk    => wordClk,
         slaveRst    => wordRst,
         slaveData   => dataIn,
         slaveValid  => '1',
         slaveReady  => open,
         masterClk   => clkx1,
         masterRst   => rstx1,
         masterData  => oserdData,
         masterValid => oserdValid,
         masterReady => '1');

   ---------------------------------------------------------------------------
   -- OSERDESE3: 8-bit DDR serializer
   -- CLK    = 625 MHz (bit clock, 4x CLKDIV)
   -- CLKDIV = 156.25 MHz (parallel data clock)
   -- 8 bits DDR @ 625 MHz = 1250 Mbps
   ---------------------------------------------------------------------------
   U_OSERDESE3 : OSERDESE3
      generic map (
         DATA_WIDTH => 8,
         SIM_DEVICE => "ULTRASCALE_PLUS")
      port map (
         CLK    => clkx4,
         CLKDIV => clkx1,
         RST    => rstx1,
         T      => '0',
         D      => oserdData,
         OQ     => txData,
         T_OUT  => open);

   ---------------------------------------------------------------------------
   -- Differential output buffer
   ---------------------------------------------------------------------------
   U_OBUFDS : OBUFDS
      port map (
         I  => txData,
         O  => timingTxDataP,
         OB => timingTxDataN);

end architecture rtl;
