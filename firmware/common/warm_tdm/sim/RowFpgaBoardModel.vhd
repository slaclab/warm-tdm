-------------------------------------------------------------------------------
-- Title      : Testbench for design "ColumnFpgaBoard"
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

library ruckus;
use ruckus.BuildInfoPkg.all;

library warm_tdm;

----------------------------------------------------------------------------------------------------

entity RowFpgaBoardModel is
   generic (
      TPD_G                   : time                  := 1 ns;
      RING_ADDR_0_G           : boolean               := false;
      SIM_PGP_PORT_NUM_G      : integer               := 7000;
      SIM_ETH_SRP_PORT_NUM_G  : integer               := 8000;
      SIM_ETH_DATA_PORT_NUM_G : integer               := 9000;
      NUM_ROW_SELECTS_G       : integer range 1 to 32 := 32;
      NUM_CHIP_SELECTS_G      : integer range 0 to 12  := 0);
   port (
      -- Front End Connector
      feThermistor : in    slv(1 downto 0) := "00";
      feI2cScl     : inout slv(3 downto 0);
      feI2cSda     : inout slv(3 downto 0);
      resetB       : out   sl;
      feVrSyncA    : out   sl;
      feVrSyncB    : out   sl;
      feDacMosi    : out   sl;
      feDacMiso    : in    sl;
      feDacSclk    : out   sl;
      feDacSyncB   : out   slv(2 downto 0);
      feDacLdacB   : out   slv(2 downto 0) := (others => '1');
      feDacResetB  : out   slv(2 downto 0) := (others => '1');
      rsDacP       : out   RealArray(31 downto 0);
      rsDacN       : out   RealArray(31 downto 0);

      -- RJ-45 Connectors
      rj45TimingRxClkP  : in  sl;          -- [in]
      rj45TimingRxClkN  : in  sl;          -- [in]
      rj45TimingRxDataP : in  sl;          -- [in]
      rj45TimingRxDataN : in  sl;          -- [in]
      rj45TimingRxMgtP  : in  sl;          -- [in]
      rj45TimingRxMgtN  : in  sl;          -- [in]
      rj45PgpRxMgtP     : in  sl;          -- [in]
      rj45PgpRxMgtN     : in  sl;          -- [in]
      rj45TimingTxClkP  : out sl;          -- [out]
      rj45TimingTxClkN  : out sl;          -- [out]
      rj45TimingTxDataP : out sl;          -- [out]
      rj45TimingTxDataN : out sl;          -- [out]
      rj45TimingTxMgtP  : out sl;          -- [out]
      rj45TimingTxMgtN  : out sl;          -- [out]
      rj45PgpTxMgtP     : out sl := '0';   -- [out]
      rj45PgpTxMgtN     : out sl := '0');  -- [out]


end entity RowFpgaBoardModel;

----------------------------------------------------------------------------------------------------

architecture sim of RowFpgaBoardModel is

   constant SIMULATION_G   : boolean          := true;
   constant SIMULATE_PGP_G : boolean          := false;
