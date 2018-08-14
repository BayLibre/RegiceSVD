#!/usr/bin/env python
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

"""
    CMSIS SVD file parser.

    Usage:

    >>> from svd import SVD
    >>> svd = SVD(filename)
    >>> svd.parse()
    This will create a tree similar to the SVD one.

    To get a list of peripherals:
    >>> svd.peripherals.keys()
    odict_keys(['TIMER0', 'TIMER1', 'TIMER2', 'TEST1'])

    To get the list of registers, for a peripheral:
    >>> svd.peripherals['TIMER1'].registers:
    OrderedDict([('CR', <svd.svd.SVDRegister object at 0x7f01790bb048>), ...])

    To get the list of fields:
    >>> svd.peripherals['TIMER1'].registers['CR'].fields
    OrderedDict([('EN', <svd.svd.SVDField object at 0x7f01790bb2e8>), ...])

    Most of tags' content are available as class property.
    Basically, to get the peripheral offset:
    >>> svd.peripherals['TIMER1'].baseAddress
    1073807616

    Or, to get the description:
    >>> svd.peripherals['TIMER1'].description
    '32 Timer / Counter, counting up or down from different sources'
"""

import os
import re
from collections import OrderedDict

import lxml.objectify


def get(name, element):
    """
        Helper method to get the content of SVD element's tag

        :param name: The name of the tag
        :param element: The SVD element from which we want to get tag's content
        :type name: string
        :type element: lxml.etree.Element
        :return: The content of tag in case of success,
                 otherwise raise an exception
    """
    return getattr(element, name)

def get_dim_index_type(attr, element):
    """
        Get the content from tag of type dimIndexType

        :param element: The SVD element from which we want to get tag's content
        :param attr: The name of the tag to get content from
        :type element: lxml.etree.Element
        :type attr: string
        :return: A list of index, or None in case of failure
    """
    value_str = str(get(attr, element))
    if ',' in value_str:
        return value_str.split(',')
    elif '-' in value_str:
        value = value_str.split('-')
        return range(int(value[0]), int(value[1]) + 1)
    return None

