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
   constant ZERO_SOURCE_C : TheveninSourceType :=
      (voltage => 0.0, impedance => 0.5);
   constant ZERO_DIFF_SOURCE_C : DifferentialSourceType :=
      (p => ZERO_SOURCE_C, n => ZERO_SOURCE_C);
   constant ZERO_DIFF_REAL_C : DifferentialRealType := (p => 0.0, n => 0.0);
   constant ZERO_COLUMN_DRIVE_C : ColumnCryoDriveType := (
      tesBias     => ZERO_DIFF_REAL_C,
      ssaBias     => ZERO_DIFF_SOURCE_C,
      ssaFeedback => ZERO_DIFF_SOURCE_C,
      sq1Bias     => ZERO_DIFF_SOURCE_C,
      sq1Feedback => ZERO_DIFF_SOURCE_C);
   constant DUAL_PRESET_DETECTOR_MAP_C : IntegerVector(0 to 23) :=
      presetWarmDetectorMap("BA4", 24, 2, 12);
   constant DUAL_PRESET_COLUMN_MAP_C : IntegerVector(0 to 23) :=
      presetWarmColumnMap("BA4", 24, 2, 12);
   constant DUAL_PRESET_RS_MAP_C : IntegerVector(0 to 19) :=
      presetRsLineMap("BA4", 2, 10, 6, true);
   constant DUAL_PRESET_CS_MAP_C : IntegerVector(0 to 11) :=
      presetCsLineMap("BA4", 2, 10, 6, true);

   signal oneColumnDrive : ColumnCryoDriveArray(0 to 15) :=
      (others => ZERO_COLUMN_DRIVE_C);
   signal oneColumnSense : ColumnCryoSenseArray(0 to 15);
   signal oneRowDrive : DifferentialSourceArray(0 to 31) :=
      (others => ZERO_DIFF_SOURCE_C);
   signal oneStimulus   : RealVector(0 to 12*60-1) := (others => 0.0);

   signal dualColumnDrive : ColumnCryoDriveArray(0 to 23) :=
      (others => ZERO_COLUMN_DRIVE_C);
   signal dualColumnSense : ColumnCryoSenseArray(0 to 23);
   signal dualRowDrive : DifferentialSourceArray(0 to 31) :=
      (others => ZERO_DIFF_SOURCE_C);
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
         columnDrive    => oneColumnDrive,
         columnSense    => oneColumnSense,
         rowSelectDrive => oneRowDrive,
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
         WARM_DETECTOR_MAP_G    => DUAL_PRESET_DETECTOR_MAP_C,
         WARM_COLUMN_MAP_G      => DUAL_PRESET_COLUMN_MAP_C,
         RS_LINE_MAP_G          => DUAL_PRESET_RS_MAP_C,
         CS_LINE_MAP_G          => DUAL_PRESET_CS_MAP_C,
         SA_BIAS_LOADS_G        => (others => 0.0),
         SA_FB_LOADS_G          => (others => 0.0),
         SQ1_BIAS_LOADS_G       => (others => 0.0),
         SQ1_FB_LOADS_G         => (others => 0.0),
         RS_LOADS_G             => (others => 0.0))
      port map (
         columnDrive    => dualColumnDrive,
         columnSense    => dualColumnSense,
         rowSelectDrive => dualRowDrive,
         tesStimulusAmp => dualStimulus);

   test : process is
      constant PIXEL_C : natural := 11*60 + 2*10 + 3;
      variable selectedVoltage : real;
   begin
      -- The physical 12-column detector occupies board 0 plus channels 0..3
      -- of board 1.  Channels 4..7 of board 1 are explicit zero terminations.
      oneColumnDrive(11).ssaBias.p.voltage <= 80.0E-6;
      oneColumnDrive(11).sq1Bias.p.voltage <= 30.0E-6;
      oneColumnDrive(15).ssaBias.p.voltage <= 80.0E-6;
      oneRowDrive(3).p.voltage             <= 150.0E-6;
      oneRowDrive(12).p.voltage            <= 125.0E-6;
      wait for 1 ns;
      assert oneColumnSense(15).ssaVoltage.p = 0.0 and
             oneColumnSense(15).ssaVoltage.n = 0.0
         report "unused 8+4 warm endpoint was not explicitly terminated"
         severity failure;
      selectedVoltage := oneColumnSense(11).ssaVoltage.p -
                         oneColumnSense(11).ssaVoltage.n;

      oneStimulus(PIXEL_C) <= 5.0E-6;
      wait for 1 ns;
      assert abs((oneColumnSense(11).ssaVoltage.p -
                  oneColumnSense(11).ssaVoltage.n) - selectedVoltage) > 1.0E-9
         report "8+4 harness did not route the selected detector pixel"
         severity failure;

      -- Check the mixed third-board endpoints and the split row-board maps.
      assert DUAL_PRESET_DETECTOR_MAP_C(16) = 0 and
             DUAL_PRESET_COLUMN_MAP_C(16) = 8 and
             DUAL_PRESET_DETECTOR_MAP_C(20) = 1 and
             DUAL_PRESET_COLUMN_MAP_C(20) = 8
         report "dual-BA4 third-board 4+4 map is incorrect"
         severity failure;
      assert DUAL_PRESET_RS_MAP_C(10) = 16 and
             DUAL_PRESET_CS_MAP_C(6) = 26
         report "dual-BA4 second-detector row map is incorrect"
         severity failure;
      assert dualColumnSense(23).ssaVoltage.p =
             dualColumnSense(23).ssaVoltage.p
         report "dual-BA4 harness produced a non-finite output"
         severity failure;

      report "GroupDetectorHarnessTb PASSED" severity note;
      stop;
      wait;
   end process test;

end architecture sim;
