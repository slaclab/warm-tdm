-------------------------------------------------------------------------------
-- Title      : AwaXe
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Simulation model for AwaXe ASIC
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

entity AwaXeChannel is
   generic (
      TPD_G      : time            := 1 ns;
      RANGE_G    : real            := 300.0e-6;
      I2C_ADDR_G : slv(6 downto 0) := (others => '0'));
   port (
      clk     : in    sl;
      rst     : in    sl;
      sda     : inout sl;
      scl     : inout sl;
      current : out   real);
end entity AwaXeChannel;


architecture rtl of AwaXeChannel is

   type RegType is record
      dac : slv(7 downto 0);
   end record RegType;

   constant REG_INIT_C : RegType := (
      dac => X"A5");

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   -- I2C RegSlave IO
   signal i2ci : i2c_in_type;
   signal i2co : i2c_out_type;

   signal i2cSlaveIn  : I2cSlaveInType;
   signal i2cSlaveOut : I2cSlaveOutType;

begin

   U_I2cSlave_1 : entity surf.I2cSlave
      generic map (
         TPD_G                => TPD_G,
         TENBIT_G             => 0,
         I2C_ADDR_G           => conv_integer(I2C_ADDR_G),
         OUTPUT_EN_POLARITY_G => 0,
         FILTER_G             => 2,
         RMODE_G              => 0,
         TMODE_G              => 0)
      port map (
         --         sRst        => rst,           -- [in]
         aRst        => rst,            -- [in]
         clk         => clk,            -- [in]
         i2cSlaveIn  => i2cSlaveIn,     -- [in]
         i2cSlaveOut => i2cSlaveOut,    -- [out]
         i2ci        => i2ci,           -- [in]
         i2co        => i2co);          -- [out]

   i2ci.scl <= to_x01z(scl);
   i2ci.sda <= to_x01z(sda);
   sda      <= i2co.sda when i2co.sdaoen = '0' else 'Z';
   scl      <= i2co.scl when i2co.scloen = '0' else 'Z';


   i2cSlaveIn.enable  <= '1';
   i2cSlaveIn.txData  <= r.dac;
   i2cSlaveIn.txValid <= '1';
   i2cSlaveIn.rxAck   <= i2cSlaveOut.rxValid;  -- Always ack   

   comb : process (i2cSlaveOut, r) is
      variable v : RegType;
   begin
      v := r;

      if (i2cSlaveOut.rxActive = '1' and i2cSlaveOut.rxValid = '1') then
         v.dac := i2cSlaveOut.rxData;
      end if;

      rin <= v;

      current <= RANGE_G * real(conv_integer(r.dac))/(2**8-1);

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
