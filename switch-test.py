import RPi.GPIO as GPIO

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
GPIO.setup(10, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

isOpen = False

def button_callback(channel):
    global isOpen
    if GPIO.input(10): # if pin is HIGH
        isOpen = True
    else: # if pin is LOW
        isOpen = False
    print("State is: ", isOpen)

# Use BOTH edge detection and increase bouncetime
GPIO.add_event_detect(10, GPIO.BOTH, callback=button_callback, bouncetime=300)

message = input("Press enter to quit\n\n")
GPIO.cleanup()