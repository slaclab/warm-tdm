-------------------------------------------------------------------------------
-- Title      : PGPv2b: https://confluence.slac.stanford.edu/x/q86fD
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description:
-- Top Level Transmit/Receive interface module for the Pretty Good Protocol core.
-------------------------------------------------------------------------------
-- This file is part of 'SLAC Firmware Standard Library'.
-- It is subject to the license terms in the LICENSE.txt file found in the
-- top-level directory of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of 'SLAC Firmware Standard Library', including this file,
-- may be copied, modified, propagated, or distributed except according to
-- the terms contained in the LICENSE.txt file.
-------------------------------------------------------------------------------

library ieee;
use ieee.std_logic_1164.all;
use ieee.std_logic_arith.all;
use ieee.std_logic_unsigned.all;


library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.SsiPkg.all;
use surf.AxiStreamPacketizer2Pkg.all;

entity RingRouter is
   generic (
      TPD_G : time := 1 ns);
   port (
      -- Clock and Reset
      axisClk : in sl;
      axisRst : in sl;

      -- Address of this instance
      address : in slv(3 downto 0);

      rxLinkGood : in sl;
      txLinkGood : in sl;

      rxLinkAxisMaster : in  AxiStreamMasterType;
      rxLinkAxisSlave  : out AxiStreamSlaveType;
      rxLinkAxisCtrl   : out AxiStreamCtrlType;
      txLinkAxisMaster : out AxiStreamMasterType;
      txLinkAxisSlave  : in  AxiStreamSlaveType;

      rxAppAxisMaster : out AxiStreamMasterType;
      rxAppAxisSlave  : in  AxiStreamSlaveType;
      txAppAxisMaster : in  AxiStreamMasterType;
      txAppAxisSlave  : out AxiStreamSlaveType
      );

end RingRouter;


-- Define architecture
architecture RingRouter of RingRouter is

   signal depacketizedRxMaster : AxiStreamMasterType;
   signal depacketizedRxSlave  : AxiStreamSlaveType;

   signal passthroughMaster : AxiStreamMasterType;
   signal passthroughSlave  : AxiStreamSlaveType;

   signal muxTxMaster : AxiStreamMasterType;
   signal muxTxSlave  : AxiStreamSlaveType;

   signal dumpMaster : AxiStreamMasterType;
   signal dumpSlave  : AxiStreamSlaveType := AXI_STREAM_SLAVE_FORCE_C;
   signal dynDest    : slv(7 downto 0);
   signal dynDump    : slv(7 downto 0);

