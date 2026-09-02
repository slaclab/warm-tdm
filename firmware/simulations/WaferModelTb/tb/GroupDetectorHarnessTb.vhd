-------------------------------------------------------------------------------
-- Title      : Group Detector Harness Self-Checking Testbench
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : Simulation
-- Standard   : VHDL-2008
-------------------------------------------------------------------------------
-- This file is part of Warm TDM. It is subject to
-- the license terms in the LICENSE.txt file found in the top-level directory
-- of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of Warm TDM, including this file, may be
-- copied, modified, propagated, or distributed except according to the terms
-- contained in the LICENSE.txt file.
-------------------------------------------------------------------------------

use std.env.all;

library surf;
use surf.StdRtlPkg.all;

library warm_tdm;
use warm_tdm.SimPkg.all;
use warm_tdm.WaferSimPkg.all;

entity GroupDetectorHarnessTb is
end entity GroupDetectorHarnessTb;

architecture sim of GroupDetectorHarnessTb is
   constant ZERO_SOURCE_C : CurrentType := (voltage => 0.0, impedance => 0.5);

   signal oneTesBiasP   : RealArray(0 to 15) := (others => 0.0);
   signal oneTesBiasN   : RealArray(0 to 15) := (others => 0.0);
   signal oneSaBiasP    : CurrentArray(0 to 15) := (others => ZERO_SOURCE_C);
   signal oneSaBiasN    : CurrentArray(0 to 15) := (others => ZERO_SOURCE_C);
   signal oneSaInP      : RealArray(0 to 15);
   signal oneSaInN      : RealArray(0 to 15);
   signal oneSaFbP      : CurrentArray(0 to 15) := (others => ZERO_SOURCE_C);
   signal oneSaFbN      : CurrentArray(0 to 15) := (others => ZERO_SOURCE_C);
   signal oneSq1BiasP   : CurrentArray(0 to 15) := (others => ZERO_SOURCE_C);
   signal oneSq1BiasN   : CurrentArray(0 to 15) := (others => ZERO_SOURCE_C);
   signal oneSq1FbP     : CurrentArray(0 to 15) := (others => ZERO_SOURCE_C);
   signal oneSq1FbN     : CurrentArray(0 to 15) := (others => ZERO_SOURCE_C);
   signal oneRsP        : CurrentArray(0 to 31) := (others => ZERO_SOURCE_C);
   signal oneRsN        : CurrentArray(0 to 31) := (others => ZERO_SOURCE_C);
   signal oneStimulus   : RealVector(0 to 12*60-1) := (others => 0.0);

   signal dualTesBiasP : RealArray(0 to 23) := (others => 0.0);
   signal dualTesBiasN : RealArray(0 to 23) := (others => 0.0);
   signal dualSourcesP : CurrentArray(0 to 23) := (others => ZERO_SOURCE_C);
   signal dualSourcesN : CurrentArray(0 to 23) := (others => ZERO_SOURCE_C);
   signal dualSaInP    : RealArray(0 to 23);
   signal dualSaInN    : RealArray(0 to 23);
   signal dualRsP      : CurrentArray(0 to 31) := (others => ZERO_SOURCE_C);
   signal dualRsN      : CurrentArray(0 to 31) := (others => ZERO_SOURCE_C);
   signal dualStimulus : RealVector(0 to 2*12*60-1) := (others => 0.0);
