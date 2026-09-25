-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Flatten two independent Ethernet bandwidth directions for cocotb.
-- Only connectivity and clocks live here; Python owns stimulus and checks.
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
use surf.AxiStreamPkg.all;
use surf.SsiPkg.all;
library warm_tdm;

entity EthSimBandwidthTb is
   generic (ETH_10G_G : boolean := false);
   port (
      rst : in sl;
      sData : in slv(255 downto 0);
      sKeep : in slv(31 downto 0);
      sUser : in slv(63 downto 0);
      sDest : in slv(31 downto 0);
      sLast : in slv(3 downto 0);
      sValid : in slv(3 downto 0);
      sReady : out slv(3 downto 0);
      mData : out slv(255 downto 0);
      mKeep : out slv(31 downto 0);
      mUser : out slv(63 downto 0);
      mDest : out slv(31 downto 0);
      mLast : out slv(3 downto 0);
      mValid : out slv(3 downto 0);
      mReady : in slv(3 downto 0));
end entity EthSimBandwidthTb;

architecture rtl of EthSimBandwidthTb is
   constant CLK_PERIOD_C : time := ite(ETH_10G_G, 6.4 ns, 8 ns);
   signal clk : sl := '0';
begin
   clk <= not clk after CLK_PERIOD_C/2;
   GEN_DIRECTION : for d in 0 to 1 generate
      signal sMasters : AxiStreamMasterArray(1 downto 0) := (others => AXI_STREAM_MASTER_INIT_C);
      signal sSlaves  : AxiStreamSlaveArray(1 downto 0);
      signal mMasters : AxiStreamMasterArray(1 downto 0);
      signal mSlaves  : AxiStreamSlaveArray(1 downto 0);
   begin
      U_DUT : entity warm_tdm.EthSimBandwidth
         generic map (
            TPD_G           => 1 ns,
            AXIS_CONFIG_G   => ssiAxiStreamConfig(dataBytes => 8, tDestBits => 8, tUserBits => 8),
            AXIS_CLK_FREQ_G => ite(ETH_10G_G, 156.25E6, 125.0E6),
            PAYLOAD_RATE_G  => ite(ETH_10G_G, 10.0E9, 1.0E9))
         port map (
            axisClk      => clk,
            axisRst      => rst,
            sAxisMasters => sMasters,
            sAxisSlaves  => sSlaves,
            mAxisMasters => mMasters,
            mAxisSlaves  => mSlaves);
      GEN_LANE : for i in 0 to 1 generate
         constant LANE_C : natural := 2*d+i;
      begin
         sMasters(i).tData(63 downto 0) <= sData(64*(LANE_C+1)-1 downto 64*LANE_C);
         mData(64*(LANE_C+1)-1 downto 64*LANE_C) <= mMasters(i).tData(63 downto 0);
         sMasters(i).tKeep(7 downto 0) <= sKeep(8*(LANE_C+1)-1 downto 8*LANE_C);
         mKeep(8*(LANE_C+1)-1 downto 8*LANE_C) <= mMasters(i).tKeep(7 downto 0);
         sMasters(i).tUser(15 downto 0) <= sUser(16*(LANE_C+1)-1 downto 16*LANE_C);
         mUser(16*(LANE_C+1)-1 downto 16*LANE_C) <= mMasters(i).tUser(15 downto 0);
         sMasters(i).tDest(7 downto 0) <= sDest(8*(LANE_C+1)-1 downto 8*LANE_C);
         mDest(8*(LANE_C+1)-1 downto 8*LANE_C) <= mMasters(i).tDest(7 downto 0);
         sMasters(i).tLast <= sLast(LANE_C);
         mLast(LANE_C) <= mMasters(i).tLast;
         sMasters(i).tValid <= sValid(LANE_C);
         mValid(LANE_C) <= mMasters(i).tValid;
         sReady(LANE_C) <= sSlaves(i).tReady;
         mSlaves(i).tReady <= mReady(LANE_C);
      end generate GEN_LANE;
   end generate GEN_DIRECTION;
end architecture rtl;
