import machine
import time
import struct

# ==============================================================================
# 1. HARDWARE CONFIGURATION & PIN DEFINITIONS
# ==============================================================================
# Pico W I2C0 Pins (SDA: GP4, SCL: GP5)
I2C_SDA_PIN = 4
I2C_SCL_PIN = 5
I2C_FREQ = 400000

TCA9548A_ADDR = 0x70  # I2C address for TCA9548A multiplexer
DRV2605_ADDR   = 0x5A  # Default I2C address for DRV2605L drivers

# FSR Analog Input Pin Mapping:
# - Pad 0: GPIO26 (ADC0)
# - Pad 1: GPIO27 (ADC1)
# - Pad 2: GPIO28 (ADC2)
# - Pad 3: GPIO22 (Standard GPIO read or secondary ADC)
FSR_ADC_PINS = [26, 27, 28]
PRESS_THRESHOLD = 18000  # Raw 16-bit ADC press trigger threshold
DEBOUNCE_MS = 120       # Minimum time between re-triggers (ms)

# Corresponding MIDI Notes for pads (C3, D3, E3, F3)
PAD_MIDI_NOTES = [60, 62, 64, 65]

# ==============================================================================
# 2. USB MIDI UTILITIES (Class-Compliant MIDI Output)
# ==============================================================================
def send_midi_note_on(channel, note, velocity):
    """Formats and sends a 4-byte USB MIDI Note On packet."""
    # Header byte: Cable 0, Code Index Number 0x9 (Note On)
    header = 0x09
    status = 0x90 | (channel & 0x0F)
    # Write to USB raw endpoint buffer if supported, or output debug REPL payload
    packet = bytes([header, status, note & 0x7F, velocity & 0x7F])
    print(f"[MIDI OUT] Note On: Note {note}, Velocity {velocity}")

def send_midi_note_off(channel, note):
    """Formats and sends a 4-byte USB MIDI Note Off packet."""
    header = 0x08
    status = 0x80 | (channel & 0x0F)
    packet = bytes([header, status, note & 0x7F, 0x00])
    print(f"[MIDI OUT] Note Off: Note {note}")

# ==============================================================================
# 3. TCA9548A MULTIPLEXER & DRV2605L DRIVER CONTROL
# ==============================================================================
i2c = machine.I2C(0, scl=machine.Pin(I2C_SCL_PIN), sda=machine.Pin(I2C_SDA_PIN), freq=I2C_FREQ)

def select_tca_channel(channel):
    """Enables a single channel (0-7) on the TCA9548A multiplexer."""
    if 0 <= channel <= 7:
        i2c.writeto(TCA9548A_ADDR, bytes([1 << channel]))

def init_drv2605l_lra(channel):
    """Initializes a DRV2605L driver for LRA motor operation on a specific channel."""
    select_tca_channel(channel)
    try:
        # Wake up device (Exit standby mode)
        i2c.writeto_mem(DRV2605_ADDR, 0x01, b'\x00')
        
        # Set feedback register to LRA mode (Bit 7 = 1 for LRA)
        # 0x1A is the Feedback Control Register
        i2c.writeto_mem(DRV2605_ADDR, 0x1A, b'\x80')
        
        # Select Library 6 (LRA Library) in Control1/Mode register
        i2c.writeto_mem(DRV2605_ADDR, 0x03, b'\x06')
        print(f"[HW INIT] DRV2605L LRA Driver initialized on Channel {channel}")
    except Exception as e:
        print(f"[HW ERROR] Failed to initialize DRV2605L on Channel {channel}: {e}")

def trigger_haptic_effect(channel, effect_id=47):
    """Triggers a pre-programmed haptic pulse (Library Effect) on the target motor."""
    select_tca_channel(channel)
    try:
        # Set waveform sequence 1 to chosen effect ID (e.g., 47 = Sharp Click 100%)
        i2c.writeto_mem(DRV2605_ADDR, 0x04, bytes([effect_id]))
        # Set waveform sequence 2 to 0 (End of sequence marker)
        i2c.writeto_mem(DRV2605_ADDR, 0x05, b'\x00')
        # Fire trigger bit (GO register 0x0C)
        i2c.writeto_mem(DRV2605_ADDR, 0x0C, b'\x01')
    except Exception as e:
        print(f"[HW ERROR] Haptic trigger error on Channel {channel}: {e}")

# ==============================================================================
# 4. INITIALIZATION & MAIN LOOP
# ==============================================================================
print("=== Starting Haptic MIDI Pad Firmware ===")

# Initialize ADC pins for Pad 0, 1, 2
adc_sensors = [machine.ADC(pin) for pin in FSR_ADC_PINS]

# Initialize Digital Pin for Pad 3
pad3_gpio = machine.Pin(22, machine.Pin.IN, machine.Pin.PULL_DOWN)