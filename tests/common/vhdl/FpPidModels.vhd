-------------------------------------------------------------------------------
-- This file is part of Warm TDM. It is subject to the license terms in the
-- LICENSE.txt file found in the top-level directory of this distribution.
-------------------------------------------------------------------------------
-- TEST ONLY: finite-value behavioral stand-ins for the configured Xilinx cores.
-- Exact integer arithmetic, nearest-even, and the XCI pipeline latencies let
-- GHDL exercise controller state, sequencing and transport. These models are
-- never imported into firmware builds and do not qualify vendor exceptions,
-- denormals, generated-IP bit accuracy, timing or synthesis.
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
package FpPidModelPkg is
   subtype Word is std_logic_vector(31 downto 0);
   function modelMac(a, b, c : Word) return Word;
   function modelInt2Fp(a : Word) return Word;
   function modelFp2Int(a : Word) return Word;
end package;
package body FpPidModelPkg is
   -- Every binary32 value is an integer times 2**-149. Use enough bits for
   -- the exact product and aligned addend, then round only the final result.
   subtype Mantissa is signed(277 downto 0);
   subtype Wide is signed(556 downto 0);
   function unpack(a : Word) return Mantissa is
      variable m : Mantissa := (others => '0');
      variable e : natural := to_integer(unsigned(a(30 downto 23)));
   begin
      assert e /= 255 report "Nonfinite test-model input" severity failure;
      m(22 downto 0) := signed(a(22 downto 0));
      if e /= 0 then
         m(23) := '1';
         m := shift_left(m, e-1);
      end if;
      if a(31) = '1' then m := -m; end if;
      return m;
   end function;

   function pack(a : Wide; scale : natural) return Word is
      variable magnitude : unsigned(a'range);
      variable result : Word := (others => '0');
      variable k, exponent, shift : integer;
      variable significand : unsigned(24 downto 0) := (others => '0');
      variable sticky : std_logic := '0';
   begin
      if a = 0 then return result; end if;
      result(31) := a(a'high);
      magnitude := unsigned(abs(a));
      k := a'high;
      while magnitude(k) = '0' loop k := k-1; end loop;
      exponent := k - scale + 127;
      assert exponent > 0 and exponent < 255
         report "Test-model result outside supported normal finite range" severity failure;
      shift := k - 23;
      if shift > 0 then
         significand(23 downto 0) := magnitude(k downto shift);
         for i in 0 to shift-2 loop sticky := sticky or magnitude(i); end loop;
         if magnitude(shift-1) = '1' and (sticky = '1' or significand(0) = '1') then
            significand := significand + 1;
         end if;
         if significand(24) = '1' then
            significand := shift_right(significand, 1);
            exponent := exponent + 1;
         end if;
      else
         significand := resize(shift_left(magnitude, -shift), 25);
      end if;
      assert exponent < 255 report "Test-model overflow" severity failure;
      result(30 downto 23) := std_logic_vector(to_unsigned(exponent, 8));
      result(22 downto 0) := std_logic_vector(significand(22 downto 0));
      return result;
   end function;

   function modelMac(a, b, c : Word) return Word is
      variable total : Wide;
   begin
      total := resize(unpack(a)*unpack(b), Wide'length) +
               shift_left(resize(unpack(c), Wide'length), 149);
      return pack(total, 298);
   end function;
   function modelInt2Fp(a : Word) return Word is
   begin
      return pack(resize(signed(a), Wide'length), 0);
   end function;
   function modelFp2Int(a : Word) return Word is
      variable m : Mantissa := unpack(a);
      variable magnitude, rounded : unsigned(m'range);
      variable sticky : std_logic := '0';
   begin
      magnitude := unsigned(abs(m));
      rounded := shift_right(magnitude, 149);
      for i in 0 to 147 loop sticky := sticky or magnitude(i); end loop;
      if magnitude(148) = '1' and (sticky = '1' or rounded(0) = '1') then
         rounded := rounded + 1;
      end if;
      assert rounded <= to_unsigned(2147483647, rounded'length) or
         (a(31) = '1' and rounded = shift_left(to_unsigned(1, rounded'length),31))
         report "Test-model Int32 overflow requires vendor qualification" severity failure;
      m := signed(rounded);
      if a(31) = '1' then m := -m; end if;
      return std_logic_vector(resize(m,32));
   end function;
end package body;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.FpPidModelPkg.all;
entity Int2Fp is
   port (
      aclk : in std_logic;
      s_axis_a_tvalid : in std_logic;
      s_axis_a_tdata : in std_logic_vector(31 downto 0);
      m_axis_result_tvalid : out std_logic;
      m_axis_result_tdata : out std_logic_vector(31 downto 0));
end entity;
architecture rtl of Int2Fp is
   type DataArray is array (0 to 1) of std_logic_vector(31 downto 0);
   signal data : DataArray := (others => (others => '0'));
   signal valid : std_logic_vector(0 to 1) := (others => '0');
begin
   m_axis_result_tdata <= data(1);
   m_axis_result_tvalid <= valid(1);
   process(aclk)
   begin
      if rising_edge(aclk) then
         valid(0) <= s_axis_a_tvalid;
         if (s_axis_a_tvalid) = '1' then
            data(0) <= modelInt2Fp(s_axis_a_tdata);
         end if;
         for i in 1 to 1 loop
            valid(i) <= valid(i-1);
            data(i) <= data(i-1);
         end loop;
      end if;
   end process;
end architecture;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.FpPidModelPkg.all;
entity Fp2Int is
   port (
      aclk : in std_logic;
      s_axis_a_tvalid : in std_logic;
      s_axis_a_tdata : in std_logic_vector(31 downto 0);
      m_axis_result_tvalid : out std_logic;
      m_axis_result_tdata : out std_logic_vector(31 downto 0));
end entity;
architecture rtl of Fp2Int is
   type DataArray is array (0 to 1) of std_logic_vector(31 downto 0);
   signal data : DataArray := (others => (others => '0'));
   signal valid : std_logic_vector(0 to 1) := (others => '0');
begin
   m_axis_result_tdata <= data(1);
   m_axis_result_tvalid <= valid(1);
   process(aclk)
   begin
      if rising_edge(aclk) then
         valid(0) <= s_axis_a_tvalid;
         if (s_axis_a_tvalid) = '1' then
            assert s_axis_a_tdata(30 downto 23) /= X"FF" report "Fp2Int: unexpected nonfinite controller operand" severity failure;
            data(0) <= modelFp2Int(s_axis_a_tdata);
         end if;
         for i in 1 to 1 loop
            valid(i) <= valid(i-1);
            data(i) <= data(i-1);
         end loop;
      end if;
   end process;
end architecture;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.FpPidModelPkg.all;
entity FpMac is
   port (
      aclk : in std_logic;
      s_axis_a_tvalid : in std_logic;
      s_axis_a_tdata : in std_logic_vector(31 downto 0);
      s_axis_b_tvalid : in std_logic;
      s_axis_b_tdata : in std_logic_vector(31 downto 0);
      s_axis_c_tvalid : in std_logic;
      s_axis_c_tdata : in std_logic_vector(31 downto 0);
      m_axis_result_tvalid : out std_logic;
      m_axis_result_tdata : out std_logic_vector(31 downto 0));
end entity;
architecture rtl of FpMac is
   type DataArray is array (0 to 3) of std_logic_vector(31 downto 0);
   signal data : DataArray := (others => (others => '0'));
   signal valid : std_logic_vector(0 to 3) := (others => '0');
begin
   m_axis_result_tdata <= data(3);
   m_axis_result_tvalid <= valid(3);
   process(aclk)
   begin
      if rising_edge(aclk) then
         valid(0) <= s_axis_a_tvalid and s_axis_b_tvalid and s_axis_c_tvalid;
         if (s_axis_a_tvalid and s_axis_b_tvalid and s_axis_c_tvalid) = '1' then
            assert s_axis_a_tdata(30 downto 23) /= X"FF" report "FpMac: unexpected nonfinite controller operand" severity failure;
            assert s_axis_b_tdata(30 downto 23) /= X"FF" report "FpMac: unexpected nonfinite controller operand" severity failure;
            assert s_axis_c_tdata(30 downto 23) /= X"FF" report "FpMac: unexpected nonfinite controller operand" severity failure;
            data(0) <= modelMac(s_axis_a_tdata, s_axis_b_tdata, s_axis_c_tdata);
         end if;
         for i in 1 to 3 loop
            valid(i) <= valid(i-1);
            data(i) <= data(i-1);
         end loop;
      end if;
   end process;
end architecture;
