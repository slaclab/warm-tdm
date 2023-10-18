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

entity RowDacDriver is

   generic (
      TPD_G              : time                  := 1 ns;
      NUM_ROW_SELECTS_G  : integer range 1 to 32 := 32;
      NUM_CHIP_SELECTS_G : integer range 0 to 8  := 0;
      AXIL_BASE_ADDR_G   : slv(31 downto 0)      := (others => '0'));

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

end entity RowDacDriver;

architecture rtl of RowDacDriver is

   constant TIMING_MODE_C : sl := '0';
   constant MANUAL_MODE_C : sl := '1';

   constant ROW_SELECT_BITS_C   : integer := log2(NUM_ROW_SELECTS_G);                     -- 5
   constant CHIP_SELECT_BITS_C  : integer := ite(NUM_CHIP_SELECTS_G > 0, log2(NUM_CHIP_SELECTS_G), 0);  -- 0
   constant BOARD_SELECT_BITS_C : integer := 8 - ROW_SELECT_BITS_C - CHIP_SELECT_BITS_C;  -- 3

   constant NUM_RS_DACS_C    : integer := NUM_ROW_SELECTS_G/2;                   -- 16
   constant NUM_CS_DACS_C    : integer := NUM_CHIP_SELECTS_G/2;                  -- 0
   constant NUM_SPARE_DACS_C : integer := 16 - (NUM_RS_DACS_C + NUM_CS_DACS_C);  -- 0

--   constant RS_DAC_CTRL_BITS_C : integer := (2**ROW_SELECT_BITS_C-1);   -- 8
--   constant CS_DAC_CTRL_BITS_C : integer := (2**CHIP_SELECT_BITS_C-1);  -- 4

   constant ROW_LOW_C   : integer := 0;
   constant ROW_HIGH_C  : integer := ROW_SELECT_BITS_C - 1;                            -- 4
   constant CHIP_LOW_C  : integer := ite(NUM_CHIP_SELECTS_G /= 0, ROW_HIGH_C + 1, 0);  -- 0
   constant CHIP_HIGH_C : integer := ite(NUM_CHIP_SELECTS_G /= 0, CHIP_LOW_C + CHIP_SELECT_BITS_C -1, 0);  --0

   constant ROW_CHIP_LOW_C  : integer := 0;
   constant ROW_CHIP_HIGH_C : integer := ROW_SELECT_BITS_C + CHIP_SELECT_BITS_C - 1;  -- 4
   constant ROW_CHIP_BITS_C : integer := ROW_CHIP_HIGH_C - ROW_CHIP_LOW_C + 1;        -- 5
   constant BOARD_LOW_C     : integer := ite(CHIP_SELECT_BITS_C /= 0, CHIP_HIGH_C + 1, ROW_HIGH_C + 1);  --
   --5
   constant BOARD_HIGH_C    : integer := BOARD_LOW_C + BOARD_SELECT_BITS_C - 1;       -- 7

   constant RS_DAC_LOW_C  : integer := 0;
   constant RS_DAC_HIGH_C : integer := (NUM_ROW_SELECTS_G / 2) - 1;                  -- 15
   constant CS_DAC_LOW_C  : integer := RS_DAC_HIGH_C + 1;                            -- 16
   constant CS_DAC_HIGH_C : integer := CS_DAC_LOW_C + (NUM_CHIP_SELECTS_G / 2) - 1;  -- 15

   constant NUM_AXIL_C          : integer := 5;
   constant LOCAL_AXIL_C        : integer := 0;
   constant ROW_FAS_ON_AXIL_C   : integer := 1;
   constant ROW_FAS_OFF_AXIL_C  : integer := 2;
   constant CHIP_FAS_ON_AXIL_C  : integer := 3;
   constant CHIP_FAS_OFF_AXIL_C : integer := 4;

   constant XBAR_COFNIG_C : AxiLiteCrossbarMasterConfigArray(NUM_AXIL_C-1 downto 0) := genAxiLiteConfig(NUM_AXIL_C, AXIL_BASE_ADDR_G, 16, 12);

   signal locAxilWriteMasters : AxiLiteWriteMasterArray(NUM_AXIL_C-1 downto 0);
   signal locAxilWriteSlaves  : AxiLiteWriteSlaveArray(NUM_AXIL_C-1 downto 0) := (others => AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C);
   signal locAxilReadMasters  : AxiLiteReadMasterArray(NUM_AXIL_C-1 downto 0);
   signal locAxilReadSlaves   : AxiLiteReadSlaveArray(NUM_AXIL_C-1 downto 0)  := (others => AXI_LITE_READ_SLAVE_EMPTY_DECERR_C);

   type StateType is (
      INIT_A_S,
      INIT_B_S,
      INIT_C_S,
      IDLE_S,
      OFF_PRE_S,
      ROW_OFF_DATA_S,
      ROW_OFF_WRITE_S,
      CHIP_OFF_DATA_S,
      CHIP_OFF_WRITE_S,
      ON_PRE_S,
      ROW_ON_DATA_S,
      ROW_ON_WRITE_S,
      CHIP_ON_DATA_S,
      CHIP_ON_WRITE_S,
      MANUAL_RS_DATA_S,
      MANUAL_RS_WRITE_S,
      MANUAL_CS_DATA_S,
      MANUAL_CS_WRITE_S,
      CLK_0_RISE_S,
      CLK_0_FALL_S,
      CLK_1_RISE_S);

   type RegType is record
      startup    : sl;
      state      : StateType;
      mode       : sl;
      cfgBoardId : slv(BOARD_SELECT_BITS_C-1 downto 0);

      boardId        : slv(BOARD_SELECT_BITS_C-1 downto 0);
      rowNum         : slv(ROW_SELECT_BITS_C-1 downto 0);
      chipNum        : slv(CHIP_SELECT_BITS_C-1 downto 0);
      rowChipNum     : slv(ROW_CHIP_BITS_C-1 downto 0);
      dacReset       : slv(15 downto 0);
      dacDb          : slv(13 downto 0);
      dacClk         : slv(15 downto 0);
      dacWrt         : slv(15 downto 0);
      dacSel         : slv(15 downto 0);
