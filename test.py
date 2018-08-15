#!/usr/bin/python3
# -*- coding: utf-8 -*-

# MIT License
#
# Copyright (c) 2018 BayLibre
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import unittest

from svd import SVD, SVDText

class TestSVD(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        # Load and parse the SVD file
        self.svd = SVD('ARM_Example.svd')
        self.svd.parse()

    def test_SVDElement(self):
        peripheral = self.svd.peripherals['TIMER0']
        self.assertTrue(hasattr(peripheral, 'name'))
        self.assertFalse(hasattr(peripheral, 'test'))

        # SVDElement must raise an exception if we try to get an invalid
        # attribute, e.g. a tag that is not defined in the spec.
        with self.assertRaises(AttributeError):
            test = peripheral.test

    def test_SVD(self):
        # This checks if there are the expected numbers of peripherals
        self.assertEqual(len(self.svd.peripherals), 5)
        # Check that TIMER0, one of the peripherals is in the list
        self.assertIn('TIMER0', self.svd.peripherals)

    def test_SVDText(self):
        file = open('ARM_Example.svd')
        svd = SVDText(file.read().encode())
        svd.parse()
        # This checks if there are the expected numbers of peripherals
        self.assertEqual(len(svd.peripherals), 5)
        # Check that TIMER0, one of the peripherals is in the list
        self.assertIn('TIMER0', svd.peripherals)

    def test_SVDPeripheral(self):
        peripheral = self.svd.peripherals['TIMER0']

        # Check if we can get the value of peripheral's tag
        self.assertEqual(peripheral.version, '1.0')
        self.assertEqual(peripheral.description,
            '32 Timer / Counter, counting up or down from different sources')
        self.assertEqual(peripheral.baseAddress, 0x40010000)
        self.assertEqual(peripheral.size, 32)

        # This checks if there are the expected numbers of registers
        registers = peripheral.registers
        self.assertEqual(len(registers), 11)
        # Check that CR, one of the peripherals is in the list
        self.assertIn('CR', registers)
        # Check that RELOAD[0], a dimable register is there in the list
        self.assertIn('RELOAD[0]', registers)

        # TIMER1 derives from TIMER0. Check that peripherals has same
        # properties than TIMER0.
        peripheral = self.svd.peripherals['TIMER1']
        registers = peripheral.registers
        self.assertEqual(peripheral.baseAddress, 0x40010100)
        self.assertIn('CR', registers)
        self.assertIn('RELOAD[0]', registers)

    def test_SVDPeripheral_derived(self):
        # TIMER1 derives from TIMER0. Check that peripherals has same
        # properties than TIMER0.
        peripheral = self.svd.peripherals['TIMER1']
        registers = peripheral.registers
        self.assertEqual(peripheral.baseAddress, 0x40010100)
        self.assertIn('CR', registers)
        self.assertIn('RELOAD[0]', registers)

    def test_SVDPeripheral_prepend(self):
        peripheral = self.svd.peripherals['TEST1']
        registers = peripheral.registers

        # TEST1_ must be appended to all registers' name
        self.assertIn('TEST1_BASE1', registers)

    def test_SVDPeripheral_append(self):
        peripheral = self.svd.peripherals['TEST2']
        registers = peripheral.registers

        # _TEST2 must be appended to all registers' name
        self.assertIn('BASE1_TEST2', registers)

    def test_SVDPeripheral_inherited(self):
        peripheral = self.svd.peripherals['TEST1']
        registers = peripheral.registers

        # Regular and derived registers' value should inherit the value from
        # peripheral except if the value has been overwritten
        register = registers['TEST1_INHERITED']
        self.assertEqual(register.resetValue, peripheral.resetValue)
        self.assertEqual(register.resetMask, peripheral.resetMask)
        self.assertEqual(register.size, peripheral.size)
        register = registers['TEST1_BASE1']
        self.assertEqual(register.resetValue, 0x00008001)
        register = registers['TEST1_DERIVED1']
        self.assertEqual(register.resetValue, 0x00008001)

        # If displayName is not defined, it must fallback to name
        self.assertEqual(register.displayName, register.name)
        register = registers['TEST1_DERIVED2']
        self.assertEqual(register.displayName, 'DERIVED2 display name')

    def test_SVDRegister(self):
        peripheral = self.svd.peripherals['TIMER0']
        registers = peripheral.registers

        # Check the value of some register's properties
        register = registers['CR']
        self.assertIn(register.name, 'CR')
        self.assertEqual(register.description, 'Control Register')
        self.assertEqual(register.addressOffset, 0x00)
        self.assertEqual(register.size, 32)
        self.assertEqual(register.resetValue, 0x00000000)
        self.assertEqual(register.resetMask, 0x1337F7F)
        self.assertEqual(register.access, 'read-write')

        # Test address(), which compute and get the register's address
        register = registers['SR']
        self.assertIn(register.name, 'SR')
        self.assertEqual(register.address(), 0x40010004)

    def test_SVDRegister_dimable(self):
        peripheral = self.svd.peripherals['TIMER0']
        registers = peripheral.registers

        # Check that the address of a dimable register is correct
        register = registers['RELOAD[0]']
        self.assertIn(register.name, 'RELOAD[0]')
        self.assertEqual(register.addressOffset, 0x50)

        # Check that the address of the next dimable register is correct
        register = registers['RELOAD[1]']
        self.assertIn(register.name, 'RELOAD[1]')
        self.assertEqual(register.addressOffset, 0x54)

        peripheral = self.svd.peripherals['TEST1']
        registers = peripheral.registers

        # Test another way to define dimable registers index
        self.assertIn('TEST1_DIM3', registers)

    def test_SVDField(self):
        peripheral = self.svd.peripherals['TIMER0']
        registers = peripheral.registers
        register = registers['CR']
        fields = register.fields

        # Check the value of some fields' properties
        field = fields['EN']
        self.assertIn(field.name, 'EN')
        self.assertEqual(field.description, 'Enable')
        self.assertEqual(field.bitOffset, 0)
        self.assertEqual(field.bitWidth, 1)

        field = fields['MODE']
        self.assertEqual(field.bitOffset, 4)
        self.assertEqual(field.bitWidth, 3)

    def test_SVDField_msb_lsb(self):
        peripheral = self.svd.peripherals['TEST1']
        registers = peripheral.registers
        register = registers['TEST1_DIM3']
        fields = register.fields

        # msb and lsb must have been converted to bitoffset and bitWidth
        field = fields['TST']
        self.assertEqual(field.bitOffset, 1)
        self.assertEqual(field.bitWidth, 2)

    def test_SVDField_bitOffset(self):
        peripheral = self.svd.peripherals['TEST1']
        registers = peripheral.registers
        register = registers['TEST1_DIM3']
        fields = register.fields

        # Test value of bitoffset and test if bitWidth is set to one,
        # when it have not been defined
        field = fields['ATST']
        self.assertEqual(field.bitOffset, 3)
        self.assertEqual(field.bitWidth, 1)

    def test_SVDEnumeratedVaue(self):
        peripheral = self.svd.peripherals['TIMER0']
        registers = peripheral.registers
        register = registers['CR']
        fields = register.fields
        field = fields['EN']
        values = field.enumeratedValues

        # Test if we can get enumerated values
        self.assertEqual(values[0].name, 'Disable')
        self.assertEqual(values[1].name, 'Enable')

    def test_SVDBrokenField(self):
        peripheral = self.svd.peripherals['TEST1']
        registers = peripheral.registers
        register = registers['TEST1_BROKEN_FIELDS']
        fields = register.fields

        self.assertIn('A0', fields)
        self.assertIn('A1', fields)
        self.assertIn('A2', fields)
        self.assertIn('A', fields)

        self.assertIn('B0', fields)
        self.assertIn('B1', fields)
        self.assertIn('B2', fields)
        self.assertNotIn('B', fields)

        self.assertIn('C0', fields)
        self.assertIn('C1', fields)
        self.assertNotIn('C', fields)

        self.assertIn('RTCSEL', fields)

if __name__ == '__main__':
    unittest.main()
