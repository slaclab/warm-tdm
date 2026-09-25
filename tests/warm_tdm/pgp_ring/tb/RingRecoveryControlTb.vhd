-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Unthrottled PHY feeding the RX guard, router and compressed-keep bridge.
--
-- Connectivity-only fixture; Python/cocotb owns stimulus and scoreboards.
-- Stream fields are flattened explicitly because the IP-integrator adapters
-- expose at most eight TUSER bits, whereas these SSI streams need sixteen.
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
use surf.Pgp2bPkg.all;
use surf.AxiStreamPacketizer2Pkg.all;
library warm_tdm;
use warm_tdm.PgpRingPkg.all;

entity RingRecoveryControlTb is
   generic (
      RX_DEPTH_G     : positive := 8;
      BRIDGE_DEPTH_G : positive := 5);
   port (
      srcData   : in  slv(63 downto 0);
      srcKeep   : in  slv(7 downto 0);
      srcUser   : in  slv(15 downto 0);
      srcDest   : in  slv(7 downto 0);
      srcLast   : in  slv(0 downto 0);
      srcValid  : in  slv(0 downto 0);
      srcReady  : out slv(0 downto 0);
      sinkData  : out slv(63 downto 0);
      sinkKeep  : out slv(7 downto 0);
      sinkUser  : out slv(15 downto 0);
      sinkDest  : out slv(7 downto 0);
      sinkLast  : out slv(0 downto 0);
      sinkValid : out slv(0 downto 0);
      sinkReady : in  slv(0 downto 0);
      overflow  : out sl;
      pause     : out sl;
      phyValid  : out sl);
end entity RingRecoveryControlTb;

architecture rtl of RingRecoveryControlTb is

   constant CFG_C : AxiStreamConfigType := ssiAxiStreamConfig(8,
      tDestBits => 8);
   signal clk     : sl := '0';
   signal ethClk  : sl := '0';
   signal axisClk : sl := '0';
   signal rst     : sl := '1';
   signal src     : AxiStreamMasterType := AXI_STREAM_MASTER_INIT_C;
   signal pkt     : AxiStreamMasterType := AXI_STREAM_MASTER_INIT_C;
   signal phy     : AxiStreamMasterType := AXI_STREAM_MASTER_INIT_C;
   signal rx      : AxiStreamMasterType := AXI_STREAM_MASTER_INIT_C;
   signal dep     : AxiStreamMasterType := AXI_STREAM_MASTER_INIT_C;
   signal ob      : AxiStreamMasterType := AXI_STREAM_MASTER_INIT_C;
   signal srcSl   : AxiStreamSlaveType := AXI_STREAM_SLAVE_INIT_C;
   signal pktSl   : AxiStreamSlaveType := AXI_STREAM_SLAVE_INIT_C;
   signal rxSl    : AxiStreamSlaveType := AXI_STREAM_SLAVE_INIT_C;
   signal depSl   : AxiStreamSlaveType := AXI_STREAM_SLAVE_INIT_C;
   signal sinkSl  : AxiStreamSlaveType := AXI_STREAM_SLAVE_INIT_C;
   signal ctrl    : AxiStreamCtrlType;

