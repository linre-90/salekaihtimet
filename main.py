"""
Created: AT + ML + linre-90
Updated: AT + ML + linre-90 / 26.03.2024
"""
from s_logger import s_dev_Log, s_dev_Log_time
import RPi.GPIO as GPIO
from s_manual_mode import manual_mode
import signal
import sys
from s_automatic_mode import update_sun_timestamps, automatic_mode, automatic_init
from s_user_mode import user_mode, update_close_time
from s_settings_server import server_start, server_close
from s_settings_parser import read_settings
from s_utils import str_to_HHMM
from s_clock import clock_init, clock_run, clock_stamp, clock_update_time, T_SCALE_100X

# Dev mode globals
DEV_MODE = True
DEV_LOGGING = True

# Operation mode pin list and initialization
MODE_MANUAL=11 # Red
MODE_TIME=13 # Blue
MODE_AUTOMATIC=15 # Green
OPERATION_MODES = [MODE_MANUAL, MODE_TIME, MODE_AUTOMATIC]
CURRENT_OPERATION_MODE = 0

# Button pin definitions
BUTTON_OPEN=3
BUTTON_CLOSE=5
BUTTON_MODE=7
BUTTON_SETUP=37
MOTOR_CHANNEL=(32,36,38,40)
LIGHT_SENSOR=19

# Setup mode has to be tracked in here
IS_SETUP_MODE = False
APP_SETTINGS = None

def reset()->None:
    """Reset gpio, active mode and settings to default."""
    clean_up_pins()
    set_up_pins()
    global CURRENT_OPERATION_MODE
    CURRENT_OPERATION_MODE = 0


