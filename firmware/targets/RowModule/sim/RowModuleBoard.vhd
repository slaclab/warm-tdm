-------------------------------------------------------------------------------
-- Title      : Testbench for design "RowModule"
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

entity RowModuleBoard is
   generic (
      TPD_G                   : time    := 1 ns;
      RING_ADDR_0_G           : boolean := false;
      SIM_PGP_PORT_NUM_G      : integer := 7000;
      SIM_ETH_SRP_PORT_NUM_G  : integer := 8000;
      SIM_ETH_DATA_PORT_NUM_G : integer := 9000;
      R_DAC_LOAD_G            : real    := 24.9;
      AMP_GAIN_G              : real    := (4.02+1.00);
      R_SHUNT_G               : real    := 1.0e3;
      R_CABLE_G               : real    := 200.0);
   );
   port (
      rj45TimingRxClkP  : in  sl;          -- [in]
      rj45TimingRxClkN  : in  sl;          -- [in]
      rj45TimingRxDataP : in  sl;          -- [in]
      rj45TimingRxDataN : in  sl;          -- [in]
      rj45TimingRxMgtP  : in  sl;          -- [in]
      rj45TimingRxMgtN  : in  sl;          -- [in]
      rj45PgpRxP        : in  sl;          -- [in]
      rj45PgpRxN        : in  sl;          -- [in]
      rj45TimingTxClkP  : out sl;          -- [out]
      rj45TimingTxClkN  : out sl;          -- [out]
      rj45TimingTxDataP : out sl;          -- [out]
      rj45TimingTxDataN : out sl;          -- [out]
      rj45TimingTxMgtP  : out sl;          -- [out]
      rj45TimingTxMgtN  : out sl;          -- [out]
      rj45PgpTxP        : out sl := '0';   -- [out]
      rj45PgpTxN        : out sl := '0');  -- [out]


end entity RowModuleBoard;

----------------------------------------------------------------------------------------------------

architecture sim of RowModuleBoard is

   -- component generics
   constant SIMULATION_G : boolean       := true;
   constant BUILD_INFO_G : BuildInfoType := BUILD_INFO_C;

   constant ETH_10G_G : boolean          := false;
   constant DHCP_G    : boolean          := true;
   constant IP_ADDR_G : slv(31 downto 0) := x"0B01A8C0";


   signal gtRefClk0P     : sl;                                                 -- [in]
   signal gtRefClk0N     : sl;                                                 -- [in]
   signal gtRefClk1P     : sl;                                                 -- [in]
   signal gtRefClk1N     : sl;                                                 -- [in]
   signal pgpTxP         : slv(1 downto 0);                                    -- [out]
   signal pgpTxN         : slv(1 downto 0);                                    -- [out]
   signal pgpRxP         : slv(1 downto 0);                                    -- [in]
   signal pgpRxN         : slv(1 downto 0);                                    -- [in]
   signal xbarDataSel    : slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");  -- [out]
   signal xbarClkSel     : slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");  -- [out]
   signal xbarMgtSel     : slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");  -- [out]
   signal xbarTimingSel  : slv(1 downto 0) := ite(RING_ADDR_0_G, "11", "00");  -- [out]
   signal timingRxClkP   : sl;                                                 -- [in]
   signal timingRxClkN   : sl;                                                 -- [in]
   signal timingRxDataP  : sl;                                                 -- [in]
   signal timingRxDataN  : sl;                                                 -- [in]
   signal timingTxClkP   : sl;                                                 -- [out]
   signal timingTxClkN   : sl;                                                 -- [out]
   signal timingTxDataP  : sl;                                                 -- [out]
   signal timingTxDataN  : sl;                                                 -- [out]
   signal sfp0TxP        : sl;                                                 -- [out]
   signal sfp0TxN        : sl;                                                 -- [out]
   signal sfp0RxP        : sl;                                                 -- [in]
   signal sfp0RxN        : sl;                                                 -- [in]
   signal bootCsL        : sl;                                                 -- [out]
   signal bootMosi       : sl;                                                 -- [out]
   signal bootMiso       : sl;                                                 -- [in]
   signal promScl        : sl;                                                 -- [inout]
   signal promSda        : sl;                                                 -- [inout]
   signal pwrScl         : sl;                                                 -- [inout]
   signal pwrSda         : sl;                                                 -- [inout]
   signal leds           : slv(7 downto 0) := "00000000";                      -- [out]
   signal conRxGreenLed  : sl              := '1';                             -- [out]
   signal conRxYellowLed : sl              := '1';                             -- [out]
   signal conTxGreenLed  : sl              := '1';                             -- [out]
   signal conTxYellowLed : sl              := '1';                             -- [out]
   signal vAuxP          : slv(3 downto 0);                                    -- [in]
   signal vAuxN          : slv(3 downto 0);                                    -- [in]
   signal dacDb          : slv(13 downto 0);                                   -- [out]
   signal dacWrt         : slv(15 downto 0);                                   -- [out]
   signal dacClk         : slv(15 downto 0);                                   -- [out]
   signal dacSel         : slv(15 downto 0);                                   -- [out]
   signal dacReset       : slv(15 downto 0);                                   -- [out]

   -- Local signals
   signal clk : sl;
   signal rst : sl;

   signal iOut1A : RealArray(15 downto 0);
   signal iOut1B : RealArray(15 downto 0);
   signal iOut2A : RealArray(15 downto 0);
   signal iOut2B : RealArray(15 downto 0);

   signal fasCurrent : RealArray(31 downto 0);