class SVDElement(object):
    """A base class to handle all SVD elements"""
    def __init__(self, element, parent):
        self.parent = parent
        self.element = element
        self.derived_element = None
        self.index = None
        self.attrs = {}
        self.dim_attrs = {
            'scaledNonNegativeInteger': ['dim', 'dimIncrement'],
            'dimIndexType': ['dimIndex'],
            'dimArrayIndexType': ['dimArrayIndex'],
            'identifierType': ['dimName'],
        }
        self.register_attrs = {
            'scaledNonNegativeInteger': ['size', 'resetValue', 'resetMask'],
            'accessType': ['access'],
            'protectionStringType': ['protection'],
        }

    def merge_attrs(self, attrs):
        """
            Adds or merge an dictionary of tag type and tag names to thr class.

            :param attrs: Dictionary to merge with class attrs dictionary
            :type attrs: dict
        """
        for attr in attrs:
            if not attr in self.attrs:
                self.attrs[attr] = []
            self.attrs[attr] += attrs[attr]
            self.attrs[attr] = list(set(self.attrs[attr]))

    def get_root(self):
        """
            Find and return the root element

            :return: The root element
            :rtype: lxml.etree.Element
        """
        parent = self.parent
        if parent is None:
            return self.element
        return parent.get_root()

    def find_derived_from(self, element):
        """
            Find and return the element to use for derived element

            This try to find the base element to use for a derived element.
            This gets the root elements, and look up for the first element
            with a matching name.
            When the base element has been find, this sets self.derived_element.

            Note:
            Currently, this doesn't respect the spec.

            :param element: The element that use derivedFrom
            :type element: lxml.etree.Element
        """
        root = self.get_root()
        name = element.attrib['derivedFrom']
        for peripheral in root.peripherals.getchildren():
            if hasattr(peripheral, 'name') and peripheral.name == name:
                self.derived_element = peripheral
                return
            if not hasattr(peripheral, 'registers'):
                continue
            for register in peripheral.registers.getchildren():
                if hasattr(register, 'name') and register.name == name:
                    self.derived_element = register
                    return
                if not hasattr(register, 'fields'):
                    continue
                for field in register.fields.getchildren():
                    if hasattr(field, 'name') and field.name == name:
                        self.derived_element = field
                        return
                    if hasattr(field, 'enumeratedValues'):
                        if hasattr(field.enumeratedValues, 'name') and \
                            field.enumeratedValues.name == name:
                            self.derived_element = field
                            return

    def get_scaled_non_negative_integer(self, attr, element):
        """
            Get the content from tag of type scaledNonNegativeInteger

            :param element: The SVD element from which we want to get tag's content
            :param attr: The name of the tag to get content from
            :type element: lxml.etree.Element
            :type attr: string
            :return: The content of the tag, converted to integer
        """
        value_str = str(get(attr, element))
        if '0x' in  value_str:
            value = int(value_str, 16)
        else:
            value = int(value_str)
        if attr == 'addressOffset' and self.index:
            value += int(self.index) * self.dimIncrement
        return value

    def get_register_name_type(self, attr, element):
        """
            Get the content from tag of types registerNameType and dimableIdentifierType

            :param element: The SVD element from which we want to get tag's content
            :param attr: The name of the tag to get content from
            :type element: lxml.etree.Element
            :type attr: string
            :return: The content of the tag, eventually updated based on other elements' properties
        """
        value_str = ""
        if hasattr(self.parent.element, 'prependToName'):
            value_str += self.parent.prependToName
        value_str += str(get(attr, element))
        if hasattr(self.parent.element, 'appendToName'):
            value_str += self.parent.appendToName
        if self.index != None:
            if self.dimIndex:
                index = self.dimIndex[self.index]
            else:
                index = self.index
            value_str = value_str.replace('%s', str(index))
        return value_str

    def __svd_getattr__(self, attr, element):
        """
            Get the content from any SVD tag

            The content of tag is converted from text to the type of the tag.

            :param element: The SVD element from which we want to get tag's content
            :param attr: The name of the tag to get content from
            :type element: lxml.etree.Element
            :type attr: string
            :return: The content of the tag, eventually updated based on other elements' properties,
                     or None if the tag is not a child of element
        """
        if not hasattr(element, attr):
            return None

        str_type = ['xs:string', 'xs:Name', 'stringType', 'identifierType']
        for attr_type in self.attrs:
            if attr in self.attrs[attr_type]:
                if attr_type in str_type or \
                    attr_type == 'accessType' or \
                    attr_type == 'protectionStringType':
                    return str(get(attr, element))
                if attr_type == 'scaledNonNegativeInteger':
                    return self.get_scaled_non_negative_integer(attr, element)
                if attr_type == 'dimIndexType':
                    indexes = get_dim_index_type(attr, element)
                    if indexes is None:
                        indexes = range(0, self.dim)
                if attr_type == 'dimableIdentifierType' or \
                    attr_type == 'registerNameType':
                    return self.get_register_name_type(attr, element)
                if attr_type == 'bitRangeType':
                    value = str(get(attr, element))[1:-1]
                    bits = value.split(':')
                    return [int(bits[0]), int(bits[1])]

    def __inherited_getattr__(self, attr):
        """
            Get inherited tag content

            Some tags are optional. If there are not used, we may use the
            parent's one.
            This go through parents element, and get the content of tag if it
            exists.
        """
        for attr_type in self.register_attrs:
            if attr in self.register_attrs[attr_type]:
                parent = self.parent
                if parent != None:
                    if hasattr(parent.element, attr):
                        return getattr(parent, attr)
                    return parent.__inherited_getattr__(attr)
        return None

    def __getattr__(self, attr):
        """
            Use class attribute to read / write SVD element property

            The content of tag is converted from text to the type of the tag.
            If the tag doesn't exist, this try to get the one defined in parent.
            If the element has been derived from another element, this uses the
            tag from the base element.

            :param attr: The name of the property (e.g. tag name) to get
            :return: The content of the tag, eventually updated based on
                     other elements' properties, None if the property is defined
        """
        derived_value = None
        if self.derived_element != None:
            derived_value = self.__svd_getattr__(attr, self.derived_element)
        value = self.__svd_getattr__(attr, self.element)
        if value is None and attr == 'displayName':
            value = self.name
        if derived_value != None and value is None:
            return derived_value
        if derived_value is None and value is None:
            value = self.__inherited_getattr__(attr)
        if value is None:
            for attr_type in self.attrs:
                if attr in self.attrs[attr_type]:
                    return value
        if value is None:
            raise AttributeError("Unknown attribute " + attr)
        return value

    def add_svd_elements(self, svd_class, array):
        """
            Allocate one more SVD element and add them to an array

            This mostly handle one particular use case which is dimable elements.
            Dimable element are declared once and instanced multiple time.
            To manage that, a svd_element_class class is allocated to get the
            element properties. If the element is dimable, then this allocates
            many svd_class using the current element.

            :param svd_class: The class to use to allocate and use a parsed
                              element
            :param array: The array used to store the elements
        """
        if self.dim:
            indexes = self.dimIndex
            if indexes is None:
                indexes = range(0, self.dim)
            for index in range(0, len(indexes)):
                element = svd_class(self.element, self.parent)
                element.index = index
                element.parse()
                array[element.name] = element
        else:
            element = svd_class(self.element, self.parent)
            element.parse()
            array[element.name] = element

    def do_parse(self, svd_element_class, svd_class, parent_tag, parent_element):
        """
            Go through a list of elements, and parse them

            This checks if the root element (e.g peripherals) is present,
            and then go through it. Only expected element are parsed
            (e.g. peripheral if list element is peripherals).

            :param svd_element_class: The class to use to allocate and parse
                                      the element
            :param svd_class: The class to use to allocate and use a parsed
                              element
            :param parent_tag: The name of element to go through
            :param parent_element: The root element (e.g. parent of element to go through)
        """
        tag = parent_tag[:-1]
        if not hasattr(parent_element, parent_tag):
            return

        for element in getattr(parent_element, parent_tag).getchildren():
            if element.tag != tag:
                continue
            svd_element = svd_element_class(element, self)
            svd_element.add_svd_elements(svd_class, getattr(self, parent_tag))

