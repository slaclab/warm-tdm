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

entity ColumnFpgaBoardModel is
   generic (
      TPD_G                   : time                  := 1 ns;
      RING_ADDR_0_G           : boolean               := false;
      SIM_PGP_PORT_NUM_G      : integer               := 7000;
      SIM_ETH_SRP_PORT_NUM_G  : integer               := 8000;
      SIM_ETH_DATA_PORT_NUM_G : integer               := 9000;
      ADC_R_GAIN_G            : RealArray(7 downto 0) := (others => 4.99e3);
      ADC_R_FB_G              : RealArray(7 downto 0) := (others => 4.99e3));
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
      tesDelatch   : out   slv(7 downto 0) := (others => '0');
      saFbDacP     : out   RealArray(7 downto 0);
      saFbDacN     : out   RealArray(7 downto 0);
      sq1FbDacP    : out   RealArray(7 downto 0);
      sq1FbDacN    : out   RealArray(7 downto 0);
      sq1BiasDacP  : out   RealArray(7 downto 0);
      sq1BiasDacN  : out   RealArray(7 downto 0);
      auxDacP      : out   RealArray(7 downto 0);
      auxDacN      : out   RealArray(7 downto 0);
      saOutP       : in    RealArray(7 downto 0);
      saOutN       : in    RealArray(7 downto 0);


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


end entity ColumnFpgaBoardModel;

----------------------------------------------------------------------------------------------------

