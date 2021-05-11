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

library warm_tdm;

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

      fsadj : in RealArray(3 downto 0) := (others => 8.0e3);

      iOutP : out slv(3 downto 0);
      iOutN : out slv(3 downto 0));

end entity Ad9106;


architecture sim of Ad9106 is

   constant RAMUPDATE_C   : slv(15 downto 0) := X"001D";
   constant PAT_STATUS_C  : slv(15 downto 0) := X"001E";
   constant PAT_TYPE_C    : slv(15 downto 0) := X"001F";
   constant PATTERN_DLY_C : slv(15 downto 0) := X"0020";
   constant DAC4DOF_C     : slv(15 downto 0) := X"0022";
   constant DAC3DOF_C     : slv(15 downto 0) := X"0023";
   constant DAC2DOF_C     : slv(15 downto 0) := X"0024";
   constant DAC1DOF_C     : slv(15 downto 0) := X"0025";
   constant PAT_PERIOD_C  : slv(15 downto 0) := X"0029";
   constant DAC4_DGAIN_C  : slv(15 downto 0) := X"0032";
   constant DAC3_DGAIN_C  : slv(15 downto 0) := X"0033";
   constant DAC2_DGAIN_C  : slv(15 downto 0) := X"0034";
   constant DAC1_DGAIN_C  : slv(15 downto 0) := X"0035";
   constant START_DLY4_C  : slv(15 downto 0) := X"0050";
   constant START_DLY3_C  : slv(15 downto 0) := X"0054";
   constant START_DLY2_C  : slv(15 downto 0) := X"0058";
   constant START_DLY1_C  : slv(15 downto 0) := X"005C";
   constant START_ADDR4_C : slv(15 downto 0) := X"0051";
   constant START_ADDR3_C : slv(15 downto 0) := X"0055";
   constant START_ADDR2_C : slv(15 downto 0) := X"0059";
   constant START_ADDR1_C : slv(15 downto 0) := X"005D";
   constant STOP_ADDR4_C  : slv(15 downto 0) := X"0052";
   constant STOP_ADDR3_C  : slv(15 downto 0) := X"0056";
   constant STOP_ADDR2_C  : slv(15 downto 0) := X"005A";
   constant STOP_ADDR1_C  : slv(15 downto 0) := X"005E";


   signal clk : sl;
   signal rst : sl;

   signal addr    : slv(15 downto 0) := (others => '0');
   signal wrData  : slv(15 downto 0) := (others => '0');
   signal rdData  : slv(15 downto 0) := (others => '0');
   signal wrValid : sl               := '0';
   signal rdReq   : sl               := '0';

   signal ramOut : slv16Array(3 downto 0);


   type BufRegType is record
      PATTERN_RPT    : sl;
      PATTERN_DELAY  : slv(15 downto 0);
      PATTERN_PERIOD : slv(15 downto 0);
      DAC_DIG_OFFSET : slv12Array(3 downto 0);
      DAC_DIG_GAIN   : slv12Array(3 downto 0);
      START_DLY      : slv16Array(3 downto 0);
      START_ADDR     : slv12Array(3 downto 0);
      STOP_ADDR      : slv12Array(3 downto 0);
   end record;

   constant BUF_REG_INIT_C : BufRegType := (
      PATTERN_RPT    => '0',
      PATTERN_DELAY  => (others => '0'),
      PATTERN_PERIOD => X"8000",
      DAC_DIG_OFFSET => (others => (others => '0')),
      DAC_DIG_GAIN   => (others => (others => '0')),
      START_DLY      => (others => (others => '0')),
      START_ADDR     => (others => (others => '0')),
      STOP_ADDR      => (others => (others => '0')));

   type RegType is record
      RAMUPDATE  : sl;
      BUF_READ   : sl;
      MEM_ACCESS : sl;
      PATTERN    : sl;
      RUN        : sl;
      tmp        : BufRegType;
      cfg        : BufRegType;
      rdData     : slv(15 downto 0);
      ramPtr     : slv15Array(3 downto 0);
   end record;

   constant REG_INIT_C : RegType := (
      RAMUPDATE  => '0',
      BUF_READ   => '0',
      MEM_ACCESS => '0',
      PATTERN    => '0',
      RUN        => '0',
      tmp        => BUF_REG_INIT_C,
      cfg        => BUF_REG_INIT_C,
      rdData     => (others => '0'),
      ramPtr     => (others => (others => '0')));

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

