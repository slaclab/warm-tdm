-------------------------------------------------------------------------------
-- Title      : Warm TDM Frame Header package
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   :
-- Standard   : VHDL 2008
-------------------------------------------------------------------------------
-- Description: Shared self-describing frame-identity header for all Warm TDM
-- bulk-data frames (readout, PID-debug fixed/float, waveform). Defines the
-- 16-byte (two 64-bit word) prefix once so every frame builder emits an
-- identical layout, and a single host decoder can read the prefix and dispatch
-- to the right body decoder. See firmware/common/DataChannelization.md
-- ("DECISION" / "Timebase") for the authoritative specification.
--
-- Header layout (little-endian on the wire; byte 0 = tData(7 downto 0)):
--   Word 0:
--     byte 0   formatType     (readout / pid-fixed / pid-float / waveform)
--     byte 1   formatVersion  (starts at 1; bump on any layout change)
--     byte 2   groupId        (reserved, 0 until the multi-Group model, #80)
--     byte 3   boardId        (source column board; cross-checks channel>>4)
--     bytes 4-7 reserved      (zero-filled; future flags / colBase)
--   Word 1:
--     bytes 8-15 timestamp    (64-bit absolute nanoseconds)
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
use ieee.numeric_std.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.SsiPkg.all;

package FrameHeaderPkg is

   -- Format type enumeration (header byte 0). Extend, never renumber.
   constant FRAME_FORMAT_READOUT_C   : slv(7 downto 0) := X"00";
   constant FRAME_FORMAT_PID_FIXED_C : slv(7 downto 0) := X"01";
   constant FRAME_FORMAT_PID_FLOAT_C : slv(7 downto 0) := X"02";
   constant FRAME_FORMAT_WAVEFORM_C  : slv(7 downto 0) := X"03";

   -- Layout version (header byte 1). Bump on ANY frame body/layout change so a
   -- reprocessing decoder can tell which layout it is reading.
   constant FRAME_FORMAT_VERSION_C : slv(7 downto 0) := X"01";

   -- The header occupies two 64-bit words on a DATA_AXIS_CONFIG_C-style bus.
   constant FRAME_HEADER_WORDS_C : integer := 2;
   constant FRAME_HEADER_BYTES_C : integer := 16;

   -- Build header word 0 from the per-frame identity fields. groupId defaults to
   -- 0 (reserved until the multi-Group model, #80) but is a parameter so the
   -- register/wiring can supply it later without a signature change; reserved
   -- bytes 4-7 are zero.
   function frameHeaderWord0 (
      formatType : slv(7 downto 0);
      boardId    : slv(7 downto 0);
      groupId    : slv(7 downto 0) := X"00")
      return slv;

   -- Build header word 1 (the 64-bit absolute-nanoseconds timestamp).
   function frameHeaderWord1 (
      timestampNs : slv(63 downto 0))
      return slv;

   -- Emit header word 0 onto an AXI-stream master variable: assert tValid, set
   -- Start-Of-Frame, and place word 0 in tData(63:0). Every frame's SOF moves
   -- here (the first header word). Intended to be called on the v.<master>
   -- variable inside a builder's frame-start FSM state.
   procedure emitFrameHeaderWord0 (
      axisConfig       : in    AxiStreamConfigType;
      variable axisMaster : inout AxiStreamMasterType;
      formatType       : in    slv(7 downto 0);
      boardId          : in    slv(7 downto 0);
      groupId          : in    slv(7 downto 0) := X"00";
      valid            : in    sl := '1');

   -- Emit header word 1 (timestamp) onto an AXI-stream master variable. No SOF.
   procedure emitFrameHeaderWord1 (
      variable axisMaster : inout AxiStreamMasterType;
      timestampNs      : in    slv(63 downto 0);
      valid            : in    sl := '1');

end package FrameHeaderPkg;

package body FrameHeaderPkg is

   function frameHeaderWord0 (
      formatType : slv(7 downto 0);
      boardId    : slv(7 downto 0);
      groupId    : slv(7 downto 0) := X"00")
      return slv is
      variable ret : slv(63 downto 0) := (others => '0');
   begin
      ret(7 downto 0)   := formatType;              -- byte 0
      ret(15 downto 8)  := FRAME_FORMAT_VERSION_C;  -- byte 1
      ret(23 downto 16) := groupId;                 -- byte 2 (reserved 0 today)
      ret(31 downto 24) := boardId;                 -- byte 3
      -- bytes 4-7 (63 downto 32) reserved, left zero
      return ret;
   end function frameHeaderWord0;

   function frameHeaderWord1 (
      timestampNs : slv(63 downto 0))
      return slv is
   begin
      return timestampNs;
   end function frameHeaderWord1;

   procedure emitFrameHeaderWord0 (
      axisConfig       : in    AxiStreamConfigType;
      variable axisMaster : inout AxiStreamMasterType;
      formatType       : in    slv(7 downto 0);
      boardId          : in    slv(7 downto 0);
      groupId          : in    slv(7 downto 0) := X"00";
      valid            : in    sl := '1') is
   begin
      axisMaster.tValid            := valid;
      axisMaster.tData(63 downto 0) := frameHeaderWord0(formatType, boardId, groupId);
      ssiSetUserSof(axisConfig, axisMaster, '1');
   end procedure emitFrameHeaderWord0;

   procedure emitFrameHeaderWord1 (
      variable axisMaster : inout AxiStreamMasterType;
      timestampNs      : in    slv(63 downto 0);
      valid            : in    sl := '1') is
   begin
      axisMaster.tValid            := valid;
      axisMaster.tData(63 downto 0) := frameHeaderWord1(timestampNs);
   end procedure emitFrameHeaderWord1;

end package body FrameHeaderPkg;
