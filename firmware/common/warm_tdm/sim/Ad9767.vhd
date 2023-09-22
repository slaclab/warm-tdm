-------------------------------------------------------------------------------
-- Title      : Ad9767
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Simulation model for AD9767 DAC
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
use ieee.std_logic_unsigned.all;
use ieee.std_logic_arith.all;

library surf;
use surf.StdRtlPkg.all;

entity Ad9767 is
   generic (
      FSADJ1_G : real := 2.0e3;
      FSADJ2_G : real := 2.0e3);

   port (
      db      : in  slv(13 downto 0);
      iqsel   : in  sl;
      iqwrt   : in  sl;
      iqclk   : in  sl;
      iqreset : in  sl;
      iOut1A  : out real;
      iOut1B  : out real;
      iOut2A  : out real;
      iOut2B  : out real);

end entity Ad9767;


architecture rtl of Ad9767 is

   constant IOUTFS_1_C : real := (1.2 / FSADJ1_G) * 32;
   constant IOUTFS_2_C : real := (1.2 / FSADJ2_G) * 32;

   signal inLatch1  : slv(13 downto 0) := (others => '0');
   signal inLatch2  : slv(13 downto 0) := (others => '0');
   signal outLatch1 : slv(13 downto 0) := (others => '0');
   signal outLatch2 : slv(13 downto 0) := (others => '0');

   signal clkDiv : sl := '1';

begin

   IN_LATCH : process (iqwrt) is
   begin
      if (rising_edge(iqwrt)) then
         if (iqsel = '1') then
            inLatch1 <= db after 2 ns;
         else
            inLatch2 <= db after 2 ns;
         end if;
      end if;
   end process IN_LATCH;

   clk_div : process (iqclk, iqreset) is
   begin
      if (iqreset = '1') then
         clkDiv <= '0' after 2 ns;
      elsif (rising_edge(iqclk)) then
         clkDiv <= not clkDiv after 2 ns;
      end if;
   end process;

   OUT_LATCH : process (clkDiv) is
   begin
      if (rising_edge(clkDiv)) then
         outLatch1 <= inLatch1 after 2 ns;
         outLatch2 <= inLatch2 after 2 ns;
      end if;
   end process OUT_LATCH;

   iOut1A <= IOUTFS_1_C * (conv_integer(outLatch1)/16384.0);
   iOut1B <= IOUTFS_1_C * ((16383-conv_integer(outLatch1))/16384.0);

   iOut2A <= IOUTFS_2_C * (conv_integer(outLatch2)/16384.0);
   iOut2B <= IOUTFS_2_C * ((16383-conv_integer(outLatch2))/16384.0);



end rtl;