begin

   -- Create a local clock to drive SpiSlave
   U_ClkRst_1 : entity surf.ClkRst
      generic map (
         CLK_PERIOD_G      => 2 ns,
         RST_START_DELAY_G => 0 ns,
         RST_HOLD_TIME_G   => 20 ns,
         SYNC_RESET_G      => true)
      port map (
         clkP => clk,                   -- [out]
         rst  => rst);                  -- [out]

   U_SpiRegSlave_1 : entity warm_tdm.SpiRegSlave
      generic map (
         TPD_G       => TPD_G,
         CPOL_G      => '0',
         CPHA_G      => '0',
         WORD_SIZE_G => 16)
      port map (
         clk     => clk,                -- [in]
         rst     => rst,                -- [in]
         sclk    => sclk,               -- [in]
         mosi    => sdio,               -- [in]
         miso    => sdo,                -- [out]
         selL    => csB,                -- [in]
         addr    => addr(14 downto 0),  -- [out]
         wrData  => wrData,             -- [out]
         wrValid => wrValid,            -- [out]
         rdData  => r.rdData,           -- [in]
         rdReq   => rdReq);             -- [out]

   comb : process (r, rdData, wrValid, wrData, addr) is
      variable v : RegType;

      procedure spiReg(
         regAddr   : in    slv(15 downto 0);
         regOffset : in    natural range 0 to 15;
         regVar    : inout slv)
      is
      begin
         if addr = regAddr then
            v.rdData(regOffset+regVar'length-1 downto regOffset) := regVar;
            if wrValid = '1' then
               regVar := wrData(regOffset+regVar'length-1 downto regOffset);
            end if;
         end if;
      end procedure;

      procedure spiReg(
         regAddr   : in    slv(15 downto 0);
         regOffset : in    natural range 0 to 15;
         regVar    : inout sl)
      is
         variable tmp : slv(0 downto 0);
      begin
         tmp(0) := regVar;
         spiReg(regAddr, regOffset, tmp);
         regVar := tmp(0);
      end procedure;


   begin
      v := r;

      if r.RAMUPDATE = '1' then
         v.cfg := r.tmp;
      end if;


      -- Default to read from the RAM
      v.rdData := rdData;

      v.RAMUPDATE := '0';

      -- Specify a few of the registers to simulate DAC functionality
      spiReg(RAMUPDATE_C, 0, v.RAMUPDATE);

      spiReg(PAT_STATUS_C, 3, v.BUF_READ);
      spiReg(PAT_STATUS_C, 2, v.MEM_ACCESS);
      spiReg(PAT_STATUS_C, 1, v.PATTERN);
      v.PATTERN := r.PATTERN;           -- Read only
      spiReg(PAT_STATUS_C, 0, v.RUN);

      spiReg(PAT_TYPE_C, 0, v.tmp.PATTERN_RPT);

      spiReg(PATTERN_DLY_C, 0, v.tmp.PATTERN_DELAY);

      spiReg(PAT_PERIOD_C, 0, v.tmp.PATTERN_PERIOD);

      spiReg(DAC4DOF_C, 4, v.tmp.DAC_DIG_OFFSET(3));
      spiReg(DAC3DOF_C, 4, v.tmp.DAC_DIG_OFFSET(2));
      spiReg(DAC2DOF_C, 4, v.tmp.DAC_DIG_OFFSET(1));
      spiReg(DAC1DOF_C, 4, v.tmp.DAC_DIG_OFFSET(0));

      spiReg(DAC4_DGAIN_C, 4, v.tmp.DAC_DIG_GAIN(3));
      spiReg(DAC3_DGAIN_C, 4, v.tmp.DAC_DIG_GAIN(2));
      spiReg(DAC2_DGAIN_C, 4, v.tmp.DAC_DIG_GAIN(1));
      spiReg(DAC1_DGAIN_C, 4, v.tmp.DAC_DIG_GAIN(0));

      spiReg(START_DLY4_C, 0, v.tmp.START_DLY(3));
      spiReg(START_DLY3_C, 0, v.tmp.START_DLY(2));
      spiReg(START_DLY2_C, 0, v.tmp.START_DLY(1));
      spiReg(START_DLY1_C, 0, v.tmp.START_DLY(0));

      spiReg(START_ADDR4_C, 4, v.tmp.START_ADDR(3));
      spiReg(START_ADDR3_C, 4, v.tmp.START_ADDR(2));
      spiReg(START_ADDR2_C, 4, v.tmp.START_ADDR(1));
      spiReg(START_ADDR1_C, 4, v.tmp.START_ADDR(0));

      spiReg(STOP_ADDR4_C, 4, v.tmp.STOP_ADDR(3));
      spiReg(STOP_ADDR3_C, 4, v.tmp.STOP_ADDR(2));
      spiReg(STOP_ADDR2_C, 4, v.tmp.STOP_ADDR(1));
      spiReg(STOP_ADDR1_C, 4, v.tmp.STOP_ADDR(0));



      rin <= v;

   end process;

   seq : process (clk) is
   begin
      if (rising_edge(clk)) then
         r <= rin after TPD_G;
      end if;
   end process;



   U_LutRam_1 : entity surf.LutRam
      generic map (
         TPD_G        => TPD_G,
         REG_EN_G     => false,
--         MODE_G         => MODE_G,
         DATA_WIDTH_G => 16,
         ADDR_WIDTH_G => 15,
         NUM_PORTS_G  => 5)
      port map (
         clka  => clk,                  -- [in]
         wea   => wrValid,              -- [in]
         rsta  => rst,                  -- [in]
         addra => addr(14 downto 0),    -- [in]
         dina  => wrData,               -- [in]
         douta => rdData,               -- [out]
         clkb  => clk,                  -- [in]
         rstb  => rst,                  -- [in]
         addrb => r.ramPtr(0),          -- [in]
         doutb => ramOut(0),            -- [out]
         addrc => r.ramPtr(1),          -- [in]
         doutc => ramOut(1),            -- [out]
         addrd => r.ramPtr(2),          -- [in]
         doutd => ramOut(2),            -- [out]
         addre => r.ramPtr(3),          -- [in]
         doute => ramOut(3));           -- [out]

end architecture sim;