--       rsDacWrt       : slv(NUM_RS_DACS_C-1 downto 0);
--       rsDacSel       : slv(NUM_RS_DACS_C-1 downto 0);
--       csDacWrt       : slv(NUM_CS_DACS_C-1 downto 0);
--       csDacSel       : slv(NUM_CS_DACS_C-1 downto 0);
      axilWriteSlave : AxiLiteWriteSlaveType;
      axilReadSlave  : AxiLiteReadSlaveType;
   end record RegType;

   constant REG_INIT_C : RegType := (
      startup        => '1',
      state          => INIT_A_S,
      mode           => TIMING_MODE_C,
      cfgBoardId     => (others => '0'),
      boardId        => (others => '0'),
      rowNum         => (others => '0'),
      chipNum        => (others => '0'),
      rowChipNum     => (others => '0'),
      dacReset       => (others => '0'),
      dacDb          => (others => '0'),
      dacClk         => (others => '0'),
      dacWrt         => (others => '0'),
      dacSel         => (others => '0'),
--       rsDacWrt       => (others => '0'),
--       rsDacSel       => (others => '0'),
--       csDacWrt       => (others => '0'),
--       csDacSel       => (others => '0'),
      axilWriteSlave => AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C,
      axilReadSlave  => AXI_LITE_READ_SLAVE_EMPTY_DECERR_C);

   signal r   : RegType := REG_INIT_C;
   signal rin : RegType;

   signal rsOnDout    : slv(15 downto 0) := (others => '0');
   signal rsOnWrValid : sl               := '0';
   signal rsOnWrAddr  : slv(ROW_SELECT_BITS_C+CHIP_SELECT_BITS_C-1 downto 0);
   signal rsOnWrData  : slv(15 downto 0);

   signal rsOffDout    : slv(15 downto 0) := (others => '0');
   signal rsOffWrValid : sl               := '0';
   signal rsOffWrAddr  : slv(ROW_SELECT_BITS_C+CHIP_SELECT_BITS_C-1 downto 0);
   signal rsOffWrData  : slv(15 downto 0);

   signal csOnDout    : slv(15 downto 0) := (others => '0');
   signal csOnWrValid : sl               := '0';
   signal csOnWrAddr  : slv(CHIP_SELECT_BITS_C-1 downto 0);
   signal csOnWrData  : slv(15 downto 0);

   signal csOffDout    : slv(15 downto 0) := (others => '0');
   signal csOffWrValid : sl               := '0';
   signal csOffWrAddr  : slv(CHIP_SELECT_BITS_C-1 downto 0);
   signal csOffWrData  : slv(15 downto 0);


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


   -- Store RS_ON value for each row that can be addressed by this board
   -- NUM_ROW_SELECTS_G * NUM_CHIP_SELECTS_G 
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
         ADDR_WIDTH_G     => ROW_CHIP_BITS_C,
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
         addr           => r.rowChipNum,                            -- [in]
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
         ADDR_WIDTH_G     => ROW_CHIP_BITS_C,
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
         addr           => r.rowChipNum,                             -- [in]
         dout           => rsOffDout,                                -- [out]
         axiWrValid     => rsOffWrValid,                             -- [out]
         axiWrAddr      => rsOffWrAddr,                              -- [out]
         axiWrData      => rsOffWrData);                             -- [out]


   -- Store Chip Select On value for each chip select line driven by this board
   -- NUM_CHIP_SELECTS_G
   GEN_CS_ON_RAM : if (NUM_CHIP_SELECTS_G /= 0) generate
      U_AxiDualPortRam_CS_ON : entity surf.AxiDualPortRam
         generic map (
            TPD_G            => TPD_G,
            SYNTH_MODE_G     => "inferred",
            MEMORY_TYPE_G    => "distributed",
            READ_LATENCY_G   => 0,
            AXI_WR_EN_G      => true,
            SYS_WR_EN_G      => false,
            SYS_BYTE_WR_EN_G => false,
            COMMON_CLK_G     => false,
            ADDR_WIDTH_G     => CHIP_SELECT_BITS_C,
            DATA_WIDTH_G     => 16,
            INIT_G           => X"2000")                                -- init to midscale for DAC
         port map (
            axiClk         => axilClk,                                  -- [in]
            axiRst         => axilRst,                                  -- [in]
            axiReadMaster  => locAxilReadMasters(CHIP_FAS_ON_AXIL_C),   -- [in]
            axiReadSlave   => locAxilReadSlaves(CHIP_FAS_ON_AXIL_C),    -- [out]
            axiWriteMaster => locAxilWriteMasters(CHIP_FAS_ON_AXIL_C),  -- [in]
            axiWriteSlave  => locAxilWriteSlaves(CHIP_FAS_ON_AXIL_C),   -- [out]
            clk            => timingRxClk125,                           -- [in]
            rst            => timingRxRst125,                           -- [in]
            addr           => r.chipNum,                                -- [in]
            dout           => csOnDout,                                 -- [out]
            axiWrValid     => csOnWrValid,                              -- [out]
            axiWrAddr      => csOnWrAddr,                               -- [out]
            axiWrData      => csOnWrData);                              -- [out]

      U_AxiDualPortRam_CS_OFF : entity surf.AxiDualPortRam
         generic map (
            TPD_G            => TPD_G,
            SYNTH_MODE_G     => "inferred",
            MEMORY_TYPE_G    => "distributed",
            READ_LATENCY_G   => 0,
            AXI_WR_EN_G      => true,
            SYS_WR_EN_G      => false,
            SYS_BYTE_WR_EN_G => false,
            COMMON_CLK_G     => false,
            ADDR_WIDTH_G     => CHIP_SELECT_BITS_C,
            DATA_WIDTH_G     => 16,
            INIT_G           => X"2000")                                 -- init to midscale for DAC
         port map (
            axiClk         => axilClk,                                   -- [in]
            axiRst         => axilRst,                                   -- [in]
            axiReadMaster  => locAxilReadMasters(CHIP_FAS_OFF_AXIL_C),   -- [in]
            axiReadSlave   => locAxilReadSlaves(CHIP_FAS_OFF_AXIL_C),    -- [out]
            axiWriteMaster => locAxilWriteMasters(CHIP_FAS_OFF_AXIL_C),  -- [in]
            axiWriteSlave  => locAxilWriteSlaves(CHIP_FAS_OFF_AXIL_C),   -- [out]
            clk            => timingRxClk125,                            -- [in]
            rst            => timingRxRst125,                            -- [in]
            addr           => r.chipNum,                                 -- [in]
            dout           => csOffDout,                                 -- [out]
            axiWrValid     => csOffWrValid,                              -- [out]
            axiWrAddr      => csOffWrAddr,                               -- [out]
            axiWrData      => csOffWrData);                              -- [out]

   end generate GEN_CS_ON_RAM;



   comb : process (csOffDout, csOnDout, csOnWrAddr, csOnWrData, csOnWrValid, locAxilReadMasters,
                   locAxilWriteMasters, r, rsOffDout, rsOnDout, rsOnWrAddr, rsOnWrData, rsOnWrValid,
                   timingRxData, timingRxRst125) is
      variable v         : RegType;
      variable axilEp    : AxiLiteEndpointType;
      variable rsDacInt  : integer;
      variable rsDacChip : integer;
      variable csDacInt  : integer;
      variable csDacChip : integer;

   begin
      v := r;

      ----------------------------------------------------------------------------------------------
      -- Configuration Registers
      ----------------------------------------------------------------------------------------------
      axiSlaveWaitTxn(axilEp, locAxilWriteMasters(0), locAxilReadMasters(0), v.axilWriteSlave, v.axilReadSlave);

      axiSlaveRegister(axilEp, X"00", 0, v.mode);
      if (BOARD_SELECT_BITS_C > 0) then
         axiSlaveRegister(axilEp, X"04", 0, v.cfgBoardId);
      end if;
      axiSlaveRegister(axilEp, X"08", 0, v.dacReset);

      axiSlaveDefault(axilEp, v.axilWriteSlave, v.axilReadSlave, AXI_RESP_DECERR_C);


      ----------------------------------------------------------------------------------------------
      -- Convert row and chip registers to Integers
      ----------------------------------------------------------------------------------------------
      rsDacInt  := conv_integer(r.rowNum);
      rsDacChip := conv_integer(r.rowNum(ROW_SELECT_BITS_C-1 downto 1));
      if (NUM_CHIP_SELECTS_G > 0) then
         csDacInt  := conv_integer(r.chipNum) + NUM_ROW_SELECTS_G;
         csDacChip := conv_integer(r.chipNum(CHIP_SELECT_BITS_C-1 downto 1)) + NUM_RS_DACS_C;
      end if;

      ----------------------------------------------------------------------------------------------
      -- State Machine
      ----------------------------------------------------------------------------------------------
      v.dacWrt := (others => '0');
      v.dacClk := (others => '0');

      case r.state is

         when INIT_A_S =>
            -- Put mid-scale on bus (drives 0 after amplifier)
            v.dacDb  := "1000000000";
            v.dacSel := (others => '0');
            v.state  := INIT_B_S;

         when INIT_B_S =>
            -- Write channel 0 and all dacs
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
            v.rowNum := (others => '0');

            -- In timing mode, wait for row strobe to set next RS DAC
            if (r.mode = TIMING_MODE_C) then
               -- Start setting DACs after sampling of current row is done
               if (timingRxData.lastSample = '1') then
                  v.state := OFF_PRE_S;
               end if;
            elsif (r.mode = MANUAL_MODE_C) then
               if (rsOnWrValid = '1') then
                  v.rowNum := rsOnWrAddr(ROW_HIGH_C downto ROW_LOW_C);
                  v.dacDb  := rsOnWrData(13 downto 0);
                  v.state  := MANUAL_RS_DATA_S;
               end if;
               if (csOnWrValid = '1') then
                  v.chipNum := csOnWrAddr;
                  v.dacDb   := csOnWrData(13 downto 0);
                  v.state   := MANUAL_CS_DATA_S;
               end if;

            end if;

         -------------------------------------------------------------------------------------------
         -- Timing Sequence
         -- Turn off row, turn off chip, turn on row, turn on chip
         -------------------------------------------------------------------------------------------
         when OFF_PRE_S =>
            v.rowNum     := timingRxData.rowIndex(ROW_HIGH_C downto ROW_LOW_C);
            v.chipNum    := timingRxData.rowIndex(CHIP_HIGH_C downto CHIP_LOW_C);
            v.rowChipNum := timingRxData.rowIndex(ROW_CHIP_HIGH_C downto ROW_CHIP_LOW_C);
            if (BOARD_SELECT_BITS_C > 0) then
               v.boardId := timingRxData.rowIndex(BOARD_HIGH_C downto BOARD_LOW_C);
            end if;
            v.state := ROW_OFF_DATA_S;

         when ROW_OFF_DATA_S =>
            v.dacDb             := rsOffDout(13 downto 0);
            v.dacSel(rsDacChip) := not r.rowNum(0);
            v.state             := ROW_OFF_WRITE_S;

         when ROW_OFF_WRITE_S =>
            if (BOARD_SELECT_BITS_C > 0 and r.boardId = r.cfgBoardId) then
               v.dacWrt(rsDacChip) := '1';
            end if;
            if (NUM_CHIP_SELECTS_G > 0) then
               v.state := CHIP_OFF_DATA_S;
            else
               v.state := ON_PRE_S;
            end if;

         when CHIP_OFF_DATA_S =>
            v.dacDb             := csOffDout(13 downto 0);
            v.dacSel(csDacChip) := not r.chipNum(0);
            v.state             := CHIP_OFF_WRITE_S;

         when CHIP_OFF_WRITE_S =>
            if (r.boardId = r.cfgBoardId) then
               v.dacWrt(csDacChip) := '1';
            end if;
            v.state := ON_PRE_S;

         when ON_PRE_S =>
            -- Switch to next row index for DAC address
            v.rowNum     := timingRxData.rowIndexNext(ROW_HIGH_C downto ROW_LOW_C);
            v.chipNum    := timingRxData.rowIndexNext(CHIP_HIGH_C downto CHIP_LOW_C);
            v.rowChipNum := timingRxData.rowIndexNext(ROW_CHIP_HIGH_C downto ROW_CHIP_LOW_C);
            v.boardId    := timingRxData.rowIndexNext(BOARD_HIGH_C downto BOARD_LOW_C);
            v.state      := ROW_ON_DATA_S;

         when ROW_ON_DATA_S =>
            v.dacDb             := rsOnDout(13 downto 0);
            v.dacSel(rsDacChip) := not r.rowNum(0);

         when ROW_ON_WRITE_S =>
            if (r.boardId = r.cfgBoardId) then
               v.dacWrt(rsDacChip) := '1';
            end if;
            if (NUM_CHIP_SELECTS_G > 0) then
               v.state := CHIP_ON_DATA_S;
            else
               v.state := CLK_0_RISE_S;
            end if;

         when CHIP_ON_DATA_S =>
            v.dacDb             := csOnDout(13 downto 0);
            v.dacSel(csDacChip) := not r.chipNum(0);

         when CHIP_ON_WRITE_S =>
            if (r.boardId = r.cfgBoardId) then
               v.dacWrt(csDacChip) := '1';
            end if;
            v.state := CLK_0_RISE_S;

         when MANUAL_RS_DATA_S =>
            -- DB already set, just do SEL
            v.dacSel(rsDacChip) := not r.rowNum(0);
            v.state             := MANUAL_RS_WRITE_S;

         when MANUAL_RS_WRITE_S =>
            v.dacWrt(rsDacChip) := '1';
            v.state             := CLK_0_RISE_S;

         when MANUAL_CS_DATA_S =>
            v.dacSel(csDacChip) := not r.chipNum(0);
            v.state             := MANUAL_CS_WRITE_S;

         when MANUAL_CS_WRITE_S =>
            v.dacWrt(csDacChip) := '1';
            v.state             := CLK_0_RISE_S;

         when CLK_0_RISE_S =>
            -- Wait for row strobe to clock new DAC values if in TIMING_MODE
            if (r.mode = TIMING_MODE_C and timingRxData.rowStrobe = '1') or
               (r.mode = MANUAL_MODE_C) then
               v.dacClk := (others => '1');
               v.state  := CLK_0_FALL_S;
            end if;

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
      -- 
      ----------------------------------------------------------------------------------------------
