## RPIO Alert

Turning Raspberry PI GPIO off and on base on temper device value

## Installation

```bash
pip3 setup.py install
```
## Usage

### Run manually

```
usage: rpioalert [-h] [--pin PIN] [--off OFF] [--on ON] [-stop] [-v]

optional arguments:
  -h, --help                show this help message and exit
  -rpc                      Start rpc server
  -stop                     Cleanup on stop service
  --pin PIN                 GPIO Pin
  --off OFF                 Pin Off condition, format: <temp|hum>:<eq|lt|lte|gt|gte>:<value>
  --on ON                   Pin On condition, format: <temp|hum>:<eq|lt|lte|gt|gte>:<value>
  --rpc_listen RPC_LISTEN   Listen address, default all 0.0.0.0
  --rpc_port RPC_PORT       Listen port, default 15555
  -v, --verbose             Log verbosity
```

--pin can be specified multiple time, useful for giving signal when condition reach and show current state e.g using RGB LED

--on or --off condition can be specified multiple time, logic AND will be use between condition

If multiple temper device installed, average value from thos device will be use for comparison

### Systemd
Copy rpioalert.service to /etc/systemd/system/rpioalert.service
Change the user inside this file to the user in temper group, and enable systemd

```bash
sudo systemctl enable rpioalert.service
sudo systemctl daemon-reload
sudo systemctl start rpioalert.service
```
