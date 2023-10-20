-------------------------------------------------------------------------------
-- Title      : 
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: 
-------------------------------------------------------------------------------
-- This file is part of SURF. It is subject to
-- the license terms in the LICENSE.txt file found in the top-level directory
-- of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of SURF, including this file, may be
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

entity Ltc4151 is
   generic (
      TPD_G        : time            := 1 ns;
      ADDR_G       : slv(1 downto 0) := "00");
   port (
      sda    : inout sl;
      scl    : inout sl;
      senseP : in    real;
      senseN : in    real;
      vin    : in    real;
      adin   : in    real);

end entity Ltc4151;


architecture rtl of Ltc4151 is

   constant I2C_ADDR_C : slv(6 downto 0) :=
      ite(ADDR_G = "00", "1101111",
          ite(ADDR_G = "0Z", "1101110",
              ite(ADDR_G = "1Z", "1101101",
                  ite(ADDR_G = "01", "1101100",
                      ite(ADDR_G = "Z0", "1101011",
                          ite(ADDR_G = "ZZ", "1101010",
                              ite(ADDR_G = "11", "1101001",
                                  ite(ADDR_G = "Z1", "1101000",
                                      ite(ADDR_G = "10", "1100111", "0000000")))))))));

   type RegType is record
      i2cRdData : slv(7 downto 0);
      sense     : slv(11 downto 0);
      vin       : slv(11 downto 0);
      adin      : slv(11 downto 0);
   end record RegType;

   constant REG_INIT_C : RegType := (
      i2cRdData => (others => '0'),
      sense     => (others => '0'),
      vin       => (others => '0'),
      adin      => (others => '0'));

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
         I2C_ADDR_G           => conv_integer(I2C_ADDR_C),
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

   comb : process (i2cAddr, r, senseP, senseN, vin, adin) is
      variable v : RegType;
   begin
      v := r;

      v.sense := adcConversion(senseP-senseN, 0.0, 81.92e-3, 12, false);
      v.vin := adcConversion(vin, 0.0, 102.4, 12, false);
      v.adin := adcConversion(adin, 0.0, 2.048, 12, false);

      case i2cAddr is
         when X"00" =>
            v.i2cRdData := r.sense(11 downto 4);
         when X"01" =>
            v.i2cRdData := r.sense(3 downto 0) & "0000";
         when X"02" =>
            v.i2cRdData := r.vin(11 downto 4);
         when X"03" =>
            v.i2cRdData := r.vin(3 downto 0) & "0000";
         when X"04" =>
            v.i2cRdData := r.adin(11 downto 4);
         when X"05" =>
            v.i2cRdData := r.adin(3 downto 0) & "0000";
         when others =>
            v.i2cRdData := (others => '0');
      end case;

      i2cRdData <= r.i2cRdData;

      rin <= v;

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