begin

   -------------------------------------------------------------------------------------------------
   -- FPGA
   -------------------------------------------------------------------------------------------------
   U_RowModule_1 : entity warm_tdm.RowModule
      generic map (
         TPD_G                   => TPD_G,
         SIMULATION_G            => SIMULATION_G,
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
         gtRefClk0P     => gtRefClk0P,      -- [in]
         gtRefClk0N     => gtRefClk0N,      -- [in]
         gtRefClk1P     => gtRefClk1P,      -- [in]
         gtRefClk1N     => gtRefClk1N,      -- [in]
         pgpTxP         => pgpTxP,          -- [out]
         pgpTxN         => pgpTxN,          -- [out]
         pgpRxP         => pgpRxP,          -- [in]
         pgpRxN         => pgpRxN,          -- [in]
         xbarDataSel    => xbarDataSel,     -- [out]
         xbarClkSel     => xbarClkSel,      -- [out]
         xbarMgtSel     => xbarMgtSel,      -- [out]
         xbarTimingSel  => xbarTimingSel,   -- [out]
         timingRxClkP   => timingRxClkP,    -- [in]
         timingRxClkN   => timingRxClkN,    -- [in]
         timingRxDataP  => timingRxDataP,   -- [in]
         timingRxDataN  => timingRxDataN,   -- [in]
         timingTxClkP   => timingTxClkP,    -- [out]
         timingTxClkN   => timingTxClkN,    -- [out]
         timingTxDataP  => timingTxDataP,   -- [out]
         timingTxDataN  => timingTxDataN,   -- [out]
         sfp0TxP        => sfp0TxP,         -- [out]
         sfp0TxN        => sfp0TxN,         -- [out]
         sfp0RxP        => sfp0RxP,         -- [in]
         sfp0RxN        => sfp0RxN,         -- [in]
         bootCsL        => bootCsL,         -- [out]
         bootMosi       => bootMosi,        -- [out]
         bootMiso       => bootMiso,        -- [in]
         promScl        => promScl,         -- [inout]
         promSda        => promSda,         -- [inout]
         pwrScl         => pwrScl,          -- [inout]
         pwrSda         => pwrSda,          -- [inout]
         leds           => leds,            -- [out]
         conRxGreenLed  => conRxGreenLed,   -- [out]
         conRxYellowLed => conRxYellowLed,  -- [out]
         conTxGreenLed  => conTxGreenLed,   -- [out]
         conTxYellowLed => conTxYellowLed,  -- [out]
         vAuxP          => vAuxP,           -- [in]
         vAuxN          => vAuxN,           -- [in]
         dacDb          => dacDb,           -- [out]
         dacWrt         => dacWrt,          -- [out]
         dacClk         => dacClk,          -- [out]
         dacSel         => dacSel,          -- [out]
         dacReset       => dacReset);       -- [out]

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
   rj45PgpTxP <= rj45PgpRxMgtP when xbarMgtSel(0) = '0' else pgpTxP(0);
   rj45PgpTxN <= rj45PgpRxMgtN when xbarMgtSel(0) = '0' else pgpTxN(0);

   pgpRxP(0) <= rj45PgpRxMgtP when xbarMgtSel(1) = '0' else pgpTxP(0);
   pgpRxN(0) <= rj45PgpRxMgtN when xbarMgtSel(1) = '0' else pgpTxN(0);

   rj45TimingTxMgtP <= rj45TimingRxMgtP when xbarTimingSel(0) = '0' else pgpTxP(1);
   rj45TimingTxMgtN <= rj45TimingRxMgtN when xbarTimingSel(0) = '0' else pgpTxN(1);

   pgpRxP(1) <= rj45TimingRxMgtP when xbarTimingSel(1) = '0' else pgpTxP(1);
   pgpRxN(1) <= rj45TimingRxMgtN when xbarTimingSel(1) = '0' else pgpTxN(1);


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
   promSda <= 'H';
   promScl <= 'H';
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
         i2cSda => promSda,             -- [inout]
         i2cScl => promScl);            -- [inout]


   -------------------------------------------------------------------------------------------------
   -- SA56004atk
   -------------------------------------------------------------------------------------------------
   pwrSda <= 'H';
   pwrScl <= 'H';
   U_i2cRamSlave_PWR : entity surf.i2cRamSlave
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
         i2cSda => pwrSda,              -- [inout]
         i2cScl => pwrScl);             -- [inout]

   ------------------------------------------------
   -- AD9106 Array
   ------------------------------------------------
   AD9106_GEN : for i in 15 downto 0 generate

      U_Ad9767_1 : entity warm_tdm.Ad9767
         generic map (
            FSADJ1_G => 2.0e3,
            FSADJ2_G => 2.0e3)
         port map (
            db      => dacDb,           -- [in]
            iqsel   => dacSel(i),       -- [in]
            iqwrt   => dacWrt(i),       -- [in]
            iqclk   => dacClk(i),       -- [in]
            iqreset => dacReset(i),     -- [in]
            iOut1A  => iOut1A(i),       -- [out]
            iOut1B  => iOut1B(i),       -- [out]
            iOut2A  => iOut2A(i),       -- [out]
            iOut2B  => iOut2B(i));      -- [out]
   end generate;

   -------------------------------------------------------------------------------------------------
   -- Differential drivers on DAC0
   -------------------------------------------------------------------------------------------------
   U_RowSelectDiffAmp_1 : entity warm_tdm.RowSelectDiffAmp
      generic map (
         R_DAC_LOAD_G => R_DAC_LOAD_G,
         AMP_GAIN_G   => AMP_GAIN_G,
         R_SHUNT_G    => R_SHUNT_G,
         R_CABLE_G    => R_CABLE_G)
      port map (
         iInP => iOut1A(0),             -- [in]
         iInN => iOut1B(0),             -- [in]
         iOut => fasCurrent(0));        -- [out]

   U_RowSelectDiffAmp_2 : entity warm_tdm.RowSelectDiffAmp
      generic map (
         R_DAC_LOAD_G => R_DAC_LOAD_G,
         AMP_GAIN_G   => AMP_GAIN_G,
         R_SHUNT_G    => R_SHUNT_G,
         R_CABLE_G    => R_CABLE_G)
      port map (
         iInP => iOut2A(0),             -- [in]
         iInN => iOut2B(0),             -- [in]
         iOut => fasCurrent(1));        -- [out]

   -------------------------------------------------------------------------------------------------
   -- Single ended drivers on DAC1 - DAC15
   -------------------------------------------------------------------------------------------------
   SE_AMPS : for i in 15 downto 1 generate
      U_RowSelectAmp_1 : entity warm_tdm.RowSelectAmp
         generic map (
            R_DAC_LOAD_G => R_DAC_LOAD_G,
            AMP_GAIN_G   => AMP_GAIN_G,
            R_SHUNT_G    => R_SHUNT_G,
            R_CABLE_G    => R_CABLE_G)
         port map (
            iInP => iOut1A(i),          -- [in]
            iInN => iOut1B(i),          -- [in]
            iOut => fasCurrent(i*2));

      U_RowSelectAmp_2 : entity warm_tdm.RowSelectAmp
         generic map (
            R_DAC_LOAD_G => R_DAC_LOAD_G,
            AMP_GAIN_G   => AMP_GAIN_G,
            R_SHUNT_G    => R_SHUNT_G,
            R_CABLE_G    => R_CABLE_G)
         port map (
            iInP => iOut2A(i),          -- [in]
            iInN => iOut2B(i),          -- [in]
            iOut => fasCurrent(i*2+1));

   end generate SE_AMPS;

end architecture sim;

----------------------------------------------------------------------------------------------------
