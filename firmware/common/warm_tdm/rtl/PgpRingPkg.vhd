-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-------------------------------------------------------------------------------
-- Description: Shared packet encodings and capacity bounds for the PGP ring.
-- The budget combines RX pressure, admitted TX data and per-hop status delay.
-- See doc/PGP_RING.md for the topology and PHY-latency assumptions.
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

package PgpRingPkg is

   -- Bound each admission grant by packetizing application frames. RX/TX FIFO
   -- depths and RX watermarks below count eight-byte packed stream entries;
   -- depth 10 therefore reserves 8 KiB per receive VC.
   constant RING_PACKET_BYTES_C    : positive := 128;
   constant RING_RX_ADDR_WIDTH_C   : positive := 10;
   constant RING_RX_PAUSE_HIGH_C   : positive := 8;
   constant RING_RX_PAUSE_LOW_C    : natural := 4;
   constant RING_TX_ADDR_WIDTH_C   : positive := 4;
   -- This is the counter's top bit, not a byte count: bits 3:0 allow sixteen
   -- two-byte PHY words, limiting a cell payload to 32 bytes.
   constant RING_PAYLOAD_CNT_TOP_C : natural := 3;
   -- Per-hop budget includes PHY/status updates, control registers and CDC.
   -- Validate with the vendor GTX simulation when changing PHY configuration.
   constant RING_STATUS_CYCLES_C : positive := 64;
   constant RING_MAX_BOARDS_C    : positive := 8;
   -- Per-node allowance for PHY, width conversion, CDC and router holding slots.
   constant RING_ELASTIC_BYTES_C : positive := 128;
   -- Conservatively allow every node's watermark, post-admission TX FIFO,
   -- in-progress packet and elasticity to converge on one blocked receiver.
   -- The final term covers two bytes per clock during collection propagation:
   -- sum the remaining hop counts 0..N-1, then multiply by the per-hop delay.
   constant RING_BUDGET_BYTES_C  : positive :=
      RING_MAX_BOARDS_C * (8*RING_RX_PAUSE_HIGH_C + 8*2**RING_TX_ADDR_WIDTH_C +
                          RING_PACKET_BYTES_C + RING_ELASTIC_BYTES_C) +
      RING_STATUS_CYCLES_C * RING_MAX_BOARDS_C * (RING_MAX_BOARDS_C-1);
   -- Reserved packetizer version zero, outside the version-2 data namespace.
   -- Bits 18:16 identify the origin. Bit 8 marks the first, local traversal.
   constant RING_ABORT_C      : slv(63 downto 0) := x"52494E47000000F0";
   constant RING_ABORT_MASK_C : slv(63 downto 0) := x"FFFFFFFFFFF8FEFF";

end package PgpRingPkg;
