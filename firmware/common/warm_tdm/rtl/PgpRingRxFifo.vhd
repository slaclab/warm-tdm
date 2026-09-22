-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Guard an unthrottled PGP receive stream and cross to axisClk.
-- Retain accepted words, terminate a damaged packet, then enqueue an ordered
-- ring-wide abort marker. No later PHY traffic is needed to finish recovery.
-- Discard new traffic until the marker is queued and a fresh SOF is observed.
-- Registered pgpClk pressure is advisory; only the Rogue PHY honors tReady.
-- pgpRst and axisRst reset their respective sides of the asynchronous FIFO.
-------------------------------------------------------------------------------
-- This file is part of Warm TDM. It is subject to the license terms in the
-- LICENSE.txt file found in the top-level directory of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of Warm TDM, including this file, may be copied, modified, propagated,
-- or distributed except according to the terms contained in LICENSE.txt.
-------------------------------------------------------------------------------
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.SsiPkg.all;
use surf.Pgp2bPkg.all;
use surf.AxiStreamPacketizer2Pkg.all;
library warm_tdm;
use warm_tdm.PgpRingPkg.all;

entity PgpRingRxFifo is
   generic (
      TPD_G             : time     := 1 ns;
      FIFO_ADDR_WIDTH_G : positive := RING_RX_ADDR_WIDTH_C;
      PAUSE_HIGH_G      : positive := RING_RX_PAUSE_HIGH_C;
      PAUSE_LOW_G       : natural  := RING_RX_PAUSE_LOW_C;
      READY_EN_G        : boolean  := false);
   port (
      -- PGP receive clock domain
      pgpClk      : in  sl;
      pgpRst      : in  sl;

      -- Unthrottled PHY input and advisory receive pressure
      rxLinkReady : in  sl;
      address     : in  slv(2 downto 0);
      pgpRxMaster : in  AxiStreamMasterType;
      pgpRxSlave  : out AxiStreamSlaveType;
      pgpRxCtrl   : out AxiStreamCtrlType;

      -- Application clock domain
      axisClk    : in  sl;
      axisRst    : in  sl;

      -- Buffered application output
      axisMaster : out AxiStreamMasterType;
      axisSlave  : in  AxiStreamSlaveType);
end entity PgpRingRxFifo;

architecture rtl of PgpRingRxFifo is

   -- HUNT discards fragments until SOF; MOVE captures a packet. After loss,
   -- CLOSE appends an error terminator and MARKER appends the ring abort. Both
   -- recovery states discard incoming PHY words, which cannot be stalled.
   type StateType is (HUNT_S, MOVE_S, CLOSE_S, MARKER_S);
   type RegType is record
      state      : StateType;
      master     : AxiStreamMasterType;
      pgpRxSlave : AxiStreamSlaveType;
      pgpRxCtrl  : AxiStreamCtrlType;
      index      : natural range 0 to 3;
      -- FIFO occupancy hysteresis, independent of recovery-forced pressure.
      pause   : sl;
      linkDly : sl;
      origin  : slv(2 downto 0);
   end record;
   constant REG_INIT_C : RegType := (
      state      => HUNT_S,
      master     => AXI_STREAM_MASTER_INIT_C,
      pgpRxSlave => AXI_STREAM_SLAVE_INIT_C,
      pgpRxCtrl  => (
         pause    => '1',
         overflow => '0',
         idle     => '1'),
      index   => 0,
      pause   => '1',
      linkDly => '0',
      origin  => "000");
   signal r         : RegType := REG_INIT_C;
   signal rin       : RegType;
   signal fifoSlave : AxiStreamSlaveType;
   signal count     : slv(FIFO_ADDR_WIDTH_G-1 downto 0);
   signal full      : sl;

