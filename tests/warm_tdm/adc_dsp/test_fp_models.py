# This file is part of Warm TDM. It is subject to the license terms in the
# LICENSE.txt file found in the top-level directory of this distribution.
"""Check test-only arithmetic against independent exact-rational expectations."""
from fractions import Fraction
from pathlib import Path
import random
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[3]


def f32(bits):
    return struct.unpack('<f', struct.pack('<I', bits))[0]


def bits(value):
    return struct.unpack('<I', struct.pack('<f', value))[0]


def nearest32(exact):
    # A binary64 approximation locates neighboring binary32 values. Select by
    # exact rational distance, including ties, so double rounding cannot decide.
    candidate = bits(float(exact))
    neighbors = {candidate, max(0, candidate-1), min(0xffffffff, candidate+1)}
    neighbors = [b for b in neighbors if b & 0x7f800000 != 0x7f800000]
    return min(neighbors, key=lambda b: (abs(Fraction.from_float(f32(b))-exact), b & 1))


def test_behavioral_arithmetic_with_exact_oracle(tmp_path):
    rng = random.Random(20260916)
    vectors = [(-1.0, -1024.0, -1234.0), (1.0, -32768.0, 41768.0),
               (.25, 1.0, 377.0), (2**-24, 1.0, 1.0),
               (2**-24, 1.0, 1.0+2**-23), (1.0, 1.0, -1.0)]
    vectors += [tuple(f32((rng.randrange(2) << 31) | (rng.randrange(90, 155) << 23) |
                          rng.randrange(1 << 23)) for _ in range(3)) for _ in range(256)]
    assertions = []
    for a, b, c in vectors:
        exact = Fraction.from_float(a)*Fraction.from_float(b)+Fraction.from_float(c)
        expected = nearest32(exact)
        assertions.append(f'assert modelMac(X"{bits(a):08X}", X"{bits(b):08X}", X"{bits(c):08X}") = X"{expected:08X}" severity failure;')
    for value in [-2147483648, 2147483647, 0, 1, -1, 16777217, -16777217] + [rng.randrange(-(1 << 31), 1 << 31) for _ in range(256)]:
        assertions.append(f'assert modelInt2Fp(X"{value & 0xffffffff:08X}") = X"{bits(value):08X}" severity failure;')
    values = [.5, -.5, .50048828125, -.50048828125, 1.5, -1.5, 2.5, -2.5, 9000, -210]
    values += [f32(bits(rng.randrange(-100000, 100000) + rng.choice([.25, .5, .75]))) for _ in range(256)]
    for value in values:
        assertions.append(f'assert modelFp2Int(X"{bits(value):08X}") = X"{round(value) & 0xffffffff:08X}" severity failure;')
    source = tmp_path/'FpModelsCheck.vhd'
    source.write_text('''library ieee;
use ieee.std_logic_1164.all;
use work.FpPidModelPkg.all;
entity FpModelsCheck is end;
architecture sim of FpModelsCheck is begin
process begin
''' + '\n'.join(assertions) + '\nstd.env.finish; wait; end process; end;\n')
    for command in (["ghdl", "-a", "--std=08", str(ROOT/'tests/common/vhdl/FpPidModels.vhd'), str(source)],
                    ["ghdl", "--elab-run", "--std=08", "FpModelsCheck"]):
        result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