--       v.dacWrt(RS_DAC_HIGH_C downto RS_DAC_LOW_C) <= v.rsDacWrt(NUM_RS_DACS_C-1 downto 0);
--       v.dacSel(RS_DAC_HIGH_C downto RS_DAC_LOW_C) <= v.rsDacSel(NUM_RS_DACS_C-1 downto 0);

--       if (NUM_CS_DACS_C > 0) then
--          v.dacWrt(CS_DAC_HIGH_C downto CS_DAC_LOW_C) <= v.csDacWrt(NUM_CS_DACS_C-1 downto 0);
--          v.dacSel(CS_DAC_HIGH_C downto CS_DAC_LOW_C) <= v.csDacSel(NUM_CS_DACS_C-1 downto 0);
--       end if;


      ----------------------------------------------------------------------------------------------
      -- Drive outputs
      ----------------------------------------------------------------------------------------------
      dacDb    <= r.dacDb;
      dacWrt   <= r.dacWrt;
      dacSel   <= r.dacSel;
      dacClk   <= r.dacClk;
      dacReset <= r.dacReset;

      locAxilReadSlaves(0)  <= r.axilReadSlave;
      locAxilWriteSlaves(0) <= r.axilWriteSlave;

      rin <= v;

   end process comb;

   seq : process (timingRxClk125) is
   begin
      if (rising_edge(timingRxClk125)) then
         r <= rin after TPD_G;
      end if;
   end process seq;

end architecture rtl;
