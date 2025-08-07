-------------------------------------------------------------------------------
-- Title      : 
-------------------------------------------------------------------------------
-- Company    : SLAC National Accelerator Laboratory
-- Platform   : 
-- Standard   : VHDL'93/02
-------------------------------------------------------------------------------
-- Description: Multi-channel bi-quad filter. Not pipelined. Takes several
-- cycles for each result. Channel expected on TID field.
-------------------------------------------------------------------------------
-- This file is part of . It is subject to
-- the license terms in the LICENSE.txt file found in the top-level directory
-- of this distribution and at:
--    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
-- No part of , including this file, may be
-- copied, modified, propagated, or distributed except according to the terms
-- contained in the LICENSE.txt file.
-------------------------------------------------------------------------------
library ieee;
use ieee.std_logic_1164.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.AxiLitePkg.all;

library warm_tdm;
use warm_tdm.WarmTdmPkg.all;
use warm_tdm.FixedPkg.all;

entity BiquadFilter is

   generic (
      TPD_G                : time                 := 1 ns;
      AXIS_CONFIG_G        : AxiStreamConfigtype  := PID_DATA_AXIS_CFG_C;
      COEFF_HIGH_G         : integer              := 1;
      COEFF_LOW_G          : integer              := -16;
      DATA_WIDTH_G         : positive             := 14;
      CASCADE_SIZE_G       : positive             := 2;
      CHANNEL_ADDR_WIDTH_G : integer range 1 to 8 := 8);

   port (
      axisClk         : in  sl;
      axisRst         : in  sl;
      sAxisMaster     : in  AxiStreamMasterType;
      sAxisSlave      : out AxiStreamSlaveType;
      mAxisMaster     : out AxiStreamMasterType;
      mAxisSlave      : in  AxiStreamSlaveType;
      axilReadMaster  : in  AxiLiteReadMasterType;
      axilReadSlave   : out AxiLiteReadSlaveType  := AXI_LITE_READ_SLAVE_EMPTY_DECERR_C;
      axilWriteMaster : in  AxiLiteWriteMasterType;
      axilWriteSlave  : out AxiLiteWriteSlaveType := AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C
      );

end entity BiquadFilter;

