#!/usr/bin/env python3
import argparse
import asyncio
import json
import logging
import signal
import sys
from concurrent.futures import ThreadPoolExecutor

from gpiozero import LED

from .temper import Temper


class Status:
    def __init__(self, temperature=0, humidity=0):
        self._temperature = temperature
        self._humidity = humidity

    @property
    def temperature(self):
        return self._temperature

    @property
    def humidity(self):
        return self._humidity

    @temperature.setter
    def temperature(self, temp):
        self._temperature = temp

    @humidity.setter
    def humidity(self, hum):
        self._humidity = hum

    def dict(self):
        return {"temperature": self._temperature, "humidity": self._humidity}


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


def compare(comparison, value_to_compare, current_value):
    try:
        if comparison == "eq":
            return float(current_value) == float(value_to_compare)
        elif comparison == "gt":
            return float(current_value) > float(value_to_compare)
        elif comparison == "gte":
            return float(current_value) >= float(value_to_compare)
        elif comparison == "lt":
            return float(current_value) < float(value_to_compare)
        elif comparison == "lte":
            return float(current_value) <= float(value_to_compare)
        else:
            return False
    except:
        return False


def logic_gate(logic, value_left, value_right):
    if logic == "or":
        result = (value_left or value_right)
    elif logic == "xor":
        result = (bool(value_left) != bool(value_right))
    elif logic == "nand":
        result = not (value_left and value_right)
    elif logic == "nor":
        result = not (value_left or value_right)
    elif logic == "xnor":
        result = not (bool(value_left) != bool(value_right))
    else:
        # Default AND
        result = (value_left and value_right)

    return result


def format_condition(condition, as_str=False):
    condition_configs = []
    for c in condition:
        condition_config = c.split(":")
        if len(condition_config) == 3:
            # Added defult logic gate
            condition_config.append("and")
            condition_configs.append(condition_config)
        elif len(condition_config) == 4:
            condition_configs.append(condition_config)
        else:
            # Remove invalid condition format
            continue

    if as_str is False:
        return condition_configs

    condition_str = []
    for i, c in enumerate(condition_configs):
        value_type, comparison, value_to_compare, logic = c
        if i > 0:
            condition_str.append(logic)
        condition_str.append("{}:{}:{}".format(
            value_type, comparison, value_to_compare))

    return " ".join(condition_str)


def toggle_led(leds, condition, avg_temp, avg_humid, turn_on):
    """
    Toggle led if condition is Reach
    return bool(reach)
    """
    logger = logging.getLogger("rpioalert.toggle_led")
    reach = None

    condition_configs = format_condition(condition)
    condition_str = format_condition(condition, True)

    for c in condition_configs:
        value_type, comparison, value_to_compare, logic = c

        if value_type in ["t", "temp", "temperature"]:
            current_value = avg_temp
        elif value_type in ["h", "hum", "humidity"]:
            current_value = avg_humid
        else:
            continue

        compare_result = compare(comparison, value_to_compare, current_value)
        if reach is None:
            reach = compare_result
            continue

        reach = logic_gate(logic, reach, compare_result)

    logger.debug("{} : {}, T:{}, H:{}, Reach:{}".format(
        "ON" if turn_on else "OFF", condition_str, avg_temp, avg_humid, reach))

    # Not reach
    if reach is False:
        return False

    for led in leds:
        if turn_on is True and led.is_lit is False:
            logger.debug("{}, T:{}, H:{}, LED:{}, OFF->ON".format(
                condition_str, avg_temp, avg_humid, led.pin.number))
            led.on()
        elif turn_on is False and led.is_lit is True:
            logger.debug("{}, T:{}, H:{}, LED:{}, ON->OFF".format(
                condition_str, avg_temp, avg_humid, led.pin.number))
            led.off()

    current_state = ["LED:{} {}".format(
        l.pin.number, "ON" if l.is_lit else "OFF") for l in leds]
    logger.debug("Current state {}".format(", ".join(current_state)))

    # Reach
    return True


