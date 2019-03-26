## RPIO Alert

Turning Raspberry PI GPIO off and on base on temper device value

## Installation

```bash
pip3 setup.py install
```
## Usage

### Run manually

```
usage: rpioalert [-h] [-rpc] [-v] [-stop] [-off_first] [--pin PIN] [--off OFF]
                 [--on ON] [--rpc_listen RPC_LISTEN] [--rpc_port RPC_PORT]

optional arguments:
  -h, --help            show this help message and exit
  -rpc                  Start rpc server
  -v, --verbose         Log verbosity
  -stop                 Cleanup on stop service
  -off_first            Check OFF condition first, then ON condition
  --pin PIN             GPIO Pin
  --off OFF             Pin Off condition, format: <temp|hum>:<eq|lt|lte|gt|gte>:<value>:[or|and|xor|nand|nor|xnor]
  --on ON               Pin On condition, format: <temp|hum>:<eq|lt|lte|gt|gte>:<value>:[or|and|xor|nand|nor|xnor]
  --rpc_listen          Listen address, default all 0.0.0.0
  --rpc_port            Listen port, default 15555
```

--pin can be specified multiple time, useful for giving signal when condition reach and show current state e.g using RGB LED

--on or --off condition can be specified multiple time, default logic AND will be use between condition if empty

Condition will be check by priority, default is ON condition then OFF condition. If first condition is reach, the second one will be skip until next iteration. Use -off_first to check OFF condition first.

If multiple temper device installed, average value from thos device will be use for comparison

### Systemd
Copy rpioalert.service to /etc/systemd/system/rpioalert.service
Change the user inside this file to the user in temper group, and enable systemd

```bash
sudo systemctl enable rpioalert.service
sudo systemctl daemon-reload
sudo systemctl start rpioalert.service
```
