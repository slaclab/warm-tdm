-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Ring of production RX guards, routers, TX FIFOs and pause synchronizers.
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

entity RingTrafficControlTb is
   generic (
      BOARDS_G        : positive := 3;
      STATUS_CYCLES_G : positive := RING_STATUS_CYCLES_C);
   port (
      srcData   : in  slv(64*BOARDS_G-1 downto 0);
      srcKeep   : in  slv(8*BOARDS_G-1 downto 0);
      srcUser   : in  slv(16*BOARDS_G-1 downto 0);
      srcDest   : in  slv(8*BOARDS_G-1 downto 0);
      srcLast   : in  slv(BOARDS_G-1 downto 0);
      srcValid  : in  slv(BOARDS_G-1 downto 0);
      srcReady  : out slv(BOARDS_G-1 downto 0);
      sinkData  : out slv(64*BOARDS_G-1 downto 0);
      sinkKeep  : out slv(8*BOARDS_G-1 downto 0);
      sinkUser  : out slv(16*BOARDS_G-1 downto 0);
      sinkDest  : out slv(8*BOARDS_G-1 downto 0);
      sinkLast  : out slv(BOARDS_G-1 downto 0);
      sinkValid : out slv(BOARDS_G-1 downto 0);
      sinkReady : in  slv(BOARDS_G-1 downto 0);
      pauseFlat : out slv(2*BOARDS_G-1 downto 0);
      overflow  : out slv(BOARDS_G-1 downto 0));
end entity RingTrafficControlTb;

architecture rtl of RingTrafficControlTb is

   constant CFG_C     : AxiStreamConfigType := PACKETIZER2_AXIS_CFG_C;
   signal clk         : sl := '0';
   signal axisClk     : sl := '0';
   signal rst         : sl := '1';
   signal localPause  : Slv2Array(BOARDS_G-1 downto 0);
   signal collect     : Slv2Array(BOARDS_G-1 downto 0);
   signal pause       : Slv2Array(BOARDS_G-1 downto 0);
   signal remotePause : Slv2Array(BOARDS_G-1 downto 0);
   signal axisPause   : Slv2Array(BOARDS_G-1 downto 0);
   signal txData      : Slv8Array(BOARDS_G-1 downto 0);
   signal rxData      : Slv8Array(BOARDS_G-1 downto 0);
   signal address     : Slv3Array(BOARDS_G-1 downto 0);
   signal rx          : AxiStreamMasterArray(BOARDS_G-1 downto 0);
   signal tx          : AxiStreamMasterArray(BOARDS_G-1 downto 0);
   signal phy         : AxiStreamMasterArray(BOARDS_G-1 downto 0);
   signal appTx       : AxiStreamMasterArray(BOARDS_G-1 downto 0);
   signal appRx       : AxiStreamMasterArray(BOARDS_G-1 downto 0);
   signal rxSl        : AxiStreamSlaveArray(BOARDS_G-1 downto 0);
   signal txSl        : AxiStreamSlaveArray(BOARDS_G-1 downto 0);
   signal appTxSl     : AxiStreamSlaveArray(BOARDS_G-1 downto 0);
   signal appRxSl     : AxiStreamSlaveArray(BOARDS_G-1 downto 0);
   signal ctrl        : AxiStreamCtrlArray(BOARDS_G-1 downto 0);