async def rpc_server(leds, stats, listen="0.0.0.0", port=15555, off_condition=[], on_condition=[], lock=None, executor=None, loop=None):
    executor = executor or ThreadPoolExecutor(max_workers=1)
    loop = loop or asyncio.get_event_loop()
    logger = logging.getLogger("rpioalert.rpc_server")

    async def rpc_handler(reader, writer):
        request = await reader.read(1024)
        request = json.loads(request.decode())

        logger.debug("Request : {}".format(request))

        response = None

        try:
            if request["method"] == "get_status":
                async with lock:
                    led_state = [{"pin": l.pin.number, "state": l.is_lit}
                                 for l in leds]
                    current_state = {"status": stats.dict(), "condition": {
                        "off": off_condition, "on": on_condition}, "led": led_state}
                    response = json.dumps(current_state)

            logger.debug("Response : {}".format(response))

            writer.write(response.encode())
            await writer.drain()
            writer.close()
        except:
            logger.debug(sys.exc_info())
            writer.close()

    try:
        logger.info("Start rpc server, listening on {}:{}".format(listen, port))
        server = asyncio.start_server(rpc_handler, listen, port)
        await server
    except:
        logger.info(sys.exc_info())


async def rpio_alert(leds, stats, off_condition=[], on_condition=[], off_first=False, lock=None, executor=None, both=False, loop=None):
    executor = executor or ThreadPoolExecutor(max_workers=1)
    loop = loop or asyncio.get_event_loop()
    logger = logging.getLogger("rpioalert.rpio_alert")

    temper = Temper()
    stop = False

    while not stop:
        try:
            temper_status = await loop.run_in_executor(executor, get_status, temper)

            if len(temper_status) == 0:
                raise Exception("Empty status")

            temps = []
            humis = []

            for s in temper_status:
                if "internal_temperature" in s:
                    temps.append(s["internal_temperature"] or 0)

                if "internal_humidity" in s:
                    humis.append(s["internal_humidity"] or 0)

            if len(temps) == 0 or len(humis) == 0:
                raise Exception("No record from temper device")

            avg_temp = sum(map(float, temps)) / len(temps)
            avg_humid = sum(map(float, humis)) / len(humis)

            async with lock:
                stats.temperature = avg_temp
                stats.humidity = avg_humid

                if off_first:
                    turn_on = [False, True]
                else:
                    turn_on = [True, False]

                reach = toggle_led(leds, off_condition, avg_temp,
                                   avg_humid, turn_on=turn_on[0])
                if not reach:
                    toggle_led(leds, on_condition, avg_temp,
                               avg_humid, turn_on=turn_on[1])
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
    parser.add_argument("-rpc", help="Start rpc server",
                        action="store_true", default=False)
    parser.add_argument("-v", "--verbose", help="Log verbosity",
                        action="store_true", default=False)
    parser.add_argument("-stop", help="Cleanup on stop service",
                        action="store_true", default=False)
    parser.add_argument(
        "-off_first", help="Check OFF condition first, then ON condition", action="store_true", default=False)
    parser.add_argument("--pin", help="GPIO Pin", type=int,
                        action='append', default=[])
    parser.add_argument(
        "--off", help="Pin Off condition, format: <temp|hum>:<eq|lt|lte|gt|gte>:<value>:[or|and|xor|nand|nor|xnor]", action="append", default=[])
    parser.add_argument(
        "--on", help="Pin On condition, format: <temp|hum>:<eq|lt|lte|gt|gte>:<value>:[or|and|xor|nand|nor|xnor]", action="append", default=[])
    parser.add_argument(
        "--rpc_listen", help="Listen address, default all 0.0.0.0", type=str, default="0.0.0.0")
    parser.add_argument(
        "--rpc_port", help="Listen port, default 15555", type=int, default=15555)

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)-30s %(message)s"
    )
    logger = logging.getLogger("rpioalert.main")

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

    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=1)

    stats = Status()
    lock = asyncio.Lock()

    tasks = [
        asyncio.ensure_future(rpio_alert(**{
            "leds": leds,
            "off_condition": args.off,
            "on_condition": args.on,
            "off_first": args.off_first,
            "stats": stats,
            "lock": lock,
            "executor": executor,
            "loop": loop
        }))
    ]

    if args.rpc:
        tasks.append(
            asyncio.ensure_future(rpc_server(**{
                "leds": leds,
                "listen": args.rpc_listen,
                "port": args.rpc_port,
                "off_condition": args.off,
                "on_condition": args.on,
                "stats": stats,
                "lock": lock,
                "executor": executor,
                "loop": loop
            }))
        )

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