--    constant SIM_PGP_PORT_NUM_G      : integer               := 0;
--    constant SIM_ETH_SRP_PORT_NUM_G  : integer               := 8000;
--    constant SIM_ETH_DATA_PORT_NUM_G : integer               := 9000;
   constant BUILD_INFO_G   : BuildInfoType    := BUILD_INFO_C;
   constant ETH_10G_G      : boolean          := false;
   constant DHCP_G         : boolean          := false;
   constant IP_ADDR_G      : slv(31 downto 0) := x"0B03A8C0";
   constant MAC_ADDR_G     : slv(47 downto 0) := x"0B_00_16_56_00_08";

   signal gtRefClk0P       : sl;                                                 -- [in]
   signal gtRefClk0N       : sl;                                                 -- [in]
   signal gtRefClk1P       : sl;                                                 -- [in]
   signal gtRefClk1N       : sl;                                                 -- [in]
   signal pgpTxP           : slv(1 downto 0);                                    -- [out]
   signal pgpTxN           : slv(1 downto 0);                                    -- [out]
   signal pgpRxP           : slv(1 downto 0);                                    -- [in]
   signal pgpRxN           : slv(1 downto 0);                                    -- [in]
   signal xbarDataSel      : slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");  -- [out]
   signal xbarClkSel       : slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");  -- [out]
   signal xbarMgtSel       : slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");  -- [out]
   signal xbarTimingSel    : slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");  -- [out]
   signal timingRxClkP     : sl;                                                 -- [in]
   signal timingRxClkN     : sl;                                                 -- [in]
   signal timingRxDataP    : sl;                                                 -- [in]
   signal timingRxDataN    : sl;                                                 -- [in]
   signal timingTxClkP     : sl;                                                 -- [out]
   signal timingTxClkN     : sl;                                                 -- [out]
   signal timingTxDataP    : sl;                                                 -- [out]
   signal timingTxDataN    : sl;                                                 -- [out]
   signal sfp0TxP          : sl;                                                 -- [out]
   signal sfp0TxN          : sl;                                                 -- [out]
   signal sfp0RxP          : sl;                                                 -- [in]
   signal sfp0RxN          : sl;                                                 -- [in]
   signal bootCsL          : sl;                                                 -- [out]
   signal bootMosi         : sl;                                                 -- [out]
   signal bootMiso         : sl;                                                 -- [in]
   signal locScl           : sl;                                                 -- [inout]
   signal locSda           : sl;                                                 -- [inout]
   signal tempAlertL       : sl;                                                 -- [in]
   signal pwrScl           : sl;                                                 -- [inout]
   signal pwrSda           : sl;                                                 -- [inout]
   signal sfpScl           : slv(1 downto 0);                                    -- [inout]
   signal sfpSda           : slv(1 downto 0);                                    -- [inout]
   signal anaPwrEn         : sl              := '1';                             -- [out]
   signal pwrSyncA         : sl              := '0';                             -- [out]
   signal pwrSyncB         : sl              := '0';                             -- [out]
   signal pwrSyncC         : sl              := '1';                             -- [out]
   signal lemoIn           : slv(1 downto 0);                                    -- [in]
   signal lemoOut          : slv(1 downto 0);                                    -- [out]
   signal leds             : slv(7 downto 0) := "00000000";                      -- [out]
   signal conRxGreenLed    : sl              := '1';                             -- [out]
   signal conRxYellowLed   : sl              := '1';                             -- [out]
   signal conTxGreenLed    : sl              := '1';                             -- [out]
   signal conTxYellowLed   : sl              := '1';                             -- [out]
   signal localThermistorP : slv(5 downto 0);                                    -- [in]
   signal localThermistorN : slv(5 downto 0);                                    -- [in]
   signal ampPdB           : slv(7 downto 0) := (others => '0');                 -- [out]
   signal adcSclk          : sl;                                                 -- [out]
   signal adcSdio          : sl;                                                 -- [inout]
   signal adcCsb           : sl;                                                 -- [out]
   signal adcSync          : sl;                                                 -- [out]
   signal adcPdwn          : sl              := '1';                             -- [out]
   signal dacDb0           : slv(13 downto 0);                                   -- [out]
   signal dacDb1           : slv(13 downto 0);                                   -- [out]
   signal dacDb2           : slv(13 downto 0);                                   -- [out]
   signal dacDb3           : slv(13 downto 0);                                   -- [out]
   signal dacWrt           : slv(15 downto 0);                                   -- [out]
   signal dacClk           : slv(15 downto 0);                                   -- [out]
   signal dacSel           : slv(15 downto 0);                                   -- [out]
   signal dacReset         : slv(15 downto 0);                                   -- [out]
   signal feThermistorP    : slv(1 downto 0);                                    -- [in]
   signal feThermistorN    : slv(1 downto 0);                                    -- [in]


   -- Local signals
   signal clk     : sl;
   signal rst     : sl;
   signal adcVinP : RealArray(7 downto 0);
   signal adcVinN : RealArray(7 downto 0);
   signal adcVin  : RealArray(7 downto 0);

