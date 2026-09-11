-------------------------------------------------------------------------------
-- Title      : Eight-Channel Sensor Wafer Compatibility Model
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : Simulation
-- Standard   : VHDL-2008
-------------------------------------------------------------------------------
-- Description:
-- Adapts the historical flat GroupTb analog interface to DetectorModuleSim.
-- Physical row-select lines 0 .. ROWS_PER_BANK_G-1 drive the row FAS devices;
-- in a two-level configuration, the following NUM_BANKS_G lines drive the
-- chip-select FAS devices.  The logical detector row count is
-- NUM_BANKS_G*ROWS_PER_BANK_G and is independent of the eight warm columns.
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

library surf;
use surf.StdRtlPkg.all;

library warm_tdm;
use warm_tdm.SimPkg.all;
use warm_tdm.WaferSimPkg.all;

entity WaferSim is

   generic (
      SA_BIAS_LOADS_G  : RealArray(7 downto 0)  := (others => 200.0);
      SA_FB_LOADS_G    : RealArray(7 downto 0)  := (others => 200.0);
      SQ1_BIAS_LOADS_G : RealArray(7 downto 0)  := (others => 200.0);
      SQ1_FB_LOADS_G   : RealArray(7 downto 0)  := (others => 200.0);
      RS_LOADS_G       : RealArray(31 downto 0) := (others => 200.0);

      NUM_ROWS_G       : integer range 1 to 80 := 4;
      NUM_BANKS_G      : integer range 1 to 8  := 1;
      ROWS_PER_BANK_G  : integer range 1 to 32 := NUM_ROWS_G;
      TWO_LEVEL_G      : boolean               := false;
      RS_LINE_OFFSET_G : integer range 0 to 31 := 0;
      CS_LINE_OFFSET_G : integer range 0 to 32 := ROWS_PER_BANK_G;
      R_SHUNT_G        : real                  := 1.0;

      SSA_RN_G     : real := 120.0;
      SSA_IC0_G    : real := 55.0e-6;
      SSA_PHINOT_G : real := 35.0e-6;

      SQ1_RN_G     : real := 14.0;
      SQ1_IC0_G    : real := 20.0e-6;
      SQ1_PHINOT_G : real := 10.0e-6;

      RS_RN_G     : real := 14.0;
      RS_IC0_G    : real := 20.0e-6;
      RS_PHINOT_G : real := 300.0e-6;

      CS_RN_G     : real := 12.0;
      CS_IC0_G    : real := 18.0e-6;
      CS_PHINOT_G : real := 250.0e-6;

      SSA_ELEMENT_COUNT_G : positive := 1;
      SQ1_ELEMENT_COUNT_G : positive := 1;
      RS_ELEMENT_COUNT_G  : positive := 1;
      CS_ELEMENT_COUNT_G  : positive := 1;

      SQ1_SERIES_R_G : real := 1.0;
      RS_SERIES_R_G  : real := 0.1;
      CS_SERIES_R_G  : real := 0.1;

      TES_CURRENT_SCALE_G      : real     := 1.0;
      USE_EXACT_MUX_SOLVER_G    : boolean  := false;
      MUX_SOLVER_ITERATIONS_G   : positive := 24;

      SSA_MODEL_PARAMS_G : SsaParamsType := (
         squid => (SSA_IC0_G, SSA_RN_G, SSA_PHINOT_G, 0.0),
         elementCount => SSA_ELEMENT_COUNT_G,
         inputPolarity => 1, feedbackPolarity => -1,
         inputCouplingScale => 1.0, feedbackCouplingScale => 1.0,
         outputOffsetVolt => 0.0, outputClampVolt => 1.0);
      SQ1_MODEL_PARAMS_G : Sq1ParamsType := (
         squid => (SQ1_IC0_G, SQ1_RN_G, SQ1_PHINOT_G, 0.0),
         elementCount => SQ1_ELEMENT_COUNT_G,
         tesPolarity => 1, feedbackPolarity => -1,
         tesCouplingScale => 1.0, feedbackCouplingScale => 1.0,
         seriesResistanceOhm => SQ1_SERIES_R_G);
      ROW_FAS_MODEL_PARAMS_G : RowFasParamsType := (
         squid => (RS_IC0_G, RS_RN_G, RS_PHINOT_G, 0.0),
         elementCount => RS_ELEMENT_COUNT_G,
         selectPolarity => 1,
         seriesResistanceOhm => RS_SERIES_R_G);
      CHIP_FAS_MODEL_PARAMS_G : ChipFasParamsType := (
         squid => (CS_IC0_G, CS_RN_G, CS_PHINOT_G, 0.0),
         elementCount => CS_ELEMENT_COUNT_G,
         selectPolarity => 1,
         seriesResistanceOhm => CS_SERIES_R_G);
      MUX_COLUMN_MODEL_PARAMS_G : MuxColumnParamsType := (
         shuntResistanceOhm => R_SHUNT_G,
         seriesResistanceOhm => 0.0,
         useExactNetworkSolver => USE_EXACT_MUX_SOLVER_G,
         solverIterations => MUX_SOLVER_ITERATIONS_G)
      );
   port (
      tesBiasP   : in  RealArray(7 downto 0);
      tesBiasN   : in  RealArray(7 downto 0);
      saBiasOutP : in  CurrentArray(7 downto 0);
      saBiasOutN : in  CurrentArray(7 downto 0);
      saBiasInP  : out RealArray(7 downto 0);
      saBiasInN  : out RealArray(7 downto 0);
      saFbP      : in  CurrentArray(7 downto 0);
      saFbN      : in  CurrentArray(7 downto 0);
      sq1BiasP   : in  CurrentArray(7 downto 0);
      sq1BiasN   : in  CurrentArray(7 downto 0);
      sq1FbP     : in  CurrentArray(7 downto 0);
      sq1FbN     : in  CurrentArray(7 downto 0);
      rsP        : in  CurrentArray(31 downto 0);
      rsN        : in  CurrentArray(31 downto 0);
      tesStimulusAmp : in RealArray(0 to 8*NUM_ROWS_G-1) := (others => 0.0));