begin

   clk     <= not clk after 8 ns;
   axisClk <= not axisClk after 4 ns;
   ethClk  <= not ethClk after 3.2 ns;
   rst     <= '0' after 160 ns;
   U_Packetizer : entity surf.AxiStreamPacketizer2
      generic map (
         CRC_MODE_G         => "NONE",
         MAX_PACKET_BYTES_G => 512,
         TDEST_BITS_G       => 8)
      port map (
         axisClk     => clk,     -- [in]
         axisRst     => rst,     -- [in]
         rearbitrate => open,    -- [out]
         sAxisMaster => src,     -- [in]
         sAxisSlave  => srcSl,   -- [out]
         mAxisMaster => pkt,     -- [out]
         mAxisSlave  => pktSl);  -- [in]
   U_Serializer : entity surf.AxiStreamGearbox
      generic map (
         SLAVE_AXI_CONFIG_G  => CFG_C,
         MASTER_AXI_CONFIG_G => SSI_PGP2B_CONFIG_C)
      port map (
         axisClk     => clk,                        -- [in]
         axisRst     => rst,                        -- [in]
         sAxisMaster => pkt,                        -- [in]
         sAxisSlave  => pktSl,                      -- [out]
         mAxisMaster => phy,                        -- [out]
         mAxisSlave  => AXI_STREAM_SLAVE_FORCE_C);  -- [in]
   U_Receiver : entity warm_tdm.PgpRingRxFifo
      generic map (
         FIFO_ADDR_WIDTH_G => RX_DEPTH_G,
         PAUSE_HIGH_G      => 192,
         PAUSE_LOW_G       => 128)
      port map (
         pgpClk      => clk,      -- [in]
         pgpRst      => rst,      -- [in]
         rxLinkReady => '1',      -- [in]
         address     => "000",    -- [in]
         pgpRxMaster => phy,      -- [in]
         pgpRxCtrl   => ctrl,     -- [out]
         pgpRxSlave  => open,     -- [out]
         axisClk     => axisClk,  -- [in]
         axisRst     => rst,      -- [in]
         axisMaster  => rx,       -- [out]
         axisSlave   => rxSl);    -- [in]
   U_Router : entity warm_tdm.RingRouter
      port map (
         axisClk          => axisClk,                   -- [in]
         axisRst          => rst,                       -- [in]
         address          => "000",                     -- [in]
         linkRxGood       => '1',                       -- [in]
         linkTxGood       => '1',                       -- [in]
         linkRxAxisMaster => rx,                        -- [in]
         linkRxAxisSlave  => rxSl,                      -- [out]
         linkRxAxisCtrl   => open,                      -- [out]
         linkTxAxisMaster => open,                      -- [out]
         linkTxAxisSlave  => AXI_STREAM_SLAVE_FORCE_C,  -- [in]
         appRxAxisMaster  => dep,                       -- [out]
         appRxAxisSlave   => depSl,                     -- [in]
         appTxAxisMaster  => AXI_STREAM_MASTER_INIT_C,  -- [in]
         appTxAxisSlave   => open,                      -- [out]
         appTxPause       => '1');                      -- [in]
   U_Bridge : entity surf.AxiStreamFifoV2
      generic map (
         INT_PIPE_STAGES_G   => 1,
         PIPE_STAGES_G       => 0,
         SLAVE_READY_EN_G    => true,
         VALID_THOLD_G       => 1,
         GEN_SYNC_FIFO_G     => false,
         SYNTH_MODE_G        => "inferred",
         MEMORY_TYPE_G       => "block",
         FIFO_ADDR_WIDTH_G   => BRIDGE_DEPTH_G,
         SLAVE_AXI_CONFIG_G  => CFG_C,
         MASTER_AXI_CONFIG_G => CFG_C)
      port map (
         sAxisClk    => axisClk,  -- [in]
         sAxisRst    => rst,      -- [in]
         sAxisMaster => dep,      -- [in]
         sAxisSlave  => depSl,    -- [out]
         mAxisClk    => ethClk,   -- [in]
         mAxisRst    => rst,      -- [in]
         mAxisMaster => ob,       -- [out]
         mAxisSlave  => sinkSl);  -- [in]
   overflow <= ctrl.overflow;
   pause    <= ctrl.pause;
   phyValid <= phy.tValid;

   src.tStrb             <= (others => '1');
   src.tId               <= (others => '0');
   src.tData             <= resize(srcData(63 downto 0), src.tData'length);
   src.tKeep             <= resize(srcKeep(7 downto 0), src.tKeep'length);
   src.tUser             <= resize(srcUser(15 downto 0), src.tUser'length);
   src.tDest             <= resize(srcDest(7 downto 0), src.tDest'length);
   src.tLast             <= srcLast(0);
   src.tValid            <= srcValid(0);
   srcReady(0)           <= srcSl.tReady;
   sinkData(63 downto 0) <= ob.tData(63 downto 0);
   sinkKeep(7 downto 0)  <= ob.tKeep(7 downto 0);
   sinkUser(15 downto 0) <= ob.tUser(15 downto 0);
   sinkDest(7 downto 0)  <= ob.tDest(7 downto 0);
   sinkLast(0)           <= ob.tLast;
   sinkValid(0)          <= ob.tValid;
   sinkSl.tReady         <= sinkReady(0);

end architecture rtl;
