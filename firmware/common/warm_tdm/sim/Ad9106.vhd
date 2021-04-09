-------------------------------------------------------------------------------
-- Title      : Ad9106 Simulation Module
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
use ieee.std_logic_arith.all;
use ieee.std_logic_unsigned.all;

library surf;
use surf.StdRtlPkg.all;

entity Ad9106 is
   generic (
      TPD_G : time := 1 ns);
   port (
      --
      sclk : in  sl;
      sdio : in  sl;
      sdo  : out sl;
      csB  : in  sl;

      clkP     : in sl;
      clkN     : in sl;
      triggerB : in sl;

      fsadj : in RealArray(3 downto 0) := (others => 8.0e3)

      iOutP : out slv(3 downto 0);
      iOutN : out slv(3 downto 0));

end entity Ad9106;


architecture sim of Ad9106 is

   signal clk : sl;
   signal rst : sl;

   signal rdData : slv(15 downto 0) := (others => '0');
   signal rdStb : sl := (others => '0');

   signal wrData : slv(15 downto 0);
   signal wrStb : sl;

begin

   -- Create a local clock to drive SpiSlave
   U_ClkRst_1: entity surf.ClkRst
      generic map (
         CLK_PERIOD_G      => 10 ns;
         RST_START_DELAY_G => 0 ns;
         RST_HOLD_TIME_G => 20 ns
         SYNC_RESET_G => true)
      port map (
         clkP => clk,                  -- [out]
         rst  => rst)                   -- [out]


   U_SpiSlave_1: entity surf.SpiSlave
      generic map (
         TPD_G       => TPD_G,
         CPOL_G      => '0',
         CPHA_G      => '0',
         WORD_SIZE_G => 16)
      port map (
         clk    => clk,                 -- [in]
         rst    => rst,                 -- [in]
         sclk   => sclk,                -- [in]
         mosi   => sdio,                -- [in]
         miso   => sdo,                -- [out]
         selL   => csB,                -- [in]
         rdData => rdData,              -- [in]
         rdStb  => rdStb,               -- [in]
         wrData => wrData,              -- [out]
         wrStb  => wrStb);              -- [out]

   comb: process (wrData, wrStb) is
      variable v : RegType;
   begin
      v := r;

      v.rdStb := '0';

      case r.state is
         when WAIT_ADDR_S =>
            if (wrStb = '1') then
               v.op := wrData(15);
               v.addr := wrData(14 downto 0);               
               if (wrData(15) = '0') then
                  v.state := WAIT_WR_STB_FALL_S
                  v.rdStb := '1';
               else
                  v.rdEn := '1';
               end if;
            end if;

         when WAIT_STB_FALL_ADDR_S =>
            if (wrStb = '0') then
               v.state := WAIT_DATA_S;
            end if;
            
         when WAIT_DATA_S =>
            if (wrStb = '1') then
               v.state := WAIT_STB_FALL_DATA_S;
               v.rdStb := '1';
               if (r.op = 0) then
                  v.wrData := wrData;
                  v.wrEn := '1';
               end if;
            end if;


         when WAIT_STB_FALL_DATA_S =>
            if (wrStb = '0') then
               v.state := WAIT_ADDR_S;
            end if;
            
      end case;

      if (r.wrEn := '1' or r.rdEn = '1') then

         case r.addr is
            when SPICONFIG_C =>
               if (r.wrEn = '1') then
                  v.regs.LSBFIRST := r.wrData(15);
                  v.regs.SPI3WIRE := r.wrData(14);
                  v.regs.
               end if;

               
            when others => null;
         end case;
         
      end if;
      
   end process comb;

end architecture sim;
