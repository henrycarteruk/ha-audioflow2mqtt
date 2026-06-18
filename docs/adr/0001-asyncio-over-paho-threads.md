# 0001 — asyncio (aiomqtt + httpx) instead of paho + threads

The original add-on ran paho-mqtt's `loop_forever()` on the main thread with daemon
threads for state/network polling, and called blocking `requests` inside the MQTT
`on_message` callback — which stalled the MQTT loop for up to the HTTP timeout on
every command and left shared device state uncoordinated across threads.

We rewrote the I/O layer on **asyncio** using **aiomqtt** (MQTT) and **httpx**
(device HTTP). For a gateway that is almost entirely network-wait, async is the
idiomatic shape: awaiting device calls no longer blocks MQTT handling, single-threaded
execution removes the shared-state races, and cancellation gives us a clean
SIGTERM shutdown.

A reader maintaining an MQTT add-on would reasonably expect plain paho; this records
that the deviation is deliberate. The cost is a full I/O-layer rewrite and a heavier
conceptual model, accepted because reliability and maintainability were the goals.
