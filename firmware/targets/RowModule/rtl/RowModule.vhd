-------------------------------------------------------------------------------
-- Title      : Warm TDM Row Module
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Top level of RowModule 
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

entity RowModule is

   generic (
      TPD_G        : time    := 1 ns;
      SIMULATION_G : boolean := false;
      BUILD_INFO_G : BuildInfoType);

   port (
      -- Clocks
      gtRefClk0P : in sl;
      gtRefClk0N : in sl;
      gtRefClkP1 : in sl;
      gtRefClk1N : in sl;

      -- PGP Interface
      pgpTxP : out sl;
      pgpTxN : out sl;
      pgpRxP : in  sl;
      pgpRxN : in  sl;

      -- Timing Interface
--       timingRxP : in sl;
--       timingRxN : in sl;

      -- Generic SFP interfaces
--       sfp0TxP : out sl;
--       sfp0TxN : out sl;
--       sfp0RxP : in  sl;
--       sfp0RxN : in  sl;
--       sfp1TxP : out sl;
--       sfp1TxN : out sl;
--       sfp1RxP : in  sl;
--       sfp1RxN : in  sl;

      -- DAC Interfaces
      dacCsB      : out   slv(11 downto 0);
      dacSdio     : inout slv(11 downto 0);
--      dacSdi2 : out slv(11 downto 0);
      dacSclk     : out   slv(11 downto 0);
      dacResetB   : out   slv(11 downto 0) := (others => '1');
      dacTriggerB : out   slv(11 downto 0) := (others => '1');
      dacClkP     : out   slv(11 downto 0);
      dacClkN     : out   slv(11 downto 0);

      promScl : inout sl;
      promSda : inout sl;

      pwrScl : inout sl;
      pwrSda : inout sl;

      leds : out slv(3 downto 0));

end entity RowModule;

architecture rtl of RowModule is

begin



end architecture rtl;
