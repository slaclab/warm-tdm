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

library warm_tdm;

----------------------------------------------------------------------------------------------------

entity RowModuleBoard is
   generic (
      TPD_G                   : time     := 1 ns;
      RING_ADDR_0_G           : boolean  := false;
      SIM_PGP_PORT_NUM_G      : positive := 7000;
      SIM_ETH_SRP_PORT_NUM_G  : positive := 8000;
      SIM_ETH_DATA_PORT_NUM_G : positive := 9000);
   port (
      rj45TimingRxClkP  : in  sl;       -- [in]
      rj45TimingRxClkN  : in  sl;       -- [in]
      rj45TimingRxDataP : in  sl;       -- [in]
      rj45TimingRxDataN : in  sl;       -- [in]
      rj45TimingTxClkP  : out sl;       -- [out]
      rj45TimingTxClkN  : out sl;       -- [out]
      rj45TimingTxDataP : out sl;       -- [out]
      rj45TimingTxDataN : out sl);      -- [out]


end entity RowModuleBoard;

----------------------------------------------------------------------------------------------------

architecture sim of RowModuleBoard is

   -- component generics
   constant SIMULATION_G : boolean       := true;
   constant BUILD_INFO_G : BuildInfoType := BUILD_INFO_DEFAULT_SLV_C;

   constant ETH_10G_G : boolean          := false;
   constant DHCP_G    : boolean          := true;
   constant IP_ADDR_G : slv(31 downto 0) := x"0B01A8C0";

   -- component ports
   signal gtRefClk0P    : sl;                                   -- [in]
   signal gtRefClk0N    : sl;                                   -- [in]
   signal gtRefClk1P    : sl;                                   -- [in]
   signal gtRefClk1N    : sl;                                   -- [in]
   signal pgpTxP        : sl               := '0';              -- [out]
   signal pgpTxN        : sl               := '0';              -- [out]
   signal pgpRxP        : sl               := '0';              -- [in]
   signal pgpRxN        : sl               := '0';              -- [in]
   signal xbarDataSel   : slv(1 downto 0)  := "00";             -- [out]
   signal xbarClkSel    : slv(1 downto 0)  := "00";             -- [out]
   signal xbarMgtSel    : slv(1 downto 0)  := "00";             -- [out]
   signal timingRxClkP  : sl;                                   -- [in]
   signal timingRxClkN  : sl;                                   -- [in]
   signal timingRxDataP : sl;                                   -- [in]
   signal timingRxDataN : sl;                                   -- [in]
   signal timingTxClkP  : sl;                                   -- [out]
   signal timingTxClkN  : sl;                                   -- [out]
   signal timingTxDataP : sl;                                   -- [out]
   signal timingTxDataN : sl;                                   -- [out]
   signal sfp0TxP       : sl               := '0';              -- [out]
   signal sfp0TxN       : sl               := '0';              -- [out]
   signal sfp0RxP       : sl               := '0';              -- [in]
   signal sfp0RxN       : sl               := '0';              -- [in]
   signal bootCsL       : sl               := '0';              -- [out]
   signal bootMosi      : sl               := '0';              -- [out]
   signal bootMiso      : sl               := '0';              -- [in]
   signal promScl       : sl;                                   -- [inout]
   signal promSda       : sl;                                   -- [inout]
   signal pwrScl        : sl;                                   -- [inout]
   signal pwrSda        : sl;                                   -- [inout]
   signal leds          : slv(7 downto 0);                      -- [out]
   signal vAuxP         : slv(3 downto 0)  := (others => '0');  -- [in]
   signal vAuxN         : slv(3 downto 0)  := (others => '0');  -- [in]
   signal dacCsB        : slv(11 downto 0);                     -- [out]
   signal dacSdio       : slv(11 downto 0);                     -- [out]
   signal dacSdo        : slv(11 downto 0);                     -- [in]
   signal dacSclk       : slv(11 downto 0);                     -- [out]
   signal dacResetB     : slv(11 downto 0) := (others => '1');  -- [out]
   signal dacTriggerB   : slv(11 downto 0) := (others => '1');  -- [out]
   signal dacClkP       : slv(11 downto 0);                     -- [out]
   signal dacClkN       : slv(11 downto 0);                     -- [out]

   -- Local signals
   signal clk : sl;
   signal rst : sl;

begin

   -------------------------------------------------------------------------------------------------
   -- FPGA
   -------------------------------------------------------------------------------------------------
   U_RowModule : entity warm_tdm.RowModule
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
         dacCsB        => dacCsB,         -- [out]
         dacSdio       => dacSdio,        -- [out]
         dacSdo        => dacSdo,         -- [in]
         dacSclk       => dacSclk,        -- [out]
         dacResetB     => dacResetB,      -- [out]
         dacTriggerB   => dacTriggerB,    -- [out]
         dacClkP       => dacClkP,        -- [out]
         dacClkN       => dacClkN);       -- [out]

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


end architecture sim;

----------------------------------------------------------------------------------------------------