end entity WaferSim;

architecture sim of WaferSim is

   signal saBiasCurrent   : RealVector(0 to 7) := (others => 0.0);
   signal saBiasSourceR   : RealVector(0 to 7) := (others => 0.0);
   signal saBiasLoadCurrent : RealVector(0 to 7) := (others => 0.0);
   signal saSenseVoltage  : RealVector(0 to 7) := (others => 0.0);
   signal saFbCurrent     : RealVector(0 to 7) := (others => 0.0);
   signal sq1BiasCurrent  : RealVector(0 to 7) := (others => 0.0);
   signal sq1BiasSourceR  : RealVector(0 to 7) := (others => 0.0);
   signal sq1FbCurrent    : RealVector(0 to 7) := (others => 0.0);
   signal rsCurrent       : RealVector(0 to ROWS_PER_BANK_G-1) := (others => 0.0);
   signal chipSelect      : RealVector(0 to NUM_BANKS_G-1) := (others => 0.0);
   signal tesCurrent      : RealVector(0 to 8*NUM_ROWS_G-1) := (others => 0.0);
   signal muxCurrent      : RealVector(0 to 7);
   signal muxVoltage      : RealVector(0 to 7);
   signal ssaPhase        : RealVector(0 to 7);
   signal ssaVoltage      : RealVector(0 to 7);

