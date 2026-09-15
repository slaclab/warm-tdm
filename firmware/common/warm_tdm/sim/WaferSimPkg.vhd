-------------------------------------------------------------------------------
-- Title      : Sensor Wafer Simulation Package
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : Simulation
-- Standard   : VHDL-2008
-------------------------------------------------------------------------------
-- Description:
-- Parameters and pure transfer functions for the TES/SQUID wafer model.
--
-- The default SQUID equation is the symmetric, overdamped, negligible-loop-
-- inductance result from The SQUID Handbook, Vol. I, Eq. (2.41).  The record
-- fields use effective whole-SQUID quantities:
--   criticalCurrentAmp         = 2 * per-junction I0
--   normalResistanceOhm        = per-junction R / 2
--   currentPerPhi0Amp          = applied-current period for one Phi0
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
use ieee.math_real.all;

package WaferSimPkg is

   type RealVector is array (natural range <>) of real;
   type IntegerVector is array (natural range <>) of integer;

   type DetectorTopologyType is record
      physicalColumns : positive;
      numBanks        : positive;
      rowsPerBank     : positive;
      twoLevel        : boolean;
   end record DetectorTopologyType;

   -- The physical dimensions are detector-module metadata.  A simulation may
   -- instantiate fewer columns while retaining the same row topology.
   constant BICEP3_TOPOLOGY_C : DetectorTopologyType := (
      physicalColumns => 12,
      numBanks        => 1,
      rowsPerBank     => 22,
      twoLevel        => false);

   -- Five ten-row banks are the current working interpretation of the NIST
   -- 50-row module; confirm this factorization against the mask schematic.
   constant NIST_50R_TOPOLOGY_C : DetectorTopologyType := (
      physicalColumns => 12,
      numBanks        => 5,
      rowsPerBank     => 10,
      twoLevel        => true);

   constant BA4_TOPOLOGY_C : DetectorTopologyType := (
      physicalColumns => 12,
      numBanks        => 6,
      rowsPerBank     => 10,
      twoLevel        => true);

   -- Warm-column endpoint order is board-major, with eight channels per
   -- board.  The third board carries columns 8..11 from each BA4 module.
   constant DUAL_BA4_WARM_DETECTOR_MAP_C : IntegerVector(0 to 23) := (
      0, 0, 0, 0, 0, 0, 0, 0,
      1, 1, 1, 1, 1, 1, 1, 1,
      0, 0, 0, 0, 1, 1, 1, 1);

   constant DUAL_BA4_WARM_COLUMN_MAP_C : IntegerVector(0 to 23) := (
      0, 1, 2, 3, 4, 5, 6, 7,
      0, 1, 2, 3, 4, 5, 6, 7,
      8, 9, 10, 11, 8, 9, 10, 11);

   -- Detector 0 uses physical select lines 0..15; detector 1 uses 16..31.
   constant DUAL_BA4_RS_LINE_MAP_C : IntegerVector(0 to 19) := (
      0, 1, 2, 3, 4, 5, 6, 7, 8, 9,
      16, 17, 18, 19, 20, 21, 22, 23, 24, 25);

   constant DUAL_BA4_CS_LINE_MAP_C : IntegerVector(0 to 11) := (
      10, 11, 12, 13, 14, 15,
      26, 27, 28, 29, 30, 31);

   type SquidParamsType is record
      criticalCurrentAmp      : real;
      normalResistanceOhm     : real;
      currentPerPhi0Amp       : real;
      phaseOffsetCycles       : real;
   end record SquidParamsType;

   type SsaParamsType is record
      squid                   : SquidParamsType;
      elementCount            : positive;
      inputPolarity           : integer range -1 to 1;
      feedbackPolarity        : integer range -1 to 1;
      inputCouplingScale      : real;
      feedbackCouplingScale   : real;
      outputOffsetVolt        : real;
      outputClampVolt         : real;
   end record SsaParamsType;

   type Sq1ParamsType is record
      squid                   : SquidParamsType;
      elementCount            : positive;
      tesPolarity             : integer range -1 to 1;
      feedbackPolarity        : integer range -1 to 1;
      tesCouplingScale        : real;
      feedbackCouplingScale   : real;
      seriesResistanceOhm     : real;
   end record Sq1ParamsType;

   type RowFasParamsType is record
      squid                   : SquidParamsType;
      elementCount            : positive;
      selectPolarity          : integer range -1 to 1;
      seriesResistanceOhm     : real;
   end record RowFasParamsType;

   type ChipFasParamsType is record
      squid                   : SquidParamsType;
      elementCount            : positive;
      selectPolarity          : integer range -1 to 1;
      seriesResistanceOhm     : real;
   end record ChipFasParamsType;

   type MuxColumnParamsType is record
      shuntResistanceOhm      : real;
      seriesResistanceOhm     : real;
      useExactNetworkSolver   : boolean;
      solverIterations        : positive;
   end record MuxColumnParamsType;

   type WaferProfileType is record
      topology    : DetectorTopologyType;
      ssa         : SsaParamsType;
      sq1         : Sq1ParamsType;
      rowFas      : RowFasParamsType;
      chipFas     : ChipFasParamsType;
      muxColumn   : MuxColumnParamsType;
   end record WaferProfileType;

   -- Resolved per-instance parameter arrays.  Leaf entities receive one element
   -- per physical device (per column, per pixel, or per bank) so a wafer can
   -- carry realistic device-to-device spread.  See the seeded builder functions
   -- below and docs/plans/sensor-wafer-model/README.md.
   type SsaParamsArray       is array (natural range <>) of SsaParamsType;
   type Sq1ParamsArray       is array (natural range <>) of Sq1ParamsType;
   type RowFasParamsArray    is array (natural range <>) of RowFasParamsType;
   type ChipFasParamsArray   is array (natural range <>) of ChipFasParamsType;
   type MuxColumnParamsArray is array (natural range <>) of MuxColumnParamsType;

   constant SSA_SQUID_SYNTHETIC_C : SquidParamsType := (
      criticalCurrentAmp  => 55.0E-6,
      -- Lumped whole-array value chosen to reproduce the measured 5--8 mV
      -- SA-feedback sweep; at the 55 uA onset bias it gives 6.6 mV peak to
      -- peak in the ideal low-inductance model.
      normalResistanceOhm => 120.0,
      currentPerPhi0Amp   => 35.0E-6,
      phaseOffsetCycles   => 0.0);

   constant SQ1_SQUID_SYNTHETIC_C : SquidParamsType := (
      criticalCurrentAmp  => 20.0E-6,
      normalResistanceOhm => 14.0,
      currentPerPhi0Amp   => 10.0E-6,
      phaseOffsetCycles   => 0.0);

   constant ROW_FAS_SQUID_SYNTHETIC_C : SquidParamsType := (
      criticalCurrentAmp  => 20.0E-6,
      normalResistanceOhm => 14.0,
      currentPerPhi0Amp   => 300.0E-6,
      phaseOffsetCycles   => 0.0);

   -- Synthetic and deliberately distinct from the row-FAS defaults.  Replace
   -- with calibrated values when the chip-select device data are available.
   constant CHIP_FAS_SQUID_SYNTHETIC_C : SquidParamsType := (
      criticalCurrentAmp  => 18.0E-6,
      normalResistanceOhm => 12.0,
      currentPerPhi0Amp   => 250.0E-6,
      phaseOffsetCycles   => 0.0);

   constant SSA_SYNTHETIC_C : SsaParamsType := (
      squid                 => SSA_SQUID_SYNTHETIC_C,
      elementCount          => 1,
      inputPolarity         => 1,
      feedbackPolarity      => -1,
      inputCouplingScale    => 1.0,
      feedbackCouplingScale => 1.0,
      outputOffsetVolt      => 0.0,
      outputClampVolt       => 1.0);

   constant SQ1_SYNTHETIC_C : Sq1ParamsType := (
      squid                 => SQ1_SQUID_SYNTHETIC_C,
      elementCount          => 1,
      tesPolarity           => 1,
      feedbackPolarity      => -1,
      tesCouplingScale      => 1.0,
      feedbackCouplingScale => 1.0,
      seriesResistanceOhm   => 1.0);

   constant ROW_FAS_SYNTHETIC_C : RowFasParamsType := (
      squid               => ROW_FAS_SQUID_SYNTHETIC_C,
      elementCount        => 1,
      selectPolarity      => 1,
      seriesResistanceOhm => 0.1);

   constant CHIP_FAS_SYNTHETIC_C : ChipFasParamsType := (
      squid               => CHIP_FAS_SQUID_SYNTHETIC_C,
      elementCount        => 1,
      selectPolarity      => 1,
      seriesResistanceOhm => 0.1);

   constant MUX_COLUMN_SYNTHETIC_C : MuxColumnParamsType := (
      shuntResistanceOhm    => 1.0,
      seriesResistanceOhm   => 0.0,
      useExactNetworkSolver => false,
      solverIterations      => 24);

   -- Per-device variation controls.  A nonzero seed makes the seeded builder
   -- functions perturb each device's nominal curve deterministically; seed 0
   -- returns the nominal unchanged (bit-for-bit the old identical-device model).
   -- The default seed is nonzero so a wafer model always carries realistic
   -- device-to-device spread.
   constant WAFER_VARIATION_SEED_C : natural := 1234567;
   -- Fractional +/- spread applied to critical current, normal resistance, and
   -- current-per-Phi0 (period).  Keep < 1.0 so perturbed values stay positive.
   constant DEVICE_SPREAD_C        : real    := 0.05;
   -- +/- spread (in flux quanta) applied to phaseOffsetCycles.  This is the knob
   -- that gives each pixel a different muxed baseline level and each channel a
   -- different tuning lock point.
   constant PHASE_SPREAD_CYCLES_C  : real    := 0.15;
   -- +/- per-pixel DC TES baseline current, summed into the pixel TES current.
   constant TES_BASELINE_AMP_C     : real    := 1.0E-6;

   constant WAFER_32_PROFILE_C : WaferProfileType := (
      topology  => (
         physicalColumns => 8,
         numBanks        => 1,
         rowsPerBank     => 32,
         twoLevel        => false),
      ssa       => SSA_SYNTHETIC_C,
      sq1       => SQ1_SYNTHETIC_C,
      rowFas    => ROW_FAS_SYNTHETIC_C,
      chipFas   => CHIP_FAS_SYNTHETIC_C,
      muxColumn => MUX_COLUMN_SYNTHETIC_C);

   constant BICEP3_PROFILE_C : WaferProfileType := (
      topology  => BICEP3_TOPOLOGY_C,
      ssa       => SSA_SYNTHETIC_C,
      sq1       => SQ1_SYNTHETIC_C,
      rowFas    => ROW_FAS_SYNTHETIC_C,
      chipFas   => CHIP_FAS_SYNTHETIC_C,
      muxColumn => MUX_COLUMN_SYNTHETIC_C);

   constant NIST_50R_PROFILE_C : WaferProfileType := (
      topology  => NIST_50R_TOPOLOGY_C,
      ssa       => SSA_SYNTHETIC_C,
      sq1       => SQ1_SYNTHETIC_C,
      rowFas    => ROW_FAS_SYNTHETIC_C,
      chipFas   => CHIP_FAS_SYNTHETIC_C,
      muxColumn => MUX_COLUMN_SYNTHETIC_C);

   constant BA4_PROFILE_C : WaferProfileType := (
      topology  => BA4_TOPOLOGY_C,
      ssa       => SSA_SYNTHETIC_C,
      sq1       => SQ1_SYNTHETIC_C,
      rowFas    => ROW_FAS_SYNTHETIC_C,
      chipFas   => CHIP_FAS_SYNTHETIC_C,
      muxColumn => MUX_COLUMN_SYNTHETIC_C);

   function topologyRows (topology : DetectorTopologyType) return positive;
   function topologySelectLines (topology : DetectorTopologyType) return positive;
   function validLoadName (loadName : string) return boolean;
   function waferProfile (loadName : string) return WaferProfileType;
   function sequentialWarmDetectorMap (
      numWarmColumns    : positive;
      numDetectors      : positive;
      columnsPerDetector : positive)
      return IntegerVector;
   function sequentialWarmColumnMap (
      numWarmColumns    : positive;
      numDetectors      : positive;
      columnsPerDetector : positive)
      return IntegerVector;
   function contiguousRsLineMap (
      numDetectors : positive;
      rowsPerBank  : positive;
      numBanks     : positive;
      twoLevel     : boolean)
      return IntegerVector;
   function contiguousCsLineMap (
      numDetectors : positive;
      rowsPerBank  : positive;
      numBanks     : positive;
      twoLevel     : boolean)
      return IntegerVector;
   function presetWarmDetectorMap (
      loadName          : string;
      numWarmColumns    : positive;
      numDetectors      : positive;
      columnsPerDetector : positive)
      return IntegerVector;
   function presetWarmColumnMap (
      loadName          : string;
      numWarmColumns    : positive;
      numDetectors      : positive;
      columnsPerDetector : positive)
      return IntegerVector;
   function presetRsLineMap (
      loadName     : string;
      numDetectors : positive;
      rowsPerBank  : positive;
      numBanks     : positive;
      twoLevel     : boolean)
      return IntegerVector;
   function presetCsLineMap (
      loadName     : string;
      numDetectors : positive;
      rowsPerBank  : positive;
      numBanks     : positive;
      twoLevel     : boolean)
      return IntegerVector;

   function validSquidParams (params : SquidParamsType) return boolean;
   function clampReal (value : real; lower : real; upper : real) return real;

   function squidPhaseCycles (
      params        : SquidParamsType;
      inputCurrent  : real;
      feedbackCurrent : real;
      inputPolarity : integer;
      feedbackPolarity : integer;
      inputScale    : real := 1.0;
      feedbackScale : real := 1.0)
      return real;

   function idealSquidCriticalCurrent (
      params      : SquidParamsType;
      phaseCycles : real)
      return real;

   function idealSquidVoltage (
      params      : SquidParamsType;
      biasCurrent : real;
      phaseCycles : real)
      return real;

   function idealSquidStaticResistance (
      params      : SquidParamsType;
      biasCurrent : real;
      phaseCycles : real)
      return real;

   function squidArrayVoltage (
      params       : SquidParamsType;
      elementCount : positive;
      biasCurrent  : real;
      phaseCycles  : real)
      return real;

   function ssaPhaseCycles (
      params        : SsaParamsType;
      inputCurrent  : real;
      feedbackCurrent : real)
      return real;

   function ssaVoltage (
      params          : SsaParamsType;
      biasCurrent     : real;
      inputCurrent    : real;
      feedbackCurrent : real)
      return real;

   function sq1PhaseCycles (
      params          : Sq1ParamsType;
      tesCurrent      : real;
      feedbackCurrent : real)
      return real;

   function sq1BranchVoltage (
      params          : Sq1ParamsType;
      biasCurrent     : real;
      tesCurrent      : real;
      feedbackCurrent : real)
      return real;

   function rowFasPhaseCycles (
      params        : RowFasParamsType;
      selectCurrent : real)
      return real;

   function rowFasBranchVoltage (
      params        : RowFasParamsType;
      biasCurrent   : real;
      selectCurrent : real)
      return real;

   function chipFasPhaseCycles (
      params        : ChipFasParamsType;
      selectCurrent : real)
      return real;

   function chipFasBranchVoltage (
      params        : ChipFasParamsType;
      biasCurrent   : real;
      selectCurrent : real)
      return real;

   -- Uniform (no-variation) arrays: every element is the nominal record.  Used
   -- by focused device tests and legacy wrappers so their analytic curves are
   -- unchanged, and as the leaf-entity generic defaults.
   function uniformSsaArray (
      nominal : SsaParamsType; count : positive) return SsaParamsArray;
   function uniformSq1Array (
      nominal : Sq1ParamsType; count : positive) return Sq1ParamsArray;
   function uniformRowFasArray (
      nominal : RowFasParamsType; count : positive) return RowFasParamsArray;
   function uniformChipFasArray (
      nominal : ChipFasParamsType; count : positive) return ChipFasParamsArray;

   -- Seeded per-instance variation builders.  seed = 0 returns the nominal
   -- unchanged; a nonzero seed applies deterministic fractional spread to the
   -- device curve and an additive phase-offset spread.  Each device type uses a
   -- distinct random sub-stream so the results are independent and repeatable.
   function resolveSsaParams (
      nominal     : SsaParamsType;
      count       : positive;
      seed        : natural;
      spread      : real := DEVICE_SPREAD_C;
      phaseSpread : real := PHASE_SPREAD_CYCLES_C)
      return SsaParamsArray;
   function resolveSq1Params (
      nominal     : Sq1ParamsType;
      count       : positive;
      seed        : natural;
      spread      : real := DEVICE_SPREAD_C;
      phaseSpread : real := PHASE_SPREAD_CYCLES_C)
      return Sq1ParamsArray;
   function resolveRowFasParams (
      nominal     : RowFasParamsType;
      count       : positive;
      seed        : natural;
      spread      : real := DEVICE_SPREAD_C;
      phaseSpread : real := PHASE_SPREAD_CYCLES_C)
      return RowFasParamsArray;
   function resolveChipFasParams (
      nominal     : ChipFasParamsType;
      count       : positive;
      seed        : natural;
      spread      : real := DEVICE_SPREAD_C;
      phaseSpread : real := PHASE_SPREAD_CYCLES_C)
      return ChipFasParamsArray;
   function resolveTesBaseline (
      count     : positive;
      seed      : natural;
      amplitude : real := TES_BASELINE_AMP_C)
      return RealVector;

