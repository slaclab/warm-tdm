-------------------------------------------------------------------------------
-- Title      : Legacy WaferSim Interface Compatibility Testbench
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

library surf;
use surf.StdRtlPkg.all;

library warm_tdm;
use warm_tdm.SimPkg.all;

entity WaferCompatibilityTb is
end entity WaferCompatibilityTb;

architecture sim of WaferCompatibilityTb is

   constant ZERO_SOURCE_C : CurrentType := (
      voltage   => 0.0,
      impedance => 0.5);

   signal tesBiasP   : RealArray(7 downto 0) := (others => 0.0);
   signal tesBiasN   : RealArray(7 downto 0) := (others => 0.0);
   signal saBiasOutP : CurrentArray(7 downto 0) := (others => ZERO_SOURCE_C);
   signal saBiasOutN : CurrentArray(7 downto 0) := (others => ZERO_SOURCE_C);
   signal saBiasInP  : RealArray(7 downto 0);
   signal saBiasInN  : RealArray(7 downto 0);
   signal saFbP      : CurrentArray(7 downto 0) := (others => ZERO_SOURCE_C);
   signal saFbN      : CurrentArray(7 downto 0) := (others => ZERO_SOURCE_C);
   signal sq1BiasP   : CurrentArray(7 downto 0) := (others => ZERO_SOURCE_C);
   signal sq1BiasN   : CurrentArray(7 downto 0) := (others => ZERO_SOURCE_C);
   signal sq1FbP     : CurrentArray(7 downto 0) := (others => ZERO_SOURCE_C);
   signal sq1FbN     : CurrentArray(7 downto 0) := (others => ZERO_SOURCE_C);
   signal rsP        : CurrentArray(31 downto 0) := (others => ZERO_SOURCE_C);
   signal rsN        : CurrentArray(31 downto 0) := (others => ZERO_SOURCE_C);
   signal tesStimulus : RealArray(0 to 31) := (others => 0.0);

begin

   U_Dut : entity warm_tdm.WaferSim
      generic map (
         SA_BIAS_LOADS_G  => (others => 0.0),
         SA_FB_LOADS_G    => (others => 0.0),
         SQ1_BIAS_LOADS_G => (others => 0.0),
         SQ1_FB_LOADS_G   => (others => 0.0),
         RS_LOADS_G       => (others => 0.0),
         NUM_ROWS_G       => 4,
         NUM_BANKS_G      => 2,
         ROWS_PER_BANK_G  => 2,
         TWO_LEVEL_G      => true,
         RS_LINE_OFFSET_G => 0,
         CS_LINE_OFFSET_G => 2,
         SSA_RN_G         => 8.0,
         SSA_IC0_G        => 40.0E-6,
         SSA_PHINOT_G     => 20.0E-6,
         SQ1_RN_G         => 4.0,
         SQ1_IC0_G        => 10.0E-6,
         SQ1_PHINOT_G     => 8.0E-6,
         RS_RN_G          => 6.0,
         RS_IC0_G         => 12.0E-6,
         RS_PHINOT_G      => 100.0E-6,
         CS_RN_G          => 10.0,
         CS_IC0_G         => 14.0E-6,
         CS_PHINOT_G      => 200.0E-6)
      port map (
         tesBiasP   => tesBiasP,
         tesBiasN   => tesBiasN,
         saBiasOutP => saBiasOutP,
         saBiasOutN => saBiasOutN,
         saBiasInP  => saBiasInP,
         saBiasInN  => saBiasInN,
         saFbP      => saFbP,
         saFbN      => saFbN,
         sq1BiasP   => sq1BiasP,
         sq1BiasN   => sq1BiasN,
         sq1FbP     => sq1FbP,
         sq1FbN     => sq1FbN,
         rsP        => rsP,
         rsN        => rsN,
         tesStimulusAmp => tesStimulus);

   test : process is
      variable rowOnlyVoltage  : real;
      variable selectedVoltage : real;
   begin
      saBiasOutP(0).voltage <= 60.0E-6;
      sq1BiasP(0).voltage   <= 10.0E-6;
      rsP(0).voltage        <= 50.0E-6;
      wait for 1 ns;

      assert saBiasInP(0) = saBiasInP(0) and saBiasInN(0) = saBiasInN(0)
         report "WaferSim compatibility output is non-finite"
         severity failure;
      assert abs(saBiasInP(0) + saBiasInN(0)) < 1.0E-15
         report "WaferSim compatibility output is not differential"
         severity failure;

      rowOnlyVoltage := saBiasInP(0) - saBiasInN(0);
      rsP(2).voltage <= 100.0E-6;
      wait for 1 ns;
      selectedVoltage := saBiasInP(0) - saBiasInN(0);
      assert abs(selectedVoltage - rowOnlyVoltage) > 1.0E-9
         report "WaferSim did not map the chip-select line into its two-level MUX"
         severity failure;

      tesStimulus(0) <= 4.0E-6;
      wait for 1 ns;
      rowOnlyVoltage := selectedVoltage;
      selectedVoltage := saBiasInP(0) - saBiasInN(0);
      assert abs(selectedVoltage - rowOnlyVoltage) > 1.0E-9
         report "WaferSim did not couple a selected per-pixel TES stimulus"
         severity failure;

      saFbP(0).voltage <= 5.0E-6;
      wait for 1 ns;
      assert abs((saBiasInP(0) - saBiasInN(0)) - selectedVoltage) > 1.0E-9
         report "SSA feedback did not change the compatibility output"
         severity failure;

      report "WaferCompatibilityTb PASSED" severity note;
      stop;
      wait;
   end process test;

end architecture sim;
