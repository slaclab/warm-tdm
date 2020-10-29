-------------------------------------------------------------------------------
-- Title      : Timing Deserializer
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

library unisim;
use unisim.vcomponents.all;

library surf;
use surf.StdRtlPkg.all;

entity TimingDeserializer is

   generic (
      TPD_G             : time   := 1 ns;
      IODELAY_GROUP_G   : string := "DEFAULT_GROUP";
      IDELAYCTRL_FREQ_G : real   := 200.0);

   port (
      rst           : in sl := '0';
      bitClk        : in sl;
      bitClkInv     : in sl;
      timingRxDataP : in sl;
      timingRxDataN : in sl;

      wordClk : in sl;
      wordRst : in sl;

      dataOut : out slv(9 downto 0);
      slip    : in  sl);

end entity TimingDeserializer;

architecture rtl of TimingDeserializer is

   signal timingRxData    : sl;
   signal timingRxDataDly : sl;

   signal shift1 : sl;
   signal shift2 : sl;

   attribute IODELAY_GROUP            : string;
   attribute IODELAY_GROUP of U_DELAY : label is IODELAY_GROUP_G;

begin


   TIMING_RX_TRIG_BUFF : IBUFDS
      port map (
         i  => timingRxDataP,
         ib => timingRxDataN,
         o  => timingRxData);

   U_DELAY : IDELAYE2
      generic map (
         DELAY_SRC             => "IDATAIN",
         HIGH_PERFORMANCE_MODE => "TRUE",
         IDELAY_TYPE           => "FIXED",  --"VAR_LOAD",
         IDELAY_VALUE          => 15,       -- Here
         REFCLK_FREQUENCY      => 200.0,
         SIGNAL_PATTERN        => "DATA"
         )
      port map (
         C           => '0',
         REGRST      => '0',
         LD          => '0',                --r.set,
         CE          => '0',
         INC         => '1',
         CINVCTRL    => '0',
         CNTVALUEIN  => (others => '0'),    --r.delay,
         IDATAIN     => timingRxData,
         DATAIN      => '0',
         LDPIPEEN    => '0',
         DATAOUT     => timingRxDataDly,
         CNTVALUEOUT => open);

   U_ISERDES_MASTER : ISERDESE2
      generic map (
         DATA_RATE         => "DDR",
         DATA_WIDTH        => 10,
         INTERFACE_TYPE    => "NETWORKING",
         DYN_CLKDIV_INV_EN => "FALSE",
         DYN_CLK_INV_EN    => "FALSE",
         NUM_CE            => 1,
         OFB_USED          => "FALSE",
         IOBDELAY          => "IFD",       -- Use input at DDLY to output the data on Q1-Q6
         SERDES_MODE       => "MASTER")
      port map (
         Q1           => dataOut(0),
         Q2           => dataOut(1),
         Q3           => dataOut(2),
         Q4           => dataOut(3),
         Q5           => dataOut(4),
         Q6           => dataOut(5),
         Q7           => dataOut(6),
         Q8           => dataOut(7),
         SHIFTOUT1    => shift1,           -- Cascade connection to Slave ISERDES
         SHIFTOUT2    => shift2,           -- Cascade connection to Slave ISERDES
         BITSLIP      => slip,             -- 1-bit Invoke Bitslip. This can be used with any
         -- DATA_WIDTH, cascaded or not.
         CE1          => '1',              -- 1-bit Clock enable input
         CE2          => '1',              -- 1-bit Clock enable input
         CLK          => bitClk,           -- Fast Source Synchronous SERDES clock from BUFIO
         CLKB         => bitClkInv,        -- Locally inverted clock
         CLKDIV       => wordClk,          -- Slow clock driven by BUFR
         CLKDIVP      => '0',
         D            => '0',
         DDLY         => timingRxDataDly,  -- 1-bit Input signal from IODELAYE1.
         RST          => rst,              -- 1-bit Asynchronous reset only.
         SHIFTIN1     => '0',
         SHIFTIN2     => '0',
         -- unused connections
         DYNCLKDIVSEL => '0',
         DYNCLKSEL    => '0',
         OFB          => '0',
         OCLK         => '0',
         OCLKB        => '0',
         O            => open);            -- unregistered output of ISERDESE1

   U_ISERDES_SLAVE : ISERDESE2
      generic map (
         DATA_RATE         => "DDR",
         DATA_WIDTH        => 14,
         INTERFACE_TYPE    => "NETWORKING",
         DYN_CLKDIV_INV_EN => "FALSE",
         DYN_CLK_INV_EN    => "FALSE",
         NUM_CE            => 1,
         OFB_USED          => "FALSE",
         IOBDELAY          => "IFD",    -- Use input at DDLY to output the data on Q1-Q6
         SERDES_MODE       => "SLAVE")
      port map (
         Q1           => open,
         Q2           => open,
         Q3           => dataOut(8),
         Q4           => dataOut(9),
         Q5           => open,
         Q6           => open,
         Q7           => open,
         Q8           => open,
         SHIFTOUT1    => open,
         SHIFTOUT2    => open,
         SHIFTIN1     => shift1,        -- Cascade connections from Master ISERDES
         SHIFTIN2     => shift2,        -- Cascade connections from Master ISERDES
         BITSLIP      => slip,          -- 1-bit Invoke Bitslip. This can be used with any
         -- DATA_WIDTH, cascaded or not.
         CE1          => '1',           -- 1-bit Clock enable input
         CE2          => '1',           -- 1-bit Clock enable input
         CLK          => bitClk,        -- Fast source synchronous serdes clock
         CLKB         => bitClkInv,     -- locally inverted clock
         CLKDIV       => wordClk,       -- Slow clock driven by BUFR.
         CLKDIVP      => '0',
         D            => '0',           -- Slave ISERDES module. No need to connect D, DDLY
         DDLY         => '0',
         RST          => rst,           -- 1-bit Asynchronous reset only.
         -- unused connections
         DYNCLKDIVSEL => '0',
         DYNCLKSEL    => '0',
         OFB          => '0',
         OCLK         => '0',
         OCLKB        => '0',
         O            => open);         -- unregistered output of ISERDESE1



end architecture rtl;
