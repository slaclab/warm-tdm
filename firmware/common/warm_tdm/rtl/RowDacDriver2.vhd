-------------------------------------------------------------------------------
-- Title      : Fast DAC Driver
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   :
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Drives AD9767 DACs for SQ1 Bias, SQ1 Feedback or SA Feedback
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
use surf.AxiLitePkg.all;

library warm_tdm;
use warm_tdm.TimingPkg.all;

entity RowDacDriver2 is

   generic (
      TPD_G            : time             := 1 ns;
      SIMULATION_G     : boolean          := false;
      AXIL_BASE_ADDR_G : slv(31 downto 0) := (others => '0'));

   port (
      timingRxClk125 : in sl;
      timingRxRst125 : in sl;

      timingRxData : in LocalTimingType;

      dacDb    : out slv(13 downto 0);
      dacWrt   : out slv(15 downto 0);
      dacClk   : out slv(15 downto 0);
      dacSel   : out slv(15 downto 0);
      dacReset : out slv(15 downto 0) := (others => '0');

      axilClk         : in  sl;
      axilRst         : in  sl;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType;
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType);

end entity RowDacDriver2;

architecture rtl of RowDacDriver2 is

   constant TIMING_MODE_C : sl := '0';
   constant MANUAL_MODE_C : sl := '1';

   constant NUM_AXIL_C         : integer := 6;
   constant LOCAL_AXIL_C       : integer := 0;
   constant ROW_FAS_ON_AXIL_C  : integer := 4;
   constant ROW_FAS_OFF_AXIL_C : integer := 5;
   constant MAP_RAM_AXIL_C     : integer := 1;

   constant XBAR_COFNIG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_C-1 downto 0) := genAxiLiteConfig(NUM_AXIL_C, AXIL_BASE_ADDR_G, 16, 12);

   signal locAxilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_C-1 downto 0);
   signal locAxilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_C-1 downto 0) := (others => AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C);
   signal locAxilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_C-1 downto 0);
   signal locAxilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_C-1 downto 0)  := (others => AXI_LITE_READ_SLAVE_EMPTY_DECERR_C);

   signal timingAxilWriteMaster : AxiLiteWriteMasterType;
   signal timingAxilWriteSlave  : AxiLiteWriteSlaveType;
   signal timingAxilReadMaster  : AxiLiteReadMasterType;
   signal timingAxilReadSlave   : AxiLiteReadSlaveType;


   type StateType is (
      STARTUP_S,
      INIT_A_S,
      INIT_B_S,
      INIT_C_S,
      IDLE_S,
      MAP_1_S,
      MAP_2_S,
      WRITE_DAC_1_S,
      WRITE_DAC_2_S,
      UPDATE_SEQUENCE_S,
      WAIT_ROW_STROBE_S,
      MANUAL_RS_DATA_S,
      MANUAL_RS_WRITE_S,
      CLK_0_RISE_S,
      CLK_0_FALL_S,
      CLK_1_RISE_S);

   type RegType is record
      startup         : sl;
      activeRowValid  : sl;
      state           : StateType;
      mode            : sl;
      rowOnOff        : sl;
      rowAB           : sl;
      manualRowOn     : slv(7 downto 0);
      setManualRowon  : sl;
      manualRowOff    : slv(7 downto 0);
      setManualRowOff : sl;
      offIndex        : slv(7 downto 0);
      onIndex         : slv(7 downto 0);
      mapRamAddr      : slv(7 downto 0);
      cfgBoardId      : slv(1 downto 0);
      rowAddr         : slv(7 downto 0);
      dacReset        : slv(15 downto 0);
      dacDb           : slv(13 downto 0);
      dacClk          : slv(15 downto 0);
      dacWrt          : slv(15 downto 0);
      dacSel          : slv(15 downto 0);
      axilWriteSlave  : AxiLiteWriteSlaveType;
      axilReadSlave   : AxiLiteReadSlaveType;
   end record RegType;

   constant REG_INIT_C : RegType := (
      startup         => '1',
      activeRowValid  => '0',
      state           => STARTUP_S,
      mode            => MANUAL_MODE_C,
      rowOnOff        => '0',
      rowAB           => '0',
      manualRowOn     => (others => '0'),
      setManualRowOn  => '0',
      manualRowOff    => (others => '0'),
      setManualRowOff => '0',
      offIndex        => (others => '0'),
      onIndex         => (others => '0'),
      mapRamAddr      => (others => '0'),
      cfgBoardId      => "00",
      rowAddr         => (others => '0'),
      dacReset        => (others => '0'),
      dacDb           => (others => '0'),
      dacClk          => (others => '0'),
      dacWrt          => (others => '0'),
      dacSel          => (others => '0'),
      axilWriteSlave  => AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C,
      axilReadSlave   => AXI_LITE_READ_SLAVE_EMPTY_DECERR_C);

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal pwrUpWaitDone : sl;

   signal rsOnDout    : slv(15 downto 0) := (others => '0');
   signal rsOnWrValid : sl               := '0';
   signal rsOnWrAddr  : slv(4 downto 0);
   signal rsOnWrData  : slv(15 downto 0);

   signal rsOffDout    : slv(15 downto 0) := (others => '0');
   signal rsOffWrValid : sl               := '0';
   signal rsOffWrAddr  : slv(4 downto 0);
   signal rsOffWrData  : slv(15 downto 0);

   signal mapRamOut : slv(15 downto 0);


   -- Map of logic to physical channel
   -- Needed because row board reorders the DAC channels
   -- into the row select signals
   constant REMAP_C : IntegerArray(0 to 31) := (
      --aux     sq1fb     sq1bias   safb
      0  => 31, 1 => 15, 2 => 23, 3 => 7,     -- aux[7], sq1fb[7], sq1bias[7], safb[7]
      4  => 30, 5 => 14, 6 => 22, 7 => 6,     -- aux[6], sq1fb[6], sq1bias[6], safb[6]
      8  => 29, 9 => 13, 10 => 21, 11 => 5,   -- aux[5], sq1fb[5], sq1bias[5], safb[5]
      12 => 28, 13 => 12, 14 => 20, 15 => 4,  -- aux[4], sq1fb[4], sq1bias[4], safb[4]
      16 => 27, 17 => 11, 18 => 19, 19 => 3,  -- aux[3], sq1fb[3], sq1bias[3], safb[3]
      20 => 26, 21 => 10, 22 => 18, 23 => 2,  -- aux[2], sq1fb[2], sq1bias[2], safb[2]
      24 => 25, 25 => 9, 26 => 17, 27 => 1,   -- aux[1], sq1fb[1], sq1bias[1], safb[1]
      28 => 24, 29 => 8, 30 => 16, 31 => 0);  -- aux[0], sq1fb[0], sq1bias[0], safb[0]

   function getRsDac (
      chanSlv : slv)
      return integer is
   begin
      return REMAP_C(conv_integer(resize(chanSlv, 5)));
   end function;

   -- Get the dacSel value to drive for a given physical dac channel
   function getDacSel (
      dacChan : integer range 0 to 31)
      return slv is
      variable dacSel     : slv(15 downto 0);
      variable chip       : integer range 0 to 15;
      variable dacChanSlv : slv(4 downto 0);
   begin
      dacSel       := (others => '0');
      dacChanSlv   := toSlv(dacChan, 5);
      chip         := conv_integer(dacChanSlv(4 downto 1));
      dacSel(chip) := not dacChanSlv(0);
      return dacSel;
   end function;

   -- Get the dacWrt value to drive for a given physical dac channel
   function getDacWrt (
      dacChan : integer range 0 to 31)
      return slv is
      variable dacWrt     : slv(15 downto 0);
      variable chip       : integer range 0 to 15;
      variable dacChanSlv : slv(4 downto 0);
   begin
      dacWrt       := (others => '0');
      dacChanSlv   := toSlv(dacChan, 5);
      chip         := conv_integer(dacChanSlv(4 downto 1));
      dacWrt(chip) := '1';
      return dacWrt;
   end function;


