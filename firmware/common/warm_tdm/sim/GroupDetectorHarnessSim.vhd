-------------------------------------------------------------------------------
-- Title      : Group Detector/Warm-Electronics Harness Model
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : Simulation
-- Standard   : VHDL-2008
-------------------------------------------------------------------------------
-- Description:
-- Maps flattened warm column and row endpoints onto one or more identical
-- detector modules.  A negative detector-map entry explicitly terminates an
-- unused warm column with zero differential input voltage.  Warm source ports
-- retain their differential Thevenin representation.  Feedback and select
-- coils use a fixed cable/coil load; SSA and SQ1 bias sources pass their
-- Norton current and source resistance into the nonlinear cold load-line
-- solver.
-------------------------------------------------------------------------------
-- This file is part of Warm TDM. It is subject to
-- the license terms in the LICENSE.txt file found in the top-level directory
-- of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of Warm TDM, including this file, may be
-- copied, modified, propagated, or distributed except according to the terms
-- contained in the LICENSE.txt file.
-------------------------------------------------------------------------------

library surf;
use surf.StdRtlPkg.all;

library warm_tdm;
use warm_tdm.SimPkg.all;
use warm_tdm.WaferSimPkg.all;

entity GroupDetectorHarnessSim is
   generic (
      NUM_WARM_COLUMNS_G     : positive := 8;
      NUM_WARM_ROW_LINES_G   : positive := 32;
      NUM_DETECTORS_G        : positive := 1;
      COLUMNS_PER_DETECTOR_G : positive := 8;
      NUM_BANKS_G            : positive := 1;
      ROWS_PER_BANK_G        : positive := 4;
      TWO_LEVEL_G            : boolean  := false;
      WARM_DETECTOR_MAP_G    : IntegerVector(0 to NUM_WARM_COLUMNS_G-1) :=
         sequentialWarmDetectorMap(
            NUM_WARM_COLUMNS_G, NUM_DETECTORS_G, COLUMNS_PER_DETECTOR_G);
      WARM_COLUMN_MAP_G      : IntegerVector(0 to NUM_WARM_COLUMNS_G-1) :=
         sequentialWarmColumnMap(
            NUM_WARM_COLUMNS_G, NUM_DETECTORS_G, COLUMNS_PER_DETECTOR_G);
      RS_LINE_MAP_G          : IntegerVector(
         0 to NUM_DETECTORS_G*ROWS_PER_BANK_G-1) :=
         contiguousRsLineMap(
            NUM_DETECTORS_G, ROWS_PER_BANK_G, NUM_BANKS_G, TWO_LEVEL_G);
      CS_LINE_MAP_G          : IntegerVector(
         0 to NUM_DETECTORS_G*NUM_BANKS_G-1) :=
         contiguousCsLineMap(
            NUM_DETECTORS_G, ROWS_PER_BANK_G, NUM_BANKS_G, TWO_LEVEL_G);
      -- Additional differential cable/wiring resistance.  These values do
      -- not replace the source impedance already carried by columnDrive.
      SA_BIAS_LOADS_G        : RealArray(0 to NUM_WARM_COLUMNS_G-1) :=
         (others => 200.0);
      -- Fixed cable plus coupling-coil resistance.
      SA_FB_LOADS_G          : RealArray(0 to NUM_WARM_COLUMNS_G-1) :=
         (others => 200.0);
      -- Additional SQ1-bias wiring resistance; the MUX impedance is solved
      -- separately and must not be included here.
      SQ1_BIAS_LOADS_G       : RealArray(0 to NUM_WARM_COLUMNS_G-1) :=
         (others => 200.0);
      -- Fixed cable plus coupling-coil resistance.
      SQ1_FB_LOADS_G         : RealArray(0 to NUM_WARM_COLUMNS_G-1) :=
         (others => 200.0);
      -- Fixed cable plus row/chip-select coupling-coil resistance.
      RS_LOADS_G             : RealArray(0 to NUM_WARM_ROW_LINES_G-1) :=
         (others => 200.0);
      TES_CURRENT_SCALE_G    : real := 1.0;
      SSA_PARAMS_G           : SsaParamsType := SSA_SYNTHETIC_C;
      SQ1_PARAMS_G           : Sq1ParamsType := SQ1_SYNTHETIC_C;
      ROW_FAS_PARAMS_G       : RowFasParamsType := ROW_FAS_SYNTHETIC_C;
      CHIP_FAS_PARAMS_G      : ChipFasParamsType := CHIP_FAS_SYNTHETIC_C;
      COLUMN_PARAMS_G        : MuxColumnParamsType := MUX_COLUMN_SYNTHETIC_C);
   port (
      columnDrive : in  ColumnCryoDriveArray(0 to NUM_WARM_COLUMNS_G-1);
      columnSense : out ColumnCryoSenseArray(0 to NUM_WARM_COLUMNS_G-1);
      rowSelectDrive : in DifferentialSourceArray(
         0 to NUM_WARM_ROW_LINES_G-1);
      tesStimulusAmp : in RealVector(
         0 to NUM_DETECTORS_G*COLUMNS_PER_DETECTOR_G*
              NUM_BANKS_G*ROWS_PER_BANK_G-1) := (others => 0.0));
