-------------------------------------------------------------------------------
-- Title      : Column Readout Front End Board Model
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

entity ColumnReadoutFebModel is

   generic (
      TPD_G : time := 1 ns);

   port (
      -- FEB Connector
      feThermistor : out   slv(1 downto 0) := "00";
      feI2cScl     : inout slv(3 downto 0);
      feI2cSda     : inout slv(3 downto 0);
      resetB       : in    sl;
      feVrSyncA    : in    sl;
      feVrSyncB    : in    sl;
      feDacMosi    : in    sl;
      feDacMiso    : out   sl;
      feDacSclk    : in    sl;
      feDacSyncB   : in    slv(2 downto 0);
      feDacLdacB   : in    slv(2 downto 0) := (others => '1');
      feDacResetB  : in    slv(2 downto 0) := (others => '1');
      tesDelatch   : in    slv(7 downto 0) := (others => '0');
      saFbDacP     : in    RealArray(7 downto 0);
      saFbDacN     : in    RealArray(7 downto 0);
      sq1FbDacP    : in    RealArray(7 downto 0);
      sq1FbDacN    : in    RealArray(7 downto 0);
      sq1BiasDacP  : in    RealArray(7 downto 0);
      sq1BiasDacN  : in    RealArray(7 downto 0);
      auxDacP      : in    RealArray(7 downto 0);
      auxDacN      : in    RealArray(7 downto 0);
      saSigOutP    : out   RealArray(7 downto 0);
      saSigOutN    : out   RealArray(7 downto 0);

      -- CRYO Connector
      tesBiasP   : out RealArray(7 downto 0);
      tesBiasN   : out RealArray(7 downto 0);
      saBiasOutP : out CurrentArray(7 downto 0);
      saBiasOutN : out CurrentArray(7 downto 0);
      saBiasInP  : in  RealArray(7 downto 0);
      saBiasInN  : in  RealArray(7 downto 0);
      saFbP      : out CurrentArray(7 downto 0);
      saFbN      : out CurrentArray(7 downto 0);
      sq1BiasP   : out CurrentArray(7 downto 0);
      sq1BiasN   : out CurrentArray(7 downto 0);
      sq1FbP     : out CurrentArray(7 downto 0);
      sq1FbN     : out CurrentArray(7 downto 0));



end entity ColumnReadoutFebModel;

architecture sim of ColumnReadoutFebModel is

   signal saOffsetDacP : RealArray(7 downto 0);
   signal saOffsetDacN : RealArray(7 downto 0);
   signal saBiasDacP   : RealArray(7 downto 0);
   signal saBiasDacN   : RealArray(7 downto 0);
   signal tesBiasDacP  : RealArray(7 downto 0);
   signal tesBiasDacN  : RealArray(7 downto 0);