architecture rtl of BiquadFilter is

   constant DATA_MATH_WIDTH_C : integer := 32;
   constant DATA_FRACT_BITS_C : integer := DATA_MATH_WIDTH_C - DATA_WIDTH_G;
   subtype DataSFixedType is sfixed(DATA_WIDTH_G-1 downto -DATA_FRACT_BITS_C);
   type DataSFixedArray is array (CASCADE_SIZE_G-1 downto 0) of DataSFixedType;
   signal dataSFixed          : DataSFixedType;

   type RamDataArray is array (CASCADE_SIZE_G-1 downto 0) of slv(DATA_MATH_WIDTH_C-1 downto 0);
   type RamStatearray is array (CASCADE_SIZE_G-1 downto 0) of slv(4*DATA_MATH_WIDTH_C-1 downto 0);

   constant COEFF_BITS_C : integer := COEFF_HIGH_G - COEFF_LOW_G + 1;
   subtype CoeffSFixedType is sfixed(COEFF_HIGH_G downto COEFF_LOW_G);
   type CoeffSlvArray is array (CASCADE_SIZE_G-1 downto 0) of slv(COEFF_BITS_C-1 downto 0);
   signal coeffSFixed    : CoeffSFixedType;

   constant RESULT_HIGH_C : integer := sfixed_high(COEFF_HIGH_G, COEFF_LOW_G, '*', DATA_WIDTH_G-1, 0);
   constant RESULT_LOW_C  : integer := sfixed_low(COEFF_HIGH_G, COEFF_LOW_G, '*', DATA_WIDTH_G-1, 0);
   subtype ResultSFixedType is sfixed(RESULT_HIGH_C downto RESULT_LOW_C);

   signal x1 : DataSFixedArray;
   signal x2 : DataSFixedArray;
   signal y1 : DataSFixedArray;
   signal y2 : DataSFixedArray;

   type StateType is (
      WAIT_DATA_S,
      WAIT_STATE_RAM_0_S,
      WAIT_STATE_RAM_1_S,
      COEFFS_S,
      FILTER_B0_S,
      FILTER_B1_S,
      FILTER_B2_S,
      FILTER_A1_S,
      FILTER_A2_S,
      RESULT_S,
      SHIFT_S,
      OUTPUT_S,
      CLEAR_FILTERS_S);

   type RegType is record
      state          : StateType;
      filterIndex    : integer range 0 to CASCADE_SIZE_G-1;
      b0             : CoeffSlvArray;
      b1             : CoeffSlvArray;
      b2             : CoeffSlvArray;
      a1             : CoeffSlvArray;
      a2             : CoeffSlvArray;
      x0_fixed       : DataSFixedType;
      x1_fixed       : DataSFixedType;
      x2_fixed       : DataSFixedType;
      y1_fixed       : DataSFixedType;
      y2_fixed       : DataSFixedType;
      b0_fixed       : CoeffSFixedType;
      b1_fixed       : CoeffSFixedType;
      b2_fixed       : CoeffSFixedType;
      a1_fixed       : CoeffSFixedType;
      a2_fixed       : CoeffSFixedType;
      coeff          : CoeffSFixedType;
      data           : DataSFixedType;
      result         : ResultSFixedType;
      clearFilters   : sl;
      ramWe          : slv(CASCADE_SIZE_G-1 downto 0);
      ramWrAddr      : ufixed(CHANNEL_ADDR_WIDTH_G-1 downto 0);
      fifoAxisSlave  : AxiStreamSlaveType;
      mAxisMaster    : AxiStreamMasterType;
      axilReadSlave  : AxiLiteReadSlaveType;
      axilWriteSlave : AxiLiteWriteSlaveType;
   end record RegType;

   constant REG_INIT_C : RegType := (
      state          => WAIT_DATA_S,
      filterIndex    => 0,
      b0             => (others => to_slv(to_sfixed(1.0, COEFF_HIGH_G, COEFF_LOW_G))),
      b1             => (others => (others => '0')),
      b2             => (others => (others => '0')),
      a1             => (others => (others => '0')),
      a2             => (others => (others => '0')),
      x0_fixed       => (others => '0'),
      x1_fixed       => (others => '0'),
      x2_fixed       => (others => '0'),
      y1_fixed       => (others => '0'),
      y2_fixed       => (others => '0'),
      b0_fixed       => (others => '0'),
      b1_fixed       => (others => '0'),
      b2_fixed       => (others => '0'),
      a1_fixed       => (others => '0'),
      a2_fixed       => (others => '0'),
      coeff          => (others => '0'),
      data           => (others => '0'),
      result         => (others => '0'),
      clearFilters   => '0',
      ramWe          => (others => '0'),
      ramWrAddr      => (others => '0'),
      fifoAxisSlave  => AXI_STREAM_SLAVE_INIT_C,
      mAxisMaster    => axiStreamMasterInit(AXIS_CONFIG_G),
      axilReadSlave  => AXI_LITE_READ_SLAVE_EMPTY_DECERR_C,
      axilWriteSlave => AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C);

   signal r   : Regtype := REG_INIT_C;
   signal rin : RegType;

   signal fifoAxisMaster : AxiStreamMasterType;
   signal ramDin         : RamStateArray;
   signal ramDout        : RamStateArray;
   signal ramWrAddr      : slv(CHANNEL_ADDR_WIDTH_G-1 downto 0);

--    signal syncAxilWriteMaster : AxiLiteWriteMasterType;
--    signal syncAxilWriteSlave  : AxiLiteWriteSlaveType;
--    signal syncAxilReadMaster  : AxiLiteReadMasterType;
--    signal syncAxilReadSlave   : AxiLiteReadSlaveType;

