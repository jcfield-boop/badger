# SPDX-FileCopyrightText: Tony DiCola 2017 for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2021 Ladyada
# SPDX-License-Identifier: MIT
"""MicroPython driver for Adafruit's 13x9 RGB Matrix QT (product 5201).

Board mapping adapted from Adafruit_CircuitPython_IS31FL3741, including its
default BGR channel permutation. See LICENSE for the upstream permission.

Copied as-is from this repo's comfort_matrix app (same board, same driver)
rather than reimplemented.
"""


class Matrix:
    WIDTH = 13
    HEIGHT = 9
    ROWS = (8, 5, 4, 3, 2, 1, 0, 7, 6)

    def __init__(self, i2c, address=0x30, current=8):
        if not 0 <= current <= 255:
            raise ValueError("Matrix current must be 0..255")
        self.i2c = i2c
        self.address = address
        self.pwm = bytearray(351)
        self.check()
        self.page(4)
        self.write(0x00, 0)
        self.write(0x3F, 0xAE)
        self.page(4)
        self.write(0x00, 0)
        self.write(0x01, current)
        for page, size in ((2, 180), (3, 171)):
            self.page(page)
            self.i2c.writeto_mem(address, 0, bytes([255]) * size)
        self.show()
        self.page(4)
        self.write(0x00, 1)

    def write(self, register, value):
        self.i2c.writeto_mem(self.address, register, bytes((value,)))

    def page(self, number):
        self.write(0xFE, 0xC5)
        self.write(0xFD, number)

    def check(self):
        if self.i2c.readfrom_mem(self.address, 0xFC, 1) != bytes((self.address * 2,)):
            raise OSError("IS31FL3741 identity mismatch")

    @classmethod
    def channels(cls, x, y):
        row = cls.ROWS[y]
        base = 3 * (x + row * 10 if x < 10 else x + 80 + row * 3)
        if x & 1 or x == 12:
            return base + 1, base, base + 2
        return base + 2, base + 1, base

    def draw(self, pixels, rgb):
        for y in range(self.HEIGHT):
            for x in range(self.WIDTH):
                channels = self.channels(x, y)
                lit = pixels[y * self.WIDTH + x]
                for channel, value in zip(channels, rgb):
                    self.pwm[channel] = value if lit else 0
        self.show()

    def show(self):
        self.page(0)
        self.i2c.writeto_mem(self.address, 0, self.pwm[:180])
        self.page(1)
        self.i2c.writeto_mem(self.address, 0, self.pwm[180:])

    def close(self):
        self.page(4)
        self.write(0x00, 0)
        self.pwm[:] = bytes(351)
        self.show()