begin

   assert NUM_ROWS_G = NUM_BANKS_G*ROWS_PER_BANK_G
      report "WaferSim: NUM_ROWS_G must equal NUM_BANKS_G*ROWS_PER_BANK_G"
      severity failure;
   assert RS_LINE_OFFSET_G + ROWS_PER_BANK_G <= 32
      report "WaferSim: row-select line mapping exceeds the 32-line interface"
      severity failure;
   assert (not TWO_LEVEL_G) or CS_LINE_OFFSET_G + NUM_BANKS_G <= 32
      report "WaferSim: chip-select line mapping exceeds the 32-line interface"
      severity failure;

   GEN_RS_CURRENT : for i in 0 to ROWS_PER_BANK_G-1 generate
      constant LINE_C : natural := RS_LINE_OFFSET_G + i;
   begin
      rsCurrent(i) <= currentDiff(rsP(LINE_C), rsN(LINE_C), RS_LOADS_G(LINE_C));
   end generate;

   GEN_CS_CURRENT : for i in 0 to NUM_BANKS_G-1 generate
      TWO_LEVEL : if TWO_LEVEL_G generate
         constant LINE_C : natural := CS_LINE_OFFSET_G + i;
      begin
         chipSelect(i) <= currentDiff(
            rsP(LINE_C), rsN(LINE_C), RS_LOADS_G(LINE_C));
      end generate TWO_LEVEL;

      ONE_LEVEL : if not TWO_LEVEL_G generate
         chipSelect(i) <= 0.0;
      end generate ONE_LEVEL;
   end generate;

   GEN_COLUMNS : for i in 0 to 7 generate
      saBiasCurrent(i)  <= currentDiff(saBiasOutP(i), saBiasOutN(i), SA_BIAS_LOADS_G(i));
      saBiasSourceR(i)  <= saBiasOutP(i).impedance +
         saBiasOutN(i).impedance + SA_BIAS_LOADS_G(i);
      saFbCurrent(i)    <= currentDiff(saFbP(i), saFbN(i), SA_FB_LOADS_G(i));
      sq1BiasCurrent(i) <= currentDiff(sq1BiasP(i), sq1BiasN(i), SQ1_BIAS_LOADS_G(i));
      sq1BiasSourceR(i) <= sq1BiasP(i).impedance +
         sq1BiasN(i).impedance + SQ1_BIAS_LOADS_G(i);
      sq1FbCurrent(i)   <= currentDiff(sq1FbP(i), sq1FbN(i), SQ1_FB_LOADS_G(i));

      GEN_TES_ROWS : for row in 0 to NUM_ROWS_G-1 generate
         -- ColumnFebTesBiasAmp presents equal and opposite terminal currents.
         -- The compatibility wrapper uses their differential value as a
         -- detector-wide TES bias term.  A runtime per-pixel equivalent input
         -- can be superimposed through tesStimulusAmp.
         tesCurrent(i*NUM_ROWS_G + row) <=
            0.5 * (tesBiasP(i) - tesBiasN(i)) * TES_CURRENT_SCALE_G +
            tesStimulusAmp(i*NUM_ROWS_G + row);
      end generate GEN_TES_ROWS;

      saSenseVoltage(i) <= ssaVoltage(i) +
         saBiasLoadCurrent(i)*SA_BIAS_LOADS_G(i);
      saBiasInP(i) <= 0.5 * saSenseVoltage(i);
      saBiasInN(i) <= -0.5 * saSenseVoltage(i);
   end generate GEN_COLUMNS;

   U_Detector : entity warm_tdm.DetectorModuleSim
      generic map (
         NUM_COLUMNS_G     => 8,
         NUM_BANKS_G       => NUM_BANKS_G,
         ROWS_PER_BANK_G   => ROWS_PER_BANK_G,
         TWO_LEVEL_G       => TWO_LEVEL_G,
         SSA_PARAMS_G      => SSA_MODEL_PARAMS_G,
         SQ1_PARAMS_G      => SQ1_MODEL_PARAMS_G,
         ROW_FAS_PARAMS_G  => ROW_FAS_MODEL_PARAMS_G,
         CHIP_FAS_PARAMS_G => CHIP_FAS_MODEL_PARAMS_G,
         COLUMN_PARAMS_G   => MUX_COLUMN_MODEL_PARAMS_G)
      port map (
         ssaBiasCurrentAmp     => saBiasCurrent,
         ssaBiasSourceResistanceOhm => saBiasSourceR,
         ssaFeedbackCurrentAmp => saFbCurrent,
         sq1BiasCurrentAmp     => sq1BiasCurrent,
         sq1BiasSourceResistanceOhm => sq1BiasSourceR,
         sq1FeedbackCurrentAmp => sq1FbCurrent,
         rowSelectCurrentAmp   => rsCurrent,
         chipSelectCurrentAmp  => chipSelect,
         tesCurrentAmp         => tesCurrent,
         muxCurrentAmp         => muxCurrent,
         muxVoltageVolt        => muxVoltage,
         ssaBiasLoadCurrentAmp => saBiasLoadCurrent,
         ssaPhaseCycles        => ssaPhase,
         ssaVoltageVolt        => ssaVoltage);


end architecture sim;
