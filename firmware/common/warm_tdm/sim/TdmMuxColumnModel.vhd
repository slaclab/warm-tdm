-------------------------------------------------------------------------------
-- Title      : TDM SQUID Multiplexer Column Behavioral Model
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : Simulation
-- Standard   : VHDL-2008
-------------------------------------------------------------------------------
-- Description:
-- A bounded, static operating-point model of one MUX column.  Each row cell is
-- an SQ1 branch in parallel with a row FAS.  For a two-level topology, the
-- series string of row cells in each bank is in parallel with a chip FAS.
-- Banks are in series and the resulting device is in parallel with the column
-- shunt.  Bisection avoids mutually dependent real-valued concurrent loops.
-------------------------------------------------------------------------------
-- This file is part of Warm TDM. It is subject to
-- the license terms in the LICENSE.txt file found in the top-level directory
-- of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of Warm TDM, including this file, may be
-- copied, modified, propagated, or distributed except according to the terms
-- contained in the LICENSE.txt file.
-------------------------------------------------------------------------------

library warm_tdm;
use warm_tdm.WaferSimPkg.all;

entity TdmMuxColumnModel is
   generic (
      NUM_BANKS_G       : positive := 1;
      ROWS_PER_BANK_G   : positive := 4;
      TWO_LEVEL_G       : boolean  := false;
      SSA_PARAMS_G      : SsaParamsType := SSA_SYNTHETIC_C;
      SQ1_PARAMS_G      : Sq1ParamsType := SQ1_SYNTHETIC_C;
      ROW_FAS_PARAMS_G  : RowFasParamsType := ROW_FAS_SYNTHETIC_C;
      CHIP_FAS_PARAMS_G : ChipFasParamsType := CHIP_FAS_SYNTHETIC_C;
      COLUMN_PARAMS_G   : MuxColumnParamsType := MUX_COLUMN_SYNTHETIC_C);
   port (
      ssaBiasCurrentAmp     : in  real;
      ssaBiasSourceResistanceOhm : in real := 0.0;
      ssaFeedbackCurrentAmp : in  real;
      sq1BiasCurrentAmp     : in  real;
      sq1BiasSourceResistanceOhm : in real := 0.0;
      sq1FeedbackCurrentAmp : in  real;
      rowSelectCurrentAmp   : in  RealVector(0 to ROWS_PER_BANK_G-1);
      chipSelectCurrentAmp  : in  RealVector(0 to NUM_BANKS_G-1);
      tesCurrentAmp         : in  RealVector(0 to NUM_BANKS_G*ROWS_PER_BANK_G-1);
      muxCurrentAmp         : out real;
      muxVoltageVolt        : out real;
      ssaPhaseCycles        : out real;
      ssaVoltageVolt        : out real);
end entity TdmMuxColumnModel;

