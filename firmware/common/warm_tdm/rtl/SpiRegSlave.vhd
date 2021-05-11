-------------------------------------------------------------------------------
-- Title      : SPI Register Slave interface
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
use ieee.std_logic_arith.all;
use ieee.std_logic_unsigned.all;

library surf;
use surf.StdRtlPkg.all;

entity SpiRegSlave is
   generic (
      TPD_G       : time     := 1 ns;
      CPOL_G      : sl       := '0';
      CPHA_G      : sl       := '1';
      WORD_SIZE_G : positive := 16);
   port (
      clk : in sl;
      rst : in sl;

      sclk : in  sl;
      mosi : in  sl;
      miso : out sl;
      selL : in  sl;

      addr    : out slv(WORD_SIZE_G-2 downto 0);
      wrData  : out slv(WORD_SIZE_G-1 downto 0);
      wrValid : out sl;

      rdData : in  slv(WORD_SIZE_G-1 downto 0);
      rdReq  : out sl);

end entity;

architecture rtl of SpiRegSlave is

   type StateType is (ADDR_S, WR_DATA_S, RD_DATA_S, WR_DATA_FALL_S, RD_DATA_SEND_S, RD_DATA_SEND_FALL_S);

   type RegType is record
      state     : StateType;
      addr      : slv(WORD_SIZE_G-2 downto 0);
      wrData    : slv(WORD_SIZE_G-1 downto 0);
      wrValid   : sl;
      spiRdData : slv(WORD_SIZE_G-1 downto 0);
      spiRdStb  : sl;
   end record;

   constant REG_INIT_C : RegType := (
      state     => ADDR_S,
      addr      => (others => '0'),
      wrData    => (others => '0'),
      wrValid   => '0',
      spiRdData => (others => '0'),
      spiRdStb  => '0');

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal spiWrData : slv(WORD_SIZE_G-1 downto 0);
   signal spiWrStb  : sl;

begin

   U_SpiSlave_1 : entity surf.SpiSlave
      generic map (
         TPD_G       => TPD_G,
         CPOL_G      => CPOL_G,
         CPHA_G      => CPHA_G,
         WORD_SIZE_G => WORD_SIZE_G)
      port map (
         clk    => clk,                 -- [in]
         rst    => rst,                 -- [in]
         sclk   => sclk,                -- [in]
         mosi   => mosi,                -- [in]
         miso   => miso,                -- [out]
         selL   => selL,                -- [in]
         rdData => rdData,              -- [in]
         rdStb  => r.spiRdStb,          -- [in]
         wrData => spiWrData,           -- [out]
         wrStb  => spiWrStb);           -- [out]


   comb : process (r, rst, spiWrData, spiWrStb) is
      variable v : RegType;
   begin
      v := r;

      v.wrValid := '0';

      case (r.state) is
         when ADDR_S =>
            if (spiWrStb = '1') then
               v.addr := spiWrData(WORD_SIZE_G-2 downto 0);

               if spiWrData(WORD_SIZE_G-1) = '1' then
                  -- Read operation
                  -- Allow addr to propagate before reading data to send back
                  v.state := RD_DATA_S;
               else
                  -- Write operation
                  v.spiRdStb := '1';
--                  v.spiRdData := (others => '0');
                  v.state    := WR_DATA_FALL_S;
               end if;
            end if;

         when WR_DATA_FALL_S =>
            if (spiWrStb = '0') then
               v.spiRdStb := '0';
               v.state    := WR_DATA_S;
            end if;

         when WR_DATA_S =>
            if (spiWrStb = '1') then
               v.wrData   := spiWrData;
               v.wrValid  := '1';
               v.spiRdStb := '1';
               v.state    := RD_DATA_SEND_FALL_S;
            end if;

         when RD_DATA_S =>
            v.spiRdStb := '1';
            if (spiWrStb = '0') then
               v.spiRdStb := '0';
               v.state    := RD_DATA_SEND_S;
            end if;

         when RD_DATA_SEND_S =>
            if (spiWrStb = '1') then
               v.spiRdStb := '1';
               v.state    := RD_DATA_SEND_FALL_S;
            end if;

         when RD_DATA_SEND_FALL_S =>
            if (spiWrStb = '0') then
               v.spiRdStb := '0';
               v.state    := ADDR_S;
            end if;

      end case;

      if rst = '1' then
         v := REG_INIT_C;
      end if;

      rin <= v;


      addr    <= r.addr;
      wrData  <= r.wrData;
      wrValid <= r.wrValid;


   end process;

   seq : process (clk) is
   begin
      if (rising_edge(clk)) then
         r <= rin after TPD_G;
      end if;
   end process seq;

end rtl;