begin

   U_AxiLiteCrossbar_1 : entity surf.AxiLiteCrossbar
      generic map (
         TPD_G              => TPD_G,
         NUM_SLAVE_SLOTS_G  => 1,
         NUM_MASTER_SLOTS_G => NUM_AXIL_C,
         MASTERS_CONFIG_G   => XBAR_COFNIG_C,
         DEBUG_G            => false)
      port map (
         axiClk              => axilClk,              -- [in]
         axiClkRst           => axilRst,              -- [in]
         sAxiWriteMasters(0) => axilWriteMaster,      -- [in]
         sAxiWriteSlaves(0)  => axilWriteSlave,       -- [out]
         sAxiReadMasters(0)  => axilReadMaster,       -- [in]
         sAxiReadSlaves(0)   => axilReadSlave,        -- [out]
         mAxiWriteMasters    => locAxilWriteMasters,  -- [out]
         mAxiWriteSlaves     => locAxilWriteSlaves,   -- [in]
         mAxiReadMasters     => locAxilReadMasters,   -- [out]
         mAxiReadSlaves      => locAxilReadSlaves);   -- [in]

   U_AxiLiteAsync_1 : entity surf.AxiLiteAsync
      generic map (
         TPD_G         => TPD_G,
         PIPE_STAGES_G => 0)
      port map (
         sAxiClk         => axilClk,                            -- [in]
         sAxiClkRst      => axilRst,                            -- [in]
         sAxiReadMaster  => locAxilReadMasters(LOCAL_AXIL_C),   -- [in]
         sAxiReadSlave   => locAxilReadSlaves(LOCAL_AXIL_C),    -- [out]
         sAxiWriteMaster => locAxilWriteMasters(LOCAL_AXIL_C),  -- [in]
         sAxiWriteSlave  => locAxilWriteSlaves(LOCAL_AXIL_C),   -- [out]
         mAxiClk         => timingRxClk125,                     -- [in]
         mAxiClkRst      => timingRxRst125,                     -- [in]
         mAxiReadMaster  => timingAxilReadMaster,               -- [out]
         mAxiReadSlave   => timingAxilReadSlave,                -- [in]
         mAxiWriteMaster => timingAxilWriteMaster,              -- [out]
         mAxiWriteSlave  => timingAxilWriteSlave);              -- [in]

   U_AxiDualPortRam_MAP_RAM : entity surf.AxiDualPortRam
      generic map (
         TPD_G            => TPD_G,
         SYNTH_MODE_G     => "inferred",
         MEMORY_TYPE_G    => "distributed",
         READ_LATENCY_G   => 0,
         AXI_WR_EN_G      => true,
         SYS_WR_EN_G      => false,
         SYS_BYTE_WR_EN_G => false,
         COMMON_CLK_G     => false,
         ADDR_WIDTH_G     => 8,
         DATA_WIDTH_G     => 16,
         INIT_G           => X"8080")                            -- init to midscale for DAC
      port map (
         axiClk         => axilClk,                              -- [in]
         axiRst         => axilRst,                              -- [in]
         axiReadMaster  => locAxilReadMasters(MAP_RAM_AXIL_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(MAP_RAM_AXIL_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(MAP_RAM_AXIL_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(MAP_RAM_AXIL_C),   -- [out]
         clk            => timingRxClk125,                       -- [in]
         rst            => timingRxRst125,                       -- [in]
         addr           => r.mapRamAddr,                         -- [in]
         dout           => mapRamOut);                           -- [out]


   -- Store RS_ON and OFF value for each physical row select DAC on this board
   -- 32 RS DACs
   U_AxiDualPortRam_RS_ON : entity surf.AxiDualPortRam
      generic map (
         TPD_G            => TPD_G,
         SYNTH_MODE_G     => "inferred",
         MEMORY_TYPE_G    => "distributed",
         READ_LATENCY_G   => 0,
         AXI_WR_EN_G      => true,
         SYS_WR_EN_G      => false,
         SYS_BYTE_WR_EN_G => false,
         COMMON_CLK_G     => false,
         ADDR_WIDTH_G     => 5,
         DATA_WIDTH_G     => 16,
         INIT_G           => X"2000")                               -- init to midscale for DAC
      port map (
         axiClk         => axilClk,                                 -- [in]
         axiRst         => axilRst,                                 -- [in]
         axiReadMaster  => locAxilReadMasters(ROW_FAS_ON_AXIL_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(ROW_FAS_ON_AXIL_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(ROW_FAS_ON_AXIL_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(ROW_FAS_ON_AXIL_C),   -- [out]
         clk            => timingRxClk125,                          -- [in]
         rst            => timingRxRst125,                          -- [in]
         addr           => r.rowAddr(4 downto 0),                   -- [in]
         dout           => rsOnDout,                                -- [out]
         axiWrValid     => rsOnWrValid,                             -- [out]
         axiWrAddr      => rsOnWrAddr,                              -- [out]
         axiWrData      => rsOnWrData);                             -- [out]

   U_AxiDualPortRam_RS_OFF : entity surf.AxiDualPortRam
      generic map (
         TPD_G            => TPD_G,
         SYNTH_MODE_G     => "inferred",
         MEMORY_TYPE_G    => "distributed",
         READ_LATENCY_G   => 0,
         AXI_WR_EN_G      => true,
         SYS_WR_EN_G      => false,
         SYS_BYTE_WR_EN_G => false,
         COMMON_CLK_G     => false,
         ADDR_WIDTH_G     => 5,
         DATA_WIDTH_G     => 16,
         INIT_G           => X"2000")                                -- init to midscale for DAC
      port map (
         axiClk         => axilClk,                                  -- [in]
         axiRst         => axilRst,                                  -- [in]
         axiReadMaster  => locAxilReadMasters(ROW_FAS_OFF_AXIL_C),   -- [in]
         axiReadSlave   => locAxilReadSlaves(ROW_FAS_OFF_AXIL_C),    -- [out]
         axiWriteMaster => locAxilWriteMasters(ROW_FAS_OFF_AXIL_C),  -- [in]
         axiWriteSlave  => locAxilWriteSlaves(ROW_FAS_OFF_AXIL_C),   -- [out]
         clk            => timingRxClk125,                           -- [in]
         rst            => timingRxRst125,                           -- [in]
         addr           => r.rowAddr(4 downto 0),                    -- [in]
         dout           => rsOffDout,                                -- [out]
         axiWrValid     => rsOffWrValid,                             -- [out]
         axiWrAddr      => rsOffWrAddr,                              -- [out]
         axiWrData      => rsOffWrData);                             -- [out]



   U_PwrUpRst_1 : entity surf.PwrUpRst
      generic map (
         TPD_G         => TPD_G,
         SIM_SPEEDUP_G => SIMULATION_G,
         DURATION_G    => 125000000*5)
      port map (
         arst   => timingRxRst125,      -- [in]
         clk    => timingRxClk125,      -- [in]
         rstOut => pwrUpWaitDone);      -- [out]   



   comb : process (mapRamOut, pwrUpWaitDone, r, rsOffDout, rsOffWrAddr, rsOffWrData, rsOffWrValid,
                   rsOnDout, rsOnWrAddr, rsOnWrData, rsOnWrValid, timingAxilReadMaster,
                   timingAxilWriteMaster, timingRxData, timingRxRst125) is
      variable v      : RegType;
      variable axilEp : AxiLiteEndpointType;
   begin
      v := r;

      if (timingRxData.startRun = '1') then
         v.activeRowValid := '0';
      elsif (timingRxData.rowStrobe = '1') then
         v.activeRowValid := '1';
      end if;

      v.setManualRowOn  := '0';
      v.setManualRowOff := '0';

      ----------------------------------------------------------------------------------------------
      -- Configuration Registers
      ----------------------------------------------------------------------------------------------
      axiSlaveWaitTxn(axilEp, timingAxilWriteMaster, timingAxilReadMaster, v.axilWriteSlave, v.axilReadSlave);

      axiSlaveRegister(axilEp, X"00", 0, v.mode);
      axiSlaveRegister(axilEp, X"04", 0, v.cfgBoardId);
      axiSlaveRegister(axilEp, X"08", 0, v.dacReset);

      axiSlaveRegister(axilEp, X"10", 0, v.manualRowOn);
      axiWrDetect(axilEp, X"10", v.setManualRowOn);
      axiSlaveRegister(axilEp, X"14", 0, v.manualRowOff);
      axiWrDetect(axilEp, X"14", v.setManualRowOff);
--       axiSlaveRegister(axilEp, X"18", 0, v.manualDacCs);


      axiSlaveDefault(axilEp, v.axilWriteSlave, v.axilReadSlave, AXI_RESP_DECERR_C);


      ----------------------------------------------------------------------------------------------
      -- Convert row and chip registers to Integers
      ----------------------------------------------------------------------------------------------
--       rsDacInt  := conv_integer(r.rowNum);
--       rsDacChip := conv_integer(r.rowNum(ROW_SELECT_BITS_C-1 downto 1));
--       if (NUM_CHIP_SELECTS_G > 0) then
--          csDacInt  := conv_integer(r.chipNum) + NUM_ROW_SELECTS_G;
--          csDacChip := conv_integer(r.chipNum(CHIP_SELECT_BITS_C-1 downto 1)) + NUM_RS_DACS_C;
--       end if;

      ----------------------------------------------------------------------------------------------
      -- State Machine
      ----------------------------------------------------------------------------------------------
      v.dacWrt := (others => '0');
      v.dacClk := (others => '0');

      case r.state is

         when STARTUP_S =>
            if (pwrUpWaitDone = '0') then
               v.state := INIT_A_S;
            end if;

         when INIT_A_S =>
            -- Put mid-scale on bus (drives 0 after amplifier)
            v.dacDb  := "10000000000000";
            v.dacSel := (others => '0');
            v.state  := INIT_B_S;

         when INIT_B_S =>
            -- Write channel 0 on all dacs
            v.dacWrt := (others => '1');
            if (r.dacWrt(0) = '1') then
               -- After write, set channel 1 and clear wrt
               v.dacWrt := (others => '0');
               v.dacSel := (others => '1');
               v.state  := INIT_C_S;
            end if;

         when INIT_C_S =>
            -- Write channel 1 on all dacs
            v.dacWrt := (others => '1');
            if (r.dacWrt(0) = '1') then
               -- After wrt, clean everything and clock the outputs
               -- Will return to IDLE_S after clocking
               v.dacDb  := (others => '0');
               v.dacWrt := (others => '0');
               v.dacSel := (others => '0');
               v.state  := CLK_0_RISE_S;
            end if;

         when IDLE_S =>
            v.rowAddr := (others => '0');

            -- In timing mode, wait for row strobe to set next RS DAC
            if (r.mode = TIMING_MODE_C) then
               if (timingRxData.stageNextRow = '1' and r.activeRowValid = '0') then
                  v.onIndex         := timingRxData.rowIndexNext;
                  v.rowOnOff        := '1';
                  v.rowAB           := '0';
                  v.state           := MAP_1_S;

               elsif (timingRxData.stageNextRow = '1') then
                  v.state    := MAP_1_S;
                  v.offIndex := timingRxData.rowIndex;
                  v.onIndex  := timingRxData.rowIndexNext;
               end if;
            elsif (r.mode = MANUAL_MODE_C) then
               if (rsOnWrValid = '1') then
                  v.rowAddr := '0' & r.cfgBoardId & rsOnWrAddr;
                  v.dacDb   := rsOnWrData(13 downto 0);
                  v.state   := MANUAL_RS_DATA_S;
               elsif (rsOffWrValid = '1') then
                  v.rowAddr := '0' & r.cfgBoardId & rsOffWrAddr;
                  v.dacDb   := rsOffWrData(13 downto 0);
                  v.state   := MANUAL_RS_DATA_S;
               end if;

               if (r.setManualRowOn = '1') then
                  v.onIndex  := r.manualRowOn;
                  v.rowOnOff := '1';
                  v.rowAB    := '0';
                  v.state    := MAP_1_S;
               end if;

               if (r.setManualRowOff = '1') then
                  v.offIndex := r.manualRowOff;
                  v.rowOnOff := '0';
                  v.rowAB    := '0';
                  v.state    := MAP_1_S;
               end if;
            end if;

         -------------------------------------------------------------------------------------------
         -- Timing Sequence
         -- Turn off row, turn off chip, turn on row, turn on chip
         -------------------------------------------------------------------------------------------
         when MAP_1_S =>
            -- Select either the on or off index
            if (r.rowOnOff = '0') then
               v.mapRamAddr := r.offIndex;
            else
               v.mapRamAddr := r.onIndex;
            end if;

            v.state := MAP_2_S;

         when MAP_2_S =>
            if (r.rowAB = '0') then
               v.rowAddr := mapRamOut(7 downto 0);
            else
               v.rowAddr := mapRamOut(15 downto 8);
            end if;

            v.state := WRITE_DAC_1_S;

         when WRITE_DAC_1_S =>
            if (r.rowOnOff = '0') then
               v.dacDb := rsOffDout(13 downto 0);
            else
               v.dacDb := rsOnDout(13 downto 0);
            end if;

            v.dacSel := getDacSel(getRsDac(r.rowAddr));
            v.state  := WRITE_DAC_2_S;

         when WRITE_DAC_2_S =>
            -- Will write nothing here if board not addressed
            if (r.rowAddr(7) = '0' and r.rowAddr(6 downto 5) = r.cfgBoardId) then
               v.dacWrt := getDacWrt(getRsDac(r.rowAddr));
            end if;
            v.state := UPDATE_SEQUENCE_S;

         when UPDATE_SEQUENCE_S =>
            -- Could do this in WRITE_DAC_2_S
            v.rowAb := not r.rowAb;
            if (r.rowAB = '1') then
               v.rowOnOff := not r.rowOnOff;
            end if;

            if (r.rowOnOff = '1' and r.rowAb = '1') then
               -- Done writing next DAC values
               v.state := WAIT_ROW_STROBE_S;
            else
               -- Do Next DAC write
               v.state := MAP_1_S;
            end if;

            -- Override for manual row activation/deactivation
            -- Clock the DAC values after doing just on or off
            if (r.mode = MANUAL_MODE_C and r.rowAB = '1') then
               v.state := CLK_0_RISE_S;
            end if;

         when WAIT_ROW_STROBE_S =>
            if (timingRxData.rowStrobe = '1') then
               v.state := CLK_0_RISE_S;
            elsif (timingRxData.running = '0') then
               v.dacDb  := (others => '0');
               v.dacSel := (others => '0');
               v.state  := IDLE_S;
            end if;

         when MANUAL_RS_DATA_S =>
            v.dacSel := getDacSel(getRsDac(r.rowAddr));
            v.state  := MANUAL_RS_WRITE_S;

         when MANUAL_RS_WRITE_S =>
            v.dacWrt := getDacWrt(getRsDac(r.rowAddr));
            v.state  := CLK_0_RISE_S;

         when CLK_0_RISE_S =>
            v.dacSel := (others => '0');
            v.dacDb  := (others => '0');
            v.dacClk := (others => '1');
            v.state  := CLK_0_FALL_S;

         when CLK_0_FALL_S =>
            v.dacClk := (others => '0');
            v.state  := CLK_1_RISE_S;

         when CLK_1_RISE_S =>
            v.dacClk := (others => '1');
            v.state  := IDLE_S;

         when others => null;
      end case;

      if (timingRxRst125 = '1') then
         v := REG_INIT_C;
      end if;


      ----------------------------------------------------------------------------------------------
      -- Drive outputs
      ----------------------------------------------------------------------------------------------
      dacDb    <= r.dacDb;
      dacWrt   <= r.dacWrt;
      dacSel   <= r.dacSel;
      dacClk   <= r.dacClk;
      dacReset <= r.dacReset;

      timingAxilReadSlave  <= r.axilReadSlave;
      timingAxilWriteSlave <= r.axilWriteSlave;

      rin <= v;

   end process comb;

   seq : process (timingRxClk125) is
   begin
      if (rising_edge(timingRxClk125)) then
         r <= rin after TPD_G;
      end if;
   end process seq;

end architecture rtl;