begin

   ----------------------------------------------------------------------------------------------
   -- Depacketize the stream
   ----------------------------------------------------------------------------------------------
   U_AxiStreamDepacketizer2_1 : entity surf.AxiStreamDepacketizer2
      generic map (
         TPD_G                => TPD_G,
         MEMORY_TYPE_G        => "bram",
         REG_EN_G             => false,
         CRC_MODE_G           => "NONE",
         TDEST_BITS_G         => 8,
         INPUT_PIPE_STAGES_G  => 0,
         OUTPUT_PIPE_STAGES_G => 1)
      port map (
         axisClk     => axisClk,               -- [in]
         axisRst     => axisRst,               -- [in]
         linkGood    => rxLinkGood,            -- [in]
         debug       => open,                  -- [out]
         sAxisMaster => rxLinkAxisMaster,      -- [in]
         sAxisSlave  => rxLinkAxisSlave,       -- [out]
         mAxisMaster => depacketizedRxMaster,  -- [out]
         mAxisSlave  => depacketizedRxSlave);  -- [in]

   ----------------------------------------------------------------------------------------------
   -- Demultiplex the depacketized stream
   -- When TDEST=address the data is local
   -- All others are passthrough and are routed back out the PGP TX
   ----------------------------------------------------------------------------------------------
   dynDest <= "0000" & address;
   dynDump <= address & "0000";         -- This catches frames that have cycled the loop without
   -- finding the intended destination address

   U_AxiStreamDeMux_1 : entity surf.AxiStreamDeMux
      generic map (
         TPD_G         => TPD_G,
         NUM_MASTERS_G => 3,
         MODE_G        => "DYNAMIC",
         PIPE_STAGES_G => 1)
      port map (
         axisClk              => axisClk,               -- [in]
         axisRst              => axisRst,               -- [in]
         dynamicRouteMasks(0) => "00001111",            -- [in]
         dynamicRouteMasks(1) => "11110000",            -- [in]
         dynamicRouteMasks(2) => "00000000",            -- [in]
         dynamicRouteDests(0) => dynDest,               -- [in]
         dynamicRouteDests(1) => dynDump,               -- [in]
         dynamicRouteDests(2) => "00000000",            -- [in]
         sAxisMaster          => depacketizedRxMaster,  -- [in]
         sAxisSlave           => depacketizedRxSlave,   -- [out]
         mAxisMasters(0)      => passthroughMaster,     -- [out]
         mAxisMasters(1)      => dumpMaster,            -- [out]
         mAxisMasters(2)      => rxAppAxisMaster,       -- [out]
         mAxisSlaves(0)       => passthroughSlave,      -- [in]
         mAxisSlaves(1)       => dumpSlave,             -- [in]
         mAxisSlaves(2)       => rxAppAxisSlave);       -- [in]



   ----------------------------------------------------------------------------------------------
   -- Multiplex the local TX frames with the passthrough frames
   ----------------------------------------------------------------------------------------------
   U_AxiStreamMux_1 : entity surf.AxiStreamMux
      generic map (
         TPD_G                => TPD_G,
         PIPE_STAGES_G        => 1,
         NUM_SLAVES_G         => 2,
         MODE_G               => "PASSTHROUGH",
         TID_MODE_G           => "PASSTHROUGH",
         ILEAVE_EN_G          => true,
         ILEAVE_ON_NOTVALID_G => true,
         ILEAVE_REARB_G       => 31,            -- Check this
         REARB_DELAY_G        => true,
         FORCED_REARB_HOLD_G  => false)         -- Check this
      port map (
         axisClk         => axisClk,            -- [in]
         axisRst         => axisRst,            -- [in]
--         rearbitrate     => rearbitrate,              -- [in]
         sAxisMasters(0) => txAppAxisMaster,    -- [in]
         sAxisMasters(1) => passthroughMaster,  -- [in]
         sAxisSlaves(0)  => txAppAxisSlave,     -- [out]
         sAxisSlaves(1)  => passthroughSlave,   -- [out]            
         mAxisMaster     => muxTxMaster,        -- [out]
         mAxisSlave      => muxTxSlave);        -- [in]

   ----------------------------------------------------------------------------------------------
   -- Packetize the multiplexed frames
   ----------------------------------------------------------------------------------------------
   U_AxiStreamPacketizer2_1 : entity surf.AxiStreamPacketizer2
      generic map (
         TPD_G                => TPD_G,
         MEMORY_TYPE_G        => "distributed",
         REG_EN_G             => false,
         CRC_MODE_G           => "NONE",
         MAX_PACKET_BYTES_G   => 1024,     -- Check this
         TDEST_BITS_G         => 8,
         INPUT_PIPE_STAGES_G  => 1,
         OUTPUT_PIPE_STAGES_G => 1)
      port map (
         axisClk     => axisClk,           -- [in]
         axisRst     => axisRst,           -- [in]
         rearbitrate => open,              -- [out] -- Check this, might want to use it
         sAxisMaster => muxTxMaster,       -- [in]
         sAxisSlave  => muxTxSlave,        -- [out]
         mAxisMaster => txLinkAxisMaster,  -- [out]
         mAxisSlave  => txLinkAxisSlave);  -- [in]


end RingRouter;

