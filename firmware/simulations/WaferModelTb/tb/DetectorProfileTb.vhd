-------------------------------------------------------------------------------
-- Title      : Physical Detector Profile Elaboration Testbench
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : Simulation
-- Standard   : VHDL-2008
-------------------------------------------------------------------------------
-- Description:
-- Elaborates the known 22x12, 50x12, and 60x12 detector-module dimensions
-- from the same configurable model source.  DetectorScaleTb separately drives
-- the full row/chip/TES behavior of an eight-column BA4 slice.
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

entity DetectorProfileTb is
end entity DetectorProfileTb;

architecture sim of DetectorProfileTb is

   constant B3_ROWS_C   : positive := topologyRows(BICEP3_TOPOLOGY_C);
   constant NIST_ROWS_C : positive := topologyRows(NIST_50R_TOPOLOGY_C);
   constant BA4_ROWS_C  : positive := topologyRows(BA4_TOPOLOGY_C);

   signal b3SsaBias : RealVector(0 to BICEP3_TOPOLOGY_C.physicalColumns-1) :=
      (others => 80.0E-6);
   signal b3ZeroColumns : RealVector(0 to BICEP3_TOPOLOGY_C.physicalColumns-1) :=
      (others => 0.0);
   signal b3Rows : RealVector(0 to BICEP3_TOPOLOGY_C.rowsPerBank-1) :=
      (others => 0.0);
   signal b3Banks : RealVector(0 to BICEP3_TOPOLOGY_C.numBanks-1) :=
      (others => 0.0);
   signal b3Tes : RealVector(
      0 to BICEP3_TOPOLOGY_C.physicalColumns*B3_ROWS_C-1) := (others => 0.0);
   signal b3MuxCurrent : RealVector(0 to BICEP3_TOPOLOGY_C.physicalColumns-1);
   signal b3MuxVoltage : RealVector(0 to BICEP3_TOPOLOGY_C.physicalColumns-1);
   signal b3SsaPhase   : RealVector(0 to BICEP3_TOPOLOGY_C.physicalColumns-1);
   signal b3SsaVoltage : RealVector(0 to BICEP3_TOPOLOGY_C.physicalColumns-1);

   signal nistSsaBias : RealVector(0 to NIST_50R_TOPOLOGY_C.physicalColumns-1) :=
      (others => 80.0E-6);
   signal nistZeroColumns : RealVector(0 to NIST_50R_TOPOLOGY_C.physicalColumns-1) :=
      (others => 0.0);
   signal nistRows : RealVector(0 to NIST_50R_TOPOLOGY_C.rowsPerBank-1) :=
      (others => 0.0);
   signal nistBanks : RealVector(0 to NIST_50R_TOPOLOGY_C.numBanks-1) :=
      (others => 0.0);
   signal nistTes : RealVector(
      0 to NIST_50R_TOPOLOGY_C.physicalColumns*NIST_ROWS_C-1) := (others => 0.0);
   signal nistMuxCurrent : RealVector(0 to NIST_50R_TOPOLOGY_C.physicalColumns-1);
   signal nistMuxVoltage : RealVector(0 to NIST_50R_TOPOLOGY_C.physicalColumns-1);
   signal nistSsaPhase   : RealVector(0 to NIST_50R_TOPOLOGY_C.physicalColumns-1);
   signal nistSsaVoltage : RealVector(0 to NIST_50R_TOPOLOGY_C.physicalColumns-1);

   signal ba4SsaBias : RealVector(0 to BA4_TOPOLOGY_C.physicalColumns-1) :=
      (others => 80.0E-6);
   signal ba4ZeroColumns : RealVector(0 to BA4_TOPOLOGY_C.physicalColumns-1) :=
      (others => 0.0);
   signal ba4Rows : RealVector(0 to BA4_TOPOLOGY_C.rowsPerBank-1) :=
      (others => 0.0);
   signal ba4Banks : RealVector(0 to BA4_TOPOLOGY_C.numBanks-1) :=
      (others => 0.0);
   signal ba4Tes : RealVector(
      0 to BA4_TOPOLOGY_C.physicalColumns*BA4_ROWS_C-1) := (others => 0.0);
   signal ba4MuxCurrent : RealVector(0 to BA4_TOPOLOGY_C.physicalColumns-1);
   signal ba4MuxVoltage : RealVector(0 to BA4_TOPOLOGY_C.physicalColumns-1);
   signal ba4SsaPhase   : RealVector(0 to BA4_TOPOLOGY_C.physicalColumns-1);
   signal ba4SsaVoltage : RealVector(0 to BA4_TOPOLOGY_C.physicalColumns-1);