begin

   clk     <= not clk after 8 ns;
   axisClk <= not axisClk after 4 ns;
   rst     <= '0' after 160 ns;
   GEN_NODES : for i in 0 to BOARDS_G-1 generate
      constant PREV_C : natural := (i+BOARDS_G-1) mod BOARDS_G;
   begin
      localPause(i)  <= '0' & ctrl(i).pause;
      remotePause(i) <= transport collect(PREV_C) after STATUS_CYCLES_G*16 ns;
      rxData(i)      <= transport txData(PREV_C) after STATUS_CYCLES_G*16 ns;
      U_Flow : entity warm_tdm.PgpRingFlowControl
         generic map (
            RING_ADDR_0_G    => i=0,
            QUALIFY_CYCLES_G => 128)
         port map (
            pgpClk         => clk,             -- [in]
            pgpRst         => rst,             -- [in]
            rxLinkGood     => '1',             -- [in]
            txLinkGood     => '1',             -- [in]
            localPause     => localPause(i),   -- [in]
            remotePause    => remotePause(i),  -- [in]
            remoteLinkData => rxData(i),       -- [in]
            collectPause   => collect(i),      -- [out]
            txLinkData     => txData(i),       -- [out]
            injectionPause => pause(i),        -- [out]
            address        => address(i));     -- [out]
      U_Receiver : entity warm_tdm.PgpRingRxFifo
         port map (
            pgpClk      => clk,          -- [in]
            pgpRst      => rst,          -- [in]
            rxLinkReady => '1',          -- [in]
            address     => address(i),   -- [in]
            pgpRxMaster => phy(PREV_C),  -- [in]
            pgpRxSlave  => open,         -- [out]
            pgpRxCtrl   => ctrl(i),      -- [out]
            axisClk     => axisClk,      -- [in]
            axisRst     => rst,          -- [in]
            axisMaster  => rx(i),        -- [out]
            axisSlave   => rxSl(i));     -- [in]
      U_PauseSync : entity surf.SynchronizerVector
         generic map (
            STAGES_G => 3,
            WIDTH_G  => 2,
            INIT_G   => "11")
         port map (
            clk     => axisClk,        -- [in]
            rst     => rst,            -- [in]
            dataIn  => pause(i),       -- [in]
            dataOut => axisPause(i));  -- [out]
      U_Router : entity warm_tdm.RingRouter
         generic map (
            PACKET_SIZE_BYTES_G => RING_PACKET_BYTES_C)
         port map (
            axisClk          => axisClk,          -- [in]
            axisRst          => rst,              -- [in]
            address          => address(i),       -- [in]
            linkRxGood       => '1',              -- [in]
            linkTxGood       => '1',              -- [in]
            appTxPause       => axisPause(i)(0),  -- [in]
            linkRxAxisMaster => rx(i),            -- [in]
            linkRxAxisSlave  => rxSl(i),          -- [out]
            linkRxAxisCtrl   => open,             -- [out]
            linkTxAxisMaster => tx(i),            -- [out]
            linkTxAxisSlave  => txSl(i),          -- [in]
            appRxAxisMaster  => appRx(i),         -- [out]
            appRxAxisSlave   => appRxSl(i),       -- [in]
            appTxAxisMaster  => appTx(i),         -- [in]
            appTxAxisSlave   => appTxSl(i));      -- [out]
      U_Transmitter : entity surf.PgpTxVcFifo
         generic map (
            INT_PIPE_STAGES_G => 1,
            PIPE_STAGES_G     => 0,
            FIFO_ADDR_WIDTH_G => RING_TX_ADDR_WIDTH_C,
            SYNTH_MODE_G      => "inferred",
            MEMORY_TYPE_G     => "block",
            GEN_SYNC_FIFO_G   => false,
            APP_AXI_CONFIG_G  => CFG_C,
            PHY_AXI_CONFIG_G  => SSI_PGP2B_CONFIG_C)
         port map (
            axisClk     => axisClk,                    -- [in]
            axisRst     => rst,                        -- [in]
            axisMaster  => tx(i),                      -- [in]
            axisSlave   => txSl(i),                    -- [out]
            pgpClk      => clk,                        -- [in]
            pgpRst      => rst,                        -- [in]
            rxLinkReady => '1',                        -- [in]
            txLinkReady => '1',                        -- [in]
            pgpTxMaster => phy(i),                     -- [out]
            pgpTxSlave  => AXI_STREAM_SLAVE_FORCE_C);  -- [in]
      pauseFlat(2*i+1 downto 2*i) <= pause(i);
      overflow(i)                 <= ctrl(i).overflow;

      appTx(i).tStrb <= (others => '1');
      appTx(i).tId <= (others => '0');
      appTx(i).tData <= resize(srcData(64*i+63 downto 64*i), appTx(i).tData'length);
      appTx(i).tKeep <= resize(srcKeep(8*i+7 downto 8*i), appTx(i).tKeep'length);
      appTx(i).tUser <= resize(srcUser(16*i+15 downto 16*i), appTx(i).tUser'length);
      appTx(i).tDest <= resize(srcDest(8*i+7 downto 8*i), appTx(i).tDest'length);
      appTx(i).tLast <= srcLast(i);
      appTx(i).tValid <= srcValid(i);
      srcReady(i)                   <= appTxSl(i).tReady;
      sinkData(64*i+63 downto 64*i) <= appRx(i).tData(63 downto 0);
      sinkKeep(8*i+7 downto 8*i)    <= appRx(i).tKeep(7 downto 0);
      sinkUser(16*i+15 downto 16*i) <= appRx(i).tUser(15 downto 0);
      sinkDest(8*i+7 downto 8*i)    <= appRx(i).tDest(7 downto 0);
      sinkLast(i)                   <= appRx(i).tLast;
      sinkValid(i)                  <= appRx(i).tValid;
      appRxSl(i).tReady <= sinkReady(i);
   end generate;

end architecture rtl;
