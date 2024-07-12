-------------------------------------------------------------------------------
-- Title      : Testbench for design "ColumnModuleBoard"
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
----------------------------------------------------------------------------------------------------

entity ColumnFpgaBoardTb is

end entity ColumnFpgaBoardTb;

----------------------------------------------------------------------------------------------------

architecture sim of ColumnFpgaBoardTb is

   -- component generics
   constant TPD_G                : time    := 1 ns;
   constant NUM_COLUMN_MODULES_C : integer := 1;

   -- component ports
   signal rj45TimingClkP  : slv(NUM_COLUMN_MODULES_C-1 downto 0);  -- [in]
   signal rj45TimingClkN  : slv(NUM_COLUMN_MODULES_C-1 downto 0);  -- [in]
   signal rj45TimingDataP : slv(NUM_COLUMN_MODULES_C-1 downto 0);  -- [in]
   signal rj45TimingDataN : slv(NUM_COLUMN_MODULES_C-1 downto 0);  -- [in]

   type RealArray8Array is array (natural range <>) of RealArray(7 downto 0);

   signal feThermistor : Slv2Array(NUM_COLUMN_MODULES_C-1 downto 0) := (others => (others => "00"));
   signal feI2cScl     : Slv4Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal feI2cSda     : Slv4Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal resetB       : slv(NUM_COLUMN_MODULES_C-1 downto 0);
   signal feVrSyncA    : slv(NUM_COLUMN_MODULES_C-1 downto 0);
   signal feVrSyncB    : slv(NUM_COLUMN_MODULES_C-1 downto 0);
   signal feDacMosi    : slv(NUM_COLUMN_MODULES_C-1 downto 0);
   signal feDacMiso    : slv(NUM_COLUMN_MODULES_C-1 downto 0);
   signal feDacSclk    : slv(NUM_COLUMN_MODULES_C-1 downto 0);
   signal feDacSyncB   : slv3Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal feDacLdacB   : slv3Array(NUM_COLUMN_MODULES_C-1 downto 0) := (others => (others => '1'));
   signal feDacResetB  : slv3Array(NUM_COLUMN_MODULES_C-1 downto 0) := (others => (others => '1'));
   signal tesDelatch   : slv8Array(NUM_COLUMN_MODULES_C-1 downto 0) := (others => (others => '0'));
   signal saFbDacP     : RealArray8Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal saFbDacN     : RealArray8Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal sq1FbDacP    : RealArray8Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal sq1FbDacN    : RealArray8Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal sq1BiasDacP  : RealArray8Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal sq1BiasDacN  : RealArray8Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal auxDacP      : RealArray8Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal auxDacN      : RealArray8Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal saOutP       : RealArray8Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal saOutN       : RealArray8Array(NUM_COLUMN_MODULES_C-1 downto 0);

   type CurrentArray8Array is array (natural range <>) of CurrentArray(7 downto 0);

   signal tesBiasP   : RealArray8Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal tesBiasN   : RealArray8Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal saBiasOutP : CurrentArray8Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal saBiasOutN : CurrentArray8Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal saBiasInP  : RealArray8Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal saBiasInN  : RealArray8Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal saFbP      : CurrentArray8Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal saFbN      : CurrentArray8Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal sq1BiasP   : CurrentArray8Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal sq1BiasN   : CurrentArray8Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal sq1FbP     : CurrentArray8Array(NUM_COLUMN_MODULES_C-1 downto 0);
   signal sq1FbN     : CurrentArray8Array(NUM_COLUMN_MODULES_C-1 downto 0);