begin

   U_Ad5679R_SA_OFFSET : entity warm_tdm.Ad5679R
      generic map (
         TPD_G => TPD_G)
      port map (
         sclk     => feDacSclk,         -- [in]
         sdi      => feDacMosi,         -- [in]
         sdo      => feDacMiso,         -- [out]
         syncB    => feDacSyncB(2),     -- [in]
         ldacB    => feDacLdacB(2),     -- [in]
         resetB   => feDacResetB(2),    -- [in]
         vout(0)  => saOffsetDacP(0),   -- [out]
         vout(1)  => saOffsetDacN(0),   -- [out]
         vout(2)  => saOffsetDacP(1),   -- [out]
         vout(3)  => saOffsetDacN(1),   -- [out]
         vout(4)  => saOffsetDacP(2),   -- [out]
         vout(5)  => saOffsetDacN(2),   -- [out]
         vout(6)  => saOffsetDacP(3),   -- [out]
         vout(7)  => saOffsetDacN(3),   -- [out]         
         vout(8)  => saOffsetDacP(4),   -- [out]
         vout(9)  => saOffsetDacN(4),   -- [out]
         vout(10) => saOffsetDacP(5),   -- [out]
         vout(11) => saOffsetDacN(5),   -- [out]
         vout(12) => saOffsetDacP(6),   -- [out]
         vout(13) => saOffsetDacN(6),   -- [out]
         vout(14) => saOffsetDacP(7),   -- [out]
         vout(15) => saOffsetDacN(7));  -- [out]         

   U_Ad5679R_SA_BIAS : entity warm_tdm.Ad5679R
      generic map (
         TPD_G => TPD_G)
      port map (
         sclk     => feDacSclk,         -- [in]
         sdi      => feDacMosi,         -- [in]
         sdo      => feDacMiso,         -- [out]
         syncB    => feDacSyncB(1),     -- [in]
         ldacB    => feDacLdacB(1),     -- [in]
         resetB   => feDacResetB(1),    -- [in]
         vout(0)  => saBiasDacP(0),     -- [out]
         vout(1)  => saBiasDacN(0),     -- [out]
         vout(2)  => saBiasDacP(1),     -- [out]
         vout(3)  => saBiasDacN(1),     -- [out]
         vout(4)  => saBiasDacP(2),     -- [out]
         vout(5)  => saBiasDacN(2),     -- [out]
         vout(6)  => saBiasDacP(3),     -- [out]
         vout(7)  => saBiasDacN(3),     -- [out]         
         vout(8)  => saBiasDacP(4),     -- [out]
         vout(9)  => saBiasDacN(4),     -- [out]
         vout(10) => saBiasDacP(5),     -- [out]
         vout(11) => saBiasDacN(5),     -- [out]
         vout(12) => saBiasDacP(6),     -- [out]
         vout(13) => saBiasDacN(6),     -- [out]
         vout(14) => saBiasDacP(7),     -- [out]
         vout(15) => saBiasDacN(7));    -- [out]         


   U_Ad5679R_TES_BIAS : entity warm_tdm.Ad5679R
      generic map (
         TPD_G => TPD_G)
      port map (
         sclk     => feDacSclk,         -- [in]
         sdi      => feDacMosi,         -- [in]
         sdo      => feDacMiso,         -- [out]
         syncB    => feDacSyncB(0),     -- [in]
         ldacB    => feDacLdacB(0),     -- [in]
         resetB   => feDacResetB(0),    -- [in]
         vout(0)  => tesBiasDacP(0),    -- [out]
         vout(1)  => tesBiasDacN(0),    -- [out]
         vout(2)  => tesBiasDacP(1),    -- [out]
         vout(3)  => tesBiasDacN(1),    -- [out]
         vout(4)  => tesBiasDacP(2),    -- [out]
         vout(5)  => tesBiasDacN(2),    -- [out]
         vout(6)  => tesBiasDacP(3),    -- [out]
         vout(7)  => tesBiasDacN(3),    -- [out]         
         vout(8)  => tesBiasDacP(4),    -- [out]
         vout(9)  => tesBiasDacN(4),    -- [out]
         vout(10) => tesBiasDacP(5),    -- [out]
         vout(11) => tesBiasDacN(5),    -- [out]
         vout(12) => tesBiasDacP(6),    -- [out]
         vout(13) => tesBiasDacN(6),    -- [out]
         vout(14) => tesBiasDacP(7),    -- [out]
         vout(15) => tesBiasDacN(7));   -- [out]         

   GEN_CHANNELS : for i in 7 downto 0 generate

      -- SA Bias Amp Model
      U_ColumnFebSaBiasAmp_1 : entity warm_tdm.ColumnFebSaBiasAmp
         generic map (
            STAGE_1_RG_G      => 40.2,
            STAGE_1_RFB_G     => 100.0,
            STAGE_2_RGND_G    => 21.0,
            STAGE_2_ROFFSET_G => 402.0,
            STAGE_2_RFB_G     => 100.0)
         port map (
            saOffsetDacP => saOffsetDacP(i),  -- [in]
            saOffsetDacN => saOffsetDacN(i),  -- [in]
            saBiasDacP   => saBiasDacP(i),    -- [in]
            saBiasDacN   => saBiasDacN(i),    -- [in]
            saBiasOutP   => saBiasOutP(i),    -- [out]
            saBiasOutN   => saBiasOutN(i),    -- [out]
            saBiasInP    => saBiasInP(i),     -- [in]
            saBiasInN    => saBiasInN(i),     -- [in]
            saSigOutP    => saSigOutP(i),     -- [out]
            saSigOutN    => saSigOutN(i));    -- [out]


      -- TES Bias Amp Model
      -- Output is swapped on schematic
      U_ColumnFebTesBiasAmp_1 : entity warm_tdm.ColumnFebTesBiasAmp
         port map (
            tesBiasDacP => tesBiasDacP(i),  -- [in]
            tesBiasDacN => tesBiasDacN(i),  -- [in]
            delatch     => tesDelatch(i),   -- [in]
            tesBiasP    => tesBiasN(i),     -- [out]
            tesBiasN    => tesBiasP(i));    -- [out]

      -- SA FB Amp Model
      U_ColumnFebFastDacAmp_SA_FB : entity warm_tdm.ColumnFebFastDacAmp
         generic map (
--             IN_LOAD_R_G => IN_LOAD_R_G,
--             FB_R_G      => FB_R_G,
--             GAIN_R_G    => GAIN_R_G,
            SHUNT_R_G => 3.48e3)
         port map (
            dacP => saFbDacP(i),        -- [in]
            dacN => saFbDacN(i),        -- [in]
            outP => saFbP(i),           -- [out]
            outN => saFbN(i));          -- [out]

      -- SQ1 Bias Amp Model
      U_ColumnFebFastDacAmp_SQ1_BIAS : entity warm_tdm.ColumnFebFastDacAmp
         generic map (
--             IN_LOAD_R_G => IN_LOAD_R_G,
--             FB_R_G      => FB_R_G,
--             GAIN_R_G    => GAIN_R_G,
            SHUNT_R_G => 4.99e3)
         port map (
            dacP => sq1BiasDacP(i),     -- [in]
            dacN => sq1BiasDacN(i),     -- [in]
            outP => sq1BiasP(i),        -- [out]
            outN => sq1BiasN(i));       -- [out]

      -- SQ1 FB Amp Model
      U_ColumnFebFastDacAmp_SQ1_FB : entity warm_tdm.ColumnFebFastDacAmp
         generic map (
--             IN_LOAD_R_G => IN_LOAD_R_G,
--             FB_R_G      => FB_R_G,
--             GAIN_R_G    => GAIN_R_G,
            SHUNT_R_G => 1.00e3)
         port map (
            dacP => sq1FbDacP(i),       -- [in]
            dacN => sq1FbDacN(i),       -- [in]
            outP => sq1FbP(i),          -- [out]
            outN => sq1FbN(i));         -- [out]


   end generate GEN_CHANNELS;

end architecture sim;