class SVDEnumeratedValueElement(SVDElement):
    """
        A class to represent EnumeratedValue element

        This class registers the list of expected tags,
        and the type of their contents.
    """
    def __init__(self, element, parent):
        super(SVDEnumeratedValueElement, self).__init__(element, parent)
        self.merge_attrs({
            'identifierType': ['name'],
            'xs:string': ['description'],
            'scaledNonNegativeInteger': ['value'],
            'xs:boolean': ['isDefault'],
        })

    def add_svd_elements(self, svd_class, array):
        self.parent.enumeratedValues[self.value] = self

class SVDEnumeratedValuesElement(SVDElement):
    """
        A base class for SVDEnumeratedValues

        This class registers the list of expected tags,
        and the type of their contents.
    """
    def __init__(self, element, parent):
        super(SVDEnumeratedValuesElement, self).__init__(element, parent)
        self.merge_attrs({
            'xs:Name': ['derivedFrom', 'name'],
            'identifierType': ['headerEnumName'],
            'enumUsageType': ['usage'],
            'enumeratedValueType': ['enumeratedValue'],
        })

class SVDFieldElement(SVDElement):
    """
        A base class for SVDField

        This class registers the list of expected tags,
        and the type of their contents.
    """
    def __init__(self, element, parent):
        super(SVDFieldElement, self).__init__(element, parent)
        self.merge_attrs({
            'dimableIdentifierType': ['name'],
            'stringType': ['description'],
            'scaledNonNegativeInteger': [
                'bitOffset', 'bitWidth', 'lsb', 'msb'
            ],
            'bitRangeType': ['bitRange'],
            'accessType': ['access'],
            'modifiedWriteValuesType': ['modifiedWriteValues'],
            'writeConstraintType': ['writeConstraint'],
            'readActionType': ['readAction'],
        })
        self.merge_attrs(self.dim_attrs)
        self.enumeratedValues = OrderedDict()

