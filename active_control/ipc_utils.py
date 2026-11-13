"""Bounded latest-value IPC shared by the USB workers."""
import queue

NEUTRAL=dict(axes=[0.]*4,triggers=[0.,0.],buttons=0,dpad=0)

def latest(channel,message):
    try: channel.put_nowait(message)
    except queue.Full:
        try: channel.get_nowait()
        except queue.Empty: pass
        try: channel.put_nowait(message)
        except queue.Full: pass