begin

   -- Buffer incomming samples just in case
   -- But really there shouldn't be backpressure
   U_AxiStreamFifoV2_IN_FIFO : entity surf.AxiStreamFifoV2
      generic map (
         TPD_G               => TPD_G,
         INT_PIPE_STAGES_G   => 0,
         PIPE_STAGES_G       => 1,
         SLAVE_READY_EN_G    => true,
--          VALID_THOLD_G       => 0,
--          VALID_BURST_MODE_G  => true,
--          FIFO_PAUSE_THRESH_G => 15,
         GEN_SYNC_FIFO_G     => true,
         FIFO_ADDR_WIDTH_G   => 4,
         SYNTH_MODE_G        => "xpm",
         MEMORY_TYPE_G       => "distributed",
         INT_WIDTH_SELECT_G  => "WIDE",
         SLAVE_AXI_CONFIG_G  => AXIS_CONFIG_G,
         MASTER_AXI_CONFIG_G => AXIS_CONFIG_G)
      port map (
         sAxisClk    => axisClk,             -- [in]
         sAxisRst    => axisRst,             -- [in]
         sAxisMaster => sAxisMaster,         -- [in]
         sAxisSlave  => sAxisSlave,          -- [out]
--         sAxisCtrl   => sAxisCtrl,           -- [out]
         mAxisClk    => axisClk,             -- [in]
         mAxisRst    => axisRst,             -- [in]
         mAxisMaster => fifoAxisMaster,      -- [out]
         mAxisSlave  => rin.fifoAxisSlave);  -- [in]

   -- Create a state ram for each filter in the cascade
   GEN_STATE_RAM : for i in CASCADE_SIZE_G-1 downto 0 generate
      U_Cache : entity surf.DualPortRam
         generic map (
            TPD_G         => TPD_G,
            MEMORY_TYPE_G => "bram",
            ADDR_WIDTH_G  => CHANNEL_ADDR_WIDTH_G,
            DATA_WIDTH_G  => 4*DATA_MATH_WIDTH_C)
         port map (
            -- Port A
            clka  => axisClk,
            wea   => r.ramWe(i),
            addra => ramWrAddr,
            dina  => ramDin(i),
            -- Port B
            clkb  => axisClk,
            addrb => fifoAxisMaster.tid(CHANNEL_ADDR_WIDTH_G-1 downto 0),
            doutb => ramDout(i));

      ramWrAddr <= to_slv(r.ramWrAddr);
      x1(i)     <= to_sfixed(ramDout(i)(DATA_MATH_WIDTH_C-1 downto 0), x1(i));
      x2(i)     <= to_sfixed(ramDout(i)(2*DATA_MATH_WIDTH_C-1 downto DATA_MATH_WIDTH_C), x2(i));
      y1(i)     <= to_sfixed(ramDout(i)(3*DATA_MATH_WIDTH_C-1 downto 2*DATA_MATH_WIDTH_C), y1(i));
      y2(i)     <= to_sfixed(ramDout(i)(4*DATA_MATH_WIDTH_C-1 downto 3*DATA_MATH_WIDTH_C), y2(i));
      ramDin(i) <= to_slv(r.y2_fixed) &
                   to_slv(r.y1_fixed) &
                   to_slv(r.x2_fixed) &
                   to_slv(r.x1_fixed);
   end generate;


   comb : process (axilReadMaster, axilWriteMaster, axisRst, dataSFixed, fifoAxisMaster, r, x1, x2,
                   y1, y2) is
      variable v      : RegType;
      variable axilEp : AxiLiteEndpointType;
   begin

      v := r;

      ----------------------------------------------------------------------------------------------
      -- Coefficient Registers
      ----------------------------------------------------------------------------------------------
      axiSlaveWaitTxn(axilEp, axilWriteMaster, axilReadMaster, v.axilWriteSlave, v.axilReadSlave);

      axiSlaveRegister(axilEp, X"000", 0, v.clearFilters);
