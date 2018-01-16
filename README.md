# zigate
python library for zigate http://zigate.fr/

inspired by https://github.com/elric91/ZiGate

WARNING : unusable NOW, dev in progress..

Usage :

```
import zigate
z = zigate.ZiGate()
print(z.get_version())

# list devices
z.list_devices()

# start inclusion mode
z.permit_join()
```