import gc
import esp # or standard garbage collection logic for Pico

# Run garbage collection on startup to free up RAM for haptic buffer memory
gc.collect()

print("Boot script complete. Handing off to main.py...")