--       axiSlaveRegisterR(axilEp, X"04", 0, to_slv(r.b1_fixed));
--       axiSlaveRegisterR(axilEp, X"08", 0, to_slv(r.b2_fixed));
--       axiSlaveRegisterR(axilEp, X"0C", 0, to_slv(r.a1_fixed));
--       axiSlaveRegisterR(axilEp, X"10", 0, to_slv(r.a2_fixed));

      for i in CASCADE_SIZE_G-1 downto 0 loop
         axiSlaveRegister(axilEp, toSlv((i)*32+32, 12), 0, v.b0(i));
         axiSlaveRegister(axilEp, toSlv((i)*32+36, 12), 0, v.b1(i));
         axiSlaveRegister(axilEp, toSlv((i)*32+40, 12), 0, v.b2(i));
         axiSlaveRegister(axilEp, toSlv((i)*32+44, 12), 0, v.a1(i));
         axiSlaveRegister(axilEp, toSlv((i)*32+48, 12), 0, v.a2(i));
      end loop;

      axiSlaveDefault(axilEp, v.axilWriteSlave, v.axilReadSlave, AXI_RESP_DECERR_C);

      v.ramWe                := (others => '0');
      v.ramWrAddr            := to_ufixed(fifoAxisMaster.tId(CHANNEL_ADDR_WIDTH_G-1 downto 0), r.ramWrAddr);
      v.fifoAxisSlave.tReady := '0';
      v.mAxisMaster          := axiStreamMasterInit(AXIS_CONFIG_G);



      ----------------------------------------------------------------------------------------------
      -- State Machine
      ----------------------------------------------------------------------------------------------
      case r.state is
         when WAIT_DATA_S =>
            if (r.clearFilters = '1') then
               v.ramWrAddr := (others => '0');
               v.state     := CLEAR_FILTERS_S;
            else
               -- Clear result
               v.filterIndex := 0;
               v.result      := (others => '0');
               v.x0_fixed    := resize(to_sfixed(fifoAxisMaster.tData(DATA_WIDTH_G-1 downto 0), DATA_WIDTH_G-1, 0), dataSFixed);
               if (fifoAxisMaster.tValid = '1') then
                  if (uOr(fifoAxisMaster.tKeep) = '0') then
                     -- Skip straight to output
                     v.state := OUTPUT_S;
                  else
                     -- Allow tdest to address state ram               
                     v.state := WAIT_STATE_RAM_0_S;
                  end if;
               end if;
            end if;

         when WAIT_STATE_RAM_0_S =>
            v.state := WAIT_STATE_RAM_1_S;

         when WAIT_STATE_RAM_1_S =>
            v.state := COEFFS_S;

         when COEFFS_S =>
            -- Load coefficients from ram into registers
            -- Maybe unnecessary?
            -- Capture x0 from FIFO

            v.x1_fixed := x1(r.filterIndex);
            v.x2_fixed := x2(r.filterIndex);
            v.y1_fixed := y1(r.filterIndex);
            v.y2_fixed := y2(r.filterIndex);

            v.b0_fixed := to_sfixed(r.b0(r.filterIndex), r.b0_fixed);
            v.b1_fixed := to_sfixed(r.b1(r.filterIndex), r.b1_fixed);
            v.b2_fixed := to_sfixed(r.b2(r.filterIndex), r.b2_fixed);
            v.a1_fixed := to_sfixed(r.a1(r.filterIndex), r.a1_fixed);
            v.a2_fixed := to_sfixed(r.a2(r.filterIndex), r.a2_fixed);

            v.state := FILTER_B0_S;

         when FILTER_B0_S =>
            -- Assign next MAC
            v.coeff  := r.b0_fixed;
            v.data   := r.x0_fixed;
            v.result := (others => '0');

            v.state := FILTER_B1_S;

         when FILTER_B1_S =>
            -- Compute MAC 
            v.result := resize(r.result + (r.data * r.coeff), r.result);

            -- Assign next MAC
            v.coeff := r.b1_fixed;
            v.data  := r.x1_fixed;

            v.state := FILTER_B2_S;

         when FILTER_B2_S =>
            -- Compute MAC 
            v.result := resize(r.result + (r.data * r.coeff), r.result);

            -- Assign next MAC
            v.coeff := r.b2_fixed;
            v.data  := r.x2_fixed;

            v.state := FILTER_A1_S;

         when FILTER_A1_S =>
            -- Compute MAC 
            v.result := resize(r.result + (r.data * r.coeff), r.result);

            -- Assign next MAC
            v.coeff := resize(-(r.a1_fixed), r.coeff);
            v.data  := r.y1_fixed;

            v.state := FILTER_A2_S;

         when FILTER_A2_S =>
            -- Compute MAC 
            v.result := resize(r.result + (r.data * r.coeff), r.result);

            -- Assign next MAC
            v.coeff := resize(-(r.a2_fixed), r.coeff);
            v.data  := r.y2_fixed;

            v.state := RESULT_S;

         when RESULT_S =>
            -- Compute MAC 
            v.result := resize(r.result + (r.data * r.coeff), r.result);

            v.state := SHIFT_S;


         when SHIFT_S =>
            -- Save the results
            v.x1_fixed             := r.x0_fixed;
            v.x2_fixed             := r.x1_fixed;
            v.y1_fixed             := resize(r.result, r.y1_fixed);
            v.y2_fixed             := r.y1_fixed;
            v.ramWe(r.filterIndex) := '1';

            if (r.filterIndex = (CASCADE_SIZE_G-1)) then
               v.state := OUTPUT_S;
            else
               v.filterIndex := r.filterIndex + 1;
               v.x0_fixed    := v.y1_fixed;
               v.state       := COEFFS_S;
            end if;

         when OUTPUT_S =>
            v.filterIndex                                := 0;
            v.mAxisMaster.tValid                         := '1';
            v.mAxisMaster.tData(DATA_WIDTH_G-1 downto 0) := to_slv(resize(r.y1_fixed, DATA_WIDTH_G-1, 0));
            v.mAxisMaster.tId                            := fifoAxisMaster.tId;
            v.mAxisMaster.tUser                          := fifoAxisMaster.tUser;
            v.mAxisMaster.tKeep                          := fifoAxisMaster.tKeep;
            v.mAxisMaster.tLast                          := fifoAxisMaster.tLast;
            v.fifoAxisSlave.tReady                       := '1';
            v.state                                      := WAIT_DATA_S;

         when CLEAR_FILTERS_S =>
            v.ramWe     := (others => '1');
            v.ramWrAddr := resize(r.ramWrAddr + 1, r.ramWrAddr);
            v.y2_fixed  := (others => '0');
            v.y1_fixed  := (others => '0');
            v.x2_fixed  := (others => '0');
            v.x1_fixed  := (others => '0');

            if (r.ramWrAddr = (2**CHANNEL_ADDR_WIDTH_G)-1) then
               v.ramWrAddr    := (others => '0');
               v.clearFilters := '0';
               v.state        := WAIT_DATA_S;
            end if;

         when others => null;
      end case;

      if (axisRst = '1') then
         v := REG_INIT_C;
      end if;

      rin <= v;

      axilReadSlave  <= r.axilReadSlave;
      axilWriteSlave <= r.axilWriteSlave;


   end process comb;

   seq : process (axisClk) is
   begin
      if rising_edge(axisClk) then
         r <= rin after TPD_G;
      end if;
   end process seq;

   -- Output FIFO
   U_AxiStreamFifoV2_OUTPUT : entity surf.AxiStreamFifoV2
      generic map (
         TPD_G               => TPD_G,
         INT_PIPE_STAGES_G   => 0,
         PIPE_STAGES_G       => 1,
         SLAVE_READY_EN_G    => false,
--          VALID_THOLD_G       => 0,
--          VALID_BURST_MODE_G  => true,
--          FIFO_PAUSE_THRESH_G => 15,
         GEN_SYNC_FIFO_G     => true,
         FIFO_ADDR_WIDTH_G   => 8,
         SYNTH_MODE_G        => "xpm",
         MEMORY_TYPE_G       => "bram",
         INT_WIDTH_SELECT_G  => "WIDE",
         SLAVE_AXI_CONFIG_G  => AXIS_CONFIG_G,
         MASTER_AXI_CONFIG_G => AXIS_CONFIG_G)
      port map (
         sAxisClk    => axisClk,        -- [in]
         sAxisRst    => axisRst,        -- [in]
         sAxisMaster => r.mAxisMaster,  -- [in]
         sAxisSlave  => open,           -- [out]
         sAxisCtrl   => open,           -- [out]
         mAxisClk    => axisClk,        -- [in]
         mAxisRst    => axisRst,        -- [in]
         mAxisMaster => mAxisMaster,    -- [out]
         mAxisSlave  => mAxisSlave);    -- [in]


end architecture rtl;
