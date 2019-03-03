#!/usr/bin/env python3
import asyncio
import argparse
import json
import sys
import logging
import signal
from gpiozero import LED
from concurrent.futures import ThreadPoolExecutor
from .temper import Temper

def get_status(temper):
    logger = logging.getLogger("rpioalert.get_status")
    status = []
    try:
        raw_status = temper.read()

        if not len(raw_status):
            raise Exception("No status")

        for stat in raw_status:
            temper_stat = {}
            for key, value in stat.items():
                key = key.replace(" ", "_").lower()

                try:
                    value = (None if value == "" else str(value))
                except:
                    pass

                temper_stat[key] = value
            status.append(temper_stat)
    except:
        logger.debug(sys.exc_info())

    return status

def compare(condition, temperature, humidity):
    try:
        value_type, comparison, cvalue = condition.split(":")
   
        if value_type == ["t", "temp", "temperature"]:
            value = temperature
        elif value_type in ["h", "hum", "humidity"]:
            value = humidity 

        if comparison == "eq":
            return float(value) == float(cvalue)
        elif comparison == "gt":
            return float(value) > float(cvalue)
        elif comparison == "gte":
            return float(value) >= float(cvalue)
        elif comparison == "lt":
            return float(value) < float(cvalue)
        elif comparison == "lte":
            return float(value) <= float(cvalue)
        else:
            return False 
    except:
        return False

def toggle_led(leds, condition, avg_temp, avg_humid, turn_on):
    logger = logging.getLogger("rpioalert.toggle_led")
    reach = True
    for c in condition:
        reach = (reach and compare(c, avg_temp, avg_humid))

    if reach is False:
        return False
    
    logger.debug("{}, T:{}, H:{}, Reach:{}".format(",".join(condition), avg_temp, avg_humid, reach))
   
    for led in leds:
        if turn_on is True and led.is_lit is False:
            logger.debug("{}, T:{}, H:{}, LED:{}, OFF->ON".format(",".join(condition), avg_temp, avg_humid, led.pin.number))
            led.on()
        elif turn_on is False and led.is_lit is True:
            logger.debug("{}, T:{}, H:{}, LED:{}, ON->OFF".format(",".join(condition), avg_temp, avg_humid, led.pin.number))
            led.off()

    current_state = ["LED:{} {}".format(l.pin.number, "ON" if l.is_lit else "OFF") for l in leds]
    logger.debug("Current state {}".format(", ".join(current_state)))


async def rpio_alert(leds, off_condition=[], on_condition=[], executor=None, both=False, loop=None):
    executor = executor or ThreadPoolExecutor(max_workers=1)
    loop = loop or asyncio.get_event_loop()
    logger = logging.getLogger("rpioalert.rpio_alert")

    temper = Temper()
    stop = False

    while not stop:
        try:
            status = await loop.run_in_executor(executor, get_status, temper)

            if len(status) == 0:
                raise Exception("Empty status")

            temps = []
            humis = []

            for stat in status:
                if "internal_temperature" in stat:
                    temps.append(stat["internal_temperature"] or 0)


                if "internal_humidity" in stat:
                    humis.append(stat["internal_humidity"] or 0)

            if len(temps) == 0 or len(humis) == 0:
                raise Exception("No record from sensorpicker")
   
            avg_temp = sum(map(float, temps)) / len(temps)
            avg_humid = sum(map(float, humis)) / len(humis)

            toggle_led(leds, off_condition, avg_temp, avg_humid, turn_on=False)
            toggle_led(leds, on_condition, avg_temp, avg_humid, turn_on=True)
        except asyncio.CancelledError:
            stop = True
        except KeyboardInterrupt:
            stop = True
        except:
            logger.debug(sys.exc_info())

        await asyncio.sleep(1)

async def shutdown(task):
    task.cancel()
    await task

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pin", help="GPIO Pin", type=int, action='append')
    parser.add_argument("--off", help="Pin Off condition, format: <temp|hum>:<eq|lt|lte|gt|gte>:<value>", action="append")
    parser.add_argument("--on", help="Pin On condition, format: <temp|hum>:<eq|lt|lte|gt|gte>:<value>", action="append")
    parser.add_argument("-stop", help="Cleanup on stop service", action="store_true", default=False)
    parser.add_argument("-v", "--verbose", help="Log verbosity", action="store_true", default=False)

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)-30s %(message)s"
    )
    logger = logging.getLogger("rpioalert.main")


    if args.pin is None:
        logger.info("Please state GPIO pin")
        sys.exit()

    if args.stop is True:
        logger.info("Reset LED")
        for pin in args.pin:
            led = LED(pin)
            led.off()
            led.close()
        sys.exit()
        
    try:
        leds = [LED(pin) for pin in args.pin]
    except:
        logger.info("Unable to connect to GPIO Pin {}".format(args.pin))
        logger.debug(sys.exc_info())
        sys.exit()

    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=1)

    kwargs = {
        "executor" : executor,
        "leds" : leds, 
        "off_condition" : args.off,
        "on_condition" : args.on,
        "loop" : loop
    }
    
    tasks = [
        asyncio.ensure_future(rpio_alert(**kwargs))
    ]

    try:
        logger.info("Start rpioalert")
        loop.run_forever()
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        pass
    except:
        logger.debug(sys.exc_info())
    
    logger.info("Stop rpioalert")
    loop.run_until_complete(asyncio.wait([shutdown(t) for t in tasks]))
    executor.shutdown(wait=True)
    loop.close()

    for led in leds:
        if not led.closed:
            led.off()
            led.close()

if __name__ == "__main__":
    main()