begin

   U_OneDetector : entity warm_tdm.GroupDetectorHarnessSim
      generic map (
         NUM_WARM_COLUMNS_G     => 16,
         NUM_WARM_ROW_LINES_G   => 32,
         NUM_DETECTORS_G        => 1,
         COLUMNS_PER_DETECTOR_G => 12,
         NUM_BANKS_G            => 6,
         ROWS_PER_BANK_G        => 10,
         TWO_LEVEL_G            => true,
         SA_BIAS_LOADS_G        => (others => 0.0),
         SA_FB_LOADS_G          => (others => 0.0),
         SQ1_BIAS_LOADS_G       => (others => 0.0),
         SQ1_FB_LOADS_G         => (others => 0.0),
         RS_LOADS_G             => (others => 0.0))
      port map (
         tesBiasP       => oneTesBiasP,
         tesBiasN       => oneTesBiasN,
         saBiasOutP     => oneSaBiasP,
         saBiasOutN     => oneSaBiasN,
         saBiasInP      => oneSaInP,
         saBiasInN      => oneSaInN,
         saFbP          => oneSaFbP,
         saFbN          => oneSaFbN,
         sq1BiasP       => oneSq1BiasP,
         sq1BiasN       => oneSq1BiasN,
         sq1FbP         => oneSq1FbP,
         sq1FbN         => oneSq1FbN,
         rsP            => oneRsP,
         rsN            => oneRsN,
         tesStimulusAmp => oneStimulus);

   U_DualBa4 : entity warm_tdm.GroupDetectorHarnessSim
      generic map (
         NUM_WARM_COLUMNS_G     => 24,
         NUM_WARM_ROW_LINES_G   => 32,
         NUM_DETECTORS_G        => 2,
         COLUMNS_PER_DETECTOR_G => 12,
         NUM_BANKS_G            => 6,
         ROWS_PER_BANK_G        => 10,
         TWO_LEVEL_G            => true,
         WARM_DETECTOR_MAP_G    => DUAL_BA4_WARM_DETECTOR_MAP_C,
         WARM_COLUMN_MAP_G      => DUAL_BA4_WARM_COLUMN_MAP_C,
         RS_LINE_MAP_G          => DUAL_BA4_RS_LINE_MAP_C,
         CS_LINE_MAP_G          => DUAL_BA4_CS_LINE_MAP_C,
         SA_BIAS_LOADS_G        => (others => 0.0),
         SA_FB_LOADS_G          => (others => 0.0),
         SQ1_BIAS_LOADS_G       => (others => 0.0),
         SQ1_FB_LOADS_G         => (others => 0.0),
         RS_LOADS_G             => (others => 0.0))
      port map (
         tesBiasP       => dualTesBiasP,
         tesBiasN       => dualTesBiasN,
         saBiasOutP     => dualSourcesP,
         saBiasOutN     => dualSourcesN,
         saBiasInP      => dualSaInP,
         saBiasInN      => dualSaInN,
         saFbP          => dualSourcesP,
         saFbN          => dualSourcesN,
         sq1BiasP       => dualSourcesP,
         sq1BiasN       => dualSourcesN,
         sq1FbP         => dualSourcesP,
         sq1FbN         => dualSourcesN,
         rsP            => dualRsP,
         rsN            => dualRsN,
         tesStimulusAmp => dualStimulus);

   test : process is
      constant PIXEL_C : natural := 11*60 + 2*10 + 3;
      variable selectedVoltage : real;
   begin
      -- The physical 12-column detector occupies board 0 plus channels 0..3
      -- of board 1.  Channels 4..7 of board 1 are explicit zero terminations.
      oneSaBiasP(11).voltage  <= 80.0E-6;
      oneSq1BiasP(11).voltage <= 30.0E-6;
      oneSaBiasP(15).voltage  <= 80.0E-6;
      oneRsP(3).voltage       <= 150.0E-6;
      oneRsP(12).voltage      <= 125.0E-6;
      wait for 1 ns;
      assert oneSaInP(15) = 0.0 and oneSaInN(15) = 0.0
         report "unused 8+4 warm endpoint was not explicitly terminated"
         severity failure;
      selectedVoltage := oneSaInP(11) - oneSaInN(11);

      oneStimulus(PIXEL_C) <= 5.0E-6;
      wait for 1 ns;
      assert abs((oneSaInP(11) - oneSaInN(11)) - selectedVoltage) > 1.0E-9
         report "8+4 harness did not route the selected detector pixel"
         severity failure;

      -- Check the mixed third-board endpoints and the split row-board maps.
      assert DUAL_BA4_WARM_DETECTOR_MAP_C(16) = 0 and
             DUAL_BA4_WARM_COLUMN_MAP_C(16) = 8 and
             DUAL_BA4_WARM_DETECTOR_MAP_C(20) = 1 and
             DUAL_BA4_WARM_COLUMN_MAP_C(20) = 8
         report "dual-BA4 third-board 4+4 map is incorrect"
         severity failure;
      assert DUAL_BA4_RS_LINE_MAP_C(10) = 16 and
             DUAL_BA4_CS_LINE_MAP_C(6) = 26
         report "dual-BA4 second-detector row map is incorrect"
         severity failure;
      assert dualSaInP(23) = dualSaInP(23)
         report "dual-BA4 harness produced a non-finite output"
         severity failure;

      report "GroupDetectorHarnessTb PASSED" severity note;
      stop;
      wait;
   end process test;

end architecture sim;
