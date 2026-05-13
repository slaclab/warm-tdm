-------------------------------------------------------------------------------
-- Title      : PGP Ring Router
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   :
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Encapsulates the PGP ring routing logic for VCs 1 downto 0.
-- Each VC has a PgpRXVcFifo (pgpClk to axiClk CDC), a RingRouter for
-- address-based stream routing, and a PgpTXVcFifo (axiClk to pgpClk CDC).
-- Also includes the PGP_RX_CTRL process that merges local flow control
-- with remote pause signals.
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
use ieee.std_logic_arith.all;
use ieee.std_logic_unsigned.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.SsiPkg.all;
use surf.AxiLitePkg.all;
use surf.Pgp2bPkg.all;

library warm_tdm;

entity PgpRingRouter is
   generic (
      TPD_G               : time    := 1 ns;
      SIMULATION_G        : boolean := false;
      RING_ADDR_0_G       : boolean := false;
      PACKET_SIZE_BYTES_G : integer := 512);
   port (
      axiClk         : in  sl;
      axiRst         : in  sl;
      pgpClk         : in  sl;
      pgpRst         : in  sl;
      pgpRxLinkReady : in  sl;
      pgpTxLinkReady : in  sl;
      -- Ring address (computed externally from remLinkData)
      address        : in  slv(2 downto 0);
      -- PGP frame interfaces (directly from/to PHY)
      pgpRxMasters   : in  AxiStreamMasterArray(3 downto 0);
      pgpRxCtrl      : out AxiStreamCtrlArray(3 downto 0);
      pgpTxMasters   : out AxiStreamMasterArray(3 downto 0);
      pgpTxSlaves    : in  AxiStreamSlaveArray(3 downto 0);
      -- Remote pause from PGP RX
      remPause       : in  slv(3 downto 0);
      -- App-side stream interfaces (axiClk domain)
      appRxMasters   : out AxiStreamMasterArray(3 downto 0);
      appRxSlaves    : in  AxiStreamSlaveArray(3 downto 0);
      appTxMasters   : in  AxiStreamMasterArray(3 downto 0);
      appTxSlaves    : out AxiStreamSlaveArray(3 downto 0));
end entity PgpRingRouter;

architecture rtl of PgpRingRouter is

   constant AXIS_CONFIG_C : AxiStreamConfigType := ssiAxiStreamConfig(dataBytes => 8, tDestBits => 8);

   signal fifoRxMasters : AxiStreamMasterArray(1 downto 0) := (others => AXI_STREAM_MASTER_INIT_C);
   signal fifoRxSlaves  : AxiStreamSlaveArray(1 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);
   signal fifoTxMasters : AxiStreamMasterArray(1 downto 0) := (others => AXI_STREAM_MASTER_INIT_C);
   signal fifoTxSlaves  : AxiStreamSlaveArray(1 downto 0)  := (others => AXI_STREAM_SLAVE_INIT_C);

   signal locPgpRxCtrl : AxiStreamCtrlArray(3 downto 0) := (others => AXI_STREAM_CTRL_UNUSED_C);