architecture sim of ColumnFpgaBoardModel is

   -- component generics
   constant SIMULATION_G : boolean       := true;
   constant BUILD_INFO_G : BuildInfoType := BUILD_INFO_C;

   constant ETH_10G_G  : boolean          := false;
   constant DHCP_G     : boolean          := true;
   constant IP_ADDR_G  : slv(31 downto 0) := x"0A01A8C0";
   constant MAC_ADDR_G : slv(47 downto 0) := x"0B_00_16_56_00_08";

   -- FPGA IO to Board
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
   signal pwrSyncA         : sl;                                                 -- [out]
   signal pwrSyncB         : sl;                                                 -- [out]
   signal pwrSyncC         : sl;                                                 -- [out]
   signal lemoIn           : slv(1 downto 0);                                    -- [in]
   signal lemoOut          : slv(1 downto 0);                                    -- [out]
   signal leds             : slv(7 downto 0) := "00000000";                      -- [out]
   signal conRxGreenLed    : sl              := '1';                             -- [out]
   signal conRxYellowLed   : sl              := '1';                             -- [out]
   signal conTxGreenLed    : sl              := '1';                             -- [out]
   signal conTxYellowLed   : sl              := '1';                             -- [out]
   signal localThermistorP : slv(5 downto 0);                                    -- [in]
   signal localThermistorN : slv(5 downto 0);                                    -- [in]
   signal ampPdB           : slv(7 downto 0) := (others => '1');                 -- [out]
   signal adcFClkP         : slv(1 downto 0);                                    -- [in]
   signal adcFClkN         : slv(1 downto 0);                                    -- [in]
   signal adcDClkP         : slv(1 downto 0);                                    -- [in]
   signal adcDClkN         : slv(1 downto 0);                                    -- [in]
   signal adcChP           : slv8Array(1 downto 0);                              -- [in]
   signal adcChN           : slv8Array(1 downto 0);                              -- [in]
   signal adcClkP          : sl;                                                 -- [out]
   signal adcClkN          : sl;                                                 -- [out]
   signal adcSclk          : sl;                                                 -- [out]
   signal adcSdio          : sl;                                                 -- [inout]
   signal adcCsb           : sl;                                                 -- [out]
   signal adcSync          : sl;                                                 -- [out]
   signal sq1BiasDb        : slv(13 downto 0);                                   -- [out]
   signal sq1BiasWrt       : slv(3 downto 0);                                    -- [out]
   signal sq1BiasClk       : slv(3 downto 0);                                    -- [out]
   signal sq1BiasSel       : slv(3 downto 0);                                    -- [out]
   signal sq1BiasReset     : slv(3 downto 0);                                    -- [out]
   signal sq1FbDb          : slv(13 downto 0);                                   -- [out]
   signal sq1FbWrt         : slv(3 downto 0);                                    -- [out]
   signal sq1FbClk         : slv(3 downto 0);                                    -- [out]
   signal sq1FbSel         : slv(3 downto 0);                                    -- [out]
   signal sq1FbReset       : slv(3 downto 0);                                    -- [out]
   signal saFbDb           : slv(13 downto 0);                                   -- [out]
   signal saFbWrt          : slv(3 downto 0);                                    -- [out]
   signal saFbClk          : slv(3 downto 0);                                    -- [out]
   signal saFbSel          : slv(3 downto 0);                                    -- [out]
   signal saFbReset        : slv(3 downto 0);                                    -- [out]
   signal auxDb            : slv(13 downto 0);                                   -- [out]
   signal auxWrt           : slv(3 downto 0);                                    -- [out]
   signal auxClk           : slv(3 downto 0);                                    -- [out]
   signal auxSel           : slv(3 downto 0);                                    -- [out]
   signal auxReset         : slv(3 downto 0);                                    -- [out]
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

   U_ColumnFpgaBoard_1 : entity warm_tdm.ColumnFpgaBoard
      generic map (
         TPD_G                   => TPD_G,
         SIMULATION_G            => SIMULATION_G,
         SIMULATE_PGP_G          => false,
         SIM_PGP_PORT_NUM_G      => SIM_PGP_PORT_NUM_G,
         SIM_ETH_SRP_PORT_NUM_G  => SIM_ETH_SRP_PORT_NUM_G,
         SIM_ETH_DATA_PORT_NUM_G => SIM_ETH_DATA_PORT_NUM_G,
         BUILD_INFO_G            => BUILD_INFO_G,
         RING_ADDR_0_G           => RING_ADDR_0_G,
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
         adcFClkP         => adcFClkP,          -- [in]
         adcFClkN         => adcFClkN,          -- [in]
         adcDClkP         => adcDClkP,          -- [in]
         adcDClkN         => adcDClkN,          -- [in]
         adcChP           => adcChP,            -- [in]
         adcChN           => adcChN,            -- [in]
         adcClkP          => adcClkP,           -- [out]
         adcClkN          => adcClkN,           -- [out]
         adcSclk          => adcSclk,           -- [out]
         adcSdio          => adcSdio,           -- [inout]
         adcCsb           => adcCsb,            -- [out]
         adcSync          => adcSync,           -- [out]
         sq1BiasDb        => sq1BiasDb,         -- [out]
         sq1BiasWrt       => sq1BiasWrt,        -- [out]
         sq1BiasClk       => sq1BiasClk,        -- [out]
         sq1BiasSel       => sq1BiasSel,        -- [out]
         sq1BiasReset     => sq1BiasReset,      -- [out]
         sq1FbDb          => sq1FbDb,           -- [out]
         sq1FbWrt         => sq1FbWrt,          -- [out]
         sq1FbClk         => sq1FbClk,          -- [out]
         sq1FbSel         => sq1FbSel,          -- [out]
         sq1FbReset       => sq1FbReset,        -- [out]
         saFbDb           => saFbDb,            -- [out]
         saFbWrt          => saFbWrt,           -- [out]
         saFbClk          => saFbClk,           -- [out]
         saFbSel          => saFbSel,           -- [out]
         saFbReset        => saFbReset,         -- [out]
         auxDb            => auxDb,             -- [out]
         auxWrt           => auxWrt,            -- [out]
         auxClk           => auxClk,            -- [out]
         auxSel           => auxSel,            -- [out]
         auxReset         => auxReset,          -- [out]         
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
         feDacResetB      => feDacResetB,       -- [out]
         tesDelatch       => tesDelatch);       -- [out]

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
   U_ClkRst_REFCLK_312 : entity surf.ClkRst
      generic map (
         CLK_PERIOD_G => 3.2 ns,
         CLK_DELAY_G  => 1 ns)
      port map (
         clkP => gtRefClk0P,
         clkN => gtRefClk0N);

   U_ClkRst_REFCLK_250 : entity surf.ClkRst
      generic map (
         CLK_PERIOD_G => 4 ns,
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
   -- ADC Amplifiers
   -------------------------------------------------------------------------------------------------
   GEN_ADC_AMPS : for i in 7 downto 0 generate
      U_AdcAda4932_1 : entity warm_tdm.AdcAda4932
         generic map (
            TPD_G    => TPD_G,
            R_GAIN_G => ADC_R_GAIN_G(i),
            R_FB_G   => ADC_R_FB_G(i))
         port map (
            ainP  => saOutP(i),         -- [in]
            ainN  => saOutN(i),         -- [in]
            vocm  => 0.9,               -- [in]
            aoutP => adcVinP(i),        -- [out]
            aoutN => adcVinN(i));       -- [out]

      adcVin(i) <= adcVinP(i) - adcVinN(i);
   end generate GEN_ADC_AMPS;

   ---------------------------------------
   -- AD9681 ADC
   ---------------------------------------
   U_Ad9681_1 : entity surf.Ad9681
      generic map (
         TPD_G => TPD_G)
      port map (
         clkP => adcClkP,               -- [in]
         clkN => adcClkN,               -- [in]
         vin  => adcVin,                -- [in]
         dP   => adcChP,                -- [out]
         dN   => adcChN,                -- [out]
         dcoP => adcDClkP,              -- [out]
         dcoN => adcDClkN,              -- [out]
         fcoP => adcFClkP,              -- [out]
         fcoN => adcFClkN,              -- [out]
         sclk => adcSclk,               -- [in]
         sdio => adcSdio,               -- [inout]
         csb  => adcCsb);               -- [in]

   adcSclk <= 'H';
   adcSdio <= 'H';
   adcCsb  <= 'H';


   -------------------------------------------------------------------------------------------------
   -- Fast Dacs
   -------------------------------------------------------------------------------------------------
   GEN_FAST_DACS : for i in 3 downto 0 generate

      U_Ad9767_SA_FB : entity warm_tdm.Ad9767
         generic map (
            FSADJ1_G => 2.0e3,
            FSADJ2_G => 2.0e3)
         port map (
            db     => saFbDb,            -- [in]
            iqsel  => saFbSel(i),        -- [in]
            iqwrt  => saFbWrt(i),        -- [in]
            iqclk  => saFbClk(i),        -- [in]
            iOut1A => saFbDacP(2*i),     -- [out]
            iOut1B => saFbDacN(2*i),     -- [out]
            iOut2A => saFbDacP(2*i+1),   -- [out]
            iOut2B => saFbDacN(2*i+1));  -- [out]

      U_Ad9767_SQ1_BIAS : entity warm_tdm.Ad9767
         generic map (
            FSADJ1_G => 2.0e3,
            FSADJ2_G => 2.0e3)
         port map (
            db     => sq1BiasDb,            -- [in]
            iqsel  => sq1BiasSel(i),        -- [in]
            iqwrt  => sq1BiasWrt(i),        -- [in]
            iqclk  => sq1BiasClk(i),        -- [in]
            iOut1A => sq1BiasDacP(2*i),     -- [out]
            iOut1B => sq1BiasDacN(2*i),     -- [out]
            iOut2A => sq1BiasDacP(2*i+1),   -- [out]
            iOut2B => sq1BiasDacN(2*i+1));  -- [out]

      U_Ad9767_SQ1_FB : entity warm_tdm.Ad9767
         generic map (
            FSADJ1_G => 2.0e3,
            FSADJ2_G => 2.0e3)
         port map (
            db     => sq1FbDb,            -- [in]
            iqsel  => sq1FbSel(i),        -- [in]
            iqwrt  => sq1FbWrt(i),        -- [in]
            iqclk  => sq1FbClk(i),        -- [in]
            iOut1A => sq1FbDacP(2*i),     -- [out]
            iOut1B => sq1FbDacN(2*i),     -- [out]
            iOut2A => sq1FbDacP(2*i+1),   -- [out]
            iOut2B => sq1FbDacN(2*i+1));  -- [out]

      U_Ad9767_AUX : entity warm_tdm.Ad9767
         generic map (
            FSADJ1_G => 2.0e3,
            FSADJ2_G => 2.0e3)
         port map (
            db     => auxDb,            -- [in]
            iqsel  => auxSel(i),        -- [in]
            iqwrt  => auxWrt(i),        -- [in]
            iqclk  => auxClk(i),        -- [in]
            iOut1A => auxDacP(2*i),     -- [out]
            iOut1B => auxDacN(2*i),     -- [out]
            iOut2A => auxDacP(2*i+1),   -- [out]
            iOut2B => auxDacN(2*i+1));  -- [out]

   end generate;

end architecture sim;

----------------------------------------------------------------------------------------------------
