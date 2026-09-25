-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Route wire packets, admit local traffic and recover damaged frames.
-- Decode destinations before local reassembly; transit retains its framing.
-- Only complete local packets enter the transmit mux, subject to pause.
-- Ordered abort markers terminate open application frames before forwarding.
-- All streams use axisClk/axisRst. Routed outputs are registered and hold
-- payload/sidebands while stalled; combinational ready reflects slot capacity.
-------------------------------------------------------------------------------
-- This file is part of Warm TDM. It is subject to the license terms in the
-- LICENSE.txt file found in the top-level directory of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of Warm TDM, including this file, may be copied, modified, propagated,
-- or distributed except according to the terms contained in LICENSE.txt.
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

library warm_tdm;
use warm_tdm.PgpRingPkg.all;

entity RingRouter is
   generic (
      TPD_G               : time    := 1 ns;
      PACKET_SIZE_BYTES_G : integer := RING_PACKET_BYTES_C);
   port (
      -- Clock and Reset
      axisClk : in  sl;
      axisRst : in  sl;

      -- Address of this instance
      address : in  slv(2 downto 0);

      linkRxGood : in  sl;
      linkTxGood : in  sl;

      linkRxAxisMaster : in  AxiStreamMasterType;
      linkRxAxisSlave  : out AxiStreamSlaveType;
      linkRxAxisCtrl   : out AxiStreamCtrlType;
      linkTxAxisMaster : out AxiStreamMasterType;
      linkTxAxisSlave  : in  AxiStreamSlaveType;

      appTxPause      : in  sl := '0';
      appRxAxisMaster : out AxiStreamMasterType;
      appRxAxisSlave  : in  AxiStreamSlaveType;
      appTxAxisMaster : in  AxiStreamMasterType;
      appTxAxisSlave  : out AxiStreamSlaveType
      );

end RingRouter;


-- Route complete wire packets before depacketizing. Only local injection is
-- subject to pause; transit packets retain their original sequence and framing.
architecture rtl of RingRouter is

   -- SURF packetizer/depacketizer application ports use eight user bits per
   -- byte; their wire packets and our application streams use two. SOF at
   -- byte zero hides this mismatch, but EOF/error at the last byte does not.
   constant REASSEMBLY_CONFIG_C : AxiStreamConfigType :=
      ssiAxiStreamConfig(8,
         tDestBits => 8,
         tUserBits => 8,
         tIdBits   => 8);
   type StateType is (
      IDLE_S, LOCAL_S, FORWARD_S, DROP_S,
      ABORT_START_S, ABORT_WAIT_S, ABORT_TERMINATE_S, ABORT_SEND_S);
   type RegType is record
      state               : StateType;
      active              : slv(255 downto 0);
      abortIndex          : natural range 0 to 255;
      quiet               : natural range 0 to 2;
      linkCount           : natural range 0 to 7;
      localRxMaster       : AxiStreamMasterType;
      passthroughMaster   : AxiStreamMasterType;
      appRxAxisMaster     : AxiStreamMasterType;
      linkRxAxisSlave     : AxiStreamSlaveType;
      depacketizerRxSlave : AxiStreamSlaveType;
      depacketizerGood    : sl;
      disableLocal        : sl;
   end record;
   constant REG_INIT_C : RegType := (
      state               => IDLE_S,
      active              => (others => '0'),
      abortIndex          => 0,
      quiet               => 0,
      linkCount           => 0,
      localRxMaster       => AXI_STREAM_MASTER_INIT_C,
      passthroughMaster   => AXI_STREAM_MASTER_INIT_C,
      appRxAxisMaster     => AXI_STREAM_MASTER_INIT_C,
      linkRxAxisSlave     => AXI_STREAM_SLAVE_INIT_C,
      depacketizerRxSlave => AXI_STREAM_SLAVE_INIT_C,
      depacketizerGood    => '1',
      disableLocal        => '1');
   signal r                    : RegType := REG_INIT_C;
   signal rin                  : RegType;
   signal localRxMaster        : AxiStreamMasterType;
   signal depacketizerRxMaster : AxiStreamMasterType;
   signal localRxSlave         : AxiStreamSlaveType;
   signal passthroughMaster    : AxiStreamMasterType;
   signal passthroughSlave     : AxiStreamSlaveType;
   signal taggedMaster         : AxiStreamMasterType;
   signal packetMaster         : AxiStreamMasterType;
   signal packetSlave          : AxiStreamSlaveType;
   signal bufferedMaster       : AxiStreamMasterType;
   signal bufferedSlave        : AxiStreamSlaveType;
   signal appRxMaster          : AxiStreamMasterType;
   signal appRxNormal          : AxiStreamMasterType;
   signal depacketizerRxSlave  : AxiStreamSlaveType;
   signal debug                : Packetizer2DebugType;
   signal depacketizerGood     : sl;
   signal disableLocal         : sl;

