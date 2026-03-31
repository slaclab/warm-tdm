-------------------------------------------------------------------------------
-- Title      : 
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: 
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

entity WaferSim is

   generic (
      SA_BIAS_LOADS_G  : RealArray(7 downto 0)  := (others => 200.0);
      SA_FB_LOADS_G    : RealArray(7 downto 0)  := (others => 200.0);
      SQ1_BIAS_LOADS_G : RealArray(7 downto 0)  := (others => 200.0);
      SQ1_FB_LOADS_G   : RealArray(7 downto 0)  := (others => 200.0);
      RS_LOADS_G       : RealArray(31 downto 0) := (others => 200.0);

      NUM_ROWS_G : integer range 1 to 32 := 4;
      R_SHUNT_G  : real                  := 1.0;

      SSA_RN_G     : real := 14.0;
      SSA_IC0_G    : real := 55.0e-6;
      SSA_PHINOT_G : real := 35.0e-6;

      SQ1_RN_G     : real := 14.0;
      SQ1_IC0_G    : real := 20.0e-6;
      SQ1_PHINOT_G : real := 10.0e-6;

      RS_RN_G     : real := 14.0;
      RS_IC0_G    : real := 20.0e-6;
      RS_PHINOT_G : real := 300.0e-6
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
      rsN        : in  CurrentArray(31 downto 0));


end entity WaferSim;

architecture sim of WaferSim is

   signal saBiasCurrent  : RealArray(7 downto 0);
   signal saFbCurrent    : RealArray(7 downto 0);
   signal sq1BiasCurrent : RealArray(7 downto 0);
   signal sq1FbCurrent   : RealArray(7 downto 0);
   signal rsCurrent      : RealArray(31 downto 0);
   signal vOut           : RealArray(7 downto 0);
   signal rEff           : RealArray(7 downto 0);

begin

   GEN_RS_CURRENT : for i in 31 downto 0 generate
      rsCurrent(i) <= currentDiff(rsP(i), rsN(i), RS_LOADS_G(i));
   end generate;


   GEN_COLUMNS : for i in 7 downto 0 generate
      saBiasCurrent(i)  <= currentDiff(saBiasOutP(i), saBiasOutN(i), SA_BIAS_LOADS_G(i));
      saFbCurrent(i)    <= currentDiff(saFbP(i), saFbN(i), SA_FB_LOADS_G(i));
      sq1BiasCurrent(i) <= currentDiff(sq1BiasP(i), sq1BiasN(i), SQ1_BIAS_LOADS_G(i));
      sq1FbCurrent(i)   <= currentDiff(sq1FbP(i), sq1FbN(i), SQ1_FB_LOADS_G(i));

      U_SquidColumn_1 : entity warm_tdm.SquidColumn
         generic map (
            NUM_ROWS_G   => NUM_ROWS_G,
            R_SHUNT_G    => R_SHUNT_G,
            SSA_RN_G     => SSA_RN_G,
            SSA_IC0_G    => SSA_IC0_G,
            SSA_PHINOT_G => SSA_PHINOT_G,
            SQ1_RN_G     => SQ1_RN_G,
            SQ1_IC0_G    => SQ1_IC0_G,
            SQ1_PHINOT_G => SQ1_PHINOT_G,
            RS_RN_G      => RS_RN_G,
            RS_IC0_G     => RS_IC0_G,
            RS_PHINOT_G  => RS_PHINOT_G)
         port map (
            ssaBias => saBiasCurrent(i),   -- [in]
            ssaFb   => saFbCurrent(i),     -- [in]
            sq1Bias => sq1BiasCurrent(i),  -- [in]
            sq1Fb   => sq1FbCurrent(i),    -- [in]
            iRs     => rsCurrent,          -- [in]
            rEff    => rEff(i),            -- [out]
            vOut    => vOut(i));           -- [out]

      saBiasInP(i) <= saBiasCurrent(i) * (rEff(i) + SA_BIAS_LOADS_G(i));
      saBiasInN(i) <= 0.0;
   end generate;


end architecture sim;

