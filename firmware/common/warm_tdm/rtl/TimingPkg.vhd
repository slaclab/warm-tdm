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

   constant K_28_5_C : slv(9 downto 0) := "0101111100";

   constant IDLE_C       : slv(7 downto 0) := "10111100";  -- K28.5, 0xBC
   constant START_RUN_C  : slv(7 downto 0) := "00011100";  -- K28.0
   constant END_RUN_C    : slv(7 downto 0) := "00111100";  -- K28.1
   constant FIRST_ROW_C  : slv(7 downto 0) := "01011100";  -- K28.2
   constant ROW_STROBE_C : slv(7 downto 0) := "01111100";  -- K28.3

   type LocalTimingType is record
      startRun     : sl;                -- Strobed at start of run
      endRun       : sl;                -- Strobed at end of run
      running      : sl;                -- Set high during run
      runTime      : slv(63 downto 0);  -- TimingClk counts since start of run
      rowStrobe    : sl;                -- Moving to new row
      rowNum       : slv(15 downto 0);  -- Current row number
      rowTime      : slv(15 downto 0);  -- timingClk counts since last row strobe
      readoutCount : slv(63 downto 0);  -- Number of full loops through all rows
   end record LocalTimingType;

   constant LOCAL_TIMING_INIT_C : LocalTimingType := (
      startRun     => '0',
      endRun       => '0',
      running      => '0',
      runTime      => (others => '0'),
      rowStrobe    => '0',
      rowNum       => (others => '0'),
      rowTime      => (others => '0'),
      readoutCount => (others => '0'));

end package TimingPkg;
