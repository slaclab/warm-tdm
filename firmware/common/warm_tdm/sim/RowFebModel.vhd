-------------------------------------------------------------------------------
-- Title      : Row Readout Front End Board Model
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

entity RowFebModel is

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
      rsDacP       : in    RealArray(31 downto 0);
      rsDacN       : in    RealArray(31 downto 0);

      -- CRYO Connector
      rsP : out CurrentArray(31 downto 0);
      rsN : out CurrentArray(31 downto 0));

end entity RowFebModel;

architecture sim of RowFebModel is


begin

   GEN_CHANNELS : for i in 31 downto 0 generate

      U_ColumnFebFastDacAmp_SA_FB : entity warm_tdm.RowFebFastDacAmp
         generic map (
--             IN_LOAD_R_G => IN_LOAD_R_G,
--             FB_R_G      => FB_R_G,
--             GAIN_R_G    => GAIN_R_G,
            SHUNT_R_G => 1.00e3)
         port map (
            dacP => rsDacP(i),          -- [in]
            dacN => rsDacN(i),          -- [in]
            outP => rsP(i),             -- [out]
            outN => rsN(i));            -- [out]

   end generate GEN_CHANNELS;

end architecture sim;
