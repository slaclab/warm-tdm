-------------------------------------------------------------------------------
-- Title      : Sensor Wafer Model Self-Checking Testbench
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

library ieee;
use ieee.std_logic_1164.all;
use std.env.all;

library warm_tdm;
use warm_tdm.WaferSimPkg.all;

entity WaferModelTb is
end entity WaferModelTb;

architecture sim of WaferModelTb is

   constant SSA_CORE_C : SquidParamsType := (
      criticalCurrentAmp  => 40.0E-6,
      normalResistanceOhm => 8.0,
      currentPerPhi0Amp   => 20.0E-6,
      phaseOffsetCycles   => 0.0);

   constant SQ1_CORE_C : SquidParamsType := (
      criticalCurrentAmp  => 10.0E-6,
      normalResistanceOhm => 4.0,
      currentPerPhi0Amp   => 8.0E-6,
      phaseOffsetCycles   => 0.0);

   constant ROW_FAS_CORE_C : SquidParamsType := (
      criticalCurrentAmp  => 12.0E-6,
      normalResistanceOhm => 6.0,
      currentPerPhi0Amp   => 100.0E-6,
      phaseOffsetCycles   => 0.0);

   constant CHIP_FAS_CORE_C : SquidParamsType := (
      criticalCurrentAmp  => 14.0E-6,
      normalResistanceOhm => 10.0,
      currentPerPhi0Amp   => 200.0E-6,
      phaseOffsetCycles   => 0.0);

   constant SSA_PARAMS_C : SsaParamsType := (
      squid                 => SSA_CORE_C,
      elementCount          => 1,
      inputPolarity         => 1,
      feedbackPolarity      => -1,
      inputCouplingScale    => 1.0,
      feedbackCouplingScale => 1.0,
      outputOffsetVolt      => 0.0,
      outputClampVolt       => 1.0);

   constant SQ1_PARAMS_C : Sq1ParamsType := (
      squid                 => SQ1_CORE_C,
      elementCount          => 1,
      tesPolarity           => 1,
      feedbackPolarity      => -1,
      tesCouplingScale      => 1.0,
      feedbackCouplingScale => 1.0,
      seriesResistanceOhm   => 0.8);

   constant ROW_FAS_PARAMS_C : RowFasParamsType := (
      squid               => ROW_FAS_CORE_C,
      elementCount        => 1,
      selectPolarity      => 1,
      seriesResistanceOhm => 0.1);

   constant CHIP_FAS_PARAMS_C : ChipFasParamsType := (
      squid               => CHIP_FAS_CORE_C,
      elementCount        => 1,
      selectPolarity      => 1,
      seriesResistanceOhm => 0.2);

   constant COLUMN_PARAMS_C : MuxColumnParamsType := (
      shuntResistanceOhm    => 1.0,
      seriesResistanceOhm   => 0.05,
      useExactNetworkSolver => true,
      solverIterations      => 40);

   constant FAST_COLUMN_PARAMS_C : MuxColumnParamsType := (
      shuntResistanceOhm    => COLUMN_PARAMS_C.shuntResistanceOhm,
      seriesResistanceOhm   => COLUMN_PARAMS_C.seriesResistanceOhm,
      useExactNetworkSolver => false,
      solverIterations      => COLUMN_PARAMS_C.solverIterations);

   signal squidBias      : real := 0.0;
   signal squidInput     : real := 0.0;
   signal squidFeedback  : real := 0.0;
   signal squidPhase     : real;
   signal squidCritical  : real;
   signal squidResistance : real;
   signal squidVoltage   : real;

   signal ssaBias       : real := 0.0;
   signal ssaInput      : real := 0.0;
   signal ssaFeedback   : real := 0.0;
   signal ssaPhase      : real;
   signal ssaOut        : real;

   signal syntheticSsaBias     : real := 55.0E-6;
   signal syntheticSsaFeedback : real := 0.0;
   signal syntheticSsaPhase    : real;
   signal syntheticSsaOut      : real;

   signal sq1Bias       : real := 0.0;
   signal tesInput      : real := 0.0;
   signal sq1Feedback   : real := 0.0;
   signal sq1Phase      : real;
   signal sq1Out        : real;

   signal rowFasBias    : real := 0.0;
   signal rowSelect     : real := 0.0;
   signal rowFasPhase   : real;
   signal rowFasResistance : real;
   signal rowFasOut     : real;

   signal chipFasBias   : real := 0.0;
   signal chipSelect    : real := 0.0;
   signal chipFasPhase  : real;
   signal chipFasResistance : real;
   signal chipFasOut    : real;

   signal detectorSsaBias     : RealVector(0 to 1) := (others => 60.0E-6);
   signal detectorSsaSourceR  : RealVector(0 to 1) := (others => 0.0);
   signal detectorSsaFb       : RealVector(0 to 1) := (others => 0.0);
   signal detectorSq1Bias     : RealVector(0 to 1) := (others => 10.0E-6);
   signal detectorSq1SourceR  : RealVector(0 to 1) := (others => 0.0);
   signal detectorSq1Fb       : RealVector(0 to 1) := (others => 0.0);
   signal detectorRowSelect   : RealVector(0 to 1) := (others => 0.0);
   signal detectorChipSelect  : RealVector(0 to 1) := (others => 0.0);
   signal detectorTes         : RealVector(0 to 7) := (others => 0.0);
   signal detectorMuxCurrent  : RealVector(0 to 1);
   signal detectorMuxVoltage  : RealVector(0 to 1);
   signal detectorSsaPhase    : RealVector(0 to 1);
   signal detectorSsaVoltage  : RealVector(0 to 1);
   signal fastMuxCurrent       : RealVector(0 to 1);
   signal fastMuxVoltage       : RealVector(0 to 1);
   signal fastSsaPhase         : RealVector(0 to 1);
   signal fastSsaVoltage       : RealVector(0 to 1);

   procedure assertClose (
      actual    : real;
      expected  : real;
      tolerance : real;
      message   : string) is
   begin
      assert abs(actual - expected) <= tolerance
         report message & ": actual=" & real'image(actual) &
                ", expected=" & real'image(expected)
         severity failure;
   end procedure assertClose;

