-------------------------------------------------------------------------------
-- Title      : Per-Device Variation Testbench
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : Simulation
-- Standard   : VHDL-2008
-------------------------------------------------------------------------------
-- Description:
-- Proves the seeded per-instance variation builders and their effect on the
-- observable model:
--   * seed 0 returns the nominal unchanged (identical devices);
--   * a nonzero seed makes each column's SSA and each pixel's SQ1 differ, so
--     tunings vary channel-to-channel and every muxed row sits at a different
--     baseline level;
--   * results are deterministic for a given seed.
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

entity DetectorVariationTb is
end entity DetectorVariationTb;

architecture sim of DetectorVariationTb is
   constant NUM_COLUMNS_C   : positive := 4;
   constant NUM_BANKS_C     : positive := 1;
   constant ROWS_PER_BANK_C : positive := 4;
   constant NUM_ROWS_C      : positive := NUM_BANKS_C*ROWS_PER_BANK_C;
   constant NUM_PIXELS_C    : positive := NUM_COLUMNS_C*NUM_ROWS_C;
   constant SEED_C          : natural  := 777;

   signal ssaBias    : RealVector(0 to NUM_COLUMNS_C-1) := (others => 80.0E-6);
   signal ssaFb      : RealVector(0 to NUM_COLUMNS_C-1) := (others => 0.0);
   signal sq1Bias    : RealVector(0 to NUM_COLUMNS_C-1) := (others => 30.0E-6);
   signal sq1Fb      : RealVector(0 to NUM_COLUMNS_C-1) := (others => 0.0);
   signal rowSelect  : RealVector(0 to ROWS_PER_BANK_C-1) := (others => 0.0);
   signal chipSelect : RealVector(0 to NUM_BANKS_C-1) := (others => 0.0);
   signal tesCurrent : RealVector(0 to NUM_PIXELS_C-1) := (others => 0.0);

   signal flatMuxCurrent   : RealVector(0 to NUM_COLUMNS_C-1);
   signal flatSsaPhase     : RealVector(0 to NUM_COLUMNS_C-1);
   signal flatSsaVoltage   : RealVector(0 to NUM_COLUMNS_C-1);
   signal variedMuxCurrent : RealVector(0 to NUM_COLUMNS_C-1);
   signal variedSsaPhase   : RealVector(0 to NUM_COLUMNS_C-1);
   signal variedSsaVoltage : RealVector(0 to NUM_COLUMNS_C-1);
