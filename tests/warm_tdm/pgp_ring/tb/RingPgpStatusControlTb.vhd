-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Native PGP scheduler/cells/status looped at decoded symbols; excludes GTX.
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

entity RingPgpStatusControlTb is
   port (
      srcData    : in  slv(64*2-1 downto 0);
      srcKeep    : in  slv(8*2-1 downto 0);
      srcUser    : in  slv(16*2-1 downto 0);
      srcDest    : in  slv(8*2-1 downto 0);
      srcLast    : in  slv(1*2-1 downto 0);
      srcValid   : in  slv(1*2-1 downto 0);
      srcReady   : out slv(1*2-1 downto 0);
      sinkData   : out slv(64*2-1 downto 0);
      sinkKeep   : out slv(8*2-1 downto 0);
      sinkUser   : out slv(16*2-1 downto 0);
      sinkDest   : out slv(8*2-1 downto 0);
      sinkLast   : out slv(1*2-1 downto 0);
      sinkValid  : out slv(1*2-1 downto 0);
      sinkReady  : in  slv(1*2-1 downto 0);
      locData    : in  slv(7 downto 0);
      pressure   : in  slv(1 downto 0);
      rxData     : out slv(7 downto 0);
      rxPause    : out slv(1 downto 0);
      rxGood     : out sl;
      txGood     : out sl;
      cellError  : out sl;
      frameError : out sl);
end entity RingPgpStatusControlTb;

architecture rtl of RingPgpStatusControlTb is

   signal clk   : sl := '0';
   signal rst   : sl := '1';
   signal txIn  : Pgp2bTxInType := PGP2B_TX_IN_HALF_DUPLEX_C;
   signal txOut : Pgp2bTxOutType;
   signal rxOut : Pgp2bRxOutType;
   signal tx    : AxiStreamMasterArray(3 downto 0) := (others =>AXI_STREAM_MASTER_INIT_C);
   signal txSl  : AxiStreamSlaveArray(3 downto 0);
   signal rx    : AxiStreamMasterArray(3 downto 0);
   signal ctrl  : AxiStreamCtrlArray(3 downto 0) := (others =>AXI_STREAM_CTRL_UNUSED_C);
   signal phyTx : Pgp2bTxPhyLaneOutArray(0 to 0);
   signal phyRx : Pgp2bRxPhyLaneInArray(0 to 0) := (others =>PGP2B_RX_PHY_LANE_IN_INIT_C);
   signal rxSl  : AxiStreamSlaveArray(1 downto 0);

begin

   clk <= not clk after 8 ns;
   rst <= '0' after 160 ns;
   phyRx(0).data <= phyTx(0).data;
   phyRx(0).dataK <= phyTx(0).dataK;
   U_DUT : entity surf.Pgp2bLane
      generic map (
         PAYLOAD_CNT_TOP_G => RING_PAYLOAD_CNT_TOP_C,
         NUM_VC_EN_G       => 2)
      port map (
         pgpTxClk         => clk,    -- [in]
         pgpTxClkRst      => rst,    -- [in]
         pgpTxIn          => txIn,   -- [in]
         pgpTxOut         => txOut,  -- [out]
         pgpTxMasters     => tx,     -- [in]
         pgpTxSlaves      => txSl,   -- [out]
         phyTxLanesOut    => phyTx,  -- [out]
         phyTxReady       => '1',    -- [in]
         pgpRxClk         => clk,    -- [in]
         pgpRxClkRst      => rst,    -- [in]
         pgpRxOut         => rxOut,  -- [out]
         pgpRxMasters     => rx,     -- [out]
         pgpRxMasterMuxed => open,   -- [out]
         pgpRxCtrl        => ctrl,   -- [in]
         phyRxLanesOut    => open,   -- [out]
         phyRxLanesIn     => phyRx,  -- [in]
         phyRxReady       => '1',    -- [in]
         phyRxInit        => open);  -- [out]
   txIn.locData <= locData;
   rxData       <= rxOut.remLinkData;
   rxPause      <= rxOut.remPause(1 downto 0);
   rxGood       <= rxOut.linkReady;
   txGood       <= txOut.linkReady;
   cellError    <= rxOut.cellError;
   frameError   <= rxOut.frameRxErr;
   GEN_VC : for i in 0 to 1 generate
      ctrl(i).pause <= pressure(i);

      tx(i).tStrb <= (others => '1');
      tx(i).tId <= (others => '0');
      tx(i).tData <= resize(srcData(64*i+63 downto 64*i), tx(i).tData'length);
      tx(i).tKeep <= resize(srcKeep(8*i+7 downto 8*i), tx(i).tKeep'length);
      tx(i).tUser <= resize(srcUser(16*i+15 downto 16*i), tx(i).tUser'length);
      tx(i).tDest <= resize(srcDest(8*i+7 downto 8*i), tx(i).tDest'length);
      tx(i).tLast <= srcLast(i);
      tx(i).tValid <= srcValid(i);
      srcReady(i)                   <= txSl(i).tReady;
      sinkData(64*i+63 downto 64*i) <= rx(i).tData(63 downto 0);
      sinkKeep(8*i+7 downto 8*i)    <= rx(i).tKeep(7 downto 0);
      sinkUser(16*i+15 downto 16*i) <= rx(i).tUser(15 downto 0);
      sinkDest(8*i+7 downto 8*i)    <= rx(i).tDest(7 downto 0);
      sinkLast(i)                   <= rx(i).tLast;
      sinkValid(i)                  <= rx(i).tValid;
      rxSl(i).tReady <= sinkReady(i);
   end generate;

end architecture rtl;
