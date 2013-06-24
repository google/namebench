import re
import os
import subprocess

def ping(target, times=4):
    """ ping target in IP/hostname format

    e.g.
        '192.168.1.1' or 'www.google.com'

    return target, ip, time, lost
        target: IP/hostname
        ip: IP address, default is 0.0.0.0
        time_min: min ping time(ms), default is -1
        time_avg: avg ping time(ms), default is -1
        time_max: max ping time(ms), default is -1
        lost: packet loss(%), default is 100

        ('www.google.com', '127.0.0.1', 5, 0)
    """

    if os.name == 'nt':  # win32
        cmd = 'ping ' + target
    else:  # unix/linux
        cmd = 'LC_CTYPE=C ping -c %d %s' % (times, target)

    # execute ping command and get stdin thru pipe
    pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).communicate()[0]
    if not pipe:
        if os.name == 'nt':  # win32
            cmd = 'ping ' + target
        else:  # unix/linux
            cmd = 'LC_CTYPE=C ping6 -c %d %s' % (times, target)
        pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).communicate()[0]
        if not pipe:
            return target, '0.0.0.0', -1, -1, -1, 100

    # replace CR/LF
    text = pipe.replace('\r\n', '\n').replace('\r', '\n')

    # match IP adddres in format: [192.168.1.1] (192.168.1.1)
    ip = re.findall(r'(?<=\(|\[)\d+\.\d+\.\d+\.\d+(?=\)|\])', text)
    ip = ip[0] if ip else '0.0.0.0'

    # avg ping time
    if os.name == 'nt':
        # TODO
        time = re.findall(r'\d+(?=ms$)', text)
    else:
        time = re.findall(r'(?=\d+\.\d+/)(\d+\.\d+)+', text)
    if time:
      time_min = float(time[0])
      time_avg = float(time[1])
      time_max = float(time[2])
    else:
      time_min = time_avg = time_max = -1

    # packet loss rate
    lost = re.findall(r'\d+(?=%)', text)
    lost = int(round(float(lost[0]))) if lost else 100

    return target, ip, time_min, time_avg, time_max, lost