begin

   assert PAUSE_LOW_G < PAUSE_HIGH_G and PAUSE_HIGH_G < 2**FIFO_ADDR_WIDTH_G
      report "Invalid ring RX watermarks" severity failure;

   comb : process(all) is
      variable v      : RegType;
      variable marker : slv(63 downto 0);
   begin
      v            := r;
      v.pgpRxCtrl  := AXI_STREAM_CTRL_UNUSED_C;
      v.linkDly    := rxLinkReady;
      v.pgpRxSlave := AXI_STREAM_SLAVE_INIT_C;
      -- r.master is a holding slot in front of the FIFO. Retire it only on
      -- FIFO acceptance; a free slot can be refilled on this same edge. During
      -- recovery it preserves the last accepted word ahead of the terminator.
      if fifoSlave.tReady = '1' then
         v.master.tValid := '0';
      end if;
      -- Count is in packed eight-byte FIFO entries, not two-byte PHY words.
      -- Assert pressure early enough to absorb admitted traffic and status
      -- propagation; hysteresis avoids chatter as the consumer drains.
      if full = '1' or unsigned(count) >= PAUSE_HIGH_G then
         v.pause := '1';
      elsif unsigned(count) <= PAUSE_LOW_G then
         v.pause := '0';
      end if;
      -- The origin removes this marker after one circuit. Bit 8 distinguishes
      -- its initial local delivery from a marker returning over the ring.
      marker               := RING_ABORT_C;
      marker(18 downto 16) := r.origin;
      marker(8)            := '1';
      case r.state is
         when HUNT_S | MOVE_S =>
            v.pgpRxSlave.tReady := not v.master.tValid;
            if pgpRxMaster.tValid = '1' and rxLinkReady = '1' then
               if v.master.tValid = '1' then
                  if not READY_EN_G then
                     -- Real PGP has already delivered this word: retaining the
                     -- occupied slot loses the new word, so framing is suspect.
                     -- Rogue instead holds the word until tReady is asserted.
                     v.pgpRxCtrl.overflow := '1';
                     v.origin             := address;
                     v.state              := CLOSE_S;
                  end if;
               elsif r.state = MOVE_S and ssiGetUserSof(SSI_PGP2B_CONFIG_C, pgpRxMaster) = '1' then
                  -- A new SOF before EOF is also loss. The stream cannot wait
                  -- while we insert an error, so discard this packet too.
                  v.pgpRxCtrl.overflow := '1';
                  v.origin             := address;
                  v.state              := CLOSE_S;
               elsif r.state = MOVE_S or ssiGetUserSof(SSI_PGP2B_CONFIG_C, pgpRxMaster) = '1' then
                  v.master := pgpRxMaster;
                  v.state  := MOVE_S;
                  if pgpRxMaster.tLast = '1' then
                     v.state := HUNT_S;
                  end if;
               end if;
            end if;
         when CLOSE_S =>
            -- Wait for capacity rather than overwriting accepted data. This
            -- synthetic EOFE also closes a packet whose real tail never arrives.
            if v.master.tValid = '0' then
               v.master        := axiStreamMasterInit(SSI_PGP2B_CONFIG_C);
               v.master.tValid := '1';
               v.master.tLast  := '1';
               ssiSetUserEofe(SSI_PGP2B_CONFIG_C, v.master, '1');
               v.index := 0;
               v.state := MARKER_S;
            end if;
         when MARKER_S =>
            -- Serialize the 64-bit abort as four PHY words, low word first.
            -- It shares the data FIFO, so no router can see the abort before
            -- the damaged packet's terminator. No new PHY traffic is required.
            if v.master.tValid = '0' then
               v.master                    := axiStreamMasterInit(SSI_PGP2B_CONFIG_C);
               v.master.tValid             := '1';
               v.master.tData(15 downto 0) := marker(16*r.index+15 downto 16*r.index);
               if r.index = 0 then
                  ssiSetUserSof(SSI_PGP2B_CONFIG_C, v.master, '1');
               end if;
               if r.index = 3 then
                  -- The final marker word still occupies the holding slot;
                  -- HUNT can accept a fresh SOF only when that slot is freed.
                  v.master.tLast := '1';
                  v.state        := HUNT_S;
               else
                  v.index := r.index + 1;
               end if;
            end if;
      end case;
      -- A link drop also needs an ordered terminator; do not clear queued data.
      -- Give the falling edge priority over normal capture/recovery progress.
      if r.linkDly = '1' and rxLinkReady = '0' then
         v.origin := address;
         v.state  := CLOSE_S;
      end if;
      -- Only the Rogue PHY honors ready. It reflects this edge's output-slot
      -- capacity; registering it would require another reserved input slot.
      if not READY_EN_G then
         v.pgpRxSlave := AXI_STREAM_SLAVE_FORCE_C;
      end if;
      -- Publish pressure with the recovery state, without an output decode.
      v.pgpRxCtrl.pause := v.pause;
      if v.state = CLOSE_S or v.state = MARKER_S or rxLinkReady /= '1' then
         v.pgpRxCtrl.pause := '1';
      end if;
      if pgpRst = '1' then
         v := REG_INIT_C;
      end if;
      rin        <= v;
      pgpRxSlave <= v.pgpRxSlave;
      pgpRxCtrl  <= r.pgpRxCtrl;
   end process;
   seq : process(pgpClk) is
   begin
      if rising_edge(pgpClk) then
         r <= rin after TPD_G;
      end if;
   end process;

   -- Streaming validity avoids a separate packet-metadata FIFO that could
   -- overflow independently. Internal ready protects the RAM even though the
   -- physical receiver cannot honor it; the holding slot detects that loss.
   U_Fifo : entity surf.AxiStreamFifoV2
      generic map (
         TPD_G               => TPD_G,
         INT_PIPE_STAGES_G   => 1,
         PIPE_STAGES_G       => 0,
         SLAVE_READY_EN_G    => true,
         VALID_THOLD_G       => 1,
         GEN_SYNC_FIFO_G     => false,
         SYNTH_MODE_G        => "inferred",
         MEMORY_TYPE_G       => "block",
         FIFO_ADDR_WIDTH_G   => FIFO_ADDR_WIDTH_G,
         SLAVE_AXI_CONFIG_G  => SSI_PGP2B_CONFIG_C,
         MASTER_AXI_CONFIG_G => PACKETIZER2_AXIS_CFG_C)
      port map (
         sAxisClk    => pgpClk,      -- [in]
         sAxisRst    => pgpRst,      -- [in]
         sAxisMaster => r.master,    -- [in]
         sAxisSlave  => fifoSlave,   -- [out]
         fifoWrCnt   => count,       -- [out]
         fifoFull    => full,        -- [out]
         mAxisClk    => axisClk,     -- [in]
         mAxisRst    => axisRst,     -- [in]
         mAxisMaster => axisMaster,  -- [out]
         mAxisSlave  => axisSlave);  -- [in]

end architecture rtl;
