-------------------------------------------------------------------------------
-- Title      : Configurable TES/SQUID Detector Module Simulation Model
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : Simulation
-- Standard   : VHDL-2008
-------------------------------------------------------------------------------
-- Description:
-- Instantiates independent MUX/SSA columns behind a detector-local set of row
-- and chip select inputs.  NUM_COLUMNS_G is deliberately independent of the
-- physical row topology so fast tests can instantiate a wafer slice.
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

entity DetectorModuleSim is
   generic (
      NUM_COLUMNS_G     : positive := 8;
      NUM_BANKS_G       : positive := 1;
      ROWS_PER_BANK_G   : positive := 4;
      TWO_LEVEL_G       : boolean  := false;
      SSA_PARAMS_G      : SsaParamsType := SSA_SYNTHETIC_C;
      SQ1_PARAMS_G      : Sq1ParamsType := SQ1_SYNTHETIC_C;
      ROW_FAS_PARAMS_G  : RowFasParamsType := ROW_FAS_SYNTHETIC_C;
      CHIP_FAS_PARAMS_G : ChipFasParamsType := CHIP_FAS_SYNTHETIC_C;
      COLUMN_PARAMS_G   : MuxColumnParamsType := MUX_COLUMN_SYNTHETIC_C);
   port (
      -- Bias currents are Norton-equivalent short-circuit currents when the
      -- corresponding source resistance is nonzero.  A zero resistance keeps
      -- the ideal-current behavior used by focused compatibility tests.
      ssaBiasCurrentAmp     : in  RealVector(0 to NUM_COLUMNS_G-1);
      ssaBiasSourceResistanceOhm : in RealVector(0 to NUM_COLUMNS_G-1) :=
         (others => 0.0);
      ssaFeedbackCurrentAmp : in  RealVector(0 to NUM_COLUMNS_G-1);
      sq1BiasCurrentAmp     : in  RealVector(0 to NUM_COLUMNS_G-1);
      sq1BiasSourceResistanceOhm : in RealVector(0 to NUM_COLUMNS_G-1) :=
         (others => 0.0);
      sq1FeedbackCurrentAmp : in  RealVector(0 to NUM_COLUMNS_G-1);
      rowSelectCurrentAmp   : in  RealVector(0 to ROWS_PER_BANK_G-1);
      chipSelectCurrentAmp  : in  RealVector(0 to NUM_BANKS_G-1);
      tesCurrentAmp         : in  RealVector(
         0 to NUM_COLUMNS_G*NUM_BANKS_G*ROWS_PER_BANK_G-1);
      muxCurrentAmp         : out RealVector(0 to NUM_COLUMNS_G-1) :=
         (others => 0.0);
      muxVoltageVolt        : out RealVector(0 to NUM_COLUMNS_G-1) :=
         (others => 0.0);
      -- Actual current after the nonlinear SSA/source load-line solution.
      ssaBiasLoadCurrentAmp : out RealVector(0 to NUM_COLUMNS_G-1) :=
         (others => 0.0);
      ssaPhaseCycles        : out RealVector(0 to NUM_COLUMNS_G-1) :=
         (others => 0.0);
      ssaVoltageVolt        : out RealVector(0 to NUM_COLUMNS_G-1) :=
         (others => 0.0));
end entity DetectorModuleSim;

architecture sim of DetectorModuleSim is
   constant NUM_ROWS_C : positive := NUM_BANKS_G * ROWS_PER_BANK_G;
begin

   GEN_COLUMNS : for column in 0 to NUM_COLUMNS_G-1 generate
      U_Column : entity warm_tdm.TdmMuxColumnModel
         generic map (
            NUM_BANKS_G       => NUM_BANKS_G,
            ROWS_PER_BANK_G   => ROWS_PER_BANK_G,
            TWO_LEVEL_G       => TWO_LEVEL_G,
            SSA_PARAMS_G      => SSA_PARAMS_G,
            SQ1_PARAMS_G      => SQ1_PARAMS_G,
            ROW_FAS_PARAMS_G  => ROW_FAS_PARAMS_G,
            CHIP_FAS_PARAMS_G => CHIP_FAS_PARAMS_G,
            COLUMN_PARAMS_G   => COLUMN_PARAMS_G)
         port map (
            ssaBiasCurrentAmp     => ssaBiasCurrentAmp(column),
            ssaBiasSourceResistanceOhm =>
               ssaBiasSourceResistanceOhm(column),
            ssaFeedbackCurrentAmp => ssaFeedbackCurrentAmp(column),
            sq1BiasCurrentAmp     => sq1BiasCurrentAmp(column),
            sq1BiasSourceResistanceOhm =>
               sq1BiasSourceResistanceOhm(column),
            sq1FeedbackCurrentAmp => sq1FeedbackCurrentAmp(column),
            rowSelectCurrentAmp   => rowSelectCurrentAmp,
            chipSelectCurrentAmp  => chipSelectCurrentAmp,
            tesCurrentAmp         => tesCurrentAmp(
               column*NUM_ROWS_C to (column+1)*NUM_ROWS_C-1),
            muxCurrentAmp         => muxCurrentAmp(column),
            muxVoltageVolt        => muxVoltageVolt(column),
            ssaBiasLoadCurrentAmp => ssaBiasLoadCurrentAmp(column),
            ssaPhaseCycles        => ssaPhaseCycles(column),
            ssaVoltageVolt        => ssaVoltageVolt(column));
   end generate GEN_COLUMNS;

end architecture sim;
