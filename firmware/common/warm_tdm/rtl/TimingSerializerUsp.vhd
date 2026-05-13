-------------------------------------------------------------------------------
-- Title      : Timing Serializer for UltraScale+
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : UltraScale+
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Serializes 10-bit parallel data (125 MHz) to 1.25 Gbps serial
--              using OSERDESE3 (8-bit max). A clock-domain crossing FIFO
--              transfers data from the 125 MHz word clock to the 156.25 MHz
--              OSERDES divided clock, and a Gearbox converts 10-bit words to
--              8-bit words for the serializer.
--
--              Timing:
--                dataIn   : 10 bits @ 125 MHz    = 1250 Mbps
--                Gearbox  : 10b in -> 8b out @ 156.25 MHz
--                OSERDESE3: 8 bits DDR @ 625 MHz = 1250 Mbps
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
      -- 10-bit parallel data input (125 MHz domain)
      wordClk       : in  sl;
      wordRst       : in  sl;
      dataIn        : in  slv(9 downto 0);
      -- OSERDES clocks (generated externally by PLL + BUFGCE_DIV)
      clkx4         : in  sl;              -- 625 MHz serial clock
      clkx1         : in  sl;              -- 156.25 MHz OSERDES divided clock
      rstx1         : in  sl;
      -- Differential serial output
      timingTxDataP : out sl;
      timingTxDataN : out sl);
end entity TimingSerializerUsp;

architecture rtl of TimingSerializerUsp is

   signal fifoValid  : sl;
   signal fifoData   : slv(9 downto 0);
   signal fifoRdEn   : sl;

   signal gearboxOut : slv(7 downto 0);
   signal gbValid    : sl;
   signal gbReady    : sl;

   signal txData     : sl;

   -- Register the gearbox output for OSERDES input
   signal oserdData  : slv(7 downto 0) := (others => '0');

begin

   ----------------------------------------------------------------------------
   -- Clock Domain Crossing: wordClk (125 MHz) -> clkx1 (156.25 MHz)
   -- Uses a small asynchronous FIFO in FWFT mode so that data is available
   -- immediately on the read side when not empty.
   ----------------------------------------------------------------------------
   U_CdcFifo : entity surf.FifoAsync
      generic map (
         TPD_G         => TPD_G,
         MEMORY_TYPE_G => "distributed",
         FWFT_EN_G     => true,
         DATA_WIDTH_G  => 10,
         ADDR_WIDTH_G  => 4)
      port map (
         rst    => wordRst,
         -- Write side (125 MHz)
         wr_clk => wordClk,
         wr_en  => '1',
         din    => dataIn,
         full   => open,
         -- Read side (156.25 MHz)
         rd_clk => clkx1,
         rd_en  => fifoRdEn,
         dout   => fifoData,
         valid  => fifoValid,
         empty  => open);

   -- Read from FIFO whenever the gearbox accepts data
   fifoRdEn <= gbReady and fifoValid;

   ----------------------------------------------------------------------------
   -- Gearbox: 10-bit input -> 8-bit output (both in clkx1 domain)
   -- Accepts 10-bit words from the CDC FIFO and produces 8-bit words
   -- for OSERDESE3. Rates: 10*125 MHz = 8*156.25 MHz = 1250 Mbps.
   ----------------------------------------------------------------------------
   U_Gearbox : entity surf.Gearbox
      generic map (
         TPD_G          => TPD_G,
         SLAVE_WIDTH_G  => 10,
         MASTER_WIDTH_G => 8)
      port map (
         clk        => clkx1,
         rst        => rstx1,
         -- Slave (10-bit input from CDC FIFO)
         slaveData  => fifoData,
         slaveValid => fifoValid,
         slaveReady => gbReady,
         -- Master (8-bit output to OSERDES)
         masterData  => gearboxOut,
         masterValid => gbValid,
         masterReady => '1');

   ----------------------------------------------------------------------------
   -- Register gearbox output for OSERDESE3
   -- When gearbox produces valid data, latch it. The OSERDES consumes one
   -- 8-bit word every clkx1 cycle, and the gearbox produces at exactly
   -- the same average rate (1250/8 = 156.25 MHz).
   ----------------------------------------------------------------------------
   process (clkx1) is
   begin
      if rising_edge(clkx1) then
         if rstx1 = '1' then
            oserdData <= (others => '0') after TPD_G;
         elsif gbValid = '1' then
            oserdData <= gearboxOut after TPD_G;
         end if;
      end if;
   end process;

   ----------------------------------------------------------------------------
   -- OSERDESE3: 8-bit DDR serializer
   -- CLK    = 625 MHz (bit clock)
   -- CLKDIV = 156.25 MHz (parallel data clock = CLK/4)
   -- 8 bits * DDR @ 625 MHz = 1250 Mbps serial output
   ----------------------------------------------------------------------------
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

   ----------------------------------------------------------------------------
   -- Differential output buffer
   ----------------------------------------------------------------------------
   U_OBUFDS : OBUFDS
      port map (
         I  => txData,
         O  => timingTxDataP,
         OB => timingTxDataN);

end architecture rtl;