end package WaferSimPkg;

package body WaferSimPkg is

   constant CURRENT_EPSILON_C : real := 1.0E-30;

   function topologyRows (topology : DetectorTopologyType) return positive is
   begin
      return topology.numBanks * topology.rowsPerBank;
   end function topologyRows;

   function topologySelectLines (topology : DetectorTopologyType) return positive is
   begin
      if topology.twoLevel then
         return topology.rowsPerBank + topology.numBanks;
      else
         return topology.rowsPerBank;
      end if;
   end function topologySelectLines;

   function validLoadName (loadName : string) return boolean is
   begin
      return loadName = "LOAD_BOARD" or
             loadName = "WAFER" or
             loadName = "WAFER_32" or
             loadName = "BICEP3" or
             loadName = "NIST_50R" or
             loadName = "BA4";
   end function validLoadName;

   function waferProfile (loadName : string) return WaferProfileType is
   begin
      if loadName = "BICEP3" then
         return BICEP3_PROFILE_C;
      elsif loadName = "NIST_50R" then
         return NIST_50R_PROFILE_C;
      elsif loadName = "BA4" then
         return BA4_PROFILE_C;
      else
         -- WAFER is retained as the legacy spelling for WAFER_32.  LOAD_BOARD
         -- also resolves here because GroupTb needs a harmless static record
         -- even when the wafer generate block is disabled.
         return WAFER_32_PROFILE_C;
      end if;
   end function waferProfile;

   function sequentialWarmDetectorMap (
      numWarmColumns     : positive;
      numDetectors       : positive;
      columnsPerDetector : positive)
      return IntegerVector is
      variable result : IntegerVector(0 to numWarmColumns-1) := (others => -1);
   begin
      for warmColumn in result'range loop
         if warmColumn < numDetectors*columnsPerDetector then
            result(warmColumn) := warmColumn / columnsPerDetector;
         end if;
      end loop;
      return result;
   end function sequentialWarmDetectorMap;

   function sequentialWarmColumnMap (
      numWarmColumns     : positive;
      numDetectors       : positive;
      columnsPerDetector : positive)
      return IntegerVector is
      variable result : IntegerVector(0 to numWarmColumns-1) := (others => -1);
   begin
      for warmColumn in result'range loop
         if warmColumn < numDetectors*columnsPerDetector then
            result(warmColumn) := warmColumn mod columnsPerDetector;
         end if;
      end loop;
      return result;
   end function sequentialWarmColumnMap;

   function contiguousRsLineMap (
      numDetectors : positive;
      rowsPerBank  : positive;
      numBanks     : positive;
      twoLevel     : boolean)
      return IntegerVector is
      variable result : IntegerVector(0 to numDetectors*rowsPerBank-1);
      variable stride : positive := rowsPerBank;
   begin
      if twoLevel then
         stride := rowsPerBank + numBanks;
      end if;
      for detector in 0 to numDetectors-1 loop
         for rowSelect in 0 to rowsPerBank-1 loop
            result(detector*rowsPerBank + rowSelect) :=
               detector*stride + rowSelect;
         end loop;
      end loop;
      return result;
   end function contiguousRsLineMap;

   function contiguousCsLineMap (
      numDetectors : positive;
      rowsPerBank  : positive;
      numBanks     : positive;
      twoLevel     : boolean)
      return IntegerVector is
      variable result : IntegerVector(0 to numDetectors*numBanks-1) :=
         (others => -1);
      variable stride : positive := rowsPerBank;
   begin
      if twoLevel then
         stride := rowsPerBank + numBanks;
         for detector in 0 to numDetectors-1 loop
            for bank in 0 to numBanks-1 loop
               result(detector*numBanks + bank) :=
                  detector*stride + rowsPerBank + bank;
            end loop;
         end loop;
      end if;
      return result;
   end function contiguousCsLineMap;

   function presetWarmDetectorMap (
      loadName           : string;
      numWarmColumns     : positive;
      numDetectors       : positive;
      columnsPerDetector : positive)
      return IntegerVector is
   begin
      if loadName = "BA4" and numWarmColumns = 24 and
         numDetectors = 2 and columnsPerDetector = 12 then
         return DUAL_BA4_WARM_DETECTOR_MAP_C;
      else
         return sequentialWarmDetectorMap(
            numWarmColumns, numDetectors, columnsPerDetector);
      end if;
   end function presetWarmDetectorMap;

   function presetWarmColumnMap (
      loadName           : string;
      numWarmColumns     : positive;
      numDetectors       : positive;
      columnsPerDetector : positive)
      return IntegerVector is
   begin
      if loadName = "BA4" and numWarmColumns = 24 and
         numDetectors = 2 and columnsPerDetector = 12 then
         return DUAL_BA4_WARM_COLUMN_MAP_C;
      else
         return sequentialWarmColumnMap(
            numWarmColumns, numDetectors, columnsPerDetector);
      end if;
   end function presetWarmColumnMap;

   function presetRsLineMap (
      loadName     : string;
      numDetectors : positive;
      rowsPerBank  : positive;
      numBanks     : positive;
      twoLevel     : boolean)
      return IntegerVector is
   begin
      if loadName = "BA4" and numDetectors = 2 and rowsPerBank = 10 and
         numBanks = 6 and twoLevel then
         return DUAL_BA4_RS_LINE_MAP_C;
      else
         return contiguousRsLineMap(
            numDetectors, rowsPerBank, numBanks, twoLevel);
      end if;
   end function presetRsLineMap;

   function presetCsLineMap (
      loadName     : string;
      numDetectors : positive;
      rowsPerBank  : positive;
      numBanks     : positive;
      twoLevel     : boolean)
      return IntegerVector is
   begin
      if loadName = "BA4" and numDetectors = 2 and rowsPerBank = 10 and
         numBanks = 6 and twoLevel then
         return DUAL_BA4_CS_LINE_MAP_C;
      else
         return contiguousCsLineMap(
            numDetectors, rowsPerBank, numBanks, twoLevel);
      end if;
   end function presetCsLineMap;

   function validSquidParams (params : SquidParamsType) return boolean is
   begin
      return params.criticalCurrentAmp > 0.0 and
             params.normalResistanceOhm > 0.0 and
             params.currentPerPhi0Amp > 0.0;
   end function validSquidParams;

   function clampReal (value : real; lower : real; upper : real) return real is
   begin
      if value < lower then
         return lower;
      elsif value > upper then
         return upper;
      else
         return value;
      end if;
   end function clampReal;

   function squidPhaseCycles (
      params           : SquidParamsType;
      inputCurrent     : real;
      feedbackCurrent  : real;
      inputPolarity    : integer;
      feedbackPolarity : integer;
      inputScale       : real := 1.0;
      feedbackScale    : real := 1.0)
      return real is
   begin
      return params.phaseOffsetCycles +
             (real(inputPolarity) * inputScale * inputCurrent +
              real(feedbackPolarity) * feedbackScale * feedbackCurrent) /
             params.currentPerPhi0Amp;
   end function squidPhaseCycles;

   function idealSquidCriticalCurrent (
      params      : SquidParamsType;
      phaseCycles : real)
      return real is
   begin
      return params.criticalCurrentAmp * abs(cos(MATH_PI * phaseCycles));
   end function idealSquidCriticalCurrent;

   function idealSquidVoltage (
      params      : SquidParamsType;
      biasCurrent : real;
      phaseCycles : real)
      return real is
      variable criticalCurrent : real;
      variable radicand        : real;
      variable magnitude       : real;
   begin
      criticalCurrent := idealSquidCriticalCurrent(params, phaseCycles);
      magnitude       := abs(biasCurrent);

      if magnitude <= criticalCurrent then
         return 0.0;
      end if;

      radicand := magnitude*magnitude - criticalCurrent*criticalCurrent;
      if biasCurrent < 0.0 then
         return -params.normalResistanceOhm * sqrt(radicand);
      else
         return params.normalResistanceOhm * sqrt(radicand);
      end if;
   end function idealSquidVoltage;

   function idealSquidStaticResistance (
      params      : SquidParamsType;
      biasCurrent : real;
      phaseCycles : real)
      return real is
   begin
      if abs(biasCurrent) <= CURRENT_EPSILON_C then
         return 0.0;
      else
         return abs(idealSquidVoltage(params, biasCurrent, phaseCycles) /
                    biasCurrent);
      end if;
   end function idealSquidStaticResistance;

   function squidArrayVoltage (
      params       : SquidParamsType;
      elementCount : positive;
      biasCurrent  : real;
      phaseCycles  : real)
      return real is
   begin
      return real(elementCount) *
             idealSquidVoltage(params, biasCurrent, phaseCycles);
   end function squidArrayVoltage;

   function ssaPhaseCycles (
      params          : SsaParamsType;
      inputCurrent    : real;
      feedbackCurrent : real)
      return real is
   begin
      return squidPhaseCycles(
         params.squid,
         inputCurrent,
         feedbackCurrent,
         params.inputPolarity,
         params.feedbackPolarity,
         params.inputCouplingScale,
         params.feedbackCouplingScale);
   end function ssaPhaseCycles;

   function ssaVoltage (
      params          : SsaParamsType;
      biasCurrent     : real;
      inputCurrent    : real;
      feedbackCurrent : real)
      return real is
      variable voltage : real;
   begin
      voltage := params.outputOffsetVolt + squidArrayVoltage(
         params.squid,
         params.elementCount,
         biasCurrent,
         ssaPhaseCycles(params, inputCurrent, feedbackCurrent));

      return clampReal(
         voltage,
         -params.outputClampVolt,
         params.outputClampVolt);
   end function ssaVoltage;

   function sq1PhaseCycles (
      params          : Sq1ParamsType;
      tesCurrent      : real;
      feedbackCurrent : real)
      return real is
   begin
      return squidPhaseCycles(
         params.squid,
         tesCurrent,
         feedbackCurrent,
         params.tesPolarity,
         params.feedbackPolarity,
         params.tesCouplingScale,
         params.feedbackCouplingScale);
   end function sq1PhaseCycles;

   function sq1BranchVoltage (
      params          : Sq1ParamsType;
      biasCurrent     : real;
      tesCurrent      : real;
      feedbackCurrent : real)
      return real is
   begin
      return squidArrayVoltage(
                params.squid,
                params.elementCount,
                biasCurrent,
                sq1PhaseCycles(params, tesCurrent, feedbackCurrent)) +
             biasCurrent * params.seriesResistanceOhm;
   end function sq1BranchVoltage;

   function rowFasPhaseCycles (
      params        : RowFasParamsType;
      selectCurrent : real)
      return real is
   begin
      return params.squid.phaseOffsetCycles +
             real(params.selectPolarity) * selectCurrent /
             params.squid.currentPerPhi0Amp;
   end function rowFasPhaseCycles;

   function rowFasBranchVoltage (
      params        : RowFasParamsType;
      biasCurrent   : real;
      selectCurrent : real)
      return real is
   begin
      return squidArrayVoltage(
                params.squid,
                params.elementCount,
                biasCurrent,
                rowFasPhaseCycles(params, selectCurrent)) +
             biasCurrent * params.seriesResistanceOhm;
   end function rowFasBranchVoltage;

   function chipFasPhaseCycles (
      params        : ChipFasParamsType;
      selectCurrent : real)
      return real is
   begin
      return params.squid.phaseOffsetCycles +
             real(params.selectPolarity) * selectCurrent /
             params.squid.currentPerPhi0Amp;
   end function chipFasPhaseCycles;

   function chipFasBranchVoltage (
      params        : ChipFasParamsType;
      biasCurrent   : real;
      selectCurrent : real)
      return real is
   begin
      return squidArrayVoltage(
                params.squid,
                params.elementCount,
                biasCurrent,
                chipFasPhaseCycles(params, selectCurrent)) +
             biasCurrent * params.seriesResistanceOhm;
   end function chipFasBranchVoltage;

   -- Distinct random sub-stream salts so device types decorrelate.
   constant SSA_SALT_C      : natural := 1;
   constant SQ1_SALT_C      : natural := 2;
   constant ROW_FAS_SALT_C  : natural := 3;
   constant CHIP_FAS_SALT_C : natural := 4;
   constant TES_SALT_C      : natural := 5;

   -- ieee.math_real.uniform requires seed1 in 1..2147483562 and seed2 in
   -- 1..2147483398.  Derive a repeatable pair from the base seed and a salt.
   procedure initSeeds (
      seed : natural;
      salt : natural;
      variable seed1 : out positive;
      variable seed2 : out positive) is
      variable v1 : natural;
      variable v2 : natural;
   begin
      v1 := ((seed mod 2147483000) + salt*7919 + 1) mod 2147483562;
      v2 := ((seed mod 2147483000) + salt*104729 + 12345) mod 2147483398;
      if v1 < 1 then
         v1 := 1;
      end if;
      if v2 < 1 then
         v2 := 1;
      end if;
      seed1 := v1;
      seed2 := v2;
   end procedure initSeeds;

   -- Perturb the whole-SQUID curve fields in place from the running stream.
   procedure perturbSquid (
      variable params : inout SquidParamsType;
      variable seed1  : inout positive;
      variable seed2  : inout positive;
      spread          : real;
      phaseSpread     : real) is
      variable u : real;
   begin
      uniform(seed1, seed2, u);
      params.criticalCurrentAmp :=
         params.criticalCurrentAmp * (1.0 + spread*(2.0*u - 1.0));
      uniform(seed1, seed2, u);
      params.normalResistanceOhm :=
         params.normalResistanceOhm * (1.0 + spread*(2.0*u - 1.0));
      uniform(seed1, seed2, u);
      params.currentPerPhi0Amp :=
         params.currentPerPhi0Amp * (1.0 + spread*(2.0*u - 1.0));
      uniform(seed1, seed2, u);
      params.phaseOffsetCycles :=
         params.phaseOffsetCycles + phaseSpread*(2.0*u - 1.0);
   end procedure perturbSquid;

   function uniformSsaArray (
      nominal : SsaParamsType; count : positive) return SsaParamsArray is
      variable result : SsaParamsArray(0 to count-1) := (others => nominal);
   begin
      return result;
   end function uniformSsaArray;

   function uniformSq1Array (
      nominal : Sq1ParamsType; count : positive) return Sq1ParamsArray is
      variable result : Sq1ParamsArray(0 to count-1) := (others => nominal);
   begin
      return result;
   end function uniformSq1Array;

   function uniformRowFasArray (
      nominal : RowFasParamsType; count : positive) return RowFasParamsArray is
      variable result : RowFasParamsArray(0 to count-1) := (others => nominal);
   begin
      return result;
   end function uniformRowFasArray;

   function uniformChipFasArray (
      nominal : ChipFasParamsType; count : positive) return ChipFasParamsArray is
      variable result : ChipFasParamsArray(0 to count-1) := (others => nominal);
   begin
      return result;
   end function uniformChipFasArray;

   function resolveSsaParams (
      nominal     : SsaParamsType;
      count       : positive;
      seed        : natural;
      spread      : real := DEVICE_SPREAD_C;
      phaseSpread : real := PHASE_SPREAD_CYCLES_C)
      return SsaParamsArray is
      variable result : SsaParamsArray(0 to count-1) := (others => nominal);
      variable seed1  : positive;
      variable seed2  : positive;
      variable squid  : SquidParamsType;
   begin
      if seed = 0 then
         return result;
      end if;
      initSeeds(seed, SSA_SALT_C, seed1, seed2);
      for i in result'range loop
         squid := nominal.squid;
         perturbSquid(squid, seed1, seed2, spread, phaseSpread);
         result(i).squid := squid;
      end loop;
      return result;
   end function resolveSsaParams;

   function resolveSq1Params (
      nominal     : Sq1ParamsType;
      count       : positive;
      seed        : natural;
      spread      : real := DEVICE_SPREAD_C;
      phaseSpread : real := PHASE_SPREAD_CYCLES_C)
      return Sq1ParamsArray is
      variable result : Sq1ParamsArray(0 to count-1) := (others => nominal);
      variable seed1  : positive;
      variable seed2  : positive;
      variable squid  : SquidParamsType;
   begin
      if seed = 0 then
         return result;
      end if;
      initSeeds(seed, SQ1_SALT_C, seed1, seed2);
      for i in result'range loop
         squid := nominal.squid;
         perturbSquid(squid, seed1, seed2, spread, phaseSpread);
         result(i).squid := squid;
      end loop;
      return result;
   end function resolveSq1Params;

   function resolveRowFasParams (
      nominal     : RowFasParamsType;
      count       : positive;
      seed        : natural;
      spread      : real := DEVICE_SPREAD_C;
      phaseSpread : real := PHASE_SPREAD_CYCLES_C)
      return RowFasParamsArray is
      variable result : RowFasParamsArray(0 to count-1) := (others => nominal);
      variable seed1  : positive;
      variable seed2  : positive;
      variable squid  : SquidParamsType;
   begin
      if seed = 0 then
         return result;
      end if;
      initSeeds(seed, ROW_FAS_SALT_C, seed1, seed2);
      for i in result'range loop
         squid := nominal.squid;
         perturbSquid(squid, seed1, seed2, spread, phaseSpread);
         result(i).squid := squid;
      end loop;
      return result;
   end function resolveRowFasParams;

   function resolveChipFasParams (
      nominal     : ChipFasParamsType;
      count       : positive;
      seed        : natural;
      spread      : real := DEVICE_SPREAD_C;
      phaseSpread : real := PHASE_SPREAD_CYCLES_C)
      return ChipFasParamsArray is
      variable result : ChipFasParamsArray(0 to count-1) := (others => nominal);
      variable seed1  : positive;
      variable seed2  : positive;
      variable squid  : SquidParamsType;
   begin
      if seed = 0 then
         return result;
      end if;
      initSeeds(seed, CHIP_FAS_SALT_C, seed1, seed2);
      for i in result'range loop
         squid := nominal.squid;
         perturbSquid(squid, seed1, seed2, spread, phaseSpread);
         result(i).squid := squid;
      end loop;
      return result;
   end function resolveChipFasParams;

   function resolveTesBaseline (
      count     : positive;
      seed      : natural;
      amplitude : real := TES_BASELINE_AMP_C)
      return RealVector is
      variable result : RealVector(0 to count-1) := (others => 0.0);
      variable seed1  : positive;
      variable seed2  : positive;
      variable u      : real;
   begin
      if seed = 0 then
         return result;
      end if;
      initSeeds(seed, TES_SALT_C, seed1, seed2);
      for i in result'range loop
         uniform(seed1, seed2, u);
         result(i) := amplitude*(2.0*u - 1.0);
      end loop;
      return result;
   end function resolveTesBaseline;

end package body WaferSimPkg;
