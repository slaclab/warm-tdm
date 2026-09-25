-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Delayed collection/broadcast topology, including legacy-peer injection.
--
-- Connectivity-only fixture; Python/cocotb owns stimulus and scoreboards.
-- Collection and broadcast have independent transport delays, including idle.
-------------------------------------------------------------------------------
-- This file is part of Warm TDM. It is subject to the license terms in the
-- LICENSE.txt file found in the top-level directory of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of Warm TDM, including this file, may be copied, modified, propagated,
-- or distributed except according to the terms contained in LICENSE.txt.
-------------------------------------------------------------------------------
library ieee;
use ieee.std_logic_1164.all;
library surf;
use surf.StdRtlPkg.all;
library warm_tdm;

entity RingFlowControlTb is
   generic (
      BOARDS_G : positive := 3);
   port (
      good           : in  slv(BOARDS_G-1 downto 0);
      legacy         : in  sl;
      localPauseFlat : in  slv(2*BOARDS_G-1 downto 0);
      pauseFlat      : out slv(2*BOARDS_G-1 downto 0);
      addressFlat    : out slv(3*BOARDS_G-1 downto 0));
end entity RingFlowControlTb;

architecture rtl of RingFlowControlTb is

   signal clk         : sl := '0';
   signal rst         : sl := '1';
   signal localPause  : Slv2Array(BOARDS_G-1 downto 0) := (others => "00");
   signal collect     : Slv2Array(BOARDS_G-1 downto 0);
   signal remotePause : Slv2Array(BOARDS_G-1 downto 0);
   signal pause       : Slv2Array(BOARDS_G-1 downto 0);
   signal txData      : Slv8Array(BOARDS_G-1 downto 0);
   signal rxData      : Slv8Array(BOARDS_G-1 downto 0);
   signal address     : Slv3Array(BOARDS_G-1 downto 0);

begin

   clk <= not clk after 8 ns;
   rst <= '0' after 160 ns;
   GEN_NODES : for i in 0 to BOARDS_G-1 generate
      constant PREV_C : natural := (i+BOARDS_G-1) mod BOARDS_G;
   begin
      -- Delayed status updates continue while all application inputs are idle.
      remotePause(i) <= transport collect(PREV_C) after 128 ns;
      rxData(i)      <= transport txData(PREV_C) after 192 ns when not (legacy = '1' and i=1) else
                   x"00";
      U_DUT : entity warm_tdm.PgpRingFlowControl
         generic map (
            RING_ADDR_0_G    => i=0,
            QUALIFY_CYCLES_G => 128)
         port map (
            pgpClk         => clk,             -- [in]
            pgpRst         => rst,             -- [in]
            rxLinkGood     => good(i),         -- [in]
            txLinkGood     => good(i),         -- [in]
            localPause     => localPause(i),   -- [in]
            remotePause    => remotePause(i),  -- [in]
            remoteLinkData => rxData(i),       -- [in]
            collectPause   => collect(i),      -- [out]
            txLinkData     => txData(i),       -- [out]
            injectionPause => pause(i),        -- [out]
            address        => address(i));     -- [out]
      localPause(i)                 <= localPauseFlat(2*i+1 downto 2*i);
      pauseFlat(2*i+1 downto 2*i)   <= pause(i);
      addressFlat(3*i+2 downto 3*i) <= address(i);
   end generate;

end architecture rtl;
