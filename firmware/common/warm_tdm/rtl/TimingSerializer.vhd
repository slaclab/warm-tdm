-------------------------------------------------------------------------------
-- Title      : Timing Serializer
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

entity TimingSerializer is

   generic (
      TPD_G : time := 1 ns);
   port (
      rst           : in  sl := '0';
      enable        : in  sl := '1';
      bitClk        : in  sl;
      timingTxDataP : out sl;
      timingTxDataN : out sl;

      wordClk : in sl;
      wordRst : in sl;
      dataIn  : in slv(9 downto 0));
end entity TimingSerializer;

architecture rtl of TimingSerializer is

   signal timingTxData : sl;

   signal shift1 : sl;
   signal shift2 : sl;

begin



   TIMING_RX_TRIG_BUFF : OBUFDS
      port map (
         o  => timingTxDataP,
         ob => timingTxDataN,
         i  => timingTxData);


   U_OSERDES_MASTER : OSERDESE2
      generic map (
         DATA_RATE_OQ   => "DDR",
         DATA_WIDTH     => 10,
         SERDES_MODE    => "MASTER",
         TRISTATE_WIDTH => 1)
      port map (
         OQ        => timingTxData,
         OFB       => open,
         TQ        => open,
         TFB       => open,
         SHIFTOUT1 => open,
         SHIFTOUT2 => open,
         CLK       => bitClk,           -- Fast SERDES clock from BUFIO
         CLKDIV    => wordClk,  -- Slow clock driven by BUFR                                           -- 
         D1        => dataIn(0),
         D2        => dataIn(1),
         D3        => dataIn(2),
         D4        => dataIn(3),
         D5        => dataIn(4),
         D6        => dataIn(5),
         D7        => dataIn(6),
         D8        => dataIn(7),
         TCE       => '0',
         OCE       => enable,           -- Output data clock enable
         TBYTEIN   => '1',
         TBYTEOUT  => open,
         RST       => rst,              -- 1-bit Asynchronous reset only.
         SHIFTIN1  => shift1,           -- Cascade connection to Slave ISERDES
         SHIFTIN2  => shift2,           -- Cascade connection to Slave ISERDES
         T1        => '0',
         T2        => '0',
         T3        => '0',
         T4        => '0');

   U_OSERDES_SLAVE : OSERDESE2
      generic map (
         DATA_RATE_OQ   => "DDR",
         DATA_WIDTH     => 10,
         SERDES_MODE    => "SLAVE",
         TRISTATE_WIDTH => 1)
      port map (
         OQ        => open,
         OFB       => open,
         TQ        => open,
         TFB       => open,
         SHIFTOUT1 => shift1,
         SHIFTOUT2 => shift2,
         CLK       => bitClk,           -- Fast SERDES clock from BUFIO
         CLKDIV    => wordClk,  -- Slow clock driven by BUFR                                           -- 
         D1        => '0',
         D2        => '0',
         D3        => dataIn(8),
         D4        => dataIn(9),
         D5        => '0',
         D6        => '0',
         D7        => '0',
         D8        => '0',
         TCE       => '0',
         OCE       => enable,           -- Output data clock enable
         TBYTEIN   => '1',
         TBYTEOUT  => open,
         RST       => rst,              -- 1-bit Asynchronous reset only.
         SHIFTIN1  => '0',
         SHIFTIN2  => '0',
         T1        => '0',
         T2        => '0',
         T3        => '0',
         T4        => '0');



end architecture rtl;