--    signal localTemperatureC    : RealArray(5 downto 0);
--    signal localTemperatureK    : RealArray(5 downto 0);
--    signal thermistorResistance : RealArray(5 downto 0);


begin

   U_RowFpgaBoard_2 : entity warm_tdm.RowFpgaBoard
      generic map (
         TPD_G                   => TPD_G,
         SIMULATION_G            => SIMULATION_G,
         SIMULATE_PGP_G          => SIMULATE_PGP_G,
         SIM_PGP_PORT_NUM_G      => SIM_PGP_PORT_NUM_G,
         SIM_ETH_SRP_PORT_NUM_G  => SIM_ETH_SRP_PORT_NUM_G,
         SIM_ETH_DATA_PORT_NUM_G => SIM_ETH_DATA_PORT_NUM_G,
         BUILD_INFO_G            => BUILD_INFO_G,
         RING_ADDR_0_G           => RING_ADDR_0_G,
         NUM_ROW_SELECTS_G       => NUM_ROW_SELECTS_G,
         NUM_CHIP_SELECTS_G      => NUM_CHIP_SELECTS_G,
         ETH_10G_G               => ETH_10G_G,
         DHCP_G                  => DHCP_G,
         IP_ADDR_G               => IP_ADDR_G,
         MAC_ADDR_G              => MAC_ADDR_G)
      port map (
         gtRefClk0P       => gtRefClk0P,        -- [in]
         gtRefClk0N       => gtRefClk0N,        -- [in]
         gtRefClk1P       => gtRefClk1P,        -- [in]
         gtRefClk1N       => gtRefClk1N,        -- [in]
         pgpTxP           => pgpTxP,            -- [out]
         pgpTxN           => pgpTxN,            -- [out]
         pgpRxP           => pgpRxP,            -- [in]
         pgpRxN           => pgpRxN,            -- [in]
         xbarDataSel      => xbarDataSel,       -- [out]
         xbarClkSel       => xbarClkSel,        -- [out]
         xbarMgtSel       => xbarMgtSel,        -- [out]
         xbarTimingSel    => xbarTimingSel,     -- [out]
         timingRxClkP     => timingRxClkP,      -- [in]
         timingRxClkN     => timingRxClkN,      -- [in]
         timingRxDataP    => timingRxDataP,     -- [in]
         timingRxDataN    => timingRxDataN,     -- [in]
         timingTxClkP     => timingTxClkP,      -- [out]
         timingTxClkN     => timingTxClkN,      -- [out]
         timingTxDataP    => timingTxDataP,     -- [out]
         timingTxDataN    => timingTxDataN,     -- [out]
         sfp0TxP          => sfp0TxP,           -- [out]
         sfp0TxN          => sfp0TxN,           -- [out]
         sfp0RxP          => sfp0RxP,           -- [in]
         sfp0RxN          => sfp0RxN,           -- [in]
         bootCsL          => bootCsL,           -- [out]
         bootMosi         => bootMosi,          -- [out]
         bootMiso         => bootMiso,          -- [in]
         locScl           => locScl,            -- [inout]
         locSda           => locSda,            -- [inout]
         tempAlertL       => tempAlertL,        -- [in]
         pwrScl           => pwrScl,            -- [inout]
         pwrSda           => pwrSda,            -- [inout]
         sfpScl           => sfpScl,            -- [inout]
         sfpSda           => sfpSda,            -- [inout]
         anaPwrEn         => anaPwrEn,          -- [out]
         pwrSyncA         => pwrSyncA,          -- [out]
         pwrSyncB         => pwrSyncB,          -- [out]
         pwrSyncC         => pwrSyncC,          -- [out]
         lemoIn           => lemoIn,            -- [in]
         lemoOut          => lemoOut,           -- [out]
         leds             => leds,              -- [out]
         conRxGreenLed    => conRxGreenLed,     -- [out]
         conRxYellowLed   => conRxYellowLed,    -- [out]
         conTxGreenLed    => conTxGreenLed,     -- [out]
         conTxYellowLed   => conTxYellowLed,    -- [out]
         localThermistorP => localThermistorP,  -- [in]
         localThermistorN => localThermistorN,  -- [in]
         ampPdB           => ampPdB,            -- [out]
         adcSclk          => adcSclk,           -- [out]
         adcSdio          => adcSdio,           -- [inout]
         adcCsb           => adcCsb,            -- [out]
         adcSync          => adcSync,           -- [out]
         adcPdwn          => adcPdwn,           -- [out]
         dacDb0           => dacDb0,            -- [out]
         dacDb1           => dacDb1,            -- [out]
         dacDb2           => dacDb2,            -- [out]
         dacDb3           => dacDb3,            -- [out]
         dacWrt           => dacWrt,            -- [out]
         dacClk           => dacClk,            -- [out]
         dacSel           => dacSel,            -- [out]
         dacReset         => dacReset,          -- [out]
         feThermistorP    => feThermistorP,     -- [in]
         feThermistorN    => feThermistorN,     -- [in]
         feI2cScl         => feI2cScl,          -- [inout]
         feI2cSda         => feI2cSda,          -- [inout]
         resetB           => resetB,            -- [out]
         feVrSyncA        => feVrSyncA,         -- [out]
         feVrSyncB        => feVrSyncB,         -- [out]
         feDacMosi        => feDacMosi,         -- [out]
         feDacMiso        => feDacMiso,         -- [in]
         feDacSclk        => feDacSclk,         -- [out]
         feDacSyncB       => feDacSyncB,        -- [out]
         feDacLdacB       => feDacLdacB,        -- [out]
         feDacResetB      => feDacResetB);       -- [out]


   -------------------------------------------------------------------------------------------------
   -- Front End Thermistors
   -------------------------------------------------------------------------------------------------
