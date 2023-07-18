import numpy as np

little = 40e-6
big = 12.275e-3

total = 12.2793192

I2C = 244*(big + 2 * little) + 10 * little
USB = total - I2C

I2CNew = I2C/10
USBNew = (1 - (2/3) - 0.1)*USB
NewTot = I2CNew + USBNew
print(f'old I2C is: {I2C}')
print(f'old USB is: {USB}')
print()
print(f'New I2C is: {I2CNew}')
print(f'New USB is: {USBNew}')
print(f'New Total is: {NewTot}')