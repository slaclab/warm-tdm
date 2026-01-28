-------------------------------------------------------------------------------
-- Title      : 
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Simulation of Column FPGA board, Column FEB and Load board
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

entity ColumnFpgaBoardSim is
   generic (
      TPD_G                   : time                  := 1 ns;
      RING_ADDR_0_G           : boolean               := false;
      SIM_PGP_PORT_NUM_G      : integer               := 7000;
      SIM_ETH_SRP_PORT_NUM_G  : integer               := 8000;
      SIM_ETH_DATA_PORT_NUM_G : integer               := 9000;
      AWAXE_G                 : boolean               := false;
      ADC_R_GAIN_G            : RealArray(7 downto 0) := (others => 1.00e3);
      ADC_R_FB_G              : RealArray(7 downto 0) := (others => 3.66e3));

   port (
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
      sq1FbN     : out CurrentArray(7 downto 0);

      -- component ports
      rj45TimingRxClkP  : in  sl;
      rj45TimingRxClkN  : in  sl;
      rj45TimingRxDataP : in  sl;
      rj45TimingRxDataN : in  sl;
      rj45TimingTxClkP  : out sl;
      rj45TimingTxClkN  : out sl;
      rj45TimingTxDataP : out sl;
      rj45TimingTxDataN : out sl);

end entity ColumnFpgaBoardSim;

architecture sim of ColumnFpgaBoardSim is

   signal feThermistor : slv(1 downto 0) := "00";
   signal feI2cScl     : slv(3 downto 0);
   signal feI2cSda     : slv(3 downto 0);
   signal resetB       : sl;
   signal feVrSyncA    : sl;
   signal feVrSyncB    : sl;
   signal feDacMosi    : sl;
   signal feDacMiso    : sl;
   signal feDacSclk    : sl;
   signal feDacSyncB   : slv(2 downto 0);
   signal feDacLdacB   : slv(2 downto 0) := "111";
   signal feDacResetB  : slv(2 downto 0) := "111";
   signal tesDelatch   : slv(7 downto 0) := (others => '0');
   signal saFbDacP     : RealArray(7 downto 0);
   signal saFbDacN     : RealArray(7 downto 0);
   signal sq1FbDacP    : RealArray(7 downto 0);
   signal sq1FbDacN    : RealArray(7 downto 0);
   signal sq1BiasDacP  : RealArray(7 downto 0);
   signal sq1BiasDacN  : RealArray(7 downto 0);
   signal auxDacP      : RealArray(7 downto 0);
   signal auxDacN      : RealArray(7 downto 0);
   signal saOutP       : RealArray(7 downto 0);
   signal saOutN       : RealArray(7 downto 0);

