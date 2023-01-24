-------------------------------------------------------------------------------
-- Title      : Testbench for design "ColumnModule"
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
use ieee.math_real.all;

library surf;
use surf.StdRtlPkg.all;

library ruckus;
use ruckus.BuildInfoPkg.all;

library warm_tdm;

----------------------------------------------------------------------------------------------------

entity ColumnModuleBoard is
   generic (
      TPD_G                   : time    := 1 ns;
      RING_ADDR_0_G           : boolean := false;
      SIM_PGP_PORT_NUM_G      : integer := 7000;
      SIM_ETH_SRP_PORT_NUM_G  : integer := 8000;
      SIM_ETH_DATA_PORT_NUM_G : integer := 9000);
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


end entity ColumnModuleBoard;

----------------------------------------------------------------------------------------------------

architecture sim of ColumnModuleBoard is

   -- component generics
   constant SIMULATION_G : boolean       := true;
   constant BUILD_INFO_G : BuildInfoType := BUILD_INFO_C;

   constant ETH_10G_G : boolean          := false;
   constant DHCP_G    : boolean          := true;
   constant IP_ADDR_G : slv(31 downto 0) := x"0A01A8C0";

   -- component ports
   signal gtRefClk0P    : sl;                                  -- [in]
   signal gtRefClk0N    : sl;                                  -- [in]
   signal gtRefClk1P    : sl;                                  -- [in]
   signal gtRefClk1N    : sl;                                  -- [in]
   signal pgpTxP        : slv(1 downto 0);                     -- [out]
   signal pgpTxN        : slv(1 downto 0);                     -- [out]
   signal pgpRxP        : slv(1 downto 0);                     -- [in]
   signal pgpRxN        : slv(1 downto 0);                     -- [in]
   signal xbarDataSel   : slv(1 downto 0) := "00";             -- [out]
   signal xbarClkSel    : slv(1 downto 0) := "00";             -- [out]
   signal xbarMgtSel    : slv(1 downto 0) := "00";             -- [out]
   signal timingRxClkP  : sl;                                  -- [in]
   signal timingRxClkN  : sl;                                  -- [in]
   signal timingRxDataP : sl;                                  -- [in]
   signal timingRxDataN : sl;                                  -- [in]
   signal timingTxClkP  : sl;                                  -- [out]
   signal timingTxClkN  : sl;                                  -- [out]
   signal timingTxDataP : sl;                                  -- [out]
   signal timingTxDataN : sl;                                  -- [out]
   signal sfp0TxP       : sl;                                  -- [out]
   signal sfp0TxN       : sl;                                  -- [out]
   signal sfp0RxP       : sl;                                  -- [in]
   signal sfp0RxN       : sl;                                  -- [in]
   signal bootCsL       : sl;                                  -- [out]
   signal bootMosi      : sl;                                  -- [out]
   signal bootMiso      : sl;                                  -- [in]
   signal promScl       : sl;                                  -- [inout]
   signal promSda       : sl;                                  -- [inout]
   signal pwrScl        : sl;                                  -- [inout]
   signal pwrSda        : sl;                                  -- [inout]
   signal leds          : slv(7 downto 0);                     -- [out]
   signal vAuxP         : slv(3 downto 0);                     -- [in]
   signal vAuxN         : slv(3 downto 0);                     -- [in]
   signal sq1BiasDb     : slv(13 downto 0);                    -- [out]
   signal sq1BiasWrt    : slv(3 downto 0);                     -- [out]
   signal sq1BiasClk    : slv(3 downto 0);                     -- [out]
   signal sq1BiasSel    : slv(3 downto 0);                     -- [out]
   signal sq1BiasReset  : slv(3 downto 0);                     -- [out]
   signal sq1FbDb       : slv(13 downto 0);                    -- [out]
   signal sq1FbWrt      : slv(3 downto 0);                     -- [out]
   signal sq1FbClk      : slv(3 downto 0);                     -- [out]
   signal sq1FbSel      : slv(3 downto 0);                     -- [out]
   signal sq1FbReset    : slv(3 downto 0);                     -- [out]
   signal saFbDb        : slv(13 downto 0);                    -- [out]
   signal saFbWrt       : slv(3 downto 0);                     -- [out]
   signal saFbClk       : slv(3 downto 0);                     -- [out]
   signal saFbSel       : slv(3 downto 0);                     -- [out]
   signal saFbReset     : slv(3 downto 0);                     -- [out]
   signal saDacMosi     : sl;                                  -- [out]
   signal saDacMiso     : sl;                                  -- [in]
   signal saDacSclk     : sl;                                  -- [out]
   signal saDacSyncB    : sl;                                  -- [out]
   signal saDacLdacB    : sl              := '1';              -- [out]
   signal saDacResetB   : sl              := '1';              -- [out]
   signal tesDacMosi    : sl;                                  -- [out]
   signal tesDacMiso    : sl;                                  -- [in]
   signal tesDacSclk    : sl;                                  -- [out]
   signal tesDacSyncB   : sl;                                  -- [out]
   signal tesDacLdacB   : sl              := '1';              -- [out]
   signal tesDacResetB  : sl              := '1';              -- [out]
   signal tesDelatch    : slv(7 downto 0) := (others => '0');  -- [out]
   signal adcFClkP      : slv(1 downto 0);                     -- [in]
   signal adcFClkN      : slv(1 downto 0);                     -- [in]
   signal adcDClkP      : slv(1 downto 0);                     -- [in]
   signal adcDClkN      : slv(1 downto 0);                     -- [in]
   signal adcChP        : slv8Array(1 downto 0);               -- [in]
   signal adcChN        : slv8Array(1 downto 0);               -- [in]
   signal adcClkP       : sl;                                  -- [out]
   signal adcClkN       : sl;                                  -- [out]
   signal adcSclk       : sl;                                  -- [out]
   signal adcSdio       : sl;                                  -- [inout]
   signal adcCsb        : sl;                                  -- [out]
   signal adcSync       : sl;                                  -- [out]

   -- Local signals
   signal clk : sl;
   signal rst : sl;

   signal saFbDacA    : RealArray(7 downto 0);
   signal saFbDacB    : RealArray(7 downto 0);
   signal sq1FbDacA   : RealArray(7 downto 0);
   signal sq1FbDacB   : RealArray(7 downto 0);
   signal sq1BiasDacA : RealArray(7 downto 0);
   signal sq1BiasDacB : RealArray(7 downto 0);

   signal saFbOut    : RealArray(7 downto 0);
   signal sq1FbOut   : RealArray(7 downto 0);
   signal sq1BiasOut : RealArray(7 downto 0);

   signal saSig : RealArray(7 downto 0);
   signal noise : RealArray(7 downto 0);

   signal adcVin : RealArray(7 downto 0) := (
      0 => -0.001,
      1 => -0.010,
      2 => -0.100,
      3 => 0.0,
      4 => 0.1,
      5 => 0.010,
      6 => 0.001,
      7 => 0.0001);

   signal tesDacVout : RealArray(15 downto 0) := (others => 0.0);
   signal tesBias    : RealArray(7 downto 0)  := (others => 0.0);

   signal saBias   : RealArray(7 downto 0) := (others => 0.0);
   signal saOffset : RealArray(7 downto 0) := (others => 0.0);

   signal saBiasCurrent : RealArray(7 downto 0) := (others => 0.0);
   signal saResistance  : RealArray(7 downto 0) := (others => 0.0);
   signal ampInP        : RealArray(7 downto 0) := (others => 0.0);
   signal amplitudeTmp  : RealArray(7 downto 0) := (others => 0.0);
   signal amplitude     : RealArray(7 downto 0) := (others => 0.0);
   signal fbCurrent     : RealArray(7 downto 0) := (others => 0.0);


