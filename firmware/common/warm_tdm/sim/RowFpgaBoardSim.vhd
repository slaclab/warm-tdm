-------------------------------------------------------------------------------
-- Title      : 
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Simulation of Row FPGA board, Row FEB and Load board
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

entity RowFpgaBoardSim is
   generic (
      TPD_G                   : time                  := 1 ns;
      RING_ADDR_0_G           : boolean               := false;
      SIM_PGP_PORT_NUM_G      : integer               := 7000;
      SIM_ETH_SRP_PORT_NUM_G  : integer               := 8000;
      SIM_ETH_DATA_PORT_NUM_G : integer               := 9000;
      NUM_WAFERS_G            : integer range 1 to 2  := 1;
      NUM_ROW_SELECTS_G       : integer range 1 to 32 := 32;
      NUM_CHIP_SELECTS_G      : integer range 0 to 12 := 0);

   port (
      rsP : out CurrentArray(31 downto 0);
      rsN : out CurrentArray(31 downto 0);

      -- component ports
      rj45TimingRxClkP  : in  sl;
      rj45TimingRxClkN  : in  sl;
      rj45TimingRxDataP : in  sl;
      rj45TimingRxDataN : in  sl;
      rj45TimingTxClkP  : out sl;
      rj45TimingTxClkN  : out sl;
      rj45TimingTxDataP : out sl;
      rj45TimingTxDataN : out sl);

end entity RowFpgaBoardSim;

architecture sim of RowFpgaBoardSim is

   signal feThermistor : slv(1 downto 0) := "00";
   signal feI2cScl     : slv(3 downto 0);
   signal feI2cSda     : slv(3 downto 0);
   signal resetB       : sl;
   signal fePwrSyncA   : sl;
   signal fePwrSyncB   : sl;
   signal feDacMosi    : sl;
   signal feDacMiso    : sl;
   signal feDacSclk    : sl;
   signal feDacSyncB   : slv(2 downto 0);
   signal feDacLdacB   : slv(2 downto 0) := "111";
   signal feDacResetB  : slv(2 downto 0) := "111";
   signal rsDacP       : RealArray(31 downto 0);
   signal rsDacN       : RealArray(31 downto 0);



begin

   U_RowFpgaBoardModel : entity warm_tdm.RowFpgaBoardModel
      generic map (
         TPD_G                   => TPD_G,
         RING_ADDR_0_G           => RING_ADDR_0_G,
         SIM_PGP_PORT_NUM_G      => SIM_PGP_PORT_NUM_G,
         SIM_ETH_SRP_PORT_NUM_G  => SIM_ETH_SRP_PORT_NUM_G,
         SIM_ETH_DATA_PORT_NUM_G => SIM_ETH_DATA_PORT_NUM_G,
         NUM_WAFERS_G            => NUM_WAFERS_G,
         NUM_ROW_SELECTS_G       => NUM_ROW_SELECTS_G,
         NUM_CHIP_SELECTS_G      => NUM_CHIP_SELECTS_G)
      port map (
         feThermistor      => feThermistor,
         feI2cScl          => feI2cScl,
         feI2cSda          => feI2cSda,
         resetB            => resetB,
         fePwrSyncA        => fePwrSyncA,
         fePwrSyncB        => fePwrSyncB,
         feDacMosi         => feDacMosi,
         feDacMiso         => feDacMiso,
         feDacSclk         => feDacSclk,
         feDacSyncB        => feDacSyncB,
         feDacLdacB        => feDacLdacB,
         feDacResetB       => feDacResetB,
         rsDacP            => rsDacP,
         rsDacN            => rsDacN,
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

   U_RowFebModel_1 : entity warm_tdm.RowFebModel
      generic map (
         TPD_G => TPD_G)
      port map (
         -- FEB Connector
         feThermistor => feThermistor,  -- [out]
         feI2cScl     => feI2cScl,      -- [inout]
         feI2cSda     => feI2cSda,      -- [inout]
         resetB       => resetB,        -- [in]
         fePwrSyncA   => fePwrSyncA,    -- [in]
         fePwrSyncB   => fePwrSyncB,    -- [in]
         feDacMosi    => feDacMosi,     -- [in]
         feDacMiso    => feDacMiso,     -- [out]
         feDacSclk    => feDacSclk,     -- [in]
         feDacSyncB   => feDacSyncB,    -- [in]
         feDacLdacB   => feDacLdacB,    -- [in]
         feDacResetB  => feDacResetB,   -- [in]
         rsDacP       => rsDacP,        -- [in]
         rsDacN       => rsDacN,        -- [in]
         -- CRYO connector
         rsP          => rsP,           -- [out]
         rsN          => rsN);          -- [out]



end architecture sim;
