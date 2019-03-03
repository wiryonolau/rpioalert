## Installation

Copy rpioalert.service to /etc/systemd/system/rpioalert.service
Change the user inside this file to the user in temper group, and enable systemd

```bash
sudo systemctl enable rpioalert.service
sudo systemctl daemon-reload
sudo systemctl start rpioalert.service
```