--    feThermistorP <= feThermistor;
--    feThermistorN <= (others => 0.0);

--    -------------------------------------------------------------------------------------------------
--    -- Board Thermistors
--    -------------------------------------------------------------------------------------------------
--    localTemperatureC <= (20.0, 21.0, 22.0, 23.0, 24.0, 25.0);
--    GEN_TEMPERATURE : for i in 5 downto 0 generate
--       localTemperatureK(i) <= localTemperatureC(i) + 273.15;
--       thermistorResistance(i) <= .03448533 * exp(3750.0/localTemperatureK(i));
--       localThermistorP(i) <= thermistorResistance(i) / (thermistorResistance(i) + 10e3);
--       localThermistorN(i) <= 0.0;
--    end generate GEN_TEMPERATURE;


   -------------------------------------------------------------------------------------------------
   -- Clocks
   -------------------------------------------------------------------------------------------------
   U_ClkRst_REFCLK_250 : entity surf.ClkRst
      generic map (
         CLK_PERIOD_G => 4.0 ns,
         CLK_DELAY_G  => 1 ns)
      port map (
         clkP => gtRefClk0P,
         clkN => gtRefClk0N);

   U_ClkRst_REFCLK_125 : entity surf.ClkRst
      generic map (
         CLK_PERIOD_G => 8.0 ns,
         CLK_DELAY_G  => 1 ns)
      port map (
         clkP => gtRefClk1P,
         clkN => gtRefClk1N);

   -------------------------------------------------------------------------------------------------
   -- Timing crossbars
   -------------------------------------------------------------------------------------------------
   rj45TimingTxDataP <= rj45TimingRxDataP when xbarDataSel(0) = '0' else timingTxDataP;
   rj45TimingTxDataN <= rj45TimingRxDataN when xbarDataSel(0) = '0' else timingTxDataN;

   timingRxDataP <= rj45TimingRxDataP when xbarDataSel(1) = '0' else timingTxDataP;
   timingRxDataN <= rj45TimingRxDataN when xbarDataSel(1) = '0' else timingTxDataN;


   rj45TimingTxClkP <= rj45TimingRxClkP when xbarClkSel(0) = '0' else timingTxClkP;
   rj45TimingTxClkN <= rj45TimingRxClkN when xbarClkSel(0) = '0' else timingTxClkN;

   timingRxClkP <= rj45TimingRxClkP when xbarClkSel(1) = '0' else timingTxClkP;
   timingRxClkN <= rj45TimingRxClkN when xbarClkSel(1) = '0' else timingTxClkN;

   -- Put PGP on timingMgt
   rj45TimingTxMgtP <= rj45TimingRxMgtP when xbarMgtSel(0) = '0' else pgpTxP(0);
   rj45TimingTxMgtN <= rj45TimingRxMgtN when xbarMgtSel(0) = '0' else pgpTxN(0);

   pgpRxP(0) <= rj45TimingRxMgtP when xbarMgtSel(1) = '0' else pgpTxP(0);
   pgpRxN(0) <= rj45TimingRxMgtN when xbarMgtSel(1) = '0' else pgpTxN(0);

   rj45PgpTxMgtP <= rj45PgpRxMgtP when xbarTimingSel(0) = '0' else pgpTxP(1);
   rj45PgpTxMgtN <= rj45PgpRxMgtN when xbarTimingSel(0) = '0' else pgpTxN(1);

   pgpRxP(1) <= rj45PgpRxMgtP when xbarTimingSel(1) = '0' else pgpTxP(1);
   pgpRxN(1) <= rj45PgpRxMgtN when xbarTimingSel(1) = '0' else pgpTxN(1);

   -------------------------------------------------------------------------------------------------
   -- Clock and reset for things that need it
   -------------------------------------------------------------------------------------------------
   U_ClkRst_1 : entity surf.ClkRst
      generic map (
         CLK_PERIOD_G => 10 ns,
         SYNC_RESET_G => true)
      port map (
         clkP => clk,                   -- [out]
         rst  => rst);                  -- [out]

   -------------------------------------------------------------------------------------------------
   -- 24LC64FT
   -------------------------------------------------------------------------------------------------
   locSda <= 'H';
   locScl <= 'H';
   U_i2cRamSlave_EEPROM : entity surf.i2cRamSlave
      generic map (
         TPD_G        => TPD_G,
         I2C_ADDR_G   => 64+16,
         TENBIT_G     => 0,
         FILTER_G     => 2,
         ADDR_SIZE_G  => 2,
         DATA_SIZE_G  => 1,
         ENDIANNESS_G => 1)
      port map (
         clk    => clk,                 -- [in]
         rst    => rst,                 -- [in]
         i2cSda => locSda,              -- [inout]
         i2cScl => locScl);             -- [inout]

   -------------------------------------------------------------------------------------------------
   -- SA56004EDP
   -------------------------------------------------------------------------------------------------
   U_i2cRamSlave_SA5600EDP : entity surf.i2cRamSlave
      generic map (
         TPD_G        => TPD_G,
         I2C_ADDR_G   => 64+8+4,
         TENBIT_G     => 0,
         FILTER_G     => 2,
         ADDR_SIZE_G  => 1,
         DATA_SIZE_G  => 1,
         ENDIANNESS_G => 1)
      port map (
         clk    => clk,                 -- [in]
         rst    => rst,                 -- [in]
         i2cSda => locSda,              -- [inout]
         i2cScl => locScl);             -- [inout]

   -------------------------------------------------------------------------------------------------
   -- LTC4151
   -------------------------------------------------------------------------------------------------
   pwrSda <= 'H';
   pwrScl <= 'H';
   U_i2cRamSlave_LTC4151_DIG : entity surf.i2cRamSlave
      generic map (
         TPD_G        => TPD_G,
         I2C_ADDR_G   => 64+32+8+4+2+1,
         TENBIT_G     => 0,
         FILTER_G     => 2,
         ADDR_SIZE_G  => 1,
         DATA_SIZE_G  => 1,
         ENDIANNESS_G => 1)
      port map (
         clk    => clk,                 -- [in]
         rst    => rst,                 -- [in]
         i2cSda => pwrSda,              -- [inout]
         i2cScl => pwrScl);             -- [inout]

   U_i2cRamSlave_LTC4151_ANA : entity surf.i2cRamSlave
      generic map (
         TPD_G        => TPD_G,
         I2C_ADDR_G   => 64+32+8+4,
         TENBIT_G     => 0,
         FILTER_G     => 2,
         ADDR_SIZE_G  => 1,
         DATA_SIZE_G  => 1,
         ENDIANNESS_G => 1)
      port map (
         clk    => clk,                 -- [in]
         rst    => rst,                 -- [in]
         i2cSda => pwrSda,              -- [inout]
         i2cScl => pwrScl);             -- [inout]


   -------------------------------------------------------------------------------------------------
   -- SFP
   -------------------------------------------------------------------------------------------------
   sfpScl <= "HH";
   sfpSda <= "HH";



   -------------------------------------------------------------------------------------------------
   -- Fast Dacs
   -------------------------------------------------------------------------------------------------
   GEN_FAST_DACS : for i in 3 downto 0 generate

      U_Ad9767_SA_FB : entity warm_tdm.Ad9767
         generic map (
            FSADJ1_G => 2.0e3,
            FSADJ2_G => 2.0e3)
         port map (
            db     => dacDb0,           -- [in]
            iqsel  => dacSel(i),        -- [in]
            iqwrt  => dacWrt(i),        -- [in]
            iqclk  => dacClk(i),        -- [in]
            iOut1A => rsDacP(2*i),      -- [out]
            iOut1B => rsDacN(2*i),      -- [out]
            iOut2A => rsDacP(2*i+1),    -- [out]
            iOut2B => rsDacN(2*i+1));   -- [out]

      U_Ad9767_SQ1_BIAS : entity warm_tdm.Ad9767
         generic map (
            FSADJ1_G => 2.0e3,
            FSADJ2_G => 2.0e3)
         port map (
            db     => dacDb1,           -- [in]
            iqsel  => dacSel(i+4),      -- [in]
            iqwrt  => dacWrt(i+4),      -- [in]
            iqclk  => dacClk(i+4),      -- [in]
            iOut1A => rsDacP(2*i+8),    -- [out]
            iOut1B => rsDacN(2*i+8),    -- [out]
            iOut2A => rsDacP(2*i+9),    -- [out]
            iOut2B => rsDacN(2*i+9));   -- [out]

      U_Ad9767_SQ1_FB : entity warm_tdm.Ad9767
         generic map (
            FSADJ1_G => 2.0e3,
            FSADJ2_G => 2.0e3)
         port map (
            db     => dacDb2,           -- [in]
            iqsel  => dacSel(i+8),      -- [in]
            iqwrt  => dacWrt(i+8),      -- [in]
            iqclk  => dacClk(i+8),      -- [in]
            iOut1A => rsDacP(2*i+16),   -- [out]
            iOut1B => rsDacN(2*i+16),   -- [out]
            iOut2A => rsDacP(2*i+17),   -- [out]
            iOut2B => rsDacN(2*i+17));  -- [out]

      U_Ad9767_AUX : entity warm_tdm.Ad9767
         generic map (
            FSADJ1_G => 2.0e3,
            FSADJ2_G => 2.0e3)
         port map (
            db     => dacDb3,           -- [in]
            iqsel  => dacSel(i+12),     -- [in]
            iqwrt  => dacWrt(i+12),     -- [in]
            iqclk  => dacClk(i+12),     -- [in]
            iOut1A => rsDacP(2*i+24),   -- [out]
            iOut1B => rsDacN(2*i+24),   -- [out]
            iOut2A => rsDacP(2*i+25),   -- [out]
            iOut2B => rsDacN(2*i+25));  -- [out]

   end generate;

end architecture sim;

----------------------------------------------------------------------------------------------------
