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
use warm_tdm.TimingPkg.all;

entity TimingRx is

   generic (
      TPD_G             : time            := 1 ns;
      IODELAY_GROUP_G   : string          := "DEFAULT_GROUP";
      IDELAYCTRL_FREQ_G : real            := 200.0;
      DEFAULT_DELAY_G   : slv(4 downto 0) := (others => '0')
      );

   port (
      timingRefClkP : in sl;
      timingRefClkN : in sl;

      timingRxClkP  : in sl;
      timingRxClkN  : in sl;
      timingRxDataP : in sl;
      timingRxDataN : in sl;

      timingClkOut : out sl;
      timingRstOut : out sl;
      timingData   : out LocalTimingType);

end entity TimingRx;

architecture rtl of TimingRx is

   signal bitClk    : sl;
   signal bitClkInv : sl;
   signal wordClk   : sl;
   signal wordRst   : sl;

   type RegType is record
      slip       : sl;
      timingData : LocalTimingType;

   end record RegType;

   constant REG_INIT_C : RegType := (
      slip       => '0',
      timingData => LOCAL_TIMING_INIT_C);

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal timingRxCodeWord : slv(9 downto 0);
   signal timingRxValid    : sl;
   signal timingRxData     : slv(7 downto 0);
   signal timingRxDataK    : sl;
   signal codeErr          : sl;
   signal dispErr          : sl;

   signal timingRefClk  : sl;
   signal timingRefClkG : sl;

   signal idelayClk : sl;
   signal idelayRst : sl;

   attribute IODELAY_GROUP                 : string;
   attribute IODELAY_GROUP of IDELAYCTRL_0 : label is IODELAY_GROUP_G;

begin

   -------------------------------------------------------------------------------------------------
   -- USE Timing Refclk to create 200 MHz IODELAY CLK
   -------------------------------------------------------------------------------------------------
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

   U_MMCM_IDELAY : entity surf.ClockManager7
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


   -------------
   -- IDELAYCTRL
   -------------
   IDELAYCTRL_0 : IDELAYCTRL
      port map (
         RDY    => open,
         REFCLK => idelayClk,
         RST    => idelayRst);

   -------------------------------------------------------------------------------------------------
   -- Create serial clock for deserializer
   -------------------------------------------------------------------------------------------------
   U_TimingMmcm_1 : entity warm_tdm.TimingMmcm
      generic map (
         TPD_G => TPD_G)
      port map (
         timingRxClkP => timingRxClkP,  -- [in]
         timingRxClkN => timingRxClkN,  -- [in]
         bitClk       => bitClk,        -- [out]
         bitClkInv    => bitClkInv,     -- [out]
         wordClk      => wordClk,       -- [out]
         wordRst      => wordRst);      -- [out]

   -------------------------------------------------------------------------------------------------
   -- Deserialize the incomming data
   -------------------------------------------------------------------------------------------------
   U_TimingDeserializer_1 : entity warm_tdm.TimingDeserializer
      generic map (
         TPD_G             => TPD_G,
         IODELAY_GROUP_G   => IODELAY_GROUP_G,
         IDELAYCTRL_FREQ_G => IDELAYCTRL_FREQ_G)
      port map (
         bitClk        => bitClk,            -- [in]
         bitClkInv     => bitClkInv,         -- [in]
         timingRxDataP => timingRxDataP,     -- [in]
         timingRxDataN => timingRxDataN,     -- [in]
         wordClk       => wordClk,           -- [in]
         wordRst       => wordRst,           -- [in]
         dataOut       => timingRxCodeWord,  -- [out]
         slip          => r.slip);           -- [in]

   timingClkOut <= wordClk;
   timingRstOut <= wordRst;

   -------------------------------------------------------------------------------------------------
   -- 8B10B decode
   -------------------------------------------------------------------------------------------------
   U_Decoder8b10b_1 : entity surf.Decoder8b10b
      generic map (
         TPD_G       => TPD_G,
         NUM_BYTES_G => 1)
      port map (
         clk         => wordClk,           -- [in]
         rst         => wordRst,           -- [in]
         dataIn      => timingRxCodeWord,  -- [in]
         dataOut     => timingRxData,      -- [out]
         dataKOut(0) => timingRxDataK,     -- [out]
         validOut    => timingRxValid,     -- [out]
         codeErr(0)  => codeErr,           -- [out]
         dispErr(0)  => dispErr);          -- [out]

   comb : process (r, timingRxData, timingRxDataK, timingRxValid, wordRst) is
      variable v : RegType;
   begin
      v := r;

      if (v.timingData.running = '1') then
         v.timingData.runTime := r.timingData.runTime + 1;
         v.timingData.rowTime := r.timingData.rowTime + 1;
      end if;

      v.timingData.startRun  := '0';
      v.timingData.endRun    := '0';
      v.timingData.rowStrobe := '0';

      if (timingRxValid = '1' and timingRxDataK = '1') then
         case timingRxData is
            when START_RUN_C =>
               v.timingData.startRun := '1';
               v.timingData.runTime  := (others => '0');
               v.timingData.running  := '1';
            when END_RUN_C =>
               v.timingData.endRun  := '1';
               v.timingData.running := '0';
            when FIRST_ROW_C =>
               v.timingData.rowStrobe := '1';
               v.timingData.rowNum    := (others => '0');
               v.timingData.rowTime   := (others => '0');
            when ROW_STROBE_C =>
               v.timingData.rowStrobe := '1';
               v.timingData.rowNum    := r.timingData.rowNum + 1;
               v.timingData.rowTime   := (others => '0');
            when others => null;
         end case;
      end if;

      if (wordRst = '1') then
         v := REG_INIT_C;
      end if;

      rin <= v;

      timingData <= r.timingData;

   end process comb;

   seq : process (wordClk) is
   begin
      if (rising_edge(wordClk)) then
         r <= rin after TPD_G;
      end if;
   end process seq;


end architecture rtl;