class SVDRegisterElement(SVDElement):
    """
        A base class for SVDRegister

        This class registers the list of expected tags,
        and the type of their contents.
    """
    def __init__(self, element, parent):
        super(SVDRegisterElement, self).__init__(element, parent)
        self.merge_attrs({
            'registerNameType': ['name'],
            'dimableIdentifierType': [
                'derivedFrom', 'alternateRegister', 'headerStructName'
            ],
            'xs:string': ['description', 'displayName'],
            'xs:Name': ['alternateGroup'],
            'scaledNonNegativeInteger': ['addressOffset'],
            'dataTypeType': ['dataType'],
            'modifiedWriteValuesType': ['modifiedWriteValues'],
            'writeConstraintType': ['writeConstraint'],
            'readActionType': ['readAction'],
        })
        self.merge_attrs(self.dim_attrs)
        self.merge_attrs(self.register_attrs)
        self.fields = OrderedDict()

class SVDPeripheralElement(SVDElement):
    """
        A base class for SVDPeripheral

        This class registers the list of expected tags,
        and the type of their contents.
    """
    def __init__(self, element, parent):
        super(SVDPeripheralElement, self).__init__(element, parent)
        self.merge_attrs({
            'dimableIdentifierType': [
                'derivedFrom', 'name', 'alternatePeripheral', 'headerStructName'
            ],
            'xs:string': ['version', 'description'],
            'xs:Name': ['groupName'],
            'identifierType': ['prependToName', 'appendToName'],
            'stringType': ['disableCondition'],
            'scaledNonNegativeInteger': ['baseAddress'],
        })
        self.merge_attrs(self.dim_attrs)
        self.merge_attrs(self.register_attrs)
        self.registers = OrderedDict()

class SVDEnumeratedValues(SVDEnumeratedValuesElement):
    """
        A class to parse a SVDFEnuratedValues element

        This class represents the field element,
        e.g an array of values.
    """
    def parse(self):
        """Parse SVDEnumerateValues element"""
        if 'derivedFrom' in self.element.enumeratedValues.attrib:
            self.find_derived_from(self.element.enumeratedValues)
            self.parent.do_parse(SVDEnumeratedValueElement, None,
                                 "enumeratedValues", self.derived_element)
        else:
            self.parent.do_parse(SVDEnumeratedValueElement, None,
                                 "enumeratedValues", self.element)

class SVDField(SVDFieldElement):
    """
        A class to parse a SVDField element

        This class represents the field element,
        e.g an array of enumerated values.
    """
    def parse(self):
        """ Parse SVDField element"""
        if self.bitOffset is None:
            bits = self.bitRange
            if not bits:
                bits = {}
                bits[0] = self.msb
                bits[1] = self.lsb
            if bits:
                setattr(self, 'bitOffset', bits[1])
                setattr(self, 'bitWidth', (bits[0] - bits[1]) + 1)
        if self.bitWidth is None:
            setattr(self, 'bitWidth', 1)

        if hasattr(self.element, 'enumeratedValues'):
            SVDEnumeratedValues(self.element, self).parse()