begin

   U_Squid : entity warm_tdm.SquidModel
      generic map (PARAMS_G => SQ1_CORE_C)
      port map (
         biasCurrentAmp      => squidBias,
         inputCurrentAmp     => squidInput,
         feedbackCurrentAmp  => squidFeedback,
         inputPolarity       => 1,
         feedbackPolarity    => -1,
         phaseCycles         => squidPhase,
         criticalCurrentAmp  => squidCritical,
         staticResistanceOhm => squidResistance,
         voltageVolt         => squidVoltage);

   U_Ssa : entity warm_tdm.SsaModel
      generic map (PARAMS_G => SSA_PARAMS_C)
      port map (
         biasCurrentAmp     => ssaBias,
         inputCurrentAmp    => ssaInput,
         feedbackCurrentAmp => ssaFeedback,
         phaseCycles        => ssaPhase,
         voltageVolt        => ssaOut);

   -- Exercise the profile used by GroupTb, not only the deliberately distinct
   -- primitive-test parameters above.
   U_SyntheticSsa : entity warm_tdm.SsaModel
      port map (
         biasCurrentAmp     => syntheticSsaBias,
         inputCurrentAmp    => 0.0,
         feedbackCurrentAmp => syntheticSsaFeedback,
         phaseCycles        => syntheticSsaPhase,
         voltageVolt        => syntheticSsaOut);

   U_Sq1 : entity warm_tdm.Sq1Model
      generic map (PARAMS_G => SQ1_PARAMS_C)
      port map (
         biasCurrentAmp     => sq1Bias,
         tesCurrentAmp      => tesInput,
         feedbackCurrentAmp => sq1Feedback,
         phaseCycles        => sq1Phase,
         voltageVolt        => sq1Out);

   U_RowFas : entity warm_tdm.RowFasModel
      generic map (PARAMS_G => ROW_FAS_PARAMS_C)
      port map (
         biasCurrentAmp      => rowFasBias,
         selectCurrentAmp    => rowSelect,
         phaseCycles         => rowFasPhase,
         staticResistanceOhm => rowFasResistance,
         voltageVolt         => rowFasOut);

   U_ChipFas : entity warm_tdm.ChipFasModel
      generic map (PARAMS_G => CHIP_FAS_PARAMS_C)
      port map (
         biasCurrentAmp      => chipFasBias,
         selectCurrentAmp    => chipSelect,
         phaseCycles         => chipFasPhase,
         staticResistanceOhm => chipFasResistance,
         voltageVolt         => chipFasOut);

   U_Detector : entity warm_tdm.DetectorModuleSim
      generic map (
         NUM_COLUMNS_G     => 2,
         NUM_BANKS_G       => 2,
         ROWS_PER_BANK_G   => 2,
         TWO_LEVEL_G       => true,
         SSA_PARAMS_G      => SSA_PARAMS_C,
         SQ1_PARAMS_G      => SQ1_PARAMS_C,
         ROW_FAS_PARAMS_G  => ROW_FAS_PARAMS_C,
         CHIP_FAS_PARAMS_G => CHIP_FAS_PARAMS_C,
         COLUMN_PARAMS_G   => COLUMN_PARAMS_C)
      port map (
         ssaBiasCurrentAmp     => detectorSsaBias,
         ssaBiasSourceResistanceOhm => detectorSsaSourceR,
         ssaFeedbackCurrentAmp => detectorSsaFb,
         sq1BiasCurrentAmp     => detectorSq1Bias,
         sq1BiasSourceResistanceOhm => detectorSq1SourceR,
         sq1FeedbackCurrentAmp => detectorSq1Fb,
         rowSelectCurrentAmp   => detectorRowSelect,
         chipSelectCurrentAmp  => detectorChipSelect,
         tesCurrentAmp         => detectorTes,
         muxCurrentAmp         => detectorMuxCurrent,
         muxVoltageVolt        => detectorMuxVoltage,
         ssaBiasLoadCurrentAmp => open,
         ssaPhaseCycles        => detectorSsaPhase,
         ssaVoltageVolt        => detectorSsaVoltage);

   U_FastDetector : entity warm_tdm.DetectorModuleSim
      generic map (
         NUM_COLUMNS_G     => 2,
         NUM_BANKS_G       => 2,
         ROWS_PER_BANK_G   => 2,
         TWO_LEVEL_G       => true,
         SSA_PARAMS_G      => SSA_PARAMS_C,
         SQ1_PARAMS_G      => SQ1_PARAMS_C,
         ROW_FAS_PARAMS_G  => ROW_FAS_PARAMS_C,
         CHIP_FAS_PARAMS_G => CHIP_FAS_PARAMS_C,
         COLUMN_PARAMS_G   => FAST_COLUMN_PARAMS_C)
      port map (
         ssaBiasCurrentAmp     => detectorSsaBias,
         ssaFeedbackCurrentAmp => detectorSsaFb,
         sq1BiasCurrentAmp     => detectorSq1Bias,
         sq1FeedbackCurrentAmp => detectorSq1Fb,
         rowSelectCurrentAmp   => detectorRowSelect,
         chipSelectCurrentAmp  => detectorChipSelect,
         tesCurrentAmp         => detectorTes,
         muxCurrentAmp         => fastMuxCurrent,
         muxVoltageVolt        => fastMuxVoltage,
         ssaBiasLoadCurrentAmp => open,
         ssaPhaseCycles        => fastSsaPhase,
         ssaVoltageVolt        => fastSsaVoltage);

   test : process is
      variable muxAllClosed : real;
      variable muxRowOnly   : real;
      variable muxSelected  : real;
      variable muxTesStep   : real;
      variable idealSourceMux : real;
      variable idealSourceSsa : real;
      variable optimumSpan  : real;
      variable highBiasSpan : real;
      variable syntheticSsaLow  : real;
      variable syntheticSsaSpan : real;
   begin
      -- Published ideal low-L, overdamped SQUID limits.
      squidBias     <= 5.0E-6;
      squidInput    <= 0.0;
      squidFeedback <= 0.0;
      wait for 1 ns;
      assertClose(squidCritical, 10.0E-6, 1.0E-15,
                  "SQUID critical current at integer Phi0");
      assertClose(squidVoltage, 0.0, 1.0E-18,
                  "subcritical SQUID voltage");

      squidBias  <= 20.0E-6;
      squidInput <= 4.0E-6;
      wait for 1 ns;
      assertClose(squidPhase, 0.5, 1.0E-12,
                  "SQ1 PHINOT controls phase period");
      assertClose(squidCritical, 0.0, 1.0E-15,
                  "SQUID critical current at half Phi0");
      assertClose(squidVoltage, 80.0E-6, 1.0E-12,
                  "SQUID normal voltage at half Phi0");
      assertClose(squidResistance, 4.0, 1.0E-9,
                  "SQUID static resistance at half Phi0");

      squidBias  <= -20.0E-6;
      wait for 1 ns;
      assertClose(squidVoltage, -80.0E-6, 1.0E-12,
                  "SQUID voltage is odd in bias current");

      -- Four independent IC0/RN/PHINOT parameter triples.
      ssaBias     <= 60.0E-6;
      ssaInput    <= 10.0E-6;
      sq1Bias     <= 20.0E-6;
      tesInput    <= 4.0E-6;
      rowFasBias  <= 10.0E-6;
      rowSelect   <= 50.0E-6;
      chipFasBias <= 10.0E-6;
      chipSelect  <= 100.0E-6;
      wait for 1 ns;
      assertClose(ssaPhase, 0.5, 1.0E-12, "SSA PHINOT");
      assertClose(ssaOut, 480.0E-6, 1.0E-12, "SSA RN");
      assertClose(sq1Phase, 0.5, 1.0E-12, "SQ1 PHINOT");
      assertClose(sq1Out, 96.0E-6, 1.0E-12, "SQ1 RN plus series R");
      assertClose(rowFasPhase, 0.5, 1.0E-12, "row-FAS PHINOT");
      assertClose(rowFasResistance, 6.1, 1.0E-9, "row-FAS RN");
      assertClose(chipFasPhase, 0.5, 1.0E-12, "chip-FAS PHINOT");
      assertClose(chipFasResistance, 10.2, 1.0E-9, "chip-FAS RN");

      -- Each role repeats at its own configured current-per-Phi0 period.
      ssaInput   <= 30.0E-6;
      tesInput   <= 12.0E-6;
      rowSelect  <= 150.0E-6;
      chipSelect <= 300.0E-6;
      wait for 1 ns;
      assertClose(ssaOut, 480.0E-6, 1.0E-12, "SSA periodicity");
      assertClose(sq1Out, 96.0E-6, 1.0E-12, "SQ1 periodicity");
      assertClose(rowFasResistance, 6.1, 1.0E-9, "row-FAS periodicity");
      assertClose(chipFasResistance, 10.2, 1.0E-9,
                  "chip-FAS periodicity");

      -- The default SSA is a lumped whole-array model calibrated to the
      -- observed 5--8 mV preamplifier SA-feedback sweep.  At Ibias=IC0 the
      -- ideal model spans zero to RN*Ibias over half a feedback period.
      syntheticSsaFeedback <= 0.0;
      wait for 1 ns;
      syntheticSsaLow := syntheticSsaOut;
      syntheticSsaFeedback <=
         0.5*SSA_SQUID_SYNTHETIC_C.currentPerPhi0Amp;
      wait for 1 ns;
      syntheticSsaSpan := abs(syntheticSsaOut - syntheticSsaLow);
      assertClose(syntheticSsaPhase, -0.5, 1.0E-12,
                  "synthetic SSA feedback phase");
      assertClose(syntheticSsaSpan, 6.6E-3, 1.0E-12,
                  "synthetic SSA sweep amplitude");
      assert syntheticSsaSpan >= 5.0E-3 and syntheticSsaSpan <= 8.0E-3
         report "synthetic SSA sweep is outside the measured 5--8 mV range: " &
                real'image(syntheticSsaSpan)
         severity failure;

      -- The ideal family has a repeatable bias-tuning optimum at the onset of
      -- its voltage state: the half-flux/integer-flux span falls at high bias.
      optimumSpan := abs(
         idealSquidVoltage(SQ1_CORE_C, SQ1_CORE_C.criticalCurrentAmp, 0.5) -
         idealSquidVoltage(SQ1_CORE_C, SQ1_CORE_C.criticalCurrentAmp, 0.0));
      highBiasSpan := abs(
         idealSquidVoltage(SQ1_CORE_C, 2.0*SQ1_CORE_C.criticalCurrentAmp, 0.5) -
         idealSquidVoltage(SQ1_CORE_C, 2.0*SQ1_CORE_C.criticalCurrentAmp, 0.0));
      assert optimumSpan > highBiasSpan
         report "ideal SQUID bias sweep has no recoverable response optimum"
         severity failure;

      -- Two-level topology: row select alone remains bypassed by chip FAS.
      wait for 1 ns;
      muxAllClosed := detectorMuxCurrent(0);
      assertClose(fastMuxCurrent(0), muxAllClosed, 0.1E-6,
                  "fast/exact closed-MUX agreement");
      detectorRowSelect(0) <= 50.0E-6;
      wait for 1 ns;
      muxRowOnly := detectorMuxCurrent(0);
      assertClose(fastMuxCurrent(0), muxRowOnly, 0.1E-6,
                  "fast/exact row-only agreement");

      detectorChipSelect(0) <= 100.0E-6;
      wait for 1 ns;
      muxSelected := detectorMuxCurrent(0);
      assertClose(fastMuxCurrent(0), muxSelected, 0.1E-6,
                  "fast/exact selected-MUX agreement");
      assert muxSelected < muxRowOnly - 0.25E-6
         report "combined row/chip select did not open the nested MUX path: closed=" &
                real'image(muxAllClosed) & ", row-only=" & real'image(muxRowOnly) &
                ", selected=" & real'image(muxSelected)
         severity failure;
      assert abs(muxSelected - muxRowOnly) >
             abs(muxRowOnly - muxAllClosed)
         report "chip-select bypass did not suppress the row-only response: closed=" &
                real'image(muxAllClosed) & ", row-only=" & real'image(muxRowOnly) &
                ", selected=" & real'image(muxSelected)
         severity failure;

      -- TES flux affects only its selected column/pixel.
      detectorTes(0) <= 4.0E-6;
      wait for 1 ns;
      muxTesStep := detectorMuxCurrent(0);
      assertClose(fastMuxCurrent(0), muxTesStep, 0.1E-6,
                  "fast/exact selected-TES agreement");
      assert abs(muxTesStep - muxSelected) > 0.05E-6
         report "selected TES current did not modulate MUX current"
         severity failure;
      assertClose(detectorMuxCurrent(1), muxSelected, 0.05E-6,
                  "TES stimulus leaked into adjacent detector column");

      assert detectorSsaVoltage(0) = detectorSsaVoltage(0) and
             detectorSsaVoltage(1) = detectorSsaVoltage(1)
         report "non-finite SSA output"
         severity failure;

      -- A finite Norton resistance diverts some commanded bias through the
      -- source impedance.  Zero retains the ideal-current compatibility mode.
      idealSourceMux := detectorMuxCurrent(0);
      idealSourceSsa := detectorSsaVoltage(0);
      detectorSq1SourceR(0) <= 1.0;
      detectorSsaSourceR(0) <= 1.0;
      wait for 1 ns;
      assert abs(detectorMuxCurrent(0)) < abs(idealSourceMux)
         report "finite SQ1-bias source resistance did not alter the load line"
         severity failure;
      assert abs(detectorSsaVoltage(0)) < abs(idealSourceSsa)
         report "finite SSA-bias source resistance did not alter the load line"
         severity failure;

      report "WaferModelTb PASSED" severity note;
      stop;
      wait;
   end process test;

end architecture sim;
