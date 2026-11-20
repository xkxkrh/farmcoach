"""Write the total duration into a fragmented MP4 made by Chrome's MediaRecorder.

Chrome leaves mvhd/tkhd/mdhd duration at 0 and has no 'mehd', so players show only the first fragment.
We compute the real length from the fragments and (1) set the header durations, (2) add an 'mehd' box.
"""
import struct, sys


def walk(b, off, end):
    i = off
    while i < end:
        sz, typ = struct.unpack(">I4s", b[i:i + 8])
        hdr = 8
        if sz == 1:
            sz = struct.unpack(">Q", b[i + 8:i + 16])[0]; hdr = 16
        elif sz == 0:
            sz = end - i
        yield i, sz, hdr, typ.decode("latin1")
        i += sz


def find(b, path, off=0, end=None):
    end = len(b) if end is None else end
    for i, sz, hdr, t in walk(b, off, end):
        if t == path[0]:
            return (i, sz, hdr) if len(path) == 1 else find(b, path[1:], i + hdr, i + sz)
    return None


def total_ticks(b):
    trex = find(b, ["moov", "mvex", "trex"])
    default_dur = struct.unpack(">I", b[trex[0] + 20:trex[0] + 24])[0] if trex else 0
    last_end = 0
    for i, sz, hdr, t in walk(b, 0, len(b)):
        if t != "moof":
            continue
        traf = find(b, ["traf"], i + hdr, i + sz)
        base = 0; dd = default_dur
        for j, s2, h2, t2 in walk(b, traf[0] + traf[2], traf[0] + traf[1]):
            flags = int.from_bytes(b[j + 9:j + 12], "big")
            if t2 == "tfdt":
                base = struct.unpack(">Q", b[j + 12:j + 20])[0] if b[j + 8] == 1 else struct.unpack(">I", b[j + 12:j + 16])[0]
            elif t2 == "tfhd":
                p = j + 16  # after track_id
                if flags & 0x1: p += 8
                if flags & 0x2: p += 4
                if flags & 0x8: dd = struct.unpack(">I", b[p:p + 4])[0]
            elif t2 == "trun":
                n = struct.unpack(">I", b[j + 12:j + 16])[0]
                p = j + 16
                if flags & 0x1: p += 4
                if flags & 0x4: p += 4
                per = sum(4 for f in (0x100, 0x200, 0x400, 0x800) if flags & f)
                dur = 0
                for k in range(n):
                    dur += struct.unpack(">I", b[p:p + 4])[0] if flags & 0x100 else dd
                    p += per
                last_end = max(last_end, base + dur)
    return last_end


def fix(path):
    b = bytearray(open(path, "rb").read())
    mdhd = find(b, ["moov", "trak", "mdia", "mdhd"])
    v = b[mdhd[0] + 8]
    media_ts = struct.unpack(">I", b[mdhd[0] + (28 if v else 20):mdhd[0] + (32 if v else 24)])[0]
    ticks = total_ticks(b)
    mvhd = find(b, ["moov", "mvhd"])
    mv = b[mvhd[0] + 8]
    movie_ts = struct.unpack(">I", b[mvhd[0] + (28 if mv else 20):mvhd[0] + (32 if mv else 24)])[0]
    movie_dur = round(ticks * movie_ts / media_ts)
    # header durations
    if mv: struct.pack_into(">Q", b, mvhd[0] + 32, movie_dur)
    else: struct.pack_into(">I", b, mvhd[0] + 24, movie_dur)
    tkhd = find(b, ["moov", "trak", "tkhd"])
    if b[tkhd[0] + 8]: struct.pack_into(">Q", b, tkhd[0] + 36, movie_dur)
    else: struct.pack_into(">I", b, tkhd[0] + 28, movie_dur)
    if v: struct.pack_into(">Q", b, mdhd[0] + 32, ticks)
    else: struct.pack_into(">I", b, mdhd[0] + 24, ticks)
    # add mehd at the start of mvex (fragments use moof-relative offsets, so growing moov is safe)
    moov = find(b, ["moov"]); mvex = find(b, ["moov", "mvex"])
    if mvex and not find(b, ["moov", "mvex", "mehd"]):
        mehd = struct.pack(">I4sI", 16, b"mehd", 0) + struct.pack(">I", movie_dur)
        ins = mvex[0] + mvex[2]
        b[ins:ins] = mehd
        struct.pack_into(">I", b, mvex[0], mvex[1] + 16)
        struct.pack_into(">I", b, moov[0], moov[1] + 16)
    open(path, "wb").write(b)
    return movie_dur / movie_ts


if __name__ == "__main__":
    print("seconds:", fix(sys.argv[1]))