begin

   assert PACKET_SIZE_BYTES_G mod 8 = 0 and PACKET_SIZE_BYTES_G >= 24
      report "Ring packet size must be an eight-byte multiple" severity failure;
   linkRxAxisCtrl <= AXI_STREAM_CTRL_UNUSED_C;

   comb : process(all) is
      variable v          : RegType;
      variable routeState : StateType;
      variable dest       : slv(7 downto 0);
      variable master     : AxiStreamMasterType;
      variable slave      : AxiStreamSlaveType;
      variable restart    : boolean;
   begin
      v := r;
      -- One registered slot on each routed output breaks the header/error mux
      -- path before the depacketizer and transmit arbiter. Ready reflects the
      -- capacity freed on this edge, permitting simultaneous consume/refill.
      v.linkRxAxisSlave     := AXI_STREAM_SLAVE_INIT_C;
      v.depacketizerRxSlave := AXI_STREAM_SLAVE_INIT_C;
      if localRxSlave.tReady = '1' then
         v.localRxMaster.tValid := '0';
      end if;
      if passthroughSlave.tReady = '1' then
         v.passthroughMaster.tValid := '0';
      end if;
      if appRxAxisSlave.tReady = '1' then
         v.appRxAxisMaster.tValid := '0';
         if r.appRxAxisMaster.tValid = '1' then
            v.active(conv_integer(r.appRxAxisMaster.tDest)) := not r.appRxAxisMaster.tLast;
         end if;
      end if;
      if r.state /= ABORT_TERMINATE_S and v.appRxAxisMaster.tValid = '0' then
         v.depacketizerRxSlave.tReady := '1';
         v.appRxAxisMaster            := appRxNormal;
      end if;
      if linkRxGood = '1' and linkTxGood = '1' then
         if r.linkCount < 7 then
            v.linkCount := r.linkCount + 1;
         end if;
      else
         v.linkCount := 0;
      end if;
      routeState := r.state;
      master     := linkRxAxisMaster;
      slave      := AXI_STREAM_SLAVE_INIT_C;
      dest       := master.tData(PACKETIZER2_HDR_TDEST_FIELD_C);
      restart    := false;
      if r.state = IDLE_S and master.tValid = '1' then
         if ssiGetUserSof(PACKETIZER2_AXIS_CFG_C, master) /= '1' then
            routeState := DROP_S;
         elsif master.tLast = '1' and
            (master.tData(63 downto 0) and RING_ABORT_MASK_C) = RING_ABORT_C then
            if master.tData(18 downto 16) = address and master.tData(8) = '0' then
               -- The marker made one complete circuit. Do not abort again:
               -- fresh frames may have been admitted behind it.
               routeState := DROP_S;
            elsif v.localRxMaster.tValid = '0' and v.passthroughMaster.tValid = '0' then
               -- Drain both routed slots before resetting reassembly so the
               -- marker cannot overtake a preceding packet's final word.
               v.state := ABORT_START_S;
            end if;
         elsif dest(2 downto 0) = address then
            routeState := LOCAL_S;
         elsif dest(6 downto 4) = address then
            routeState := DROP_S;
         else
            routeState := FORWARD_S;
         end if;
      elsif (r.state = LOCAL_S or r.state = FORWARD_S) and
         master.tValid = '1' and ssiGetUserSof(PACKETIZER2_AXIS_CFG_C, master) = '1' then
         -- Missing tail: close the old packet with error WITHOUT consuming the
         -- fresh header. It is retried as a header after this transfer.
         master                    := axiStreamMasterInit(PACKETIZER2_AXIS_CFG_C);
         master.tValid             := '1';
         master.tLast              := '1';
         master.tData(63 downto 0) := makePacketizer2TailTdata("NONE");
         ssiSetUserEofe(PACKETIZER2_AXIS_CFG_C, master, '1');
         restart := true;
      end if;
      case routeState is
         when LOCAL_S =>
            if master.tLast = '1' and ssiGetUserEofe(PACKETIZER2_AXIS_CFG_C, master) = '1' then
               -- A PHY error terminator can end on any two-byte boundary.
               -- Its data is not a packetizer tail. Supply valid tail fields
               -- so the depacketizer cannot derive a zero/invalid keep mask
               -- and lose the error in a downstream compressed-keep FIFO.
               master.tData(63 downto 0) := makePacketizer2TailTdata("NONE");
               master.tKeep              := genTKeep(8);
               ssiSetUserEofe(PACKETIZER2_AXIS_CFG_C, master, '1');
            end if;
            slave.tReady := not v.localRxMaster.tValid;
            if slave.tReady = '1' then
               v.localRxMaster := master;
            end if;
         when FORWARD_S =>
            slave.tReady := not v.passthroughMaster.tValid;
            if slave.tReady = '1' then
               v.passthroughMaster := master;
            end if;
         when DROP_S =>
            slave.tReady := '1';
            -- Orphan words are discarded individually so a new SOF is never
            -- swallowed while waiting for the missing packet's tail.
            if r.state = IDLE_S then
               routeState := IDLE_S;
            end if;
         when ABORT_START_S =>
            v.quiet := 0;
            v.state := ABORT_WAIT_S;
         when ABORT_WAIT_S =>
            -- Drain the reassembly output pipeline after clearing its RAM.
            if debug.initDone = '1' and appRxNormal.tValid = '0' and
               v.appRxAxisMaster.tValid = '0' then
               if r.quiet = 2 then
                  v.abortIndex := 0;
                  v.state      := ABORT_TERMINATE_S;
               else
                  v.quiet := r.quiet + 1;
               end if;
            else
               v.quiet := 0;
            end if;
         when ABORT_TERMINATE_S =>
            -- Track frames actually delivered to the application, independently
            -- of the depacketizer RAM's read/write latency during termination.
            -- Any EOFE already emitted by the depacketizer cleared this bit.
            if v.appRxAxisMaster.tValid = '0' then
               v.appRxAxisMaster        := axiStreamMasterInit(PACKETIZER2_AXIS_CFG_C);
               v.appRxAxisMaster.tValid := v.active(r.abortIndex);
               v.appRxAxisMaster.tLast  := '1';
               v.appRxAxisMaster.tDest  := toSlv(r.abortIndex, 8);
               ssiSetUserEofe(PACKETIZER2_AXIS_CFG_C, v.appRxAxisMaster, '1');
               if r.abortIndex = 255 then
                  v.state := ABORT_SEND_S;
               else
                  v.abortIndex := r.abortIndex + 1;
               end if;
            end if;
         when ABORT_SEND_S =>
            -- PgpTxVcFifo flushes while either link is down. Retain the marker
            -- until its link-status synchronizer has also left flush mode.
            if r.linkCount = 7 and v.appRxAxisMaster.tValid = '0' then
               master.tData(8) := '0';
               slave.tReady    := not v.passthroughMaster.tValid;
               if slave.tReady = '1' then
                  v.passthroughMaster := master;
               end if;
            end if;
         when others =>
            null;
      end case;
      if master.tValid = '1' and slave.tReady = '1' then
         v.state := routeState;
         if master.tLast = '1' then
            v.state := IDLE_S;
         end if;
      end if;
      v.linkRxAxisSlave := slave;
      if restart then
         v.linkRxAxisSlave.tReady := '0';
      end if;
      v.depacketizerGood := '1';
      if v.state = ABORT_START_S then
         v.depacketizerGood := '0';
      end if;
      -- Admission is a combinational backpressure exception: the mux must
      -- observe current pause and transit availability before granting a new
      -- packet. A delayed grant veto would admit an additional whole packet.
      -- Already selected packets remain owned by the mux until their tLast.
      v.disableLocal := appTxPause or r.passthroughMaster.tValid or not linkTxGood or not linkRxGood;
      if axisRst = '1' then
         v := REG_INIT_C;
      end if;
      rin                 <= v;
      localRxMaster       <= r.localRxMaster;
      passthroughMaster   <= r.passthroughMaster;
      appRxAxisMaster     <= r.appRxAxisMaster;
      linkRxAxisSlave     <= v.linkRxAxisSlave;
      depacketizerRxSlave <= v.depacketizerRxSlave;
      depacketizerGood    <= r.depacketizerGood;
      disableLocal        <= v.disableLocal;
   end process;
   seq : process(axisClk) is
   begin
      if rising_edge(axisClk) then
         r <= rin after TPD_G;
      end if;
   end process;

   U_Depacketizer : entity surf.AxiStreamDepacketizer2
      generic map (
         TPD_G                => TPD_G,
         MEMORY_TYPE_G        => "bram",
         REG_EN_G             => false,
         CRC_MODE_G           => "NONE",
         TDEST_BITS_G         => 8,
         INPUT_PIPE_STAGES_G  => 0,
         OUTPUT_PIPE_STAGES_G => 0)
      port map (
         axisClk     => axisClk,               -- [in]
         axisRst     => axisRst,               -- [in]
         linkGood    => depacketizerGood,      -- [in]
         debug       => debug,                 -- [out]
         sAxisMaster => depacketizerRxMaster,  -- [in]
         sAxisSlave  => localRxSlave,          -- [out]
         mAxisMaster => appRxMaster,           -- [out]
         mAxisSlave  => depacketizerRxSlave);  -- [in]
   -- Representation-only boundary conversion: retain the producers' valid and
   -- ready timing while changing user-bit packing and source-address fields.
   swapAndTag : process(all) is
      variable rx     : AxiStreamMasterType;
      variable tx     : AxiStreamMasterType;
      variable packet : AxiStreamMasterType;
   begin
      rx       := appRxMaster;
      rx.tDest := rx.tDest(3 downto 0) & rx.tDest(7 downto 4);
      rx.tUser := (others => '0');
      axiStreamSetUserField(PACKETIZER2_AXIS_CFG_C, rx,
         resize(axiStreamGetUserField(REASSEMBLY_CONFIG_C, appRxMaster, 0), 2), 0);
      axiStreamSetUserField(PACKETIZER2_AXIS_CFG_C, rx,
         resize(axiStreamGetUserField(REASSEMBLY_CONFIG_C, appRxMaster, -1), 2), -1);
      tx                   := appTxAxisMaster;
      tx.tDest(6 downto 4) := address;
      tx.tUser             := (others => '0');
      axiStreamSetUserField(REASSEMBLY_CONFIG_C, tx,
         axiStreamGetUserField(PACKETIZER2_AXIS_CFG_C, appTxAxisMaster, 0), 0);
      axiStreamSetUserField(REASSEMBLY_CONFIG_C, tx,
         axiStreamGetUserField(PACKETIZER2_AXIS_CFG_C, appTxAxisMaster, -1), -1);
      packet       := localRxMaster;
      packet.tUser := (others => '0');
      axiStreamSetUserField(REASSEMBLY_CONFIG_C, packet,
         axiStreamGetUserField(PACKETIZER2_AXIS_CFG_C, localRxMaster, 0), 0);
      axiStreamSetUserField(REASSEMBLY_CONFIG_C, packet,
         axiStreamGetUserField(PACKETIZER2_AXIS_CFG_C, localRxMaster, -1), -1);
      depacketizerRxMaster <= packet;
      appRxNormal          <= rx;
      taggedMaster         <= tx;
   end process;

   U_Packetizer : entity surf.AxiStreamPacketizer2
      generic map (
         TPD_G                => TPD_G,
         MEMORY_TYPE_G        => "distributed",
         REG_EN_G             => false,
         CRC_MODE_G           => "NONE",
         MAX_PACKET_BYTES_G   => PACKET_SIZE_BYTES_G,
         TDEST_BITS_G         => 8,
         INPUT_PIPE_STAGES_G  => 0,
         OUTPUT_PIPE_STAGES_G => 0)
      port map (
         axisClk     => axisClk,         -- [in]
         axisRst     => axisRst,         -- [in]
         rearbitrate => open,            -- [out]
         sAxisMaster => taggedMaster,    -- [in]
         sAxisSlave  => appTxAxisSlave,  -- [out]
         mAxisMaster => packetMaster,    -- [out]
         mAxisSlave  => packetSlave);    -- [in]
   -- A stalled local producer must not capture the transmit mux with half a
   -- packet. Storage is BEFORE admission, and holds at least one whole packet.
   U_CompletePacket : entity surf.AxiStreamFifoV2
      generic map (
         TPD_G               => TPD_G,
         SLAVE_READY_EN_G    => true,
         VALID_THOLD_G       => 0,
         GEN_SYNC_FIFO_G     => true,
         FIFO_ADDR_WIDTH_G   => maximum(4, bitSize(PACKET_SIZE_BYTES_G/8)),
         SYNTH_MODE_G        => "inferred",
         MEMORY_TYPE_G       => "block",
         SLAVE_AXI_CONFIG_G  => PACKETIZER2_AXIS_CFG_C,
         MASTER_AXI_CONFIG_G => PACKETIZER2_AXIS_CFG_C)
      port map (
         sAxisClk    => axisClk,         -- [in]
         sAxisRst    => axisRst,         -- [in]
         sAxisMaster => packetMaster,    -- [in]
         sAxisSlave  => packetSlave,     -- [out]
         mAxisClk    => axisClk,         -- [in]
         mAxisRst    => axisRst,         -- [in]
         mAxisMaster => bufferedMaster,  -- [out]
         mAxisSlave  => bufferedSlave);  -- [in]
   U_TxMux : entity surf.AxiStreamMux
      generic map (
         TPD_G         => TPD_G,
         PIPE_STAGES_G => 0,
         NUM_SLAVES_G  => 2,
         MODE_G        => "PASSTHROUGH",
         TID_MODE_G    => "PASSTHROUGH",
         ILEAVE_EN_G   => false)
      port map (
         axisClk         => axisClk,            -- [in]
         axisRst         => axisRst,            -- [in]
         disableSel(0)   => disableLocal,       -- [in]
         disableSel(1)   => '0',                -- [in]
         sAxisMasters(0) => bufferedMaster,     -- [in]
         sAxisMasters(1) => passthroughMaster,  -- [in]
         sAxisSlaves(0)  => bufferedSlave,      -- [out]
         sAxisSlaves(1)  => passthroughSlave,   -- [out]
         mAxisMaster     => linkTxAxisMaster,   -- [out]
         mAxisSlave      => linkTxAxisSlave);   -- [in]

end architecture rtl;