begin

   -- component instantiation
   ColumnModGen : for i in 0 to NUM_COLUMN_MODULES_C-1 generate
      U_ColumnFpgaBoard : entity warm_tdm.ColumnFpgaBoardModel
         generic map (
            TPD_G                   => TPD_G,
            RING_ADDR_0_G           => (i = 0),
            SIM_PGP_PORT_NUM_G      => 7000,  --7000 + (10*i),
            SIM_ETH_SRP_PORT_NUM_G  => 10000 + (1000*i),
            SIM_ETH_DATA_PORT_NUM_G => 20000 + (1000*i))
         port map (
            feThermistor      => feThermistor(i),
            feI2cScl          => feI2cScl(i),
            feI2cSda          => feI2cSda(i),
            resetB            => resetB(i),
            feVrSyncA         => feVrSyncA(i),
            feVrSyncB         => feVrSyncB(i),
            feDacMosi         => feDacMosi(i),
            feDacMiso         => feDacMiso(i),
            feDacSclk         => feDacSclk(i),
            feDacSyncB        => feDacSyncB(i),
            feDacLdacB        => feDacLdacB(i),
            feDacResetB       => feDacResetB(i),
            tesDelatch        => tesDelatch(i),
            saFbDacP          => saFbDacP(i),
            saFbDacN          => saFbDacN(i),
            sq1FbDacP         => sq1FbDacP(i),
            sq1FbDacN         => sq1FbDacN(i),
            sq1BiasDacP       => sq1BiasDacP(i),
            sq1BiasDacN       => sq1BiasDacN(i),
            auxDacP           => auxDacP(i),
            auxDacN           => auxDacN(i),
            saOutP            => saOutP(i),
            saOutN            => saOutN(i),
            rj45TimingRxClkP  => rj45TimingClkP(ite(i = 0, NUM_COLUMN_MODULES_C-1, i-1)),   -- [in]
            rj45TimingRxClkN  => rj45TimingClkN(ite(i = 0, NUM_COLUMN_MODULES_C-1, i-1)),   -- [in]
            rj45TimingRxDataP => rj45TimingDataP(ite(i = 0, NUM_COLUMN_MODULES_C-1, i-1)),  -- [in]
            rj45TimingRxDataN => rj45TimingDataN(ite(i = 0, NUM_COLUMN_MODULES_C-1, i-1)),  -- [in]
            rj45TimingTxClkP  => rj45TimingClkP(i),                                         -- [out]
            rj45TimingTxClkN  => rj45TimingClkN(i),                                         -- [out]
            rj45TimingTxDataP => rj45TimingDataP(i),                                        -- [out]
            rj45TimingTxDataN => rj45TimingDataN(i));                                       -- [out]

      U_ColumnReadoutFebModel_1 : entity warm_tdm.ColumnReadoutFebModel
         generic map (
            TPD_G => TPD_G)
         port map (
            -- FEB Connector
            feThermistor => feThermistor(i),  -- [out]
            feI2cScl     => feI2cScl(i),      -- [inout]
            feI2cSda     => feI2cSda(i),      -- [inout]
            resetB       => resetB(i),        -- [in]
            feVrSyncA    => feVrSyncA(i),     -- [in]
            feVrSyncB    => feVrSyncB(i),     -- [in]
            feDacMosi    => feDacMosi(i),     -- [in]
            feDacMiso    => feDacMiso(i),     -- [out]
            feDacSclk    => feDacSclk(i),     -- [in]
            feDacSyncB   => feDacSyncB(i),    -- [in]
            feDacLdacB   => feDacLdacB(i),    -- [in]
            feDacResetB  => feDacResetB(i),   -- [in]
            tesDelatch   => tesDelatch(i),    -- [in]
            saFbDacP     => saFbDacP(i),      -- [in]
            saFbDacN     => saFbDacN(i),      -- [in]
            sq1FbDacP    => sq1FbDacP(i),     -- [in]
            sq1FbDacN    => sq1FbDacN(i),     -- [in]
            sq1BiasDacP  => sq1BiasDacP(i),   -- [in]
            sq1BiasDacN  => sq1BiasDacN(i),   -- [in]
            auxDacP      => auxDacP(i),       -- [in]
            auxDacN      => auxDacN(i),       -- [in]
            saSigOutP    => saSigOutP(i),     -- [out]
            saSigOutN    => saSigOutN(i),     -- [out]
            -- CRYO connector
            tesBiasP     => tesBiasP(i),      -- [out]
            tesBiasN     => tesBiasN(i),      -- [out]
            saBiasOutP   => saBiasOutP(i),    -- [out]
            saBiasOutN   => saBiasOutN(i),    -- [out]
            saBiasInP    => saBiasInP(i),     -- [in]
            saBiasInN    => saBiasInN(i),     -- [in]
            saFbP        => saFbP(i),         -- [out]
            saFbN        => saFbN(i),         -- [out]
            sq1BiasP     => sq1BiasP(i),      -- [out]
            sq1BiasN     => sq1BiasN(i),      -- [out]
            sq1FbP       => sq1FbP(i),        -- [out]
            sq1FbN       => sq1FbN(i));       -- [out]

      U_ColumnLoadBoard_1 : entity warm_tdm.ColumnLoadBoard
--         generic map (
--             SA_BIAS_LOADS_G  => SA_BIAS_LOADS_G,
--             SA_FB_LOADS_G    => SA_FB_LOADS_G,
--             SQ1_BIAS_LOADS_G => SQ1_BIAS_LOADS_G,
--             SQ1_FB_LOADS_G   => SQ1_FB_LOADS_G)
         port map (
            tesBiasP   => tesBiasP(i),    -- [in]
            tesBiasN   => tesBiasN(i),    -- [in]
            saBiasOutP => saBiasOutP(i),  -- [in]
            saBiasOutN => saBiasOutN(i),  -- [in]
            saBiasInP  => saBiasInP(i),   -- [out]
            saBiasInN  => saBiasInN(i),   -- [out]
            saFbP      => saFbP(i),       -- [in]
            saFbN      => saFbN(i),       -- [in]
            sq1BiasP   => sq1BiasP(i),    -- [in]
            sq1BiasN   => sq1BiasN(i),    -- [in]
            sq1FbP     => sq1FbP(i),      -- [in]
            sq1FbN     => sq1FbN(i));     -- [in]
   end generate ColumnModGen;


end architecture sim;

----------------------------------------------------------------------------------------------------