begin

   -- Identical devices (default uniform arrays).
   U_Flat : entity warm_tdm.DetectorModuleSim
      generic map (
         NUM_COLUMNS_G   => NUM_COLUMNS_C,
         NUM_BANKS_G     => NUM_BANKS_C,
         ROWS_PER_BANK_G => ROWS_PER_BANK_C,
         TWO_LEVEL_G     => false)
      port map (
         ssaBiasCurrentAmp     => ssaBias,
         ssaFeedbackCurrentAmp => ssaFb,
         sq1BiasCurrentAmp     => sq1Bias,
         sq1FeedbackCurrentAmp => sq1Fb,
         rowSelectCurrentAmp   => rowSelect,
         chipSelectCurrentAmp  => chipSelect,
         tesCurrentAmp         => tesCurrent,
         muxCurrentAmp         => flatMuxCurrent,
         muxVoltageVolt        => open,
         ssaBiasLoadCurrentAmp => open,
         ssaPhaseCycles        => flatSsaPhase,
         ssaVoltageVolt        => flatSsaVoltage);

   -- Seeded per-instance variation.
   U_Varied : entity warm_tdm.DetectorModuleSim
      generic map (
         NUM_COLUMNS_G     => NUM_COLUMNS_C,
         NUM_BANKS_G       => NUM_BANKS_C,
         ROWS_PER_BANK_G   => ROWS_PER_BANK_C,
         TWO_LEVEL_G       => false,
         SSA_PARAMS_G      => resolveSsaParams(
            SSA_SYNTHETIC_C, NUM_COLUMNS_C, SEED_C),
         SQ1_PARAMS_G      => resolveSq1Params(
            SQ1_SYNTHETIC_C, NUM_PIXELS_C, SEED_C),
         ROW_FAS_PARAMS_G  => resolveRowFasParams(
            ROW_FAS_SYNTHETIC_C, NUM_PIXELS_C, SEED_C))
      port map (
         ssaBiasCurrentAmp     => ssaBias,
         ssaFeedbackCurrentAmp => ssaFb,
         sq1BiasCurrentAmp     => sq1Bias,
         sq1FeedbackCurrentAmp => sq1Fb,
         rowSelectCurrentAmp   => rowSelect,
         chipSelectCurrentAmp  => chipSelect,
         tesCurrentAmp         => tesCurrent,
         muxCurrentAmp         => variedMuxCurrent,
         muxVoltageVolt        => open,
         ssaBiasLoadCurrentAmp => open,
         ssaPhaseCycles        => variedSsaPhase,
         ssaVoltageVolt        => variedSsaVoltage);

   test : process is
      variable ssaZero    : SsaParamsArray(0 to NUM_COLUMNS_C-1);
      variable ssaA       : SsaParamsArray(0 to NUM_COLUMNS_C-1);
      variable ssaB       : SsaParamsArray(0 to NUM_COLUMNS_C-1);
      variable sq1Seeded  : Sq1ParamsArray(0 to NUM_PIXELS_C-1);
      variable rowNom     : RowFasParamsArray(0 to 0);
      variable tesZero    : RealVector(0 to NUM_PIXELS_C-1);
      variable tesSeeded  : RealVector(0 to NUM_PIXELS_C-1);
      variable distinctPhases : boolean;
      variable nonzeroBaseline : boolean;
   begin
      -- Activate a row so a mux current flows into each SSA.  The half-flux
      -- select current is read from a resolved (seed-0) row-FAS record to avoid
      -- selecting a package record-constant field directly.
      rowNom := resolveRowFasParams(ROW_FAS_SYNTHETIC_C, 1, 0);
      rowSelect(0) <= 0.5 * rowNom(0).squid.currentPerPhi0Amp;
      wait for 1 ns;

      ----------------------------------------------------------------------
      -- 1. Builder flatness: seed 0 gives identical devices.
      ----------------------------------------------------------------------
      ssaZero := resolveSsaParams(SSA_SYNTHETIC_C, NUM_COLUMNS_C, 0);
      for c in ssaZero'range loop
         assert ssaZero(c).squid.criticalCurrentAmp =
                   ssaZero(0).squid.criticalCurrentAmp and
                ssaZero(c).squid.phaseOffsetCycles =
                   ssaZero(0).squid.phaseOffsetCycles
            report "seed 0 must give identical (unvaried) devices"
            severity failure;
      end loop;
      tesZero := resolveTesBaseline(NUM_PIXELS_C, 0);
      for p in tesZero'range loop
         assert tesZero(p) = 0.0
            report "seed 0 must give a zero TES baseline"
            severity failure;
      end loop;

      ----------------------------------------------------------------------
      -- 2. Determinism: same seed reproduces the same arrays.
      ----------------------------------------------------------------------
      ssaA := resolveSsaParams(SSA_SYNTHETIC_C, NUM_COLUMNS_C, SEED_C);
      ssaB := resolveSsaParams(SSA_SYNTHETIC_C, NUM_COLUMNS_C, SEED_C);
      for c in ssaA'range loop
         assert ssaA(c).squid.criticalCurrentAmp =
                   ssaB(c).squid.criticalCurrentAmp and
                ssaA(c).squid.currentPerPhi0Amp =
                   ssaB(c).squid.currentPerPhi0Amp and
                ssaA(c).squid.phaseOffsetCycles =
                   ssaB(c).squid.phaseOffsetCycles
            report "seeded builder is not deterministic"
            severity failure;
      end loop;

      ----------------------------------------------------------------------
      -- 3. Per-pixel SQ1 spread: distinct phase offsets -> each muxed row
      --    sits at a different baseline level.
      ----------------------------------------------------------------------
      sq1Seeded := resolveSq1Params(SQ1_SYNTHETIC_C, NUM_PIXELS_C, SEED_C);
      distinctPhases := false;
      for p in 1 to NUM_PIXELS_C-1 loop
         if abs(sq1Seeded(p).squid.phaseOffsetCycles -
                sq1Seeded(0).squid.phaseOffsetCycles) > 1.0E-9 then
            distinctPhases := true;
         end if;
      end loop;
      assert distinctPhases
         report "seeded SQ1 pixels must have distinct phase offsets"
         severity failure;

      tesSeeded := resolveTesBaseline(NUM_PIXELS_C, SEED_C);
      nonzeroBaseline := false;
      for p in tesSeeded'range loop
         assert abs(tesSeeded(p)) <= TES_BASELINE_AMP_C + 1.0E-15
            report "TES baseline exceeded its configured amplitude"
            severity failure;
         if abs(tesSeeded(p)) > 0.0 then
            nonzeroBaseline := true;
         end if;
      end loop;
      assert nonzeroBaseline
         report "seeded TES baseline must be nonzero"
         severity failure;

      ----------------------------------------------------------------------
      -- 4. Observable model: identical devices read identically, varied
      --    devices differ column-to-column and versus the flat model.
      ----------------------------------------------------------------------
      for c in 1 to NUM_COLUMNS_C-1 loop
         assert abs(flatSsaPhase(c) - flatSsaPhase(0)) < 1.0E-12
            report "identical-device columns must share one SSA phase"
            severity failure;
      end loop;

      distinctPhases := false;
      for c in 1 to NUM_COLUMNS_C-1 loop
         if abs(variedSsaPhase(c) - variedSsaPhase(0)) > 1.0E-9 then
            distinctPhases := true;
         end if;
      end loop;
      assert distinctPhases
         report "varied columns must show different SSA tunings"
         severity failure;

      assert abs(variedSsaVoltage(0) - flatSsaVoltage(0)) > 0.0 or
             abs(variedSsaVoltage(1) - flatSsaVoltage(1)) > 0.0 or
             abs(variedSsaVoltage(2) - flatSsaVoltage(2)) > 0.0 or
             abs(variedSsaVoltage(3) - flatSsaVoltage(3)) > 0.0
         report "device variation did not change any observable SSA output"
         severity failure;

      report "DetectorVariationTb PASSED" severity note;
      stop;
      wait;
   end process test;

end architecture sim;
