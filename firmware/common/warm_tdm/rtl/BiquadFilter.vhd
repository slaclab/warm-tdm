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
use ieee.std_logic_arith.all;
use ieee.std_logic_unsigned.all;

library surf;
use surf.StdRtlPkg.all;
use surf.AxiStreamPkg.all;
use surf.AxiLitePkg.all;

library warm_tdm;
use warm_tdm.WarmTdmPkg.all;

entity BiquadFilter is

   generic (
      TPD_G                : time                 := 1 ns;
      DATA_WIDTH_G         : positive             := 24;
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
--   constant DATA_FRACT_BITS_C : integer := DATA_MATH_WIDTH_C - DATA_WIDTH_G;
--   subtype DataSFixedType is sfixed(DATA_WIDTH_G-1 downto -DATA_FRACT_BITS_C);
   type DataArray is array (CASCADE_SIZE_G-1 downto 0) of slv(31 downto 0);
--   signal dataSFixed          : DataSFixedType;

--   type RamDataArray is array (CASCADE_SIZE_G-1 downto 0) of slv(31 downto 0);
   type RamStatearray is array (CASCADE_SIZE_G-1 downto 0) of slv(4*32-1 downto 0);

--   constant COEFF_BITS_C : integer := COEFF_HIGH_G - COEFF_LOW_G + 1;
--   subtype CoeffSFixedType is sfixed(COEFF_HIGH_G downto COEFF_LOW_G);
--   type CoeffSlvArray is array (CASCADE_SIZE_G-1 downto 0) of slv(31 downto 0);
--   signal coeffSFixed    : CoeffSFixedType;

--   constant RESULT_HIGH_C : integer := sfixed_high(COEFF_HIGH_G, COEFF_LOW_G, '*', DATA_WIDTH_G-1, -DATA_FRACT_BITS_C);
--   constant RESULT_LOW_C  : integer := sfixed_low(COEFF_HIGH_G, COEFF_LOW_G, '*', DATA_WIDTH_G-1, -DATA_FRACT_BITS_C);
--   subtype ResultSFixedType is sfixed(RESULT_HIGH_C downto RESULT_LOW_C);

   signal x1 : DataArray;
   signal x2 : DataArray;
   signal y1 : DataArray;
   signal y2 : DataArray;

   type StateType is (
      WAIT_DATA_S,
      WAIT_FP_CONV_S,
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
      int2FpInValid  : sl;
      int2FpInData   : slv(31 downto 0);
      fpMacInValid   : sl;
--      debugInput     : slv(DATA_WIDTH_G-1 downto 0);
      debugOutput    : slv(31 downto 0);
      b0             : DataArray;
      b1             : DataArray;
      b2             : DataArray;
      a1             : DataArray;
      a2             : DataArray;
      x0_active      : slv(31 downto 0);
      x1_active      : slv(31 downto 0);
      x2_active      : slv(31 downto 0);
      y1_active      : slv(31 downto 0);
      y2_active      : slv(31 downto 0);
      b0_active      : slv(31 downto 0);
      b1_active      : slv(31 downto 0);
      b2_active      : slv(31 downto 0);
      a1_active      : slv(31 downto 0);
      a2_active      : slv(31 downto 0);
      coeff          : slv(31 downto 0);
      data           : slv(31 downto 0);
      result         : slv(31 downto 0);
      clearFilters   : sl;
      ramWe          : slv(CASCADE_SIZE_G-1 downto 0);
      ramWrAddr      : slv(CHANNEL_ADDR_WIDTH_G-1 downto 0);
      fifoAxisSlave  : AxiStreamSlaveType;
      mAxisMaster    : AxiStreamMasterType;
      axilReadSlave  : AxiLiteReadSlaveType;
      axilWriteSlave : AxiLiteWriteSlaveType;
   end record RegType;

   constant REG_INIT_C : RegType := (
      state          => WAIT_DATA_S,
      filterIndex    => 0,
      int2FpInValid  => '0',
      int2FpInData   => (others => '0'),
      fpMacInValid   => '0',
--      debugInput     => (others => '0'),
      debugOutput    => (others => '0'),
      b0             => (others => X"3F800000"),  -- float32 representation of 1.0
      b1             => (others => (others => '0')),
      b2             => (others => (others => '0')),
      a1             => (others => (others => '0')),
      a2             => (others => (others => '0')),
      x0_active      => (others => '0'),
      x1_active      => (others => '0'),
      x2_active      => (others => '0'),
      y1_active      => (others => '0'),
      y2_active      => (others => '0'),
      b0_active      => (others => '0'),
      b1_active      => (others => '0'),
      b2_active      => (others => '0'),
      a1_active      => (others => '0'),
      a2_active      => (others => '0'),
      coeff          => (others => '0'),
      data           => (others => '0'),
      result         => (others => '0'),
      clearFilters   => '0',
      ramWe          => (others => '0'),
      ramWrAddr      => (others => '0'),
      fifoAxisSlave  => AXI_STREAM_SLAVE_INIT_C,
      mAxisMaster    => axiStreamMasterInit(DOWNSAMPLE_DATA_AXIS_CFG_C),
      axilReadSlave  => AXI_LITE_READ_SLAVE_EMPTY_DECERR_C,
      axilWriteSlave => AXI_LITE_WRITE_SLAVE_EMPTY_DECERR_C);

   signal r   : Regtype := REG_INIT_C;
   signal rin : RegType;

   signal fifoAxisMaster : AxiStreamMasterType;
   signal ramDin         : RamStateArray;
   signal ramDout        : RamStateArray;
   signal ramWrAddr      : slv(CHANNEL_ADDR_WIDTH_G-1 downto 0);

   signal int2FpOutValid : sl;
   signal int2FpOutData  : slv(31 downto 0);

   signal fpMacOutValid : sl;
   signal fpMacOutData  : slv(31 downto 0);

   component FpMac
      port (
         aclk                    : in  std_logic;
         s_axis_a_tvalid         : in  std_logic;
         s_axis_a_tdata          : in  std_logic_vector(31 downto 0);
         s_axis_b_tvalid         : in  std_logic;
         s_axis_b_tdata          : in  std_logic_vector(31 downto 0);
         s_axis_c_tvalid         : in  std_logic;
         s_axis_c_tdata          : in  std_logic_vector(31 downto 0);
         m_axis_result_tvalid    : out std_logic;
         m_axis_result_tdata     : out std_logic_vector(31 downto 0)
         );
   end component;

   component Int2Fp
      port (
         aclk                 : in  std_logic;
         s_axis_a_tvalid      : in  std_logic;
         s_axis_a_tdata       : in  std_logic_vector(31 downto 0);
         m_axis_result_tvalid : out std_logic;
         m_axis_result_tdata  : out std_logic_vector(31 downto 0)
         );
   end component;

begin


   -- Buffer incomming samples just in case
   -- But really there shouldn't be backpressure
   U_AxiStreamFifoV2_IN_FIFO : entity surf.AxiStreamFifoV2
      generic map (
         TPD_G               => TPD_G,
         INT_PIPE_STAGES_G   => 0,
         PIPE_STAGES_G       => 0,
         SLAVE_READY_EN_G    => true,
--          VALID_THOLD_G       => 0,
--          VALID_BURST_MODE_G  => true,
--          FIFO_PAUSE_THRESH_G => 15,
         GEN_SYNC_FIFO_G     => true,
         FIFO_ADDR_WIDTH_G   => 4,
         SYNTH_MODE_G        => "xpm",
         MEMORY_TYPE_G       => "distributed",
         INT_WIDTH_SELECT_G  => "WIDE",
         SLAVE_AXI_CONFIG_G  => PID_DATA_AXIS_CFG_C,
         MASTER_AXI_CONFIG_G => PID_DATA_AXIS_CFG_C)
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
            DATA_WIDTH_G  => 4*32)
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
      x1(i)     <= ramDout(i)(DATA_MATH_WIDTH_C-1 downto 0);
      x2(i)     <= ramDout(i)(2*DATA_MATH_WIDTH_C-1 downto DATA_MATH_WIDTH_C);
      y1(i)     <= ramDout(i)(3*DATA_MATH_WIDTH_C-1 downto 2*DATA_MATH_WIDTH_C);
      y2(i)     <= ramDout(i)(4*DATA_MATH_WIDTH_C-1 downto 3*DATA_MATH_WIDTH_C);
      ramDin(i) <= to_slv(r.y2_active) &
                   to_slv(r.y1_active) &
                   to_slv(r.x2_active) &
                   to_slv(r.x1_active);
   end generate;

   U_Int2Fp_1 : Int2Fp
      port map (
         aclk                 => axisClk,          -- [in]
         s_axis_a_tvalid      => r.int2FpInValid,  -- [in]
         s_axis_a_tdata       => r.int2FpInData,   -- [in]
         m_axis_result_tvalid => int2FpOutValid,   -- [out]
         m_axis_result_tdata  => int2FpOutData);   -- [out]

   U_FpMac_1 : FpMac
      port map (
         aclk                    => axisClk,         -- [in]
         s_axis_a_tvalid         => r.fpMacInValid,  -- [in]
         s_axis_a_tdata          => r.data,          -- [in]
         s_axis_b_tvalid         => r.fpMacInValid,  -- [in]
         s_axis_b_tdata          => r.coeff,         -- [in]
         s_axis_c_tvalid         => r.fpMacInValid,  -- [in]
         s_axis_c_tdata          => r.result,        -- [in]
         m_axis_result_tvalid    => fpMacOutValid,   -- [out]
         m_axis_result_tdata     => fpMacOutData);   -- [out]


   comb : process (axilReadMaster, axilWriteMaster, axisRst, fifoAxisMaster, fpMacOutData,
                   fpMacOutValid, int2FpOutData, int2FpOutValid, r, x1, x2, y1, y2) is
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
      v.ramWrAddr            := fifoAxisMaster.tId(CHANNEL_ADDR_WIDTH_G-1 downto 0);
      v.fifoAxisSlave.tReady := '0';
      v.mAxisMaster          := axiStreamMasterInit(DOWNSAMPLE_DATA_AXIS_CFG_C);


      v.int2FpInValid := '0';
      v.fpMacInValid  := '0';
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

               if (fifoAxisMaster.tValid = '1') then
                  v.int2FpInData  := resize(fifoAxisMaster.tData(DATA_WIDTH_G-1 downto 0), 24);
                  v.int2FpInValid := '1';

                  if (uOr(fifoAxisMaster.tKeep) = '0') then
                     -- Skip straight to output
                     v.int2FpInValid := '0';
                     v.state         := OUTPUT_S;
                  else
                     -- Allow tdest to address state ram               
                     v.state := WAIT_FP_CONV_S;
                  end if;
               end if;
            end if;

         when WAIT_FP_CONV_S =>
            -- Wait for int 2 fp conversion to finish
            -- Coefficients should also be ready from ram by this time
            if (int2FpOutValid = '1') then
               v.x0_active := int2FpOutData;
               v.state     := COEFFS_S;
            end if;

         when COEFFS_S =>
            -- Load coefficients from ram into registers
            -- Maybe unnecessary?
            -- Capture x0 from FIFO

            v.x1_active := x1(r.filterIndex);
            v.x2_active := x2(r.filterIndex);
            v.y1_active := y1(r.filterIndex);
            v.y2_active := y2(r.filterIndex);

            v.b0_active := r.b0(r.filterIndex);
            v.b1_active := r.b1(r.filterIndex);
            v.b2_active := r.b2(r.filterIndex);
            v.a1_active := r.a1(r.filterIndex);
            v.a2_active := r.a2(r.filterIndex);

            v.state := FILTER_B0_S;

         when FILTER_B0_S =>
            v.fpMacInValid := '1';
            v.coeff        := r.b0_active;
            v.data         := r.x0_active;
            v.result       := (others => '0');
            v.state        := FILTER_B1_S;

         when FILTER_B1_S =>
            if (fpMacOutValid = '1') then
               v.fpMacInValid := '1';
               v.result       := fpMacOutData;
               v.coeff        := r.b1_active;
               v.data         := r.x1_active;
               v.state        := FILTER_B2_S;
            end if;

         when FILTER_B2_S =>
            if (fpMacOutValid = '1') then
               v.fpMacInValid := '1';
               v.result       := fpMacOutData;
               v.coeff        := r.b2_active;
               v.data         := r.x2_active;
               v.state        := FILTER_A1_S;
            end if;

         when FILTER_A1_S =>
            if (fpMacOutValid = '1') then
               v.fpMacInValid := '1';
               v.result       := fpMacOutData;
               v.coeff        := r.a1_active;
               -- Invert coeff to subtract
               v.coeff(31)    := not v.coeff(31);
               v.data         := r.y1_active;
               v.state        := FILTER_A2_S;
            end if;


         when FILTER_A2_S =>
            if (fpMacOutValid = '1') then
               v.fpMacInValid := '1';
               v.result       := fpMacOutData;
               v.coeff        := r.a2_active;
               -- Invert coeff to subtract
               v.coeff(31)    := not v.coeff(31);
               v.data         := r.y2_active;
               v.state        := RESULT_S;
            end if;

         when RESULT_S =>
            if (fpMacOutValid = '1') then
               v.result := fpMacOutData;
               v.state  := SHIFT_S;
            end if;

         when SHIFT_S =>
            -- Save the results
            v.x1_active            := r.x0_active;
            v.x2_active            := r.x1_active;
            v.y1_active            := r.result;
            v.y2_active            := r.y1_active;
            v.ramWe(r.filterIndex) := '1';

            if (r.filterIndex = (CASCADE_SIZE_G-1)) then
               v.state := OUTPUT_S;
            else
               v.filterIndex := r.filterIndex + 1;
               v.x0_active   := v.y1_active;
               v.state       := COEFFS_S;
            end if;

         when OUTPUT_S =>
            v.filterIndex                     := 0;
            v.mAxisMaster.tValid              := '1';
            v.mAxisMaster.tData(31 downto 0)  := r.y1_active;
            v.mAxisMaster.tData(63 downto 32) := resize(r.int2FpInData, 32);
            v.debugOutput                     := r.y1_active;
            v.mAxisMaster.tId                 := fifoAxisMaster.tId;
            v.mAxisMaster.tUser               := fifoAxisMaster.tUser;
            v.mAxisMaster.tKeep               := fifoAxisMaster.tKeep;
            v.mAxisMaster.tLast               := fifoAxisMaster.tLast;
            v.fifoAxisSlave.tReady            := '1';
            v.state                           := WAIT_DATA_S;

         when CLEAR_FILTERS_S =>
            v.ramWe     := (others => '1');
            v.ramWrAddr := r.ramWrAddr + 1;
            v.y2_active := (others => '0');
            v.y1_active := (others => '0');
            v.x2_active := (others => '0');
            v.x1_active := (others => '0');

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
         PIPE_STAGES_G       => 0,
         SLAVE_READY_EN_G    => false,
--          VALID_THOLD_G       => 0,
--          VALID_BURST_MODE_G  => true,
--          FIFO_PAUSE_THRESH_G => 15,
         GEN_SYNC_FIFO_G     => true,
         FIFO_ADDR_WIDTH_G   => 8,
         SYNTH_MODE_G        => "xpm",
         MEMORY_TYPE_G       => "bram",
         INT_WIDTH_SELECT_G  => "WIDE",
         SLAVE_AXI_CONFIG_G  => DOWNSAMPLE_DATA_AXIS_CFG_C,
         MASTER_AXI_CONFIG_G => DOWNSAMPLE_DATA_AXIS_CFG_C)
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
