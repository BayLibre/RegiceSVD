CMSIS SVD file parser

Usage:

    >>> from svd import SVD
    >>> svd = SVD(filename)
    >>> svd.parse()
This will create a tree similar to the SVD one.

To get a list of peripherals:

    >>>     >>> svd.peripherals.keys()
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
