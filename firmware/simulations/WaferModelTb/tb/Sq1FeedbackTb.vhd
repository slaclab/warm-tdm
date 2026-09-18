-------------------------------------------------------------------------------
-- Title      : Nominal SQ1 Feedback Sweep Testbench
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
use warm_tdm.SimPkg.all;
use warm_tdm.WaferSimPkg.all;

entity Sq1FeedbackTb is
end entity Sq1FeedbackTb;

architecture sim of Sq1FeedbackTb is
   constant FEEDBACK_PERIOD_C : real := 23.0E-6;
   constant CABLE_RESISTANCE_C : real := 200.0;
   -- Per-leg impedances from the current GroupTb FEB models. Apply physical
   -- coil currents here, independently of the software DAC conversion.
   constant SQ1_FB_SOURCE_C   : real := 7680.0 + 2.0*149.7;
   constant SQ1_BIAS_SOURCE_C : real := 15400.0 + 2.0*149.7;
   constant SA_FB_SOURCE_C    : real := 3480.0 + 2.0*149.7;
   constant SA_BIAS_SOURCE_C  : real := 14990.0;

   signal columnDrive : ColumnCryoDriveArray(0 to 0) :=
      (others => ZERO_COLUMN_CRYO_DRIVE_C);
   signal columnSense : ColumnCryoSenseArray(0 to 0);
   signal rowDrive : DifferentialSourceArray(0 to 31) :=
      (others => ZERO_DIFFERENTIAL_SOURCE_C);

   function sourceForCurrent (
      currentAmp        : real;
      legResistanceOhm  : real)
      return DifferentialSourceType is
      variable halfVoltage : real;
   begin
      halfVoltage := currentAmp *
         (2.0*legResistanceOhm + CABLE_RESISTANCE_C)/2.0;
      return (
         p => (voltage => halfVoltage, impedance => legResistanceOhm),
         n => (voltage => -halfVoltage, impedance => legResistanceOhm));
   end function sourceForCurrent;

begin
   U_Harness : entity warm_tdm.GroupDetectorHarnessSim
      generic map (
         NUM_WARM_COLUMNS_G     => 1,
         NUM_WARM_ROW_LINES_G   => 32,
         COLUMNS_PER_DETECTOR_G => 1,
         NUM_BANKS_G            => 1,
         ROWS_PER_BANK_G        => 32,
         TWO_LEVEL_G            => false,
         VARIATION_SEED_G       => 0)
      port map (
         columnDrive    => columnDrive,
         columnSense    => columnSense,
         rowSelectDrive => rowDrive);

   test : process is
      variable feedbackCurrent : real;
      variable referenceVoltage : real;
      variable measuredVoltage : real;
      variable minimumVoltage : real;
      variable maximumVoltage : real;
      variable riseSeen : boolean;
      variable fallSeen : boolean;
      variable previousVoltage : real;
   begin
      assert SQ1_SQUID_SYNTHETIC_C.currentPerPhi0Amp = FEEDBACK_PERIOD_C
         report "Nominal SQ1 feedback period must be 23 uA"
         severity failure;

      columnDrive(0).ssaBias <= sourceForCurrent(55.0E-6, SA_BIAS_SOURCE_C);
      columnDrive(0).ssaFeedback <= sourceForCurrent(9.13E-6, SA_FB_SOURCE_C);

      -- Exercise the ideal select extremum and the SetCosimTunePoints value,
      -- with two physically achievable SQ1 column-bias currents.
      for selectStep in 0 to 1 loop
         rowDrive(0) <= sourceForCurrent(
            (150.0 + 13.0*real(selectStep))*1.0E-6, 0.0);
         for biasStep in 0 to 1 loop
            columnDrive(0).sq1Bias <= sourceForCurrent(
               (50.0 + 25.0*real(biasStep))*1.0E-6, SQ1_BIAS_SOURCE_C);
            minimumVoltage := 1.0;
            maximumVoltage := -1.0;
            riseSeen := false;
            fallSeen := false;
            previousVoltage := 0.0;

            -- Sweep three periods, including negative feedback. Compare each
            -- point with its opposite polarity and a one-period translation.
            for feedbackStep in -15 to 15 loop
               feedbackCurrent := real(feedbackStep)*FEEDBACK_PERIOD_C/10.0;
               columnDrive(0).sq1Feedback <= sourceForCurrent(
                  feedbackCurrent, SQ1_FB_SOURCE_C);
               wait for 1 ns;
               referenceVoltage := columnSense(0).saSenseVoltage.p -
                                   columnSense(0).saSenseVoltage.n;
               if referenceVoltage < minimumVoltage then
                  minimumVoltage := referenceVoltage;
               end if;
               if referenceVoltage > maximumVoltage then
                  maximumVoltage := referenceVoltage;
               end if;
               if feedbackStep > -15 then
                  riseSeen := riseSeen or referenceVoltage > previousVoltage + 1.0E-8;
                  fallSeen := fallSeen or referenceVoltage < previousVoltage - 1.0E-8;
               end if;
               previousVoltage := referenceVoltage;

               columnDrive(0).sq1Feedback <= sourceForCurrent(
                  -feedbackCurrent, SQ1_FB_SOURCE_C);
               wait for 1 ns;
               measuredVoltage := columnSense(0).saSenseVoltage.p -
                                  columnSense(0).saSenseVoltage.n;
               assert abs(measuredVoltage - referenceVoltage) < 1.0E-8
                  report "Nominal SQ1 response differs with feedback polarity"
                  severity failure;

               columnDrive(0).sq1Feedback <= sourceForCurrent(
                  feedbackCurrent + FEEDBACK_PERIOD_C, SQ1_FB_SOURCE_C);
               wait for 1 ns;
               measuredVoltage := columnSense(0).saSenseVoltage.p -
                                  columnSense(0).saSenseVoltage.n;
               assert abs(measuredVoltage - referenceVoltage) < 1.0E-8
                  report "Nominal SQ1 response does not repeat after 23 uA"
                  severity failure;
            end loop;

            assert maximumVoltage - minimumVoltage > 0.1E-3
               report "Selected SQ1 feedback sweep has no useful modulation"
               severity failure;
            assert riseSeen and fallSeen
               report "Selected SQ1 feedback sweep has no turnover"
               severity failure;
            report "SQ1 feedback sweep: row select=" &
               real'image(150.0 + 13.0*real(selectStep)) &
               " uA, column bias=" & real'image(50.0 + 25.0*real(biasStep)) &
               " uA, SA sense span=" &
               real'image(1.0E3*(maximumVoltage - minimumVoltage)) & " mV";
         end loop;
      end loop;
      report "Sq1FeedbackTb PASSED" severity note;
      stop;
      wait;
   end process test;
end architecture sim;
