-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Production packet router with raw packet and application stream access.
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

entity RingRouterControlTb is
   port (
      -- Active-high synchronous reset; fixture generates the 125 MHz clock.
      rst        : in  sl;
      pause      : in  sl;
      rxGood     : in  sl;
      rxData     : in  slv(63 downto 0);
      rxKeep     : in  slv(7 downto 0);
      rxUser     : in  slv(15 downto 0);
      rxDest     : in  slv(7 downto 0);
      rxLast     : in  slv(0 downto 0);
      rxValid    : in  slv(0 downto 0);
      rxReady    : out slv(0 downto 0);
      txData     : out slv(63 downto 0);
      txKeep     : out slv(7 downto 0);
      txUser     : out slv(15 downto 0);
      txDest     : out slv(7 downto 0);
      txLast     : out slv(0 downto 0);
      txValid    : out slv(0 downto 0);
      txReady    : in  slv(0 downto 0);
      appRxData  : out slv(63 downto 0);
      appRxKeep  : out slv(7 downto 0);
      appRxUser  : out slv(15 downto 0);
      appRxDest  : out slv(7 downto 0);
      appRxLast  : out slv(0 downto 0);
      appRxValid : out slv(0 downto 0);
      appRxReady : in  slv(0 downto 0);
      appTxData  : in  slv(63 downto 0);
      appTxKeep  : in  slv(7 downto 0);
      appTxUser  : in  slv(15 downto 0);
      appTxDest  : in  slv(7 downto 0);
      appTxLast  : in  slv(0 downto 0);
      appTxValid : in  slv(0 downto 0);
      appTxReady : out slv(0 downto 0));
end entity RingRouterControlTb;

architecture rtl of RingRouterControlTb is

   signal clk     : sl := '0';
   signal rx      : AxiStreamMasterType := AXI_STREAM_MASTER_INIT_C;
   signal tx      : AxiStreamMasterType := AXI_STREAM_MASTER_INIT_C;
   signal appRx   : AxiStreamMasterType := AXI_STREAM_MASTER_INIT_C;
   signal appTx   : AxiStreamMasterType := AXI_STREAM_MASTER_INIT_C;
   signal rxSl    : AxiStreamSlaveType;
   signal txSl    : AxiStreamSlaveType;
   signal appRxSl : AxiStreamSlaveType;
   signal appTxSl : AxiStreamSlaveType;

begin

   clk <= not clk after 4 ns;
   U_DUT : entity warm_tdm.RingRouter
      generic map (
         PACKET_SIZE_BYTES_G => 256)
      port map (
         axisClk          => clk,       -- [in]
         axisRst          => rst,       -- [in]
         address          => "000",     -- [in]
         linkRxGood       => rxGood,    -- [in]
         linkTxGood       => '1',       -- [in]
         appTxPause       => pause,     -- [in]
         linkRxAxisMaster => rx,        -- [in]
         linkRxAxisSlave  => rxSl,      -- [out]
         linkRxAxisCtrl   => open,      -- [out]
         linkTxAxisMaster => tx,        -- [out]
         linkTxAxisSlave  => txSl,      -- [in]
         appRxAxisMaster  => appRx,     -- [out]
         appRxAxisSlave   => appRxSl,   -- [in]
         appTxAxisMaster  => appTx,     -- [in]
         appTxAxisSlave   => appTxSl);  -- [out]
   rx.tStrb               <= (others => '1');
   rx.tId                 <= (others => '0');
   rx.tData               <= resize(rxData(63 downto 0), rx.tData'length);
   rx.tKeep               <= resize(rxKeep(7 downto 0), rx.tKeep'length);
   rx.tUser               <= resize(rxUser(15 downto 0), rx.tUser'length);
   rx.tDest               <= resize(rxDest(7 downto 0), rx.tDest'length);
   rx.tLast               <= rxLast(0);
   rx.tValid              <= rxValid(0);
   rxReady(0)             <= rxSl.tReady;
   txData(63 downto 0)    <= tx.tData(63 downto 0);
   txKeep(7 downto 0)     <= tx.tKeep(7 downto 0);
   txUser(15 downto 0)    <= tx.tUser(15 downto 0);
   txDest(7 downto 0)     <= tx.tDest(7 downto 0);
   txLast(0)              <= tx.tLast;
   txValid(0)             <= tx.tValid;
   txSl.tReady            <= txReady(0);
   appRxData(63 downto 0) <= appRx.tData(63 downto 0);
   appRxKeep(7 downto 0)  <= appRx.tKeep(7 downto 0);
   appRxUser(15 downto 0) <= appRx.tUser(15 downto 0);
   appRxDest(7 downto 0)  <= appRx.tDest(7 downto 0);
   appRxLast(0)           <= appRx.tLast;
   appRxValid(0)          <= appRx.tValid;
   appRxSl.tReady         <= appRxReady(0);

   appTx.tStrb   <= (others => '1');
   appTx.tId     <= (others => '0');
   appTx.tData   <= resize(appTxData(63 downto 0), appTx.tData'length);
   appTx.tKeep   <= resize(appTxKeep(7 downto 0), appTx.tKeep'length);
   appTx.tUser   <= resize(appTxUser(15 downto 0), appTx.tUser'length);
   appTx.tDest   <= resize(appTxDest(7 downto 0), appTx.tDest'length);
   appTx.tLast   <= appTxLast(0);
   appTx.tValid  <= appTxValid(0);
   appTxReady(0) <= appTxSl.tReady;

end architecture rtl;
