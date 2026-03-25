-------------------------------------------------------------------------------
-- Title      : Timing Support Package
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: 
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


library warm_tdm;

package TimingPkg is

   constant TIMING_NUM_BITS_C : integer := 259;

   constant K_28_5_C : slv(9 downto 0) := "0101111100";

   constant IDLE_C              : slv(7 downto 0) := "10111100";  -- K28.5, 0xBC
   constant START_RUN_C         : slv(7 downto 0) := "00011100";  -- K28.0
   constant END_RUN_C           : slv(7 downto 0) := "00111100";  -- K28.1
   constant ROW_SEQ_START_C     : slv(7 downto 0) := "01011100";  -- K28.2
   constant DAQ_READOUT_START_C : slv(7 downto 0) := "11111101";  -- K29.7
   constant ROW_STROBE_C        : slv(7 downto 0) := "01111100";  -- K28.3
   constant SAMPLE_START_C      : slv(7 downto 0) := "10011100";  -- K28.4
   constant SAMPLE_END_C        : slv(7 downto 0) := "11011100";  -- K28.6
   constant VR_SYNC_WAIT_C      : slv(7 downto 0) := "11111100";  -- K28.7
   constant LOAD_DACS_C         : slv(7 downto 0) := "11110111";  -- K23.7
   constant WAVEFORM_CAPTURE_C  : slv(7 downto 0) := "11111110";  -- K30.7

   type LocalTimingType is record
      startRun        : sl;                -- Strobed at start of run
      endRun          : sl;                -- Strobed at end of run
      running         : sl;                -- Set high during run
      runTime         : slv(63 downto 0);  -- TimingClk counts since start of run
      rowStrobe       : sl;                -- Commit the pending row on a row-boundary event
      rowSeqStart     : sl;
      daqReadoutStart : sl;
      sample          : sl;
      firstSample     : sl;
      lastSample      : sl;
      loadDacs        : sl;
      rowSeq          : slv(7 downto 0);   -- Sequence index of the active row in the row-order list
      rowIndex        : slv(7 downto 0);   -- Active row index currently in effect
      rowIndexNext    : slv(7 downto 0);   -- Pending row index preloaded for the next row strobe
      rowTime         : slv(31 downto 0);  -- timingClk counts since last row strobe
      rowSeqCount     : slv(63 downto 0);  -- Number of full loops through all rows
      daqReadoutCount : slv(63 downto 0);  -- Number of DAQ readouts
      waveformCapture : sl;                -- Capture ADC waveforms on all channels
   end record LocalTimingType;

   constant LOCAL_TIMING_INIT_C : LocalTimingType := (
      startRun        => '0',
      endRun          => '0',
      running         => '0',
      runTime         => (others => '0'),
      rowStrobe       => '0',
      rowSeqStart     => '0',
      daqReadoutStart => '0',
      sample          => '0',
      firstSample     => '0',
      lastSample      => '0',
      loadDacs        => '0',
      rowSeq          => (others => '0'),
      rowIndex        => (others => '0'),
      rowIndexNext    => (others => '0'),
      rowTime         => (others => '0'),
      rowSeqCount     => (others => '0'),
      daqReadoutCount => (others => '0'),
      waveformCapture => '0');

   function toSlv (
      timing : LocalTimingType)
      return slv;

   function toLocalTimingType (
      vec : slv(TIMING_NUM_BITS_C-1 downto 0))
      return LocalTimingType;

end package TimingPkg;

package body TimingPkg is

   function toSlv (
      timing : LocalTimingType)
      return slv is
      variable vec : slv(TIMING_NUM_BITS_C-1 downto 0);
      variable i   : integer;
   begin
      i := 0;
      assignSlv(i, vec, timing.startRun);
      assignSlv(i, vec, timing.endRun);
      assignSlv(i, vec, timing.running);
      assignSlv(i, vec, timing.runTime);
      assignSlv(i, vec, timing.rowStrobe);
      assignSlv(i, vec, timing.rowSeqStart);
      assignSlv(i, vec, timing.daqReadoutStart);
      assignSlv(i, vec, timing.sample);
      assignSlv(i, vec, timing.firstSample);
      assignSlv(i, vec, timing.lastSample);
      assignSlv(i, vec, timing.loadDacs);
      assignSlv(i, vec, timing.rowSeq);
      assignSlv(i, vec, timing.rowIndex);
      assignSlv(i, vec, timing.rowIndexNext);
      assignSlv(i, vec, timing.rowTime);
      assignSlv(i, vec, timing.rowSeqCount);
      assignSlv(i, vec, timing.daqReadoutCount);
      assignSlv(i, vec, timing.waveformCapture);
      return vec;
   end function toSlv;

   function toLocalTimingType (
      vec : slv(TIMING_NUM_BITS_C-1 downto 0))
      return LocalTimingType is
      variable timing : LocalTimingType;
      variable i      : integer;
   begin
      i := 0;
      assignRecord(i, vec, timing.startRun);
      assignRecord(i, vec, timing.endRun);
      assignRecord(i, vec, timing.running);
      assignRecord(i, vec, timing.runTime);
      assignRecord(i, vec, timing.rowStrobe);
      assignRecord(i, vec, timing.rowSeqStart);
      assignRecord(i, vec, timing.daqReadoutStart);
      assignRecord(i, vec, timing.sample);
      assignRecord(i, vec, timing.firstSample);
      assignRecord(i, vec, timing.lastSample);
      assignRecord(i, vec, timing.loadDacs);
      assignRecord(i, vec, timing.rowSeq);
      assignRecord(i, vec, timing.rowIndex);
      assignRecord(i, vec, timing.rowIndexNext);
      assignRecord(i, vec, timing.rowTime);
      assignRecord(i, vec, timing.rowSeqCount);
      assignRecord(i, vec, timing.daqReadoutCount);
      assignRecord(i, vec, timing.waveformCapture);
      return timing;
   end function toLocalTimingType;

end package body TimingPkg;
