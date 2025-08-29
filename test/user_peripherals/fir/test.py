# SPDX-FileCopyrightText: © 2025
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles

from tqv import TinyQV

PERIPHERAL_NUM = 39  # change to your slot

# Register map
ADDR_CONTROL  = 0x00
ADDR_H0       = 0x01
ADDR_H1       = 0x02
ADDR_H2       = 0x03
ADDR_H3       = 0x04
ADDR_XIN      = 0x05
ADDR_YOUT     = 0x06


async def load_coeffs(tqv, coeffs):
    """Load 4 FIR coefficients."""
    await tqv.write_byte_reg(ADDR_H0, coeffs[0] & 0xFF)
    await tqv.write_byte_reg(ADDR_H1, coeffs[1] & 0xFF)
    await tqv.write_byte_reg(ADDR_H2, coeffs[2] & 0xFF)
    await tqv.write_byte_reg(ADDR_H3, coeffs[3] & 0xFF)


async def push_sample(tqv, x):
    """Push a new input sample and return FIR output."""
    await tqv.write_byte_reg(ADDR_XIN, x & 0xFF)
    y = await tqv.read_byte_reg(ADDR_YOUT)
    return y


@cocotb.test()
async def test_fir_average(dut):
    """Test FIR as a simple moving average filter."""
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    tqv = TinyQV(dut, PERIPHERAL_NUM)

    await tqv.reset()

    # Enable FIR
    await tqv.write_byte_reg(ADDR_CONTROL, 0x01)

    # Coeffs = [64,64,64,64]  -> (1/4 average) since >>8 scaling
    await load_coeffs(tqv, [64, 64, 64, 64])

    # Input sequence: 0,0,0,255
    seq = [0, 0, 0, 255]
    outputs = []
    for x in seq:
        y = await push_sample(tqv, x)
        outputs.append(y)
        await ClockCycles(dut.clk, 1)

    dut._log.info(f"Outputs = {outputs}")

    # Expected: first three are 0, last one is about 63 (≈255/4)
    assert outputs[0] == 0
    assert outputs[1] == 0
    assert outputs[2] == 0
    assert abs(outputs[3] - 63) <= 1


@cocotb.test()
async def test_fir_impulse(dut):
    """Impulse response should equal coefficients."""
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    tqv = TinyQV(dut, PERIPHERAL_NUM)

    await tqv.reset()
    await tqv.write_byte_reg(ADDR_CONTROL, 0x01)

    # Example coeffs = [128, 64, 32, 16]
    coeffs = [128, 64, 32, 16]
    await load_coeffs(tqv, coeffs)

    # Feed impulse = 255 then zeros
    seq = [255, 0, 0, 0, 0]
    outputs = []
    for x in seq:
        y = await push_sample(tqv, x)
        outputs.append(y)
        await ClockCycles(dut.clk, 1)

    dut._log.info(f"Impulse response = {outputs}")

    # Expected ≈ coeffs * 255 >> 8
    exp = [(c * 255) >> 8 for c in coeffs] + [0]
    for i in range(4):
        assert abs(outputs[i] - exp[i]) <= 1, f"Mismatch at tap {i}"
