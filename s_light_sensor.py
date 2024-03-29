"""
Created: ML + linre-90/20.03.2024
Updated:
"""

import time
import RPi.GPIO as GPIO
from math import floor
from s_logger import s_dev_Log


# found min with phone flashlight(max brightness) = 10
RANGE_MIN = 10

# found max with fingering sensor (max darkness) = 51900
RANGE_MAX = 51900


def sensor_read_single_value(pin)->int:
    """
    Read single data point from ldr.
    """
    count = 0
    # Dry out voltage from capacitor
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)
    time.sleep(0.1)

    # Set pin to input mode effectively start "measure mode"
    GPIO.setup(pin, GPIO.IN)

    # count amount of loops it takes to reach 1.8v, HIGH input.
    while (GPIO.input(pin) == GPIO.LOW):
        count += 1
    if count < RANGE_MIN:
        return 14
    if count > RANGE_MAX:
        return 51900
    s_dev_Log(True, f"time:{time.time()}, sensor_snapshot_value: {count}")
    return count


def sensor_val_to_percentage(value: int)->int:
    """Convert data point to open percentage."""
    r_max = RANGE_MAX - RANGE_MIN
    r_val = value - RANGE_MIN
    return floor((r_val / r_max) * 100)


if __name__ == "__main__":
    GPIO.setmode(GPIO.BOARD)
    try:
        while True:
            time.sleep(.5)
            val = sensor_read_single_value(31)
            print(sensor_val_to_percentage(val))

    except KeyboardInterrupt:
        pass
    finally:
        GPIO.cleanup()