begin

   U_ColumnFpgaBoard : entity warm_tdm.ColumnFpgaBoardModel
      generic map (
         TPD_G                   => TPD_G,
         RING_ADDR_0_G           => RING_ADDR_0_G,
         SIM_PGP_PORT_NUM_G      => SIM_PGP_PORT_NUM_G,
         SIM_ETH_SRP_PORT_NUM_G  => SIM_ETH_SRP_PORT_NUM_G,
         SIM_ETH_DATA_PORT_NUM_G => SIM_ETH_DATA_PORT_NUM_G)
      port map (
         feThermistor      => feThermistor,
         feI2cScl          => feI2cScl,
         feI2cSda          => feI2cSda,
         resetB            => resetB,
         feVrSyncA         => feVrSyncA,
         feVrSyncB         => feVrSyncB,
         feDacMosi         => feDacMosi,
         feDacMiso         => feDacMiso,
         feDacSclk         => feDacSclk,
         feDacSyncB        => feDacSyncB,
         feDacLdacB        => feDacLdacB,
         feDacResetB       => feDacResetB,
         tesDelatch        => tesDelatch,
         saFbDacP          => saFbDacP,
         saFbDacN          => saFbDacN,
         sq1FbDacP         => sq1FbDacP,
         sq1FbDacN         => sq1FbDacN,
         sq1BiasDacP       => sq1BiasDacP,
         sq1BiasDacN       => sq1BiasDacN,
         auxDacP           => auxDacP,
         auxDacN           => auxDacN,
         saOutP            => saOutP,
         saOutN            => saOutN,
         rj45TimingRxClkP  => rj45TimingRxClkP,   -- [in]
         rj45TimingRxClkN  => rj45TimingRxClkN,   -- [in]
         rj45TimingRxDataP => rj45TimingRxDataP,  -- [in]
         rj45TimingRxDataN => rj45TimingRxDataN,  -- [in] 
         rj45TimingRxMgtP  => '0',  -- TODO: connect this to something?                   -- [in]
         rj45TimingRxMgtN  => '1',  -- TODO: connect this to something?                   -- [in]
         rj45PgpRxMgtP     => '0',  -- TODO: connect this to something?                   -- [in]
         rj45PgpRxMgtN     => '1',  -- TODO: connect this to something?                   -- [in]
         rj45TimingTxClkP  => rj45TimingTxClkP,   -- [out]
         rj45TimingTxClkN  => rj45TimingTxClkN,   -- [out]
         rj45TimingTxDataP => rj45TimingTxDataP,  -- [out]
         rj45TimingTxDataN => rj45TimingTxDataN,  -- [out]
         rj45TimingTxMgtP  => open,     -- [out]
         rj45TimingTxMgtN  => open,     -- [out]
         rj45PgpTxMgtP     => open,     -- [out]
         rj45PgpTxMgtN     => open);    -- [out]

   U_ColumnReadoutFebModel_1 : entity warm_tdm.ColumnReadoutFebModel
      generic map (
         TPD_G   => TPD_G,
         AWAXE_G => AWAXE_G)
      port map (
         -- FEB Connector
         feThermistor => feThermistor,  -- [out]
         feI2cScl     => feI2cScl,      -- [inout]
         feI2cSda     => feI2cSda,      -- [inout]
         resetB       => resetB,        -- [in]
         feVrSyncA    => feVrSyncA,     -- [in]
         feVrSyncB    => feVrSyncB,     -- [in]
         feDacMosi    => feDacMosi,     -- [in]
         feDacMiso    => feDacMiso,     -- [out]
         feDacSclk    => feDacSclk,     -- [in]
         feDacSyncB   => feDacSyncB,    -- [in]
         feDacLdacB   => feDacLdacB,    -- [in]
         feDacResetB  => feDacResetB,   -- [in]
         tesDelatch   => tesDelatch,    -- [in]
         saFbDacP     => saFbDacP,      -- [in]
         saFbDacN     => saFbDacN,      -- [in]
         sq1FbDacP    => sq1FbDacP,     -- [in]
         sq1FbDacN    => sq1FbDacN,     -- [in]
         sq1BiasDacP  => sq1BiasDacP,   -- [in]
         sq1BiasDacN  => sq1BiasDacN,   -- [in]
         auxDacP      => auxDacP,       -- [in]
         auxDacN      => auxDacN,       -- [in]
         saSigOutP    => saOutP,        -- [out]
         saSigOutN    => saOutN,        -- [out]
         -- CRYO connector
         tesBiasP     => tesBiasP,      -- [out]
         tesBiasN     => tesBiasN,      -- [out]
         saBiasOutP   => saBiasOutP,    -- [out]
         saBiasOutN   => saBiasOutN,    -- [out]
         saBiasInP    => saBiasInP,     -- [in]
         saBiasInN    => saBiasInN,     -- [in]
         saFbP        => saFbP,         -- [out]
         saFbN        => saFbN,         -- [out]
         sq1BiasP     => sq1BiasP,      -- [out]
         sq1BiasN     => sq1BiasN,      -- [out]
         sq1FbP       => sq1FbP,        -- [out]
         sq1FbN       => sq1FbN);       -- [out]




end architecture sim;