end entity GroupDetectorHarnessSim;

architecture sim of GroupDetectorHarnessSim is
   constant NUM_DETECTOR_COLUMNS_C : positive :=
      NUM_DETECTORS_G*COLUMNS_PER_DETECTOR_G;
   constant NUM_ROWS_C : positive := NUM_BANKS_G*ROWS_PER_BANK_G;
   constant NUM_PIXELS_C : positive := NUM_DETECTOR_COLUMNS_C*NUM_ROWS_C;

   signal ssaBiasCurrent : RealVector(0 to NUM_DETECTOR_COLUMNS_C-1) :=
      (others => 0.0);
   signal ssaBiasSourceResistance : RealVector(
      0 to NUM_DETECTOR_COLUMNS_C-1) := (others => 0.0);
   signal ssaFbCurrent : RealVector(0 to NUM_DETECTOR_COLUMNS_C-1) :=
      (others => 0.0);
   signal sq1BiasCurrent : RealVector(0 to NUM_DETECTOR_COLUMNS_C-1) :=
      (others => 0.0);
   signal sq1BiasSourceResistance : RealVector(
      0 to NUM_DETECTOR_COLUMNS_C-1) := (others => 0.0);
   signal sq1FbCurrent : RealVector(0 to NUM_DETECTOR_COLUMNS_C-1) :=
      (others => 0.0);
   signal rowLineCurrent : RealVector(0 to NUM_WARM_ROW_LINES_G-1) :=
      (others => 0.0);
   signal detectorRsCurrent : RealVector(
      0 to NUM_DETECTORS_G*ROWS_PER_BANK_G-1) := (others => 0.0);
   signal detectorCsCurrent : RealVector(
      0 to NUM_DETECTORS_G*NUM_BANKS_G-1) := (others => 0.0);
   signal detectorTesCurrent : RealVector(0 to NUM_PIXELS_C-1) :=
      (others => 0.0);
   signal muxCurrent : RealVector(0 to NUM_DETECTOR_COLUMNS_C-1);
   signal muxVoltage : RealVector(0 to NUM_DETECTOR_COLUMNS_C-1);
   signal ssaPhase   : RealVector(0 to NUM_DETECTOR_COLUMNS_C-1);
   signal ssaVoltage : RealVector(0 to NUM_DETECTOR_COLUMNS_C-1);
