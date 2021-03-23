-------------------------------------------------------------------------------
-- Title      : Timing Rx
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

library unisim;
use unisim.vcomponents.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.AxiLitePkg.all;

library warm_tdm;
use warm_tdm.TimingPkg.all;

entity TimingTx is

   generic (
      TPD_G        : time    := 1 ns;
      SIMULATION_G : boolean := false);

   port (
      timingClk125 : in sl;
      timingRst125 : in sl;

      timingTxClkP  : out sl;
      timingTxClkN  : out sl;
      timingTxDataP : out sl;
      timingTxDataN : out sl;

      axilClk         : in  sl;
      axilRst         : in  sl;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C;
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C);

end entity TimingTx;

architecture rtl of TimingTx is

   signal bitClk  : sl;
   signal wordClk : sl;
   signal wordRst : sl;

   signal timingTxCodeWord : slv(9 downto 0);

   type RegType is record
      -- Config
      enable         : sl;
      startRun       : sl;
      endRun         : sl;
      rowPeriod      : slv(15 downto 0);
      numRows        : slv(15 downto 0);
      -- State
      timingData     : LocalTimingType;
      timingTx       : slv(7 downto 0);
      -- AXIL
      axilWriteSlave : AxiLiteWriteSlaveType;
      axilReadSlave  : AxiLiteReadSlaveType;
   end record RegType;

   constant REG_INIT_C : RegType := (
      enable         => '0',
      startRun       => '0',
      endRun         => '0',
      rowPeriod      => toSlv(250, 16),  -- 125 MHz / 250 = 500 kHz
      numRows        => toSlv(80, 16),   -- Default of 80 rows
      timingTx       => IDLE_C,
      timingData     => LOCAL_TIMING_INIT_C,
      axilWriteSlave => AXI_LITE_WRITE_SLAVE_INIT_C,
      axilReadSlave  => AXI_LITE_READ_SLAVE_INIT_C);

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal timingAxilWriteMaster : AxiLiteWriteMasterType;
   signal timingAxilWriteSlave  : AxiLiteWriteSlaveType;
   signal timingAxilReadMaster  : AxiLiteReadMasterType;
   signal timingAxilReadSlave   : AxiLiteReadSlaveType;

