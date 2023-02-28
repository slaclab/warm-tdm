-------------------------------------------------------------------------------
-- Title      : Ad5263
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Simulation model for Ad5263
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
use surf.I2cPkg.all;

entity Ad5263 is
   generic (
      TPD_G        : time            := 1 ns;
      RESISTANCE_G : real            := 20.0e3;
      ADDR_G       : slv(1 downto 0) := "00");
   port (
      sda : inout sl;
      scl : inout sl;
      w   : out   RealArray(3 downto 0));

end entity Ad5263;


architecture rtl of Ad5263 is

   type RegType is record
      i2cRdData : slv(7 downto 0);
      rdac      : slv8Array(3 downto 0);
   end record RegType;

   constant REG_INIT_C : RegType := (
      i2cRdData => (others => '0'),
      rdac      => (others => (others => '0')));

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal clk : sl;
   signal rst : sl;

   -- I2C RegSlave IO
   signal i2ci      : i2c_in_type;
   signal i2co      : i2c_out_type;
   signal i2cAddr   : slv(7 downto 0);
   signal i2cWrEn   : sl;
   signal i2cWrData : slv(7 downto 0);
   signal i2cRdEn   : sl;
   signal i2cRdData : slv(7 downto 0);
begin

   i2ci.scl <= to_x01z(scl);
   i2ci.sda <= to_x01z(sda);
   sda      <= i2co.sda when i2co.sdaoen = '0' else 'Z';
   scl      <= i2co.scl when i2co.scloen = '0' else 'Z';

   U_ClkRst_1 : entity surf.ClkRst
      generic map (
         CLK_PERIOD_G => 10 ns)
      port map (
         clkP => clk,                   -- [out]
         rst  => rst);                  -- [out]

   I2cRegSlave_1 : entity surf.I2cRegSlave
      generic map (
         TPD_G                => TPD_G,
         TENBIT_G             => 0,
         I2C_ADDR_G           => conv_integer("01011" & ADDR_G),
         OUTPUT_EN_POLARITY_G => 0,
         FILTER_G             => 2,
         ADDR_SIZE_G          => 1,
         DATA_SIZE_G          => 1,
         ENDIANNESS_G         => 1)
      port map (
         aRst   => rst,
         clk    => clk,
         addr   => i2cAddr,
         wrEn   => i2cWrEn,
         wrData => i2cWrData,
         rdEn   => i2cRdEn,
         rdData => i2cRdData,
         i2ci   => i2ci,
         i2co   => i2co);

   comb : process (i2cAddr, i2cWrData, i2cWrEn, r) is
      variable v : RegType;
   begin
      v := r;
      if (i2cWrEn = '1') then
         v.rdac(conv_integer(i2cAddr(6 downto 5))) := i2cWrData;
      end if;
      v.i2cRdData := r.rdac(conv_integer(i2cAddr(6 downto 5)));

      i2cRdData <= r.i2cRdData;

      rin <= v;

      for i in 3 downto 0 loop
         w(i) <= conv_integer(r.rdac(i)) * RESISTANCE_G;
      end loop;
   end process;

   seq : process (clk, rst) is
   begin
      if (rst = '1') then
         r <= REG_INIT_C after TPD_G;
      elsif (rising_edge(clk)) then
         r <= rin after TPD_G;
      end if;
   end process seq;
end architecture rtl;
