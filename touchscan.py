#!/usr/bin/env python3

import sys
import linuxcnc
import math

probe_radius = 2.0
probe_speed = 100
hits = []

out = open('probe.txt', 'w')
if not out:
    print("failed to open output file")

PI = math.pi

s = linuxcnc.stat()
c = linuxcnc.command()

def ok_for_mdi():
    s.poll()
    return not s.estop and s.enabled and (s.homed.count(1) == s.joints) and (s.interp_state == linuxcnc.INTERP_IDLE)

if not ok_for_mdi():
    print("machine not ready for mdi");
    sys.exit(1)

def get_position():
    s.poll()
    g5x_off = s.g5x_offset
    pos = s.actual_position

    return [pos[0] - g5x_off[0], pos[1] - g5x_off[1]]

def target_point(pos, len, angle):
    return [
        pos[0] + len * math.cos(angle),
        pos[1] + len * math.sin(angle)
    ]

def probe_to(pos, until_hit):
    cmd = "G38.3" if until_hit else "G38.5"
    c.mdi("{} X{} Y{} F{}".format(cmd, pos[0], pos[1], probe_speed))
    c.wait_complete()
    s.poll()
    g5x_off = s.g5x_offset
    pos = s.probed_position
    return [s.probe_tripped, [pos[0] - g5x_off[0], pos[1] - g5x_off[1]]]

def emit_point(pos, angle):
    est_point = target_point(pos, probe_radius, angle);
    print("est. hit at {}".format(est_point));
    out.write("estimated {:.3f} {:.3f} hitpos {:.3f} {:.3f} angle {:.3f}\n".
        format(est_point[0], est_point[1], pos[0], pos[1], angle))
    out.flush()
    hits.append(est_point);

def add_angle(a, b):
    a += b
    if a >= 2 * PI:
        a -= 2 * PI
    if a < 0:
        a += 2 * PI
    return a

c.mode(linuxcnc.MODE_MDI)
c.wait_complete() # wait until mode switch executed

start_pos = get_position()
print("start x {} y {}".format(start_pos[0], start_pos[1]))

angle = 0.0
initial_probe_len = 20.0
probing_radius = probe_radius * 0.25
probing_segments = 20
rounds = 5
probe_len = probing_radius * 2.0 * PI / probing_segments

p = target_point(start_pos, initial_probe_len, angle)
hit, hitpos = probe_to(p, True)
if not hit:
    print("no hit on initial probe")
    sys.exit(1)

emit_point(hitpos, angle)

angle = add_angle(angle, PI)

first = True
round = 0
prev_hit = hitpos
position = hitpos
in_start_area = True

while True:
    p = target_point(position, probe_len, angle)
    if first:
        print("unhit: probing to {}".format(p))
        if False:
            hit, position = probe_to(p, False)
            if not hit:
                print("not able to move out of probe")
                sys.exit(1)
        else:
            c.mdi("g1 X{} Y{} F{}".format(p[0], p[1], probe_speed))
            c.wait_complete()
        first = False
        print("unhit pos at {}".format(p))

    print("probing to {}".format(p))
    hit, position = probe_to(p, True)
    if hit:
        print("hit at {}".format(position))
        # calc normal vector
        dx = position[0] - prev_hit[0]
        dy = position[1] - prev_hit[1]
        print("dx: {}, dy: {}".format(dx, dy))
        print("old angle: {}".format(angle * 180.0 / PI))
        angle = math.atan2(dy, dx)
        print("new angle: {}".format(angle * 180.0 / PI))
        angle = add_angle(angle, 3.0 * PI / 2.0)
        print("angle: {}".format(angle * 180.0 / PI))
        emit_point(position, add_angle(angle, PI))
        first = True
        prev_hit = position
        if len(hits) > 0:
            dx = hits[0][0] - position[0]
            dy = hits[0][1] - position[1]
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < probe_radius * 1.5:
                if not in_start_area:
                    in_start_area = True
                    round += 1
                    print("round done")
                    if round == rounds:
                        print("done")
                        probe_to(start_pos, False)
                        probe_to(start_pos, True)
                        break
            else:
                in_start_area = False
    else:
        angle = add_angle(angle, PI * 2.0 / probing_segments)