def set_up_pins():
    """Setup pin io modes etc..."""
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(BUTTON_OPEN, GPIO.IN)
    GPIO.setup(BUTTON_CLOSE, GPIO.IN)
    GPIO.setup(MOTOR_CHANNEL, GPIO.OUT)
    GPIO.setup(BUTTON_MODE, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(BUTTON_SETUP, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(MODE_MANUAL, GPIO.OUT)
    GPIO.setup(MODE_TIME, GPIO.OUT)
    GPIO.setup(MODE_AUTOMATIC, GPIO.OUT)
    GPIO.setwarnings(DEV_MODE)
    s_dev_Log(DEV_LOGGING, "Running in development mode.")
    s_dev_Log(DEV_LOGGING, "Development logging enabled.")
    s_dev_Log(DEV_LOGGING, f"Pins: manual_mode={OPERATION_MODES[0]}, time_mode={OPERATION_MODES[1]}, automatic_mode={OPERATION_MODES[2]}")


def clean_up_pins():
    """Set everything back to 0 before shutting down."""
    GPIO.cleanup()


def mode_toggle(channel):
    """Cycles through the operation modes."""
    if channel == BUTTON_MODE:
        if IS_SETUP_MODE:
            return
        global CURRENT_OPERATION_MODE
        # If CURRENT_OPERATION_MODE can be incremented and stay under 3,
        # increment the variable. If not, give CURRENT_OPERATION_MODE value 0
        # to cycle back to first mode.
        if CURRENT_OPERATION_MODE + 1 <= 2:
            CURRENT_OPERATION_MODE += 1
            s_dev_Log(DEV_LOGGING, f"Mode change to {CURRENT_OPERATION_MODE}")
            mode_light_toggle()
            return
        CURRENT_OPERATION_MODE = 0
        s_dev_Log(DEV_LOGGING, f"Mode change to {CURRENT_OPERATION_MODE}")
        mode_light_toggle()


def setup_mode_toggle(channel):
    """Enables settings upload mode."""
    if channel == BUTTON_SETUP:
        global IS_SETUP_MODE
        if IS_SETUP_MODE: # Setup mode is active need to exit and close server
            server_close(load_settings)
            IS_SETUP_MODE = False
            mode_light_toggle()
            s_dev_Log(DEV_LOGGING, f"Exited setup mode")
        else: # Setup mode is not active need to enable setup mode and start server
            IS_SETUP_MODE = True
            # set setup led indicator
            GPIO.output(MODE_MANUAL, GPIO.HIGH)
            GPIO.output(MODE_TIME, GPIO.LOW)
            GPIO.output(MODE_AUTOMATIC, GPIO.HIGH)
            # Start settings upload server on different thread
            server_start()
            s_dev_Log(DEV_LOGGING, f"Entered setup mode")


def mode_light_toggle():
    "Lights up the corresponding colored LED while changing operation modes."
    if IS_SETUP_MODE:
        return
    if CURRENT_OPERATION_MODE == 0:
        # Manual mode red led
        GPIO.output(MODE_MANUAL, GPIO.HIGH)
        GPIO.output(MODE_TIME, GPIO.LOW)
        GPIO.output(MODE_AUTOMATIC, GPIO.LOW)
    if CURRENT_OPERATION_MODE == 1:
        # User mode blue led
        GPIO.output(MODE_MANUAL, GPIO.LOW)
        GPIO.output(MODE_TIME, GPIO.HIGH)
        GPIO.output(MODE_AUTOMATIC, GPIO.LOW)
    if CURRENT_OPERATION_MODE == 2:
        # Automatic mode green led
        GPIO.output(MODE_MANUAL, GPIO.LOW)
        GPIO.output(MODE_TIME, GPIO.LOW)
        GPIO.output(MODE_AUTOMATIC, GPIO.HIGH)


def handle_keyboard_interrupt(sig, frame):
    """Assisting function for development."""
    clean_up_pins()
    server_close(load_settings)
    sys.exit(0)


def load_settings():
    """Loads user settings and sets variables. If user settings does not exists loads default settings."""
    global APP_SETTINGS
    try:
        APP_SETTINGS = read_settings("user_settings.kaihdin")
        s_dev_Log(DEV_LOGGING, f"Loaded user settings.")
    except:
        APP_SETTINGS = read_settings("default_settings.kaihdin")
        s_dev_Log(DEV_LOGGING, f"Loaded default settings.")


def main():
    # Load user or default settings
    load_settings()

    # bind ctrl+c in dev mode.
    if DEV_MODE:
        signal.signal(signal.SIGINT, handle_keyboard_interrupt)
    
    # Handles the button presses for the mode swap.
    GPIO.add_event_detect(BUTTON_MODE, GPIO.FALLING, callback=mode_toggle, bouncetime=2000)
    mode_light_toggle()
    
    # Handles the button presses for setup mode
    GPIO.add_event_detect(BUTTON_SETUP, GPIO.FALLING, callback=setup_mode_toggle, bouncetime=2000)

    # Intializes the time by calling the init() function.
    timestamp = clock_init()
    update_sun_timestamps((float(APP_SETTINGS["latitude"]), float(APP_SETTINGS["longitude"])), timestamp)
    update_close_time(
        timestamp, 
        str_to_HHMM(APP_SETTINGS["close_start"])[0], 
        str_to_HHMM(APP_SETTINGS["close_start"])[1], 
        int(APP_SETTINGS["close_duration"])
    )

    automatic_init(5, 6, timestamp)

    # Main program loop that selects the operation mode.
    while True:

        t_start = clock_stamp()

        if IS_SETUP_MODE:
            # No other operations are allowed if in setup mode.
            continue
        if CURRENT_OPERATION_MODE == 0:
            manual_mode(BUTTON_OPEN, BUTTON_CLOSE, MOTOR_CHANNEL)
        if CURRENT_OPERATION_MODE == 1:
            user_mode(
                timestamp, 
                MOTOR_CHANNEL, 
                str_to_HHMM(APP_SETTINGS["close_start"])[0], 
                str_to_HHMM(APP_SETTINGS["close_start"])[1], 
                int(APP_SETTINGS["close_duration"])
            )
        if CURRENT_OPERATION_MODE == 2:
            automatic_mode(
                timestamp, 
                (float(APP_SETTINGS["latitude"]), float(APP_SETTINGS["longitude"])), 
                MOTOR_CHANNEL, 
                str_to_HHMM(APP_SETTINGS["close_start"])[0], 
                str_to_HHMM(APP_SETTINGS["close_start"])[1], 
                int(APP_SETTINGS["close_duration"])
            )
        clock_run(DEV_MODE)
        t_end = clock_stamp()
        timestamp = clock_update_time(timestamp, DEV_MODE, (t_end - t_start).microseconds, T_SCALE_100X)
        s_dev_Log_time(DEV_LOGGING, timestamp)


if __name__ == "__main__":
    clean_up_pins()
    set_up_pins()
    main()