begin

   -------------------------------------------------------------------------------------------------
   -- Merge local RX flow control with remote pause
   -------------------------------------------------------------------------------------------------
   PGP_RX_CTRL : process (locPgpRxCtrl, pgpRxLinkReady, remPause) is
      variable tmp : AxiStreamCtrlArray(3 downto 0);
   begin
      tmp := locPgpRxCtrl;
      for i in 3 downto 0 loop
         if (RING_ADDR_0_G = false) then
            if (pgpRxLinkReady = '1') then
               tmp(i).pause := locPgpRxCtrl(i).pause or remPause(i);
            end if;
         end if;
      end loop;
      pgpRxCtrl <= tmp;
   end process PGP_RX_CTRL;

   -------------------------------------------------------------------------------------------------
   -- Ring Router generate loop for VCs 1 downto 0
   -------------------------------------------------------------------------------------------------
   RING_ROUTER_GEN : for i in 1 downto 0 generate

      -- RX FIFO: pgpClk -> axiClk CDC
      U_PgpRXVcFifo : entity surf.PgpRXVcFifo
         generic map (
            TPD_G               => TPD_G,
            ROGUE_SIM_EN_G      => SIMULATION_G,
            INT_PIPE_STAGES_G   => 1,
            PIPE_STAGES_G       => 0,
            VALID_THOLD_G       => PACKET_SIZE_BYTES_G/8,
            VALID_BURST_MODE_G  => true,
            SYNTH_MODE_G        => "inferred",
            MEMORY_TYPE_G       => "block",
            GEN_SYNC_FIFO_G     => false,
            FIFO_ADDR_WIDTH_G   => 10,
            FIFO_PAUSE_THRESH_G => PACKET_SIZE_BYTES_G/4,
            PHY_AXI_CONFIG_G    => SSI_PGP2B_CONFIG_C,
            APP_AXI_CONFIG_G    => AXIS_CONFIG_C)
         port map (
            pgpClk      => pgpClk,            -- [in]
            pgpRst      => pgpRst,            -- [in]
            rxlinkReady => pgpRxLinkReady,    -- [in]
            pgpRxMaster => pgpRxMasters(i),   -- [in]
            pgpRxCtrl   => locPgpRxCtrl(i),   -- [out]
            pgpRxSlave  => open,              -- [out]
            axisClk     => axiClk,            -- [in]
            axisRst     => axiRst,            -- [in]
            axisMaster  => fifoRxMasters(i),  -- [out]
            axisSlave   => fifoRxSlaves(i));  -- [in]

      -- Ring Router: address-based stream routing
      U_RingRouter : entity warm_tdm.RingRouter
         generic map (
            TPD_G               => TPD_G,
            PACKET_SIZE_BYTES_G => PACKET_SIZE_BYTES_G)
         port map (
            axisClk          => axiClk,            -- [in]
            axisRst          => axiRst,            -- [in]
            address          => address,           -- [in]
            linkRxGood       => pgpRxLinkReady,    -- [in]
            linkTxGood       => pgpTxLinkReady,    -- [in]
            linkRxAxisMaster => fifoRxMasters(i),  -- [in]
            linkRxAxisSlave  => fifoRxSlaves(i),   -- [out]
            linkTxAxisMaster => fifoTxMasters(i),  -- [out]
            linkTxAxisSlave  => fifoTxSlaves(i),   -- [in]
            appRxAxisMaster  => appRxMasters(i),   -- [out]
            appRxAxisSlave   => appRxSlaves(i),    -- [in]
            appTxAxisMaster  => appTxMasters(i),   -- [in]
            appTxAxisSlave   => appTxSlaves(i));   -- [out]

      -- TX FIFO: axiClk -> pgpClk CDC
      U_PgpTXVcFifo : entity surf.PgpTXVcFifo
         generic map (
            TPD_G              => TPD_G,
            INT_PIPE_STAGES_G  => 1,
            PIPE_STAGES_G      => 0,
            VALID_BURST_MODE_G => true,
            SYNTH_MODE_G       => "inferred",
            MEMORY_TYPE_G      => "block",
            GEN_SYNC_FIFO_G    => false,
            FIFO_ADDR_WIDTH_G  => 10,
            APP_AXI_CONFIG_G   => AXIS_CONFIG_C,
            PHY_AXI_CONFIG_G   => SSI_PGP2B_CONFIG_C)
         port map (
            axisClk     => axiClk,            -- [in]
            axisRst     => axiRst,            -- [in]
            axisMaster  => fifoTxMasters(i),  -- [in]
            axisSlave   => fifoTxSlaves(i),   -- [out]
            pgpClk      => pgpClk,            -- [in]
            pgpRst      => pgpRst,            -- [in]
            rxlinkReady => pgpRxLinkReady,    -- [in]
            txlinkReady => pgpTxLinkReady,    -- [in]
            pgpTxMaster => pgpTxMasters(i),   -- [out]
            pgpTxSlave  => pgpTxSlaves(i));   -- [in]

   end generate RING_ROUTER_GEN;

end architecture rtl;