begin

   U_AxiLiteAsync_1 : entity surf.AxiLiteAsync
      generic map (
         TPD_G         => TPD_G,
         PIPE_STAGES_G => 0)
      port map (
         sAxiClk         => axilClk,                -- [in]
         sAxiClkRst      => axilRst,                -- [in]
         sAxiReadMaster  => axilReadMaster,         -- [in]
         sAxiReadSlave   => axilReadSlave,          -- [out]
         sAxiWriteMaster => axilWriteMaster,        -- [in]
         sAxiWriteSlave  => axilWriteSlave,         -- [out]
         mAxiClk         => timingClk125,           -- [in]
         mAxiClkRst      => timingRst125,           -- [in]
         mAxiReadMaster  => timingAxilReadMaster,   -- [out]
         mAxiReadSlave   => timingAxilReadSlave,    -- [in]
         mAxiWriteMaster => timingAxilWriteMaster,  -- [out]
         mAxiWriteSlave  => timingAxilWriteSlave);  -- [in]

   comb : process (r, timingAxilReadMaster, timingAxilWriteMaster, timingRst125) is
      variable v      : RegType;
      variable axilEp : AxiLiteEndpointType;
   begin
      v := r;

      --------------------
      -- AXI Lite
      --------------------
      axiSlaveWaitTxn(axilEp, timingAxilWriteMaster, timingAxilReadMaster, v.axilWriteSlave, v.axilReadSlave);

      v.timingData.startRun := '0';
      v.timingData.endRun   := '0';
      -- Configuration
      axiSlaveRegister(axilEp, X"30", 0, v.enable);

      axiSlaveRegister(axilEp, X"00", 0, v.timingData.startRun);
      axiSlaveRegister(axilEp, X"04", 0, v.timingData.endRun);
      axiSlaveRegister(axilEp, X"08", 0, v.rowPeriod);
      axiSlaveRegister(axilEp, X"0C", 0, v.numRows);

      -- Status
      axiSlaveRegisterR(axilEp, X"10", 0, r.timingData.running);
      axiSlaveRegisterR(axilEp, X"14", 0, r.timingData.rowNum);
      axiSlaveRegisterR(axilEp, X"18", 0, r.timingData.runTime);
      axiSlaveRegisterR(axilEp, X"1C", 0, r.timingData.rowTime);
      axiSlaveRegisterR(axilEp, X"20", 0, r.timingData.readoutCount);

      axiSlaveDefault(axilEp, v.axilWriteSlave, v.axilReadSlave, AXI_RESP_DECERR_C);

      ----------------------
      -- Timing Gen
      ----------------------
      v.timingTx := IDLE_C;

      -- Start run
      if (r.timingData.startRun = '1' and r.timingData.running = '0') then
         v.timingData.running      := '1';
         v.timingData.runTime      := (others => '0');
         v.timingData.rowNum       := (others => '0');
         v.timingData.rowTime      := (others => '0');
         v.timingData.readoutCount := (others => '0');
         v.timingTx                := START_RUN_C;
      end if;


      if (r.timingData.running = '1') then
         -- Count the things
         v.timingData.runTime := r.timingData.runTime + 1;
         v.timingData.rowTime := r.timingData.rowTime + 1;

         if (r.timingData.rowTime = r.rowPeriod) then
            v.timingData.rowTime := (others => '0');
            v.timingData.rowNum  := r.timingData.rowNum + 1;

            if (r.timingData.rowNum = r.numRows) then
               v.timingData.rowNum       := (others => '0');
               v.timingData.readoutCount := r.timingData.readoutCount + 1;
            end if;
         end if;

         -- Send codes
         if (r.timingData.rowTime = 0) then
            v.timingTx := ROW_STROBE_C;

            if (r.timingData.rowNum = 0) then
               v.timingTx := FIRST_ROW_C;
            end if;
         end if;

         if (r.timingData.endRun = '1') then
            v.timingData.running := '0';
            v.timingTx           := END_RUN_C;
         end if;
      end if;


      if (timingRst125 = '1') then
         v := REG_INIT_C;
      end if;

      rin                  <= v;
      timingAxilWriteSlave <= r.axilWriteSlave;
      timingAxilReadSlave  <= r.axilReadSlave;


   end process;

   seq : process (timingClk125) is
   begin
      if (rising_edge(timingClk125)) then
         r <= rin after TPD_G;
      end if;
   end process;

   --------------------------------------
   -- Output Timing Clock
   -------------------------------------
   U_ClkOutBufDiff_1 : entity surf.ClkOutBufDiff
      generic map (
         TPD_G => TPD_G)
      port map (
         clkIn   => timingClk125,       -- [in]
         clkOutP => timingTxClkP,       -- [out]
         clkOutN => timingTxClkN);      -- [out]

   -------------------------------------------------------------------------------------------------
   -- Create serial clock for serializer
   -------------------------------------------------------------------------------------------------
   U_TimingMmcm_1 : entity warm_tdm.TimingMmcm
      generic map (
         TPD_G     => TPD_G,
         USE_HPC_G => false)
      port map (
         timingRxClk => timingClk125,   -- [in]
         timingRxRst => timingRst125,   -- [in]
         bitClk      => bitClk,         -- [out]
         wordClk     => wordClk,        -- [out]
         wordRst     => wordRst);       -- [out]

   -------------------------------------------------------------------------------------------------
   -- 8B10B encode
   -------------------------------------------------------------------------------------------------
   U_Encoder8b10b_1 : entity surf.Encoder8b10b
      generic map (
         TPD_G       => TPD_G,
         NUM_BYTES_G => 1)
      port map (
         clk     => wordClk,            -- [in]
         rst     => wordRst,            -- [in]
         dataIn  => r.timingTx,         -- [in]
         dataKIn => "1",                -- [in]
         dataOut => timingTxCodeWord);  -- [out]


   -------------------------------------------------------------------------------------------------
   -- Serialize the data stream
   -------------------------------------------------------------------------------------------------
   U_TimingSerializer_1 : entity warm_tdm.TimingSerializer
      generic map (
         TPD_G => TPD_G)
      port map (
         rst           => '0',                -- [in]
         enable        => r.enable,           -- [in]
         bitClk        => bitClk,             -- [in]
         timingTxDataP => timingTxDataP,      -- [in]
         timingTxDataN => timingTxDataN,      -- [in]
         wordClk       => wordClk,            -- [in]
         wordRst       => wordRst,            -- [in]
         dataIn        => timingTxCodeWord);  -- [out]


end architecture rtl;
