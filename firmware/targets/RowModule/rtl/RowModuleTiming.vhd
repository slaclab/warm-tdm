-------------------------------------------------------------------------------
-- Title      : Row Module Timing
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Timing receiver logic for row module
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

library unisim;
use unisim.vcomponents.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.AxiLitePkg.all;
use surf.I2cPkg.all;

library warm_tdm;

entity RowModuleTiming is

   generic (
      TPD_G : time := 1 ns);

   port (
      timingRefClkP : in sl;
      timingRefClkN : in sl;

      timingRxClkP  : in sl;
      timingRxClkN  : in sl;
      timingRxTrigP : in sl;
      timingRxTrigN : in sl;

      dacTriggerB : out slv(11 downto 0);
      dacClkP     : out slv(11 downto 0);
      dacClkN     : out slv(11 downto 0));

end entity RowModuleTiming;

architecture rtl of RowModuleTiming is

   constant DAC_CLK_DIV_C : integer         := 99;
   constant ALIGN_CODE_C  : slv(9 downto 0) := "0101001010";
   constant START_CODE_C  : slv(9 downto 0) := "1010110101";

   type RegType is record
      shiftReg       : slv(9 downto 0);
      dacClkDivCount : slv(7 downto 0);
      dacClk         : sl;
      dacTriggerB    : sl;
   end record RegType;

   constant REG_INIT_C : RegType := (
      shiftReg       => (others => '0'),
      dacClkDivCount => (others => '0'),
      dacClk         => '0',
      dacTriggerB    => '1');

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal timingRefClk  : sl;
   signal timingRefClkG : sl;

   signal idelayClk : sl;
   signal idelayRst : sl;

   signal timingTrigDly : sl;
   signal timingClk     : sl;
   signal timingTrig    : sl;

   signal dacClk : sl;

   attribute IODELAY_GROUP                 : string;
   attribute IODELAY_GROUP of IDELAYCTRL_0 : label is "IDELAYCTRL0";
   attribute IODELAY_GROUP of U_DELAY      : label is "IDELAYCTRL0";


begin

   U_IBUFDS_GTE2 : IBUFDS_GTE2
      port map (
         I     => timingRefClkP,
         IB    => timingRefClkN,
         CEB   => '0',
         ODIV2 => open,
         O     => timingRefClk);

   U_BUFG : BUFG
      port map (
         I => timingRefClk,
         O => timingRefClkG);

   U_MMCM : entity surf.ClockManager7
      generic map(
         TPD_G              => TPD_G,
         TYPE_G             => "MMCM",
         INPUT_BUFG_G       => false,
         FB_BUFG_G          => true,    -- Without this, will never lock in simulation
         RST_IN_POLARITY_G  => '1',
         NUM_CLOCKS_G       => 1,
         -- MMCM attributes
         BANDWIDTH_G        => "OPTIMIZED",
         CLKIN_PERIOD_G     => 4.0,     -- 250 MHz
         DIVCLK_DIVIDE_G    => 1,       -- 250 MHz
         CLKFBOUT_MULT_F_G  => 4.0,     -- 1.0GHz =  x 250 MHz
         CLKOUT0_DIVIDE_F_G => 5.0)     --  = 200 MHz = 1.0GHz/5
      port map(
         clkIn     => timingRefClkG,
         rstIn     => '0',
         clkOut(0) => idelayClk,
         rstOut(0) => idelayRst,
         locked    => open);


   IDELAYCTRL_0 : IDELAYCTRL
      port map (
         RDY    => open,
         REFCLK => idelayClk,
         RST    => idelayRst);


   TIMING_RX_CLK_BUFF : IBUFGDS
      port map (
         i  => timingRxClkP,
         ib => timingRxClkN,
         o  => timingClk);


   TIMING_RX_TRIG_BUFF : IBUFGDS
      port map (
         i  => timingRxTrigP,
         ib => timingRxTrigN,
         o  => timingTrig);

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
         IDATAIN     => timingTrig,
         DATAIN      => '0',
         LDPIPEEN    => '0',
         DATAOUT     => timingTrigDly,
         CNTVALUEOUT => open);

   comb : process (r, timingTrigDly) is
      variable v : RegType;
   begin
      v := r;

      -- Shift trigger data in
      v.shiftReg := r. shiftReg(8 downto 0) & timingTrigDly;

      -- Count every clock
      v.dacClkDivCount := r.dacClkDivCount + 1;
      if (r.dacClkDivCount = DAC_CLK_DIV_C) then
         -- Restart counter
         v.dacClkDivCount := (others => '0');

         -- Toggle clock
         v.dacClk := not r.dacClk;

         -- Reset trigger
         if (r.dacClk = '1') then
            v.dacTriggerB := '1';
         end if;
      end if;

      -- Reset clock upon align code
      if (r.shiftReg = ALIGN_CODE_C) then
         v.dacClkDivCount := (others => '0');
         v.dacClk         := '0';
      end if;

      -- Send trigger upon start code
      if (r.shiftReg = START_CODE_C) then
         v.dacTriggerB := '0';
      end if;

      rin <= v;

      for i in 11 downto 0 loop
         dacTriggerB(i) <= r.dacTriggerB;
      end loop;


   end process comb;

   DAC_CLK_BUFG : BUFG
      port map (
         i => r.dacClk,
         o => dacClk);

   DAC_CLK_OUT_BUFF_GEN : for i in 11 downto 0 generate
      U_ClkOutBufDiff_1 : entity surf.ClkOutBufDiff
         generic map (
            TPD_G        => TPD_G,
            XIL_DEVICE_G => "7SERIES")
         port map (
            clkIn   => dacClk,          -- [in]
            clkOutP => dacClkP(i),      -- [out]
            clkOutN => dacClkN(i));     -- [out]

   end generate DAC_CLK_OUT_BUFF_GEN;

   seq : process (timingClk) is
   begin
      if (rising_edge(timingClk)) then
         r <= rin after TPD_G;
      end if;
   end process seq;

end architecture rtl;