begin

   VALIDATE : process is
      variable connections : natural;
   begin
      for warmColumn in 0 to NUM_WARM_COLUMNS_G-1 loop
         assert WARM_DETECTOR_MAP_G(warmColumn) >= -1 and
                WARM_DETECTOR_MAP_G(warmColumn) < NUM_DETECTORS_G
            report "GroupDetectorHarnessSim: detector map entry is out of range"
            severity failure;
         if WARM_DETECTOR_MAP_G(warmColumn) >= 0 then
            assert WARM_COLUMN_MAP_G(warmColumn) >= 0 and
                   WARM_COLUMN_MAP_G(warmColumn) < COLUMNS_PER_DETECTOR_G
               report "GroupDetectorHarnessSim: detector-column map entry is out of range"
               severity failure;
            for otherWarmColumn in warmColumn+1 to NUM_WARM_COLUMNS_G-1 loop
               assert WARM_DETECTOR_MAP_G(otherWarmColumn) < 0 or
                      WARM_DETECTOR_MAP_G(otherWarmColumn) /=
                         WARM_DETECTOR_MAP_G(warmColumn) or
                      WARM_COLUMN_MAP_G(otherWarmColumn) /=
                         WARM_COLUMN_MAP_G(warmColumn)
                  report "GroupDetectorHarnessSim: detector column is connected more than once"
                  severity failure;
            end loop;
         end if;
      end loop;

      for detector in 0 to NUM_DETECTORS_G-1 loop
         for detectorColumn in 0 to COLUMNS_PER_DETECTOR_G-1 loop
            connections := 0;
            for warmColumn in 0 to NUM_WARM_COLUMNS_G-1 loop
               if WARM_DETECTOR_MAP_G(warmColumn) = detector and
                  WARM_COLUMN_MAP_G(warmColumn) = detectorColumn then
                  connections := connections + 1;
               end if;
            end loop;
            assert connections = 1
               report "GroupDetectorHarnessSim: detector column is not connected exactly once"
               severity failure;
         end loop;
      end loop;

      for index in RS_LINE_MAP_G'range loop
         assert RS_LINE_MAP_G(index) >= 0 and
                RS_LINE_MAP_G(index) < NUM_WARM_ROW_LINES_G
            report "GroupDetectorHarnessSim: row-select map entry is out of range"
            severity failure;
         for otherIndex in index+1 to RS_LINE_MAP_G'high loop
            assert RS_LINE_MAP_G(index) /= RS_LINE_MAP_G(otherIndex)
               report "GroupDetectorHarnessSim: warm row line drives more than one detector row terminal"
               severity failure;
         end loop;
      end loop;
      if TWO_LEVEL_G then
         for index in CS_LINE_MAP_G'range loop
            assert CS_LINE_MAP_G(index) >= 0 and
                   CS_LINE_MAP_G(index) < NUM_WARM_ROW_LINES_G
               report "GroupDetectorHarnessSim: chip-select map entry is out of range"
               severity failure;
            for otherIndex in index+1 to CS_LINE_MAP_G'high loop
               assert CS_LINE_MAP_G(index) /= CS_LINE_MAP_G(otherIndex)
                  report "GroupDetectorHarnessSim: warm row line drives more than one detector chip terminal"
                  severity failure;
            end loop;
            for rowIndex in RS_LINE_MAP_G'range loop
               assert CS_LINE_MAP_G(index) /= RS_LINE_MAP_G(rowIndex)
                  report "GroupDetectorHarnessSim: warm row line is shared by row and chip terminals"
                  severity failure;
            end loop;
         end loop;
      end if;
      wait;
   end process VALIDATE;

   GEN_ROW_LINES : for line in 0 to NUM_WARM_ROW_LINES_G-1 generate
      rowLineCurrent(line) <= currentDiff(
         rowSelectDrive(line), RS_LOADS_G(line));
   end generate GEN_ROW_LINES;

   ROUTE_ROWS : process (all) is
   begin
      detectorRsCurrent <= (others => 0.0);
      detectorCsCurrent <= (others => 0.0);
      for index in detectorRsCurrent'range loop
         if RS_LINE_MAP_G(index) >= 0 and
            RS_LINE_MAP_G(index) < NUM_WARM_ROW_LINES_G then
            detectorRsCurrent(index) <= rowLineCurrent(RS_LINE_MAP_G(index));
         end if;
      end loop;
      if TWO_LEVEL_G then
         for index in detectorCsCurrent'range loop
            if CS_LINE_MAP_G(index) >= 0 and
               CS_LINE_MAP_G(index) < NUM_WARM_ROW_LINES_G then
               detectorCsCurrent(index) <= rowLineCurrent(CS_LINE_MAP_G(index));
            end if;
         end loop;
      end if;
   end process ROUTE_ROWS;

   ROUTE_COLUMNS : process (all) is
      variable detectorColumn : integer;
      variable pixel          : natural;
   begin
      ssaBiasCurrent <= (others => 0.0);
      ssaBiasSourceResistance <= (others => 0.0);
      ssaFbCurrent   <= (others => 0.0);
      sq1BiasCurrent <= (others => 0.0);
      sq1BiasSourceResistance <= (others => 0.0);
      sq1FbCurrent   <= (others => 0.0);
      detectorTesCurrent <= tesStimulusAmp;
      columnSense <= (others => (ssaVoltage => (p => 0.0, n => 0.0)));

      for warmColumn in 0 to NUM_WARM_COLUMNS_G-1 loop
         if WARM_DETECTOR_MAP_G(warmColumn) >= 0 and
            WARM_DETECTOR_MAP_G(warmColumn) < NUM_DETECTORS_G and
            WARM_COLUMN_MAP_G(warmColumn) >= 0 and
            WARM_COLUMN_MAP_G(warmColumn) < COLUMNS_PER_DETECTOR_G then
            detectorColumn :=
               WARM_DETECTOR_MAP_G(warmColumn)*COLUMNS_PER_DETECTOR_G +
               WARM_COLUMN_MAP_G(warmColumn);
            ssaBiasCurrent(detectorColumn) <= currentDiff(
               columnDrive(warmColumn).ssaBias,
               SA_BIAS_LOADS_G(warmColumn));
            ssaBiasSourceResistance(detectorColumn) <=
               differentialImpedance(
                  columnDrive(warmColumn).ssaBias,
                  SA_BIAS_LOADS_G(warmColumn));
            ssaFbCurrent(detectorColumn) <= currentDiff(
               columnDrive(warmColumn).ssaFeedback,
               SA_FB_LOADS_G(warmColumn));
            sq1BiasCurrent(detectorColumn) <= currentDiff(
               columnDrive(warmColumn).sq1Bias,
               SQ1_BIAS_LOADS_G(warmColumn));
            sq1BiasSourceResistance(detectorColumn) <=
               differentialImpedance(
                  columnDrive(warmColumn).sq1Bias,
                  SQ1_BIAS_LOADS_G(warmColumn));
            sq1FbCurrent(detectorColumn) <= currentDiff(
               columnDrive(warmColumn).sq1Feedback,
               SQ1_FB_LOADS_G(warmColumn));
            columnSense(warmColumn).ssaVoltage.p <=
               0.5*ssaVoltage(detectorColumn);
            columnSense(warmColumn).ssaVoltage.n <=
               -0.5*ssaVoltage(detectorColumn);
            for row in 0 to NUM_ROWS_C-1 loop
               pixel := detectorColumn*NUM_ROWS_C + row;
               detectorTesCurrent(pixel) <= tesStimulusAmp(pixel) +
                  0.5*(columnDrive(warmColumn).tesBias.p -
                       columnDrive(warmColumn).tesBias.n)*
                  TES_CURRENT_SCALE_G;
            end loop;
         end if;
      end loop;
   end process ROUTE_COLUMNS;

   GEN_DETECTORS : for detector in 0 to NUM_DETECTORS_G-1 generate
      constant COLUMN_LOW_C : natural := detector*COLUMNS_PER_DETECTOR_G;
      constant COLUMN_HIGH_C : natural :=
         (detector+1)*COLUMNS_PER_DETECTOR_G-1;
      constant RS_LOW_C : natural := detector*ROWS_PER_BANK_G;
      constant RS_HIGH_C : natural := (detector+1)*ROWS_PER_BANK_G-1;
      constant CS_LOW_C : natural := detector*NUM_BANKS_G;
      constant CS_HIGH_C : natural := (detector+1)*NUM_BANKS_G-1;
      constant PIXEL_LOW_C : natural :=
         detector*COLUMNS_PER_DETECTOR_G*NUM_ROWS_C;
      constant PIXEL_HIGH_C : natural :=
         (detector+1)*COLUMNS_PER_DETECTOR_G*NUM_ROWS_C-1;
   begin
      U_Detector : entity warm_tdm.DetectorModuleSim
         generic map (
            NUM_COLUMNS_G     => COLUMNS_PER_DETECTOR_G,
            NUM_BANKS_G       => NUM_BANKS_G,
            ROWS_PER_BANK_G   => ROWS_PER_BANK_G,
            TWO_LEVEL_G       => TWO_LEVEL_G,
            SSA_PARAMS_G      => SSA_PARAMS_G,
            SQ1_PARAMS_G      => SQ1_PARAMS_G,
            ROW_FAS_PARAMS_G  => ROW_FAS_PARAMS_G,
            CHIP_FAS_PARAMS_G => CHIP_FAS_PARAMS_G,
            COLUMN_PARAMS_G   => COLUMN_PARAMS_G)
         port map (
            ssaBiasCurrentAmp     => ssaBiasCurrent(COLUMN_LOW_C to COLUMN_HIGH_C),
            ssaBiasSourceResistanceOhm =>
               ssaBiasSourceResistance(COLUMN_LOW_C to COLUMN_HIGH_C),
            ssaFeedbackCurrentAmp => ssaFbCurrent(COLUMN_LOW_C to COLUMN_HIGH_C),
            sq1BiasCurrentAmp     => sq1BiasCurrent(COLUMN_LOW_C to COLUMN_HIGH_C),
            sq1BiasSourceResistanceOhm =>
               sq1BiasSourceResistance(COLUMN_LOW_C to COLUMN_HIGH_C),
            sq1FeedbackCurrentAmp => sq1FbCurrent(COLUMN_LOW_C to COLUMN_HIGH_C),
            rowSelectCurrentAmp   => detectorRsCurrent(RS_LOW_C to RS_HIGH_C),
            chipSelectCurrentAmp  => detectorCsCurrent(CS_LOW_C to CS_HIGH_C),
            tesCurrentAmp         => detectorTesCurrent(PIXEL_LOW_C to PIXEL_HIGH_C),
            muxCurrentAmp         => muxCurrent(COLUMN_LOW_C to COLUMN_HIGH_C),
            muxVoltageVolt        => muxVoltage(COLUMN_LOW_C to COLUMN_HIGH_C),
            ssaPhaseCycles        => ssaPhase(COLUMN_LOW_C to COLUMN_HIGH_C),
            ssaVoltageVolt        => ssaVoltage(COLUMN_LOW_C to COLUMN_HIGH_C));
   end generate GEN_DETECTORS;

end architecture sim;
