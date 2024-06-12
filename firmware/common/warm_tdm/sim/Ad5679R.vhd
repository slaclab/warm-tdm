-------------------------------------------------------------------------------
-- Title      : Ad5679R Simulation Module
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

library warm_tdm;

entity Ad5679R is
   generic (
      TPD_G : time := 1 ns);
   port (
      --
      sclk  : in  sl;
      sdi   : in  sl;
      sdo   : out sl;
      syncB : in  sl;

      ldacB  : in sl;
      resetB : in sl;

      vout : out RealArray(15 downto 0));
end entity Ad5679R;


architecture sim of Ad5679R is

   constant NOP_CMD_C        : slv(3 downto 0) := "0000";
   constant WR_INP_CMD_C     : slv(3 downto 0) := "0001";
   constant DAC_UPDATE_CMD_C : slv(3 downto 0) := "0010";
   constant WR_DAC_CMD_C     : slv(3 downto 0) := "0011";
   constant PWR_DOWN_CMD_C   : slv(3 downto 0) := "0100";
   constant LDAC_MASK_CMD_C  : slv(3 downto 0) := "0101";
   constant SOFT_RST_CMD_C   : slv(3 downto 0) := "0110";
   constant INT_REF_CMD_C    : slv(3 downto 0) := "0111";
   constant DCEN_CMD_C       : slv(3 downto 0) := "1000";
   constant RDBACK_CMD_C     : slv(3 downto 0) := "1001";
   constant WR_ALL_INP_CMD_C : slv(3 downto 0) := "1010";
   constant WR_ALL_DAC_CMD_C : slv(3 downto 0) := "1011";



   signal clk : sl;
   signal rst : sl;

   signal wrData : slv(23 downto 0) := (others => '0');
   signal wrStb  : sl               := '0';

   type RegType is record
      inp       : slv16Array(15 downto 0);
      dac       : slv16Array(15 downto 0);
      rdData    : slv(23 downto 0);
      rdStb     : sl;
      ldacMask  : slv(15 downto 0);
      ldacLast  : sl;
      wrStbLast : sl;
   end record;

   constant REG_INIT_C : RegType := (
      inp       => (others => (others => '0')),
      dac       => (others => (others => '0')),
      rdData    => (others => '0'),
      rdStb     => '0',
      ldacMask  => (others => '0'),
      ldacLast  => '0',
      wrStbLast => '0');

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

begin

   -- Create a local clock to drive SpiSlave
   U_ClkRst_1 : entity surf.ClkRst
      generic map (
         CLK_PERIOD_G      => 10 ns,
         RST_START_DELAY_G => 0 ns,
         RST_HOLD_TIME_G   => 20 ns,
         SYNC_RESET_G      => true)
      port map (
         clkP => clk,                   -- [out]
         rst  => rst);                  -- [out]

   U_Spilave_1 : entity surf.SpiSlave
      generic map (
         TPD_G       => TPD_G,
         CPOL_G      => '0',
         CPHA_G      => '1',
         WORD_SIZE_G => 24)
      port map (
         clk    => clk,                 -- [in]
         rst    => rst,                 -- [in]
         sclk   => sclk,                -- [in]
         mosi   => sdi,                 -- [in]
         miso   => sdo,                 -- [out]
         selL   => syncB,               -- [in]
         rdData => r.rdData,            -- [in]
         rdStb  => r.rdStb,             -- [in]
         wrData => wrData,              -- [out]
         wrStb  => wrStb);              -- [out]

   comb : process (ldacB, r, resetB, wrData, wrStb) is
      variable v    : RegType;
      variable cmd  : slv(3 downto 0);
      variable addr : integer range 0 to 15;
      variable data : slv(15 downto 0);

   begin
      v := r;

      v.rdStb := '0';

      v.ldacLast  := ldacB;
      v.wrStbLast := wrStb;

      cmd  := wrData(23 downto 20);
      addr := conv_integer(wrData(19 downto 16));
      data := wrData(15 downto 0);

      if (wrStb = '1' and r.wrStbLast = '0') then
         case cmd is
            when WR_INP_CMD_C =>
               v.inp(addr) := data;

            when DAC_UPDATE_CMD_C =>
               v.dac(addr) := data;

            when WR_DAC_CMD_C =>
               v.inp(addr) := data;
               v.dac(addr) := data;

            when LDAC_MASK_CMD_C =>
               v.ldacMask := data;

            when SOFT_RST_CMD_C =>
               if (addr = 0 and data = X"1234") then
                  v := REG_INIT_C;
               end if;

            when RDBACK_CMD_C =>
               v.rdData := RDBACK_CMD_C & "0000" & r.inp(addr);
               v.rdStb  := '1';

            when WR_ALL_INP_CMD_C =>
               for i in 15 downto 0 loop
                  v.inp(i) := data;
               end loop;

            when WR_ALL_DAC_CMD_C =>
               for i in 15 downto 0 loop
                  v.dac(i) := data;
               end loop;
            when others => null;
         end case;

      end if;



      if (resetB = '0') then
         v := REG_INIT_C;
      end if;


      rin <= v;

      for i in 15 downto 0 loop
         vout(i) <= 2.5 * (real(conv_integer(r.dac(i))) / 65536.0);
      end loop;

   end process;

   seq : process (clk) is
   begin
      if (rising_edge(clk)) then
         r <= rin after TPD_G;
      end if;
   end process;


end architecture sim;