begin

   U_Bicep3 : entity warm_tdm.DetectorModuleSim
      generic map (
         NUM_COLUMNS_G   => BICEP3_TOPOLOGY_C.physicalColumns,
         NUM_BANKS_G     => BICEP3_TOPOLOGY_C.numBanks,
         ROWS_PER_BANK_G => BICEP3_TOPOLOGY_C.rowsPerBank,
         TWO_LEVEL_G     => BICEP3_TOPOLOGY_C.twoLevel)
      port map (
         ssaBiasCurrentAmp     => b3SsaBias,
         ssaFeedbackCurrentAmp => b3ZeroColumns,
         sq1BiasCurrentAmp     => b3ZeroColumns,
         sq1FeedbackCurrentAmp => b3ZeroColumns,
         rowSelectCurrentAmp   => b3Rows,
         chipSelectCurrentAmp  => b3Banks,
         tesCurrentAmp         => b3Tes,
         muxCurrentAmp         => b3MuxCurrent,
         muxVoltageVolt        => b3MuxVoltage,
         ssaPhaseCycles        => b3SsaPhase,
         ssaVoltageVolt        => b3SsaVoltage);

   U_Nist50r : entity warm_tdm.DetectorModuleSim
      generic map (
         NUM_COLUMNS_G   => NIST_50R_TOPOLOGY_C.physicalColumns,
         NUM_BANKS_G     => NIST_50R_TOPOLOGY_C.numBanks,
         ROWS_PER_BANK_G => NIST_50R_TOPOLOGY_C.rowsPerBank,
         TWO_LEVEL_G     => NIST_50R_TOPOLOGY_C.twoLevel)
      port map (
         ssaBiasCurrentAmp     => nistSsaBias,
         ssaFeedbackCurrentAmp => nistZeroColumns,
         sq1BiasCurrentAmp     => nistZeroColumns,
         sq1FeedbackCurrentAmp => nistZeroColumns,
         rowSelectCurrentAmp   => nistRows,
         chipSelectCurrentAmp  => nistBanks,
         tesCurrentAmp         => nistTes,
         muxCurrentAmp         => nistMuxCurrent,
         muxVoltageVolt        => nistMuxVoltage,
         ssaPhaseCycles        => nistSsaPhase,
         ssaVoltageVolt        => nistSsaVoltage);

   U_Ba4 : entity warm_tdm.DetectorModuleSim
      generic map (
         NUM_COLUMNS_G   => BA4_TOPOLOGY_C.physicalColumns,
         NUM_BANKS_G     => BA4_TOPOLOGY_C.numBanks,
         ROWS_PER_BANK_G => BA4_TOPOLOGY_C.rowsPerBank,
         TWO_LEVEL_G     => BA4_TOPOLOGY_C.twoLevel)
      port map (
         ssaBiasCurrentAmp     => ba4SsaBias,
         ssaFeedbackCurrentAmp => ba4ZeroColumns,
         sq1BiasCurrentAmp     => ba4ZeroColumns,
         sq1FeedbackCurrentAmp => ba4ZeroColumns,
         rowSelectCurrentAmp   => ba4Rows,
         chipSelectCurrentAmp  => ba4Banks,
         tesCurrentAmp         => ba4Tes,
         muxCurrentAmp         => ba4MuxCurrent,
         muxVoltageVolt        => ba4MuxVoltage,
         ssaPhaseCycles        => ba4SsaPhase,
         ssaVoltageVolt        => ba4SsaVoltage);

   test : process is
      variable selectedProfile : WaferProfileType;
   begin
      assert B3_ROWS_C = 22 and NIST_ROWS_C = 50 and BA4_ROWS_C = 60
         report "physical detector row-profile metadata is incorrect"
         severity failure;
      assert topologySelectLines(BICEP3_TOPOLOGY_C) = 22 and
             topologySelectLines(NIST_50R_TOPOLOGY_C) = 15 and
             topologySelectLines(BA4_TOPOLOGY_C) = 16
         report "physical detector select-line metadata is incorrect"
         severity failure;

      selectedProfile := waferProfile("BICEP3");
      assert topologyRows(selectedProfile.topology) = 22
         report "BICEP3 LOAD_G profile selection is incorrect"
         severity failure;
      selectedProfile := waferProfile("NIST_50R");
      assert topologyRows(selectedProfile.topology) = 50 and
             selectedProfile.topology.twoLevel
         report "NIST_50R LOAD_G profile selection is incorrect"
         severity failure;
      selectedProfile := waferProfile("BA4");
      assert topologyRows(selectedProfile.topology) = 60 and
             selectedProfile.topology.twoLevel
         report "BA4 LOAD_G profile selection is incorrect"
         severity failure;
      assert validLoadName("LOAD_BOARD") and validLoadName("WAFER") and
             not validLoadName("UNKNOWN")
         report "GroupTb load-name validation is incorrect"
         severity failure;

      wait for 1 ns;
      assert b3SsaVoltage(11) = b3SsaVoltage(11) and
             nistSsaVoltage(11) = nistSsaVoltage(11) and
             ba4SsaVoltage(11) = ba4SsaVoltage(11)
         report "a physical detector profile produced a non-finite SSA output"
         severity failure;

      report "DetectorProfileTb PASSED" severity note;
      stop;
      wait;
   end process test;

end architecture sim;
