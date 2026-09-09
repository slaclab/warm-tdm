-------------------------------------------------------------------------------
-- Title      : Eight-Column, 6x10 Detector Slice Testbench
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

library warm_tdm;
use warm_tdm.WaferSimPkg.all;

entity DetectorScaleTb is
end entity DetectorScaleTb;

architecture sim of DetectorScaleTb is
   constant NUM_COLUMNS_C : positive := 8;
   constant NUM_BANKS_C   : positive := 6;
   constant ROWS_PER_BANK_C : positive := 10;
   constant NUM_ROWS_C    : positive := NUM_BANKS_C * ROWS_PER_BANK_C;

   signal ssaBias    : RealVector(0 to NUM_COLUMNS_C-1) := (others => 80.0E-6);
   signal ssaFb      : RealVector(0 to NUM_COLUMNS_C-1) := (others => 0.0);
   signal sq1Bias    : RealVector(0 to NUM_COLUMNS_C-1) := (others => 30.0E-6);
   signal sq1Fb      : RealVector(0 to NUM_COLUMNS_C-1) := (others => 0.0);
   signal rowSelect  : RealVector(0 to ROWS_PER_BANK_C-1) := (others => 0.0);
   signal chipSelect : RealVector(0 to NUM_BANKS_C-1) := (others => 0.0);
   signal tesCurrent : RealVector(0 to NUM_COLUMNS_C*NUM_ROWS_C-1) :=
      (others => 0.0);
   signal muxCurrent : RealVector(0 to NUM_COLUMNS_C-1);
   signal muxVoltage : RealVector(0 to NUM_COLUMNS_C-1);
   signal ssaPhase   : RealVector(0 to NUM_COLUMNS_C-1);
   signal ssaVoltage : RealVector(0 to NUM_COLUMNS_C-1);
begin

   U_Dut : entity warm_tdm.DetectorModuleSim
      generic map (
         NUM_COLUMNS_G   => NUM_COLUMNS_C,
         NUM_BANKS_G     => NUM_BANKS_C,
         ROWS_PER_BANK_G => ROWS_PER_BANK_C,
         TWO_LEVEL_G     => true)
      port map (
         ssaBiasCurrentAmp     => ssaBias,
         ssaFeedbackCurrentAmp => ssaFb,
         sq1BiasCurrentAmp     => sq1Bias,
         sq1FeedbackCurrentAmp => sq1Fb,
         rowSelectCurrentAmp   => rowSelect,
         chipSelectCurrentAmp  => chipSelect,
         tesCurrentAmp         => tesCurrent,
         muxCurrentAmp         => muxCurrent,
         muxVoltageVolt        => muxVoltage,
         ssaBiasLoadCurrentAmp => open,
         ssaPhaseCycles        => ssaPhase,
         ssaVoltageVolt        => ssaVoltage);

   test : process is
      constant TEST_COLUMN_C : natural := 5;
      constant TEST_BANK_C   : natural := 2;
      constant TEST_ROW_C    : natural := 3;
      constant PIXEL_C       : natural :=
         TEST_COLUMN_C*NUM_ROWS_C + TEST_BANK_C*ROWS_PER_BANK_C + TEST_ROW_C;
      variable rowOnlyCurrent : real;
      variable selectedCurrent : real;
      variable adjacentCurrent : real;
   begin
      wait for 1 ns;
      rowSelect(TEST_ROW_C) <= 0.5 *
         ROW_FAS_SYNTHETIC_C.squid.currentPerPhi0Amp;
      wait for 1 ns;
      rowOnlyCurrent := muxCurrent(TEST_COLUMN_C);

      chipSelect(TEST_BANK_C) <= 0.5 *
         CHIP_FAS_SYNTHETIC_C.squid.currentPerPhi0Amp;
      wait for 1 ns;
      selectedCurrent := muxCurrent(TEST_COLUMN_C);
      assert abs(selectedCurrent - rowOnlyCurrent) > 0.005E-6
         report "6x10 detector did not require both row and chip select: row-only=" &
                real'image(rowOnlyCurrent) & ", selected=" &
                real'image(selectedCurrent)
         severity failure;

      adjacentCurrent := muxCurrent(TEST_COLUMN_C-1);
      tesCurrent(PIXEL_C) <= 0.5 *
         SQ1_SYNTHETIC_C.squid.currentPerPhi0Amp;
      wait for 1 ns;
      assert abs(muxCurrent(TEST_COLUMN_C) - selectedCurrent) > 0.005E-6
         report "selected pixel did not modulate its 6x10 detector column: before=" &
                real'image(selectedCurrent) & ", after=" &
                real'image(muxCurrent(TEST_COLUMN_C))
         severity failure;
      assert abs(muxCurrent(TEST_COLUMN_C-1) - adjacentCurrent) < 1.0E-12
         report "selected pixel leaked into an adjacent detector column"
         severity failure;

      for column in 0 to NUM_COLUMNS_C-1 loop
         assert ssaVoltage(column) = ssaVoltage(column)
            report "non-finite SSA output in 8-column detector slice"
            severity failure;
      end loop;

      report "DetectorScaleTb PASSED" severity note;
      stop;
      wait;
   end process test;

end architecture sim;