class SVDRegister(SVDRegisterElement):
    """
        A class to parse a SVDRegister element

        This class represents the register element,
        e.g an array of fields.
    """
    def parse(self):
        """ Parse SVDRegister element"""
        if 'derivedFrom' in self.element.attrib:
            self.find_derived_from(self.element)
            self.do_parse(SVDFieldElement, SVDField, "fields",
                          self.derived_element)
        self.do_parse(SVDFieldElement, SVDField, "fields", self.element)

    def address(self):
        """
            Compute and return the register offset

            :return: The address of the register
            :rtype: int
        """
        return self.parent.baseAddress + self.addressOffset

class SVDPeripheral(SVDPeripheralElement):
    """
        A class to parse a SVDPeripheral element

        This class represents the peripheral element,
        e.g an array of registers.
    """
    def parse(self):
        """ Parse SVDPeripheral element"""
        if 'derivedFrom' in self.element.attrib:
            self.find_derived_from(self.element)
            self.do_parse(SVDRegisterElement, SVDRegister,
                          "registers", self.derived_element)
        self.do_parse(SVDRegisterElement, SVDRegister, "registers", self.element)

class SVD(SVDElement):
    """
        A class to open and parse a SVD file

        This could be used to open and parse a SVD.
        After parsing has been done, this create a tree that could be used
        to access to SVD properties.

        This class represents the root elements, e.g an array of peripherals.
    """
    def __init__(self, fname):
        svd_file = lxml.objectify.parse(os.path.expanduser(fname))
        super(SVD, self).__init__(svd_file.getroot(), None)
        self.merge_attrs({
            'xs:string': [
                'vendor', 'vendorID', 'name', 'series', 'version',
                'description', 'licenseText', 'cpu',
            ],
            'scaledNonNegativeInteger': ['addressUnitBits', 'width'],
        })
        self.merge_attrs(self.register_attrs)
        self.peripherals = OrderedDict()

    def parse(self):
        """
            Parse a CMSIS SVD file

            This parse a SVD file and creates a tree.
            After a call to this function, all elements and properties
            should be available.
        """
        self.do_parse(SVDPeripheralElement, SVDPeripheral,
                      "peripherals", self.element)
        self.fixup()

    def fixup_bits_to_field(self, register, name):
        """
            Fix up broken fields

            Sometime, in SVD, a field with a width greater than one is defined
            using more than one field.
            By example, instead of defining a field 'A', with a width of 2 bits,
            this defines 'A0' and 'A1'.
        """
        res = re.search(r'(?P<name>.*)\d+', name)
        if not res:
            return
        fields = {}
        base_name = res.group('name')
        if not hasattr(register, 'fixed_fields'):
            setattr(register, 'fixed_fields', {})
        if not base_name in register.fixed_fields:
            offset = 32
            bitwidth = 0
            for field_name in register.fields:
                field = register.fields[field_name]
                if re.match(base_name + r'\d+', field_name):
                    if field.bitWidth > 1:
                        return
                    bitwidth += 1
                    offset = min(field.bitOffset, offset)
                    fields[field.bitOffset] = field

            contigous = True
            for bitoffset in fields:
                if not contigous:
                    return
                if bitoffset + 1 in fields:
                    continue
                else:
                    contigous = False
                    continue

            obj = SVDField(field, register)
            setattr(obj, 'name', base_name)
            setattr(obj, 'bitWidth', bitwidth)
            setattr(obj, 'bitOffset', offset)
            register.fixed_fields[base_name] = obj

    def fixup(self):
        """
            Fix up SVD quirks

            There are some quirks present in SVD files.
            This tries to handle them, in order to get the same behavior for
            every SVD files.
        """
        for peripheral_name in self.peripherals:
            peripheral = self.peripherals[peripheral_name]
            for register_name in peripheral.registers:
                register = peripheral.registers[register_name]
                for field_name in register.fields:
                    self.fixup_bits_to_field(register, field_name)
                if hasattr(register, 'fixed_fields'):
                    for field in register.fixed_fields:
                        register.fields[field] = register.fixed_fields[field]