begin

   -- component instantiation
   U_ColumnModule : entity warm_tdm.ColumnModule
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
         IP_ADDR_G               => IP_ADDR_G)
      port map (
         gtRefClk0P    => gtRefClk0P,     -- [in]
         gtRefClk0N    => gtRefClk0N,     -- [in]
         gtRefClk1P    => gtRefClk1P,     -- [in]
         gtRefClk1N    => gtRefClk1N,     -- [in]
         pgpTxP        => pgpTxP,         -- [out]
         pgpTxN        => pgpTxN,         -- [out]
         pgpRxP        => pgpRxP,         -- [in]
         pgpRxN        => pgpRxN,         -- [in]
         xbarDataSel   => xbarDataSel,    -- [out]
         xbarClkSel    => xbarClkSel,     -- [out]
         xbarMgtSel    => xbarMgtSel,     -- [out]
         timingRxClkP  => timingRxClkP,   -- [in]
         timingRxClkN  => timingRxClkN,   -- [in]
         timingRxDataP => timingRxDataP,  -- [in]
         timingRxDataN => timingRxDataN,  -- [in]
         timingTxClkP  => timingTxClkP,   -- [out]
         timingTxClkN  => timingTxClkN,   -- [out]
         timingTxDataP => timingTxDataP,  -- [out]
         timingTxDataN => timingTxDataN,  -- [out]
         sfp0TxP       => sfp0TxP,        -- [out]
         sfp0TxN       => sfp0TxN,        -- [out]
         sfp0RxP       => sfp0RxP,        -- [in]
         sfp0RxN       => sfp0RxN,        -- [in]
         bootCsL       => bootCsL,        -- [out]
         bootMosi      => bootMosi,       -- [out]
         bootMiso      => bootMiso,       -- [in]
         promScl       => promScl,        -- [inout]
         promSda       => promSda,        -- [inout]
         pwrScl        => pwrScl,         -- [inout]
         pwrSda        => pwrSda,         -- [inout]
         leds          => leds,           -- [out]
         vAuxP         => vAuxP,          -- [in]
         vAuxN         => vAuxN,          -- [in]
         sq1BiasDb     => sq1BiasDb,      -- [out]
         sq1BiasWrt    => sq1BiasWrt,     -- [out]
         sq1BiasClk    => sq1BiasClk,     -- [out]
         sq1BiasSel    => sq1BiasSel,     -- [out]
         sq1BiasReset  => sq1BiasReset,   -- [out]
         sq1FbDb       => sq1FbDb,        -- [out]
         sq1FbWrt      => sq1FbWrt,       -- [out]
         sq1FbClk      => sq1FbClk,       -- [out]
         sq1FbSel      => sq1FbSel,       -- [out]
         sq1FbReset    => sq1FbReset,     -- [out]
         saFbDb        => saFbDb,         -- [out]
         saFbWrt       => saFbWrt,        -- [out]
         saFbClk       => saFbClk,        -- [out]
         saFbSel       => saFbSel,        -- [out]
         saFbReset     => saFbReset,      -- [out]
         saDacMosi     => saDacMosi,      -- [out]
         saDacMiso     => saDacMiso,      -- [in]
         saDacSclk     => saDacSclk,      -- [out]
         saDacSyncB    => saDacSyncB,     -- [out]
         saDacLdacB    => saDacLdacB,     -- [out]
         saDacResetB   => saDacResetB,    -- [out]
         tesDacMosi    => tesDacMosi,     -- [out]
         tesDacMiso    => tesDacMiso,     -- [in]
         tesDacSclk    => tesDacSclk,     -- [out]
         tesDacSyncB   => tesDacSyncB,    -- [out]
         tesDacLdacB   => tesDacLdacB,    -- [out]
         tesDacResetB  => tesDacResetB,   -- [out]
         tesDelatch    => tesDelatch,     -- [out]
         adcFClkP      => adcFClkP,       -- [in]
         adcFClkN      => adcFClkN,       -- [in]
         adcDClkP      => adcDClkP,       -- [in]
         adcDClkN      => adcDClkN,       -- [in]
         adcChP        => adcChP,         -- [in]
         adcChN        => adcChN,         -- [in]
         adcClkP       => adcClkP,        -- [out]
         adcClkN       => adcClkN,        -- [out]
         adcSclk       => adcSclk,        -- [out]
         adcSdio       => adcSdio,        -- [inout]
         adcCsb        => adcCsb,         -- [out]
         adcSync       => adcSync);       -- [out]


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

   rj45PgpTxP <= pgpTxP(1);
   rj45PgpTxN <= pgpTxN(1);

   pgpRxP(1) <= rj45PgpRxP;
   pgpRxN(1) <= rj45PgpRxN;

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

   U_Ad5263_1 : entity warm_tdm.Ad5263
      generic map (
         TPD_G        => TPD_G,
         RESISTANCE_G => 20.0e3,
         ADDR_G       => "00")
      port map (
         sda => promSda,                -- [inout]
         scl => promScl,                -- [inout]
         w   => open);                  -- [out]

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
   -- TES Bias DAC
   -------------------------------------------------------------------------------------------------
   U_Ad5679R_TES_BIAS : entity warm_tdm.Ad5679R
      generic map (
         TPD_G => TPD_G)
      port map (
         sclk   => tesDacSclk,          -- [in]
         sdi    => tesDacMosi,          -- [in]
         sdo    => tesDacMiso,          -- [out]
         syncB  => tesDacSyncB,         -- [in]
         ldacB  => tesDacLdacB,         -- [in]
         resetB => tesDacResetB,        -- [in]
         vout   => tesDacVout);         -- [out]

   TES_BIAS_LOOP : for i in 7 downto 0 generate
      tesBias(i) <= (tesDacVout(i)-tesDacVout(i+8)) * 0.5 when tesDelatch(i) = '0' else
                    (tesDacVout(i)-tesDacVout(i+8)) * 3.2;
   end generate;

   -------------------------------------------------------------------------------------------------
   -- SA Bias DAC
   -------------------------------------------------------------------------------------------------
   U_Ad5679R_SA_BIAS : entity warm_tdm.Ad5679R
      generic map (
         TPD_G => TPD_G)
      port map (
         sclk              => saDacSclk,    -- [in]
         sdi               => saDacMosi,    -- [in]
         sdo               => saDacMiso,    -- [out]
         syncB             => saDacSyncB,   -- [in]
         ldacB             => saDacLdacB,   -- [in]
         resetB            => saDacResetB,  -- [in]
         vout(7 downto 0)  => saBias,
         vout(15 downto 8) => saOffset);    -- [out]

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
            iOut1A => saFbDacA(2*i),     -- [out]
            iOut1B => saFbDacB(2*i),     -- [out]
            iOut2A => saFbDacA(2*i+1),   -- [out]
            iOut2B => saFbDacB(2*i+1));  -- [out]

      U_Ad9767_SQ1_BIAS : entity warm_tdm.Ad9767
         generic map (
            FSADJ1_G => 2.0e3,
            FSADJ2_G => 2.0e3)
         port map (
            db     => sq1BiasDb,            -- [in]
            iqsel  => sq1BiasSel(i),        -- [in]
            iqwrt  => sq1BiasWrt(i),        -- [in]
            iqclk  => sq1BiasClk(i),        -- [in]
            iOut1A => sq1BiasDacA(2*i),     -- [out]
            iOut1B => sq1BiasDacB(2*i),     -- [out]
            iOut2A => sq1BiasDacA(2*i+1),   -- [out]
            iOut2B => sq1BiasDacB(2*i+1));  -- [out]

      U_Ad9767_SQ1_FB : entity warm_tdm.Ad9767
         generic map (
            FSADJ1_G => 2.0e3,
            FSADJ2_G => 2.0e3)
         port map (
            db     => sq1FbDb,            -- [in]
            iqsel  => sq1FbSel(i),        -- [in]
            iqwrt  => sq1FbWrt(i),        -- [in]
            iqclk  => sq1FbClk(i),        -- [in]
            iOut1A => sq1FbDacA(2*i),     -- [out]
            iOut1B => sq1FbDacB(2*i),     -- [out]
            iOut2A => sq1FbDacA(2*i+1),   -- [out]
            iOut2B => sq1FbDacB(2*i+1));  -- [out]

   end generate;

   FAST_DAC_AMPS : for i in 7 downto 0 generate
      saFbOut(i)    <= (((saFbDacA(i) * 25) - (saFbDacB(i) * 25)) * (-5.0));        -- / 4.15e3;
      sq1FbOut(i)   <= (((sq1FbDacA(i) * 25) - (sq1FbDacB(i) * 25)) * (-5.0));      -- / 4.15e3;
      sq1BiasOut(i) <= (((sq1BiasDacA(i) * 25) - (sq1BiasDacB(i) * 25)) * (-5.0));  -- / 4.15e3;
   end generate FAST_DAC_AMPS;


   GEN_NOISE : process (timingRxClkP) is
      variable rand         : real;
      variable seed1, seed2 : positive;
      variable tmp          : RealArray(7 downto 0);
   begin
      if (rising_edge(timingRxClkP)) then
         for i in 7 downto 0 loop
            uniform(seed1, seed2, rand);
            tmp(i) := rand * 1.0E-5;
         end loop;
         noise <= tmp;
      end if;
   end process;


   GEN_AMPLIFIER : for i in 7 downto 0 generate
      constant R_BIAS_C     : real := 15.0e3;
      constant R_OFFSET_C   : real := 4.22e3;
      constant R_GAIN_C     : real := 100.0;
      constant R_FB_C       : real := 1.1e3;
      constant R_CABLE_C    : real := 200.0;
      constant R_FB_SHUNT_C : real := 7.15e3;

      constant G_BIAS_C   : real := 1.0/R_BIAS_C;
      constant G_OFFSET_C : real := 1.0/R_OFFSET_C;
      constant G_GAIN_C   : real := 1.0/R_GAIN_C;
      constant G_FB_C     : real := 1.0/R_FB_C;
      constant G_CABLE_C  : real := 1.0/R_CABLE_C;

      constant G2_C : real := 11.0;
      constant G3_C : real := 1.5;

      constant PHI_NOT_C : real := 40.0e-6;

   begin
      saBiasCurrent(i) <= saBias(i)/R_BIAS_C;

      -- Calculate max SA Resistance based on current
      amplitudeTmp(i) <= (-100.0e9) * (saBiasCurrent(i)-20.0e-6) * (saBiasCurrent(i)-60.0e-6);
      amplitude(i)    <= ite(amplitudeTmp(i) < 0.0, 0.0, amplitudeTmp(i));

      fbCurrent(i) <= saFbOut(i)/R_FB_SHUNT_C;

      saResistance(i) <= 125.0 + amplitude(i) * cos(fbCurrent(i) * 2 * MATH_PI / PHI_NOT_C - saBias(i)) + amplitude(i);

      saSig(i) <= saBias(i) * saResistance(i) / (saResistance(i) + R_BIAS_C);

      ampInP(i) <= ((saSig(i) * G_CABLE_C) + (saBias(i) * G_BIAS_C)) / (G_BIAS_C + G_CABLE_C);
--      ampInP <= saBias(i) * R_CABLE_C/(R_BIAS_C+R_CABLE_C) + saSig(i);

      adcVin(i) <= R_FB_C * (ampInP(i) * (G_GAIN_C + G_OFFSET_C + G_FB_C) - (saOffset(i) * G_OFFSET_C)) * G2_C * G3_C * (-1.0);

      --adcVin(i) <= 0.080044 * (saBias(i)-1.08288*(saOffset(i)-138.621*saSig(i))) * 11 * (-1.5);

   end generate;


end architecture sim;

----------------------------------------------------------------------------------------------------
