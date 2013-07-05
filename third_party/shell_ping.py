import os
import re
import subprocess

def ping(target, times=4):
    """ ping target in IP/hostname format

    e.g.
        '192.168.1.1' or 'www.google.com'

    return ip, time_min, time_avg, time_max, lost
        ip: IP address of target, default is 0.0.0.0
        time_min: min ping time(ms), default is -1
        time_avg: avg ping time(ms), default is -1
        time_max: max ping time(ms), default is -1
        lost: packet loss(%), default is 100

        ('www.google.com', '127.0.0.1', 5, 0)
    """

    if os.name == 'nt':  # win32
        cmd = 'ping -w 2000 ' + target
    else:  # unix/linux
        cmd = 'ping -c%d -W2000 %s' % (times, target)

    # execute ping command and get stdin thru pipe
    pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).communicate()[0]
    if not pipe:
        if os.name == 'nt':  # win32
            cmd = 'ping -w 2000 ' + target
        else:  # unix/linux
            cmd = 'ping6 -c%d -W2000 %s' % (times, target)
        pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True).communicate()[0]
        if not pipe:
            return '0.0.0.0', -1, -1, -1, 100

    # replace CR/LF
    text = pipe.replace('\r\n', '\n').replace('\r', '\n')

    # match IP address in format: [192.168.1.1] (192.168.1.1)
    ip = re.findall(r'(?<=\(|\[)\d+\.\d+\.\d+\.\d+(?=\)|\])', text)
    if ip:
        ip = ip[0]
    else:
        ip = re.findall(r'\d+\.\d+\.\d+\.\d+', text)
        ip = ip[0] if ip else '0.0.0.0'

    # avg ping time
    if os.name == 'nt':
        time = re.findall(r'(\d+(?=ms))+', text)
        if time:
          time_avg = float(time[len(time) - 1])
          time_max = float(time[len(time) - 2])
          time_min = float(time[len(time) - 3])
    else:
        time = re.findall(r'(?=\d+\.\d+/)(\d+\.\d+)+', text)
        if time:
          time_min = float(time[0])
          time_avg = float(time[1])
          time_max = float(time[2])
    if not time:
       time_min = time_avg = time_max = -1

    # packet loss rate
    lost = re.findall(r'\d+(?=%)', text)
    lost = int(round(float(lost[0]))) if lost else 100

    return ip, time_min, time_avg, time_max, lost
