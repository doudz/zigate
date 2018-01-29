# zigate
python library for zigate http://zigate.fr/

Usage :

```
import zigate
z = zigate.ZiGate(port=None) # Leave None to auto-discover the port
print(z.get_version())

# list devices
z.list_devices()

# start inclusion mode
z.permit_join()
```
Wifi ZiGate:

```
import zigate
z = zigate.ZiGateWiFi(host='192.168.0.10', port=9999)
print(z.get_version())

# list devices
z.list_devices()

# start inclusion mode
z.permit_join()
```