architecture sim of TdmMuxColumnModel is

   function currentSign (value : real) return real is
   begin
      if value < 0.0 then
         return -1.0;
      else
         return 1.0;
      end if;
   end function currentSign;

   function parallelResistance (
      firstResistance  : real;
      secondResistance : real)
      return real is
   begin
      if firstResistance <= 0.0 or secondResistance <= 0.0 then
         return 0.0;
      else
         return firstResistance * secondResistance /
                (firstResistance + secondResistance);
      end if;
   end function parallelResistance;

   function fastCellResistance (
      probeCurrent       : real;
      tesCurrent         : real;
      sq1FeedbackCurrent : real;
      rowSelectCurrent   : real;
      sq1Params          : Sq1ParamsType;
      rowFasParams       : RowFasParamsType)
      return real is
      variable sq1Resistance : real;
      variable fasResistance : real;
   begin
      sq1Resistance := sq1Params.seriesResistanceOhm +
         real(sq1Params.elementCount) * idealSquidStaticResistance(
            sq1Params.squid,
            probeCurrent,
            sq1PhaseCycles(sq1Params, tesCurrent, sq1FeedbackCurrent));
      fasResistance := rowFasParams.seriesResistanceOhm +
         real(rowFasParams.elementCount) * idealSquidStaticResistance(
            rowFasParams.squid,
            probeCurrent,
            rowFasPhaseCycles(rowFasParams, rowSelectCurrent));
      return parallelResistance(sq1Resistance, fasResistance);
   end function fastCellResistance;

   function fastRowNetworkResistance (
      probeCurrent       : real;
      bankIndex          : natural;
      rowsPerBank        : positive;
      tesCurrent         : RealVector;
      rowSelectCurrent   : RealVector;
      sq1FeedbackCurrent : real;
      sq1Params          : Sq1ParamsType;
      rowFasParams       : RowFasParamsType)
      return real is
      variable resistance : real := 0.0;
      variable row        : natural;
   begin
      for localRow in 0 to rowsPerBank-1 loop
         row := bankIndex*rowsPerBank + localRow;
         resistance := resistance + fastCellResistance(
            probeCurrent,
            tesCurrent(tesCurrent'low + row),
            sq1FeedbackCurrent,
            rowSelectCurrent(rowSelectCurrent'low + localRow),
            sq1Params,
            rowFasParams);
      end loop;
      return resistance;
   end function fastRowNetworkResistance;

   function fastColumnResistance (
      probeCurrent       : real;
      numBanks           : positive;
      rowsPerBank        : positive;
      twoLevel           : boolean;
      tesCurrent         : RealVector;
      rowSelectCurrent   : RealVector;
      chipSelectCurrent  : RealVector;
      sq1FeedbackCurrent : real;
      sq1Params          : Sq1ParamsType;
      rowFasParams       : RowFasParamsType;
      chipFasParams      : ChipFasParamsType;
      columnParams       : MuxColumnParamsType)
      return real is
      variable resistance    : real := columnParams.seriesResistanceOhm;
      variable rowResistance : real;
      variable chipResistance : real;
   begin
      for bank in 0 to numBanks-1 loop
         rowResistance := fastRowNetworkResistance(
            probeCurrent,
            bank,
            rowsPerBank,
            tesCurrent,
            rowSelectCurrent,
            sq1FeedbackCurrent,
            sq1Params,
            rowFasParams);

         if twoLevel then
            chipResistance := chipFasParams.seriesResistanceOhm +
               real(chipFasParams.elementCount) *
               idealSquidStaticResistance(
                  chipFasParams.squid,
                  probeCurrent,
                  chipFasPhaseCycles(
                     chipFasParams,
                     chipSelectCurrent(chipSelectCurrent'low + bank)));
            resistance := resistance + parallelResistance(
               rowResistance, chipResistance);
         else
            resistance := resistance + rowResistance;
         end if;
      end loop;
      return resistance;
   end function fastColumnResistance;

   function fastMuxCurrent (
      sourceCurrent      : real;
      numBanks           : positive;
      rowsPerBank        : positive;
      twoLevel           : boolean;
      tesCurrent         : RealVector;
      rowSelectCurrent   : RealVector;
      chipSelectCurrent  : RealVector;
      sq1FeedbackCurrent : real;
      sq1Params          : Sq1ParamsType;
      rowFasParams       : RowFasParamsType;
      chipFasParams      : ChipFasParamsType;
      columnParams       : MuxColumnParamsType)
      return real is
      variable direction        : real;
      variable magnitude        : real;
      variable lower            : real;
      variable upper            : real;
      variable deviceMag        : real;
      variable deviceCurrent    : real;
      variable deviceResistance : real;
      variable deviceVoltage    : real;
      variable shuntVoltage     : real;
   begin
      if sourceCurrent = 0.0 then
         return 0.0;
      end if;

      direction := currentSign(sourceCurrent);
      magnitude := abs(sourceCurrent);
      lower     := 0.0;
      upper     := magnitude;

      -- This reduced solver avoids the nested branch-current bisections but
      -- still finds a self-consistent column/shunt load-line operating point.
      for i in 1 to columnParams.solverIterations loop
         deviceMag     := 0.5 * (lower + upper);
         deviceCurrent := direction * deviceMag;
         deviceResistance := fastColumnResistance(
            deviceCurrent,
            numBanks,
            rowsPerBank,
            twoLevel,
            tesCurrent,
            rowSelectCurrent,
            chipSelectCurrent,
            sq1FeedbackCurrent,
            sq1Params,
            rowFasParams,
            chipFasParams,
            columnParams);
         deviceVoltage := deviceMag * deviceResistance;
         shuntVoltage  := (magnitude - deviceMag) *
                          columnParams.shuntResistanceOhm;

         if deviceVoltage > shuntVoltage then
            upper := deviceMag;
         else
            lower := deviceMag;
         end if;
      end loop;

      return direction * 0.5 * (lower + upper);
   end function fastMuxCurrent;

   function cellVoltage (
      totalCurrent       : real;
      tesCurrent         : real;
      sq1FeedbackCurrent : real;
      rowSelectCurrent   : real;
      sq1Params          : Sq1ParamsType;
      rowFasParams       : RowFasParamsType;
      iterations         : positive)
      return real is
      variable direction  : real;
      variable magnitude  : real;
      variable lower      : real;
      variable upper      : real;
      variable sq1Mag     : real;
      variable sq1Current : real;
      variable fasCurrent : real;
      variable sq1Voltage : real;
      variable fasVoltage : real;
      variable delta      : real;
   begin
      if totalCurrent = 0.0 then
         return 0.0;
      end if;

      direction := currentSign(totalCurrent);
      magnitude := abs(totalCurrent);
      lower     := 0.0;
      upper     := magnitude;

      for i in 1 to iterations loop
         sq1Mag     := 0.5 * (lower + upper);
         sq1Current := direction * sq1Mag;
         fasCurrent := direction * (magnitude - sq1Mag);
         sq1Voltage := sq1BranchVoltage(
            sq1Params, sq1Current, tesCurrent, sq1FeedbackCurrent);
         fasVoltage := rowFasBranchVoltage(
            rowFasParams, fasCurrent, rowSelectCurrent);
         delta := direction * (sq1Voltage - fasVoltage);

         if delta > 0.0 then
            upper := sq1Mag;
         else
            lower := sq1Mag;
         end if;
      end loop;

      sq1Mag     := 0.5 * (lower + upper);
      sq1Current := direction * sq1Mag;
      fasCurrent := direction * (magnitude - sq1Mag);
      sq1Voltage := sq1BranchVoltage(
         sq1Params, sq1Current, tesCurrent, sq1FeedbackCurrent);
      fasVoltage := rowFasBranchVoltage(
         rowFasParams, fasCurrent, rowSelectCurrent);
      return 0.5 * (sq1Voltage + fasVoltage);
   end function cellVoltage;

   function rowNetworkVoltage (
      totalCurrent       : real;
      bankIndex          : natural;
      rowsPerBank        : positive;
      tesCurrent         : RealVector;
      rowSelectCurrent   : RealVector;
      sq1FeedbackCurrent : real;
      sq1Params          : Sq1ParamsType;
      rowFasParams       : RowFasParamsType;
      iterations         : positive)
      return real is
      variable voltage : real := 0.0;
      variable row     : natural;
   begin
      for localRow in 0 to rowsPerBank-1 loop
         row := bankIndex*rowsPerBank + localRow;
         voltage := voltage + cellVoltage(
            totalCurrent,
            tesCurrent(tesCurrent'low + row),
            sq1FeedbackCurrent,
            rowSelectCurrent(rowSelectCurrent'low + localRow),
            sq1Params,
            rowFasParams,
            iterations);
      end loop;
      return voltage;
   end function rowNetworkVoltage;

   function bankVoltage (
      totalCurrent       : real;
      bankIndex          : natural;
      rowsPerBank        : positive;
      twoLevel           : boolean;
      tesCurrent         : RealVector;
      rowSelectCurrent   : RealVector;
      chipSelectCurrent  : RealVector;
      sq1FeedbackCurrent : real;
      sq1Params          : Sq1ParamsType;
      rowFasParams       : RowFasParamsType;
      chipFasParams      : ChipFasParamsType;
      iterations         : positive)
      return real is
      variable direction   : real;
      variable magnitude   : real;
      variable lower       : real;
      variable upper       : real;
      variable rowsMag     : real;
      variable rowsCurrent : real;
      variable chipCurrent : real;
      variable rowsVoltage : real;
      variable chipVoltage : real;
      variable delta       : real;
   begin
      if not twoLevel then
         return rowNetworkVoltage(
            totalCurrent,
            bankIndex,
            rowsPerBank,
            tesCurrent,
            rowSelectCurrent,
            sq1FeedbackCurrent,
            sq1Params,
            rowFasParams,
            iterations);
      end if;

      if totalCurrent = 0.0 then
         return 0.0;
      end if;

      direction := currentSign(totalCurrent);
      magnitude := abs(totalCurrent);
      lower     := 0.0;
      upper     := magnitude;

      for i in 1 to iterations loop
         rowsMag     := 0.5 * (lower + upper);
         rowsCurrent := direction * rowsMag;
         chipCurrent := direction * (magnitude - rowsMag);
         rowsVoltage := rowNetworkVoltage(
            rowsCurrent,
            bankIndex,
            rowsPerBank,
            tesCurrent,
            rowSelectCurrent,
            sq1FeedbackCurrent,
            sq1Params,
            rowFasParams,
            iterations);
         chipVoltage := chipFasBranchVoltage(
            chipFasParams,
            chipCurrent,
            chipSelectCurrent(chipSelectCurrent'low + bankIndex));
         delta := direction * (rowsVoltage - chipVoltage);

         if delta > 0.0 then
            upper := rowsMag;
         else
            lower := rowsMag;
         end if;
      end loop;

      rowsMag     := 0.5 * (lower + upper);
      rowsCurrent := direction * rowsMag;
      chipCurrent := direction * (magnitude - rowsMag);
      rowsVoltage := rowNetworkVoltage(
         rowsCurrent,
         bankIndex,
         rowsPerBank,
         tesCurrent,
         rowSelectCurrent,
         sq1FeedbackCurrent,
         sq1Params,
         rowFasParams,
         iterations);
      chipVoltage := chipFasBranchVoltage(
         chipFasParams,
         chipCurrent,
         chipSelectCurrent(chipSelectCurrent'low + bankIndex));
      return 0.5 * (rowsVoltage + chipVoltage);
   end function bankVoltage;

   function columnDeviceVoltage (
      deviceCurrent      : real;
      numBanks           : positive;
      rowsPerBank        : positive;
      twoLevel           : boolean;
      tesCurrent         : RealVector;
      rowSelectCurrent   : RealVector;
      chipSelectCurrent  : RealVector;
      sq1FeedbackCurrent : real;
      sq1Params          : Sq1ParamsType;
      rowFasParams       : RowFasParamsType;
      chipFasParams      : ChipFasParamsType;
      columnParams       : MuxColumnParamsType)
      return real is
      variable voltage : real := deviceCurrent * columnParams.seriesResistanceOhm;
   begin
      for bank in 0 to numBanks-1 loop
         voltage := voltage + bankVoltage(
            deviceCurrent,
            bank,
            rowsPerBank,
            twoLevel,
            tesCurrent,
            rowSelectCurrent,
            chipSelectCurrent,
            sq1FeedbackCurrent,
            sq1Params,
            rowFasParams,
            chipFasParams,
            columnParams.solverIterations);
      end loop;
      return voltage;
   end function columnDeviceVoltage;

   function solveMuxCurrent (
      sourceCurrent      : real;
      numBanks           : positive;
      rowsPerBank        : positive;
      twoLevel           : boolean;
      tesCurrent         : RealVector;
      rowSelectCurrent   : RealVector;
      chipSelectCurrent  : RealVector;
      sq1FeedbackCurrent : real;
      sq1Params          : Sq1ParamsType;
      rowFasParams       : RowFasParamsType;
      chipFasParams      : ChipFasParamsType;
      columnParams       : MuxColumnParamsType)
      return real is
      variable direction    : real;
      variable magnitude    : real;
      variable lower        : real;
      variable upper        : real;
      variable deviceMag    : real;
      variable deviceCurrent : real;
      variable deviceVoltage : real;
      variable shuntVoltage  : real;
      variable delta         : real;
   begin
      if sourceCurrent = 0.0 then
         return 0.0;
      end if;

      direction := currentSign(sourceCurrent);
      magnitude := abs(sourceCurrent);
      lower     := 0.0;
      upper     := magnitude;

      for i in 1 to columnParams.solverIterations loop
         deviceMag     := 0.5 * (lower + upper);
         deviceCurrent := direction * deviceMag;
         deviceVoltage := columnDeviceVoltage(
            deviceCurrent,
            numBanks,
            rowsPerBank,
            twoLevel,
            tesCurrent,
            rowSelectCurrent,
            chipSelectCurrent,
            sq1FeedbackCurrent,
            sq1Params,
            rowFasParams,
            chipFasParams,
            columnParams);
         shuntVoltage := direction * (magnitude - deviceMag) *
                         columnParams.shuntResistanceOhm;
         delta := direction * (deviceVoltage - shuntVoltage);

         if delta > 0.0 then
            upper := deviceMag;
         else
            lower := deviceMag;
         end if;
      end loop;

      return direction * 0.5 * (lower + upper);
   end function solveMuxCurrent;

   function muxCurrentForSource (
      sourceCurrent      : real;
      numBanks           : positive;
      rowsPerBank        : positive;
      twoLevel           : boolean;
      tesCurrent         : RealVector;
      rowSelectCurrent   : RealVector;
      chipSelectCurrent  : RealVector;
      sq1FeedbackCurrent : real;
      sq1Params          : Sq1ParamsType;
      rowFasParams       : RowFasParamsType;
      chipFasParams      : ChipFasParamsType;
      columnParams       : MuxColumnParamsType)
      return real is
   begin
      if columnParams.useExactNetworkSolver then
         return solveMuxCurrent(
            sourceCurrent, numBanks, rowsPerBank, twoLevel, tesCurrent,
            rowSelectCurrent, chipSelectCurrent, sq1FeedbackCurrent,
            sq1Params, rowFasParams, chipFasParams, columnParams);
      else
         return fastMuxCurrent(
            sourceCurrent, numBanks, rowsPerBank, twoLevel, tesCurrent,
            rowSelectCurrent, chipSelectCurrent, sq1FeedbackCurrent,
            sq1Params, rowFasParams, chipFasParams, columnParams);
      end if;
   end function muxCurrentForSource;

   -- Solve a Norton-equivalent source, source resistance, column shunt, and
   -- nonlinear MUX in one bisection.  Folding the source term into the
   -- existing load-line equation avoids an expensive nested outer solve.
   function solveSourceAwareMuxCurrent (
      nortonCurrent      : real;
      sourceResistance   : real;
      numBanks           : positive;
      rowsPerBank        : positive;
      twoLevel           : boolean;
      tesCurrent         : RealVector;
      rowSelectCurrent   : RealVector;
      chipSelectCurrent  : RealVector;
      sq1FeedbackCurrent : real;
      sq1Params          : Sq1ParamsType;
      rowFasParams       : RowFasParamsType;
      chipFasParams      : ChipFasParamsType;
      columnParams       : MuxColumnParamsType)
      return real is
      variable direction       : real;
      variable magnitude       : real;
      variable lower           : real;
      variable upper           : real;
      variable deviceCurrent   : real;
      variable deviceVoltage   : real;
      variable residual        : real;
   begin
      if nortonCurrent = 0.0 or sourceResistance <= 0.0 then
         return muxCurrentForSource(
            nortonCurrent, numBanks, rowsPerBank, twoLevel, tesCurrent,
            rowSelectCurrent, chipSelectCurrent, sq1FeedbackCurrent,
            sq1Params, rowFasParams, chipFasParams, columnParams);
      end if;

      direction := currentSign(nortonCurrent);
      magnitude := abs(nortonCurrent);
      lower := 0.0;
      upper := magnitude;
      for i in 1 to columnParams.solverIterations loop
         deviceCurrent := direction*0.5*(lower + upper);
         if columnParams.useExactNetworkSolver then
            deviceVoltage := columnDeviceVoltage(
               deviceCurrent, numBanks, rowsPerBank, twoLevel, tesCurrent,
               rowSelectCurrent, chipSelectCurrent, sq1FeedbackCurrent,
               sq1Params, rowFasParams, chipFasParams, columnParams);
         else
            deviceVoltage := deviceCurrent*fastColumnResistance(
               deviceCurrent, numBanks, rowsPerBank, twoLevel, tesCurrent,
               rowSelectCurrent, chipSelectCurrent, sq1FeedbackCurrent,
               sq1Params, rowFasParams, chipFasParams, columnParams);
         end if;
         residual := direction*(
            deviceCurrent + deviceVoltage/
               columnParams.shuntResistanceOhm +
            deviceVoltage/sourceResistance - nortonCurrent);
         if residual > 0.0 then
            upper := abs(deviceCurrent);
         else
            lower := abs(deviceCurrent);
         end if;
      end loop;
      return direction*0.5*(lower + upper);
   end function solveSourceAwareMuxCurrent;

   function solveSsaBiasCurrent (
      nortonCurrent    : real;
      sourceResistance : real;
      inputCurrent     : real;
      feedbackCurrent  : real;
      params           : SsaParamsType;
      iterations       : positive)
      return real is
      variable direction : real;
      variable magnitude : real;
      variable lower     : real;
      variable upper     : real;
      variable biasMag   : real;
      variable bias      : real;
      variable voltage   : real;
      variable residual  : real;
   begin
      if nortonCurrent = 0.0 or sourceResistance <= 0.0 then
         return nortonCurrent;
      end if;

      direction := currentSign(nortonCurrent);
      magnitude := abs(nortonCurrent);
      lower := 0.0;
      upper := magnitude;
      for i in 1 to iterations loop
         biasMag := 0.5*(lower + upper);
         bias := direction*biasMag;
         voltage := ssaVoltage(params, bias, inputCurrent, feedbackCurrent);
         residual := direction*(
            bias + voltage/sourceResistance - nortonCurrent);
         if residual > 0.0 then
            upper := biasMag;
         else
            lower := biasMag;
         end if;
      end loop;
      return direction*0.5*(lower + upper);
   end function solveSsaBiasCurrent;

begin

   assert validSquidParams(SSA_PARAMS_G.squid)
      report "TdmMuxColumnModel: invalid SSA parameters"
      severity failure;
   assert validSquidParams(SQ1_PARAMS_G.squid)
      report "TdmMuxColumnModel: invalid SQ1 parameters"
      severity failure;
   assert validSquidParams(ROW_FAS_PARAMS_G.squid)
      report "TdmMuxColumnModel: invalid row-FAS parameters"
      severity failure;
   assert validSquidParams(CHIP_FAS_PARAMS_G.squid)
      report "TdmMuxColumnModel: invalid chip-FAS parameters"
      severity failure;
   assert SSA_PARAMS_G.inputPolarity /= 0 and
          SSA_PARAMS_G.feedbackPolarity /= 0 and
          SSA_PARAMS_G.inputCouplingScale > 0.0 and
          SSA_PARAMS_G.feedbackCouplingScale > 0.0 and
          SSA_PARAMS_G.outputClampVolt > 0.0
      report "TdmMuxColumnModel: invalid SSA coupling or output parameters"
      severity failure;
   assert SQ1_PARAMS_G.tesPolarity /= 0 and
          SQ1_PARAMS_G.feedbackPolarity /= 0 and
          SQ1_PARAMS_G.tesCouplingScale > 0.0 and
          SQ1_PARAMS_G.feedbackCouplingScale > 0.0
      report "TdmMuxColumnModel: invalid SQ1 coupling parameters"
      severity failure;
   assert ROW_FAS_PARAMS_G.selectPolarity /= 0
      report "TdmMuxColumnModel: invalid row-FAS select polarity"
      severity failure;
   assert CHIP_FAS_PARAMS_G.selectPolarity /= 0
      report "TdmMuxColumnModel: invalid chip-FAS select polarity"
      severity failure;
   assert COLUMN_PARAMS_G.shuntResistanceOhm > 0.0
      report "TdmMuxColumnModel: shunt resistance must be positive"
      severity failure;
   assert COLUMN_PARAMS_G.seriesResistanceOhm >= 0.0
      report "TdmMuxColumnModel: series resistance must be nonnegative"
      severity failure;
   assert ssaBiasSourceResistanceOhm >= 0.0 and
          sq1BiasSourceResistanceOhm >= 0.0
      report "TdmMuxColumnModel: bias source resistance must be nonnegative"
      severity failure;
   assert SQ1_PARAMS_G.seriesResistanceOhm > 0.0
      report "TdmMuxColumnModel: SQ1 branch needs positive series resistance"
      severity failure;
   assert ROW_FAS_PARAMS_G.seriesResistanceOhm > 0.0
      report "TdmMuxColumnModel: row-FAS branch needs positive series resistance"
      severity failure;
   assert (not TWO_LEVEL_G) or CHIP_FAS_PARAMS_G.seriesResistanceOhm > 0.0
      report "TdmMuxColumnModel: chip-FAS branch needs positive series resistance"
      severity failure;

   comb : process (all) is
      variable current        : real;
      variable muxVoltage     : real;
      variable ssaBiasCurrent : real;
   begin
      current := solveSourceAwareMuxCurrent(
         sq1BiasCurrentAmp, sq1BiasSourceResistanceOhm,
         NUM_BANKS_G, ROWS_PER_BANK_G, TWO_LEVEL_G, tesCurrentAmp,
         rowSelectCurrentAmp, chipSelectCurrentAmp, sq1FeedbackCurrentAmp,
         SQ1_PARAMS_G, ROW_FAS_PARAMS_G, CHIP_FAS_PARAMS_G,
         COLUMN_PARAMS_G);
      if COLUMN_PARAMS_G.useExactNetworkSolver then
         muxVoltage := columnDeviceVoltage(
            current, NUM_BANKS_G, ROWS_PER_BANK_G, TWO_LEVEL_G,
            tesCurrentAmp, rowSelectCurrentAmp, chipSelectCurrentAmp,
            sq1FeedbackCurrentAmp, SQ1_PARAMS_G, ROW_FAS_PARAMS_G,
            CHIP_FAS_PARAMS_G, COLUMN_PARAMS_G);
      else
         muxVoltage := current*fastColumnResistance(
            current, NUM_BANKS_G, ROWS_PER_BANK_G, TWO_LEVEL_G,
            tesCurrentAmp, rowSelectCurrentAmp, chipSelectCurrentAmp,
            sq1FeedbackCurrentAmp, SQ1_PARAMS_G, ROW_FAS_PARAMS_G,
            CHIP_FAS_PARAMS_G, COLUMN_PARAMS_G);
      end if;
      ssaBiasCurrent := solveSsaBiasCurrent(
         ssaBiasCurrentAmp, ssaBiasSourceResistanceOhm, current,
         ssaFeedbackCurrentAmp, SSA_PARAMS_G,
         COLUMN_PARAMS_G.solverIterations);

      muxCurrentAmp  <= current;
      muxVoltageVolt <= muxVoltage;
      ssaPhaseCycles <= warm_tdm.WaferSimPkg.ssaPhaseCycles(
         SSA_PARAMS_G, current, ssaFeedbackCurrentAmp);
      ssaVoltageVolt <= ssaVoltage(
         SSA_PARAMS_G, ssaBiasCurrent, current, ssaFeedbackCurrentAmp);
   end process comb;

end architecture sim;
