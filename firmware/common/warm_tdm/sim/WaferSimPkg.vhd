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

   constant SSA_SQUID_SYNTHETIC_C : SquidParamsType := (
      criticalCurrentAmp  => 55.0E-6,
      normalResistanceOhm => 14.0,
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

end package body WaferSimPkg;